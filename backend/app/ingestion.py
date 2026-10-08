"""CSV ingestion: validate -> quarantine invalid rows -> bulk load into PostgreSQL."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import config, db


def _arr(v) -> str | None:
    if v is None or (isinstance(v, float) and v != v) or v == "":
        return None
    return "{" + ",".join(str(x) for x in str(v).split("|")) + "}"


def _read(name: str, d: Path) -> pd.DataFrame:
    return pd.read_csv(d / f"{name}.csv", dtype=str)


def _quarantine(rows: list[dict]) -> None:
    if not rows:
        return
    with db.begin() as conn:
        from sqlalchemy import text
        conn.execute(text("INSERT INTO quarantine (source_table, row_number, reason, raw) VALUES (:t,:r,:why,CAST(:raw AS jsonb))"),
                     [{"t": r["table"], "r": r["row"], "why": r["reason"], "raw": json.dumps({k: (None if (isinstance(v, float) and v != v) else v) for k, v in r["raw"].items()}, default=str)} for r in rows])


def validate_claims(df: pd.DataFrame, valid_ids: dict[str, set]) -> tuple[pd.DataFrame, list[dict]]:
    """Return (valid_df, quarantine_rows). Every rejected row carries an explicit reason."""
    df = df.copy()
    reasons = pd.Series("", index=df.index)

    def flag(mask: pd.Series, why: str):
        nonlocal reasons
        reasons = reasons.where(~(mask & (reasons == "")), why)

    flag(df.claim_id.isna() | df.claim_id.duplicated(keep="first"), "missing or duplicate claim_id")
    flag(df.member_id.isna(), "missing member_id")
    flag(~df.member_id.isin(valid_ids["members"]) & df.member_id.notna(), "unknown member_id")
    flag(~df.provider_id.isin(valid_ids["providers"]), "unknown provider_id")
    flag(~df.facility_id.isin(valid_ids["facilities"]), "unknown facility_id")
    flag(~df.procedure_code.isin(valid_ids["procedures"]), "unknown procedure_code")
    flag(df.referring_provider_id.notna() & ~df.referring_provider_id.isin(valid_ids["providers"]), "unknown referring_provider_id")
    sd = pd.to_datetime(df.service_date, errors="coerce")
    sb = pd.to_datetime(df.submit_date, errors="coerce")
    flag(sd.isna(), "invalid service_date")
    flag(sb.isna(), "invalid submit_date")
    flag(sd.notna() & ((sd < pd.Timestamp(config.DATA_START)) | (sd > pd.Timestamp(config.DATA_END))), "service_date outside dataset window")
    flag(sd.notna() & sb.notna() & (sb < sd), "submit_date before service_date")
    for col in ("billed_amount", "allowed_amount", "paid_amount"):
        v = pd.to_numeric(df[col], errors="coerce")
        flag(v.isna(), f"non-numeric {col}")
        flag(v < 0, f"negative {col}")
    units = pd.to_numeric(df.units, errors="coerce")
    flag(units.isna() | (units <= 0), "units must be a positive integer")
    bad = reasons != ""
    q = [{"table": "claims", "row": int(i) + 2, "reason": reasons[i], "raw": df.loc[i].to_dict()} for i in df.index[bad]]
    return df.loc[~bad], q


def ingest(data_dir: Path | None = None, reset: bool = True) -> dict:
    d = Path(data_dir or config.SYNTH_DIR)
    if reset:
        db.apply_schema()
    stats: dict = {}
    qrows: list[dict] = []

    fac = _read("facilities", d)
    db.copy_df(fac, "facilities", ["facility_id", "name", "facility_type", "region", "city", "lat", "lon"])
    prov = _read("providers", d)
    db.copy_df(prov, "providers", ["provider_id", "display_label", "name", "specialty", "region", "city", "primary_facility_id",
                                   "primary_facility_type", "enrolled_date"])
    mem = _read("members", d)
    db.copy_df(mem, "members", ["member_id", "age", "sex", "region", "death_date"])
    proc = _read("procedures", d)
    proc["facility_types"] = proc.facility_types.apply(_arr)
    db.copy_df(proc, "procedures", ["code", "description", "category", "em_level", "base_amount", "bundle_group", "is_bundle_parent",
                                    "allowed_sex", "min_age", "max_age", "facility_types", "service_minutes", "repeat_same_day_ok"])
    ids = {"members": set(mem.member_id), "providers": set(prov.provider_id), "facilities": set(fac.facility_id), "procedures": set(proc.code)}

    claims = _read("claims", d)
    good, q = validate_claims(claims, ids)
    qrows += q
    db.copy_df(good, "claims", ["claim_id", "member_id", "provider_id", "referring_provider_id", "facility_id", "service_date", "submit_date",
                                "procedure_code", "units", "billed_amount", "allowed_amount", "paid_amount", "service_minutes", "claim_type"])
    stats["claims_read"] = len(claims)
    stats["claims_loaded"] = len(good)
    stats["claims_quarantined"] = len(q)

    labels = _read("claim_labels", d)
    labels = labels[labels.claim_id.isin(set(good.claim_id))]
    db.copy_df(labels, "claim_labels", ["claim_id", "injected_fwa", "scenario"])
    pl = _read("provider_labels", d)
    pl["scenarios"] = pl.scenarios.apply(lambda v: _arr(v) or "{}")
    db.copy_df(pl, "provider_labels", ["provider_id", "role", "scenarios", "scenario_start", "notes"])

    ref = _read("referrals", d)
    rb = (~ref.referring_provider_id.isin(ids["providers"])) | (~ref.target_provider_id.isin(ids["providers"])) | (~ref.member_id.isin(ids["members"])) \
        | pd.to_datetime(ref.referral_date, errors="coerce").isna()
    qrows += [{"table": "referrals", "row": int(i) + 2, "reason": "invalid reference or date", "raw": ref.loc[i].to_dict()} for i in ref.index[rb]]
    db.copy_df(ref[~rb], "referrals", ["referral_id", "referring_provider_id", "target_provider_id", "target_facility_id", "member_id", "referral_date"])
    stats["referrals_loaded"] = int((~rb).sum())

    rel = _read("relationships", d)
    ok = (rel.entity_a_id.isin(ids["providers"])) & (rel.entity_b_id.isin(ids["providers"] | ids["facilities"]))
    qrows += [{"table": "relationships", "row": int(i) + 2, "reason": "unknown entity", "raw": rel.loc[i].to_dict()} for i in rel.index[~ok]]
    db.copy_df(rel[ok], "relationships", ["relationship_id", "entity_a_type", "entity_a_id", "entity_b_type", "entity_b_id", "relationship_type", "start_date", "source"])
    stats["relationships_loaded"] = int(ok.sum())

    inv = _read("investigations", d)
    inv["patterns"] = inv.patterns.apply(lambda v: _arr(v) or "{}")
    inv = inv[inv.provider_id.isin(ids["providers"])]
    db.copy_df(inv, "investigations", ["investigation_id", "provider_id", "opened_date", "closed_date", "patterns", "specialty", "outcome",
                                       "amount_identified", "summary", "analyst_notes"])
    stats["investigations_loaded"] = len(inv)
    stats.update({"facilities_loaded": len(fac), "providers_loaded": len(prov), "members_loaded": len(mem), "procedures_loaded": len(proc)})
    _quarantine(qrows)
    stats["quarantine_total"] = len(qrows)
    stats["quarantine_reasons"] = pd.Series([r["reason"] for r in qrows]).value_counts().to_dict() if qrows else {}
    return stats
