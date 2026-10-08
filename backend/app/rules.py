"""Deterministic FWA rules R001-R008. Every hit emits a structured evidence object (never a bare boolean)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import binom

from . import config
from .evidence import make_ev
from .loader import haversine_km

AS_OF = pd.Timestamp(config.AS_OF)
W180 = AS_OF - pd.Timedelta(days=179)

RULES = {
    "R001_DUPLICATE": "Duplicate billing",
    "R002_UPCODING": "Upcoding",
    "R003_UNBUNDLING": "Unbundling",
    "R004_IMPLAUSIBLE_SERVICE": "Implausible / phantom service",
    "R005_EXCESSIVE_UTILIZATION": "Excessive utilization",
    "R006_IMPOSSIBLE_TIMING": "Impossible timing",
    "R007_REFERRAL_CONCENTRATION": "Referral concentration",
    "R008_NETWORK_EXPANSION": "Network expansion",
}


def _sev(n: float, medium: float, high: float, critical: float) -> str:
    return "CRITICAL" if n >= critical else "HIGH" if n >= high else "MEDIUM" if n >= medium else "LOW"


def duplicate_groups(c: pd.DataFrame) -> pd.DataFrame:
    key = ["provider_id", "member_id", "procedure_code", "service_date"]
    size = c.groupby(key).claim_id.transform("size")
    d = c[size > 1]
    return d


def duplicate_claim_ids(c: pd.DataFrame) -> set[str]:
    return set(duplicate_groups(c).claim_id)


def run_claim_level(c: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """R001, R003, R004, R006. Returns (claim flags, evidence)."""
    evs: list[dict] = []
    flags = pd.DataFrame({"claim_id": c.claim_id, "f_dup": False, "f_unbundle": False, "f_implaus": False, "f_timing": False}).set_index("claim_id")

    # ---- R001 duplicate billing: same provider + member + procedure + service date ---------------------------------
    d = duplicate_groups(c)
    key = ["provider_id", "member_id", "procedure_code", "service_date"]
    if len(d):
        grp = d.sort_values("claim_id").groupby(key).agg(claim_ids=("claim_id", list), n=("claim_id", "size"), paid=("paid_amount", list)).reset_index()
        grp["redundant_paid"] = grp.paid.apply(lambda x: float(sum(x[1:])))
        recent = grp[grp.service_date >= W180].groupby("provider_id").size()
        for r in grp.itertuples():
            n_prov = int(recent.get(r.provider_id, 0))
            sev = _sev(n_prov, 3, 6, 12)
            evs.append(make_ev(
                rule_id="R001_DUPLICATE", severity=sev, source_table="claims", source_row_id=r.claim_ids[0], claim_ids=r.claim_ids,
                provider_id=r.provider_id, feature="same_day_same_procedure_claim_count", observed=r.n, expected=1, unit="claims", ts=r.service_date,
                explanation=(f"{r.n} claims ({', '.join(r.claim_ids)}) from {r.provider_id} bill the same member, procedure {r.procedure_code} and "
                             f"service date {r.service_date.date()}; one claim was expected. Provider has {n_prov} such groups in the last 180 days."),
                payload={"member_id": r.member_id, "procedure_code": r.procedure_code, "redundant_paid": r.redundant_paid, "provider_dup_groups_180d": n_prov}))
        flags.loc[d.claim_id, "f_dup"] = True

    # ---- R003 unbundling: >=3 component codes of one bundle billed the same day without the parent code ------------
    b = c[c.bundle_group.notna()]
    if len(b):
        k3 = ["provider_id", "member_id", "service_date", "bundle_group"]
        g = b.groupby(k3).agg(comps=("procedure_code", lambda s: s[~b.loc[s.index, "is_bundle_parent"]].nunique()),
                              parents=("is_bundle_parent", "sum"), claim_ids=("claim_id", list), paid=("paid_amount", "sum")).reset_index()
        hit = g[(g.comps >= 3) & (g.parents == 0)]
        recent = hit[hit.service_date >= W180].groupby("provider_id").size()
        for r in hit.itertuples():
            n_prov = int(recent.get(r.provider_id, 0))
            evs.append(make_ev(
                rule_id="R003_UNBUNDLING", severity=_sev(n_prov, 3, 8, 20), source_table="claims", source_row_id=r.claim_ids[0], claim_ids=r.claim_ids,
                provider_id=r.provider_id, feature="component_codes_without_parent", observed=r.comps, expected=0 if False else 1, unit="codes", ts=r.service_date,
                explanation=(f"{r.comps} component codes of bundle {r.bundle_group} were billed separately on {r.service_date.date()} for one member "
                             f"without the bundled parent code ({', '.join(r.claim_ids)}). Provider has {n_prov} such member-days in the last 180 days."),
                payload={"bundle_group": r.bundle_group, "member_id": r.member_id, "paid": float(r.paid), "provider_groups_180d": n_prov}))
            flags.loc[r.claim_ids, "f_unbundle"] = True

    # ---- R004 implausible / phantom service ----------------------------------------------------------------------
    viol = []
    after = c.death_date.notna() & (c.service_date > c.death_date)
    viol.append(("service_after_member_death_days", after, (c.service_date - c.death_date).dt.days, 0, "HIGH", "days", "service date is after the member's recorded death date"))
    sexbad = (c.allowed_sex != "A") & (c.allowed_sex != c.member_sex)
    viol.append(("sex_restricted_procedure_mismatch", sexbad, pd.Series(1.0, index=c.index), 0, "MEDIUM", "flag", "procedure is restricted by sex and does not match the member"))
    agebad = (c.member_age < c.min_age) | (c.member_age > c.max_age)
    viol.append(("procedure_age_range_violation", agebad, c.member_age.astype(float), np.where(c.member_age < c.min_age, c.min_age, c.max_age), "MEDIUM", "years",
                 "member age is outside the procedure's valid age range"))
    fac_ok = pd.Series([(ft in fl.split("|")) if fl else True for ft, fl in zip(c.facility_type, c.proc_facility_types.fillna(""))], index=c.index)
    viol.append(("procedure_facility_type_mismatch", ~fac_ok, pd.Series(1.0, index=c.index), 0, "MEDIUM", "flag", "procedure cannot normally be performed at this facility type"))
    per_prov = {}
    allm = pd.Series(False, index=c.index)
    for _, mask, *_ in viol:
        allm |= mask
    cnt_recent = c[allm & (c.service_date >= W180)].groupby("provider_id").size()
    for feat, mask, obs, exp, sev0, unit, why in viol:
        for idx in c.index[mask]:
            r = c.loc[idx]
            n_prov = int(cnt_recent.get(r.provider_id, 0))
            sev = _sev(n_prov, 3, 8, 20) if sev0 == "MEDIUM" else ("CRITICAL" if n_prov >= 8 else "HIGH")
            if n_prov <= 1:
                sev = "LOW" if sev0 == "MEDIUM" else "MEDIUM"
            e = float(exp[idx]) if hasattr(exp, "__getitem__") and not isinstance(exp, (int, float)) else float(exp)
            evs.append(make_ev(
                rule_id="R004_IMPLAUSIBLE_SERVICE", severity=sev, source_table="claims", source_row_id=r.claim_id, claim_ids=[r.claim_id], provider_id=r.provider_id,
                feature=feat, observed=float(obs[idx]), expected=e, unit=unit, ts=r.service_date, facility_id=r.facility_id,
                explanation=f"Claim {r.claim_id} (procedure {r.procedure_code}, member {r.member_id}): {why}. Provider has {n_prov} implausible-service claims in the last 180 days.",
                payload={"member_id": r.member_id, "procedure_code": r.procedure_code, "facility_type": r.facility_type, "provider_implausible_180d": n_prov}))
        flags.loc[c.loc[mask, "claim_id"], "f_implaus"] = True

    # ---- R006 impossible timing: >16h billed in a day, or distant facilities on the same day -----------------------
    day = c.groupby(["provider_id", "service_date"]).agg(minutes=("service_minutes", "sum"), n=("claim_id", "size"), nfac=("facility_id", "nunique"),
                                                          claim_ids=("claim_id", list), lat0=("fac_lat", "min"), lat1=("fac_lat", "max"),
                                                          lon0=("fac_lon", "min"), lon1=("fac_lon", "max")).reset_index()
    day["km"] = np.where(day.nfac > 1, haversine_km(day.lat0, day.lon0, day.lat1, day.lon1), 0.0)
    vol = day[day.minutes > 960]
    geo = day[(day.km > 250)]
    ph = pd.concat([vol.assign(kind="minutes"), geo.assign(kind="distance")])
    rec = ph[ph.service_date >= W180].groupby("provider_id").size()
    for r in ph.itertuples():
        n_prov = int(rec.get(r.provider_id, 0))
        if r.kind == "minutes":
            feat, obs, exp, unit = "billed_minutes_per_day", float(r.minutes), 960.0, "minutes"
            why = f"{r.provider_id} billed {r.minutes} service minutes ({r.minutes / 60:.1f} h) across {r.n} claims on {r.service_date.date()}; more than 16 h/day is not plausible"
        else:
            feat, obs, exp, unit = "same_day_facility_distance_km", float(r.km), 250.0, "km"
            why = f"{r.provider_id} billed services at facilities ~{r.km:.0f} km apart on {r.service_date.date()}; same-day services at that distance are not plausible"
        evs.append(make_ev(rule_id="R006_IMPOSSIBLE_TIMING", severity=_sev(n_prov, 3, 10, 25), source_table="claims", source_row_id=r.claim_ids[0],
                           claim_ids=r.claim_ids, provider_id=r.provider_id, feature=feat, observed=obs, expected=exp, unit=unit, ts=r.service_date,
                           explanation=why + f". Provider has {n_prov} such days in the last 180 days.", payload={"claims_that_day": int(r.n), "provider_days_180d": n_prov}))
        flags.loc[r.claim_ids, "f_timing"] = True
    return flags.reset_index(), evs


def run_provider_level(feats: pd.DataFrame, claims: pd.DataFrame, referrals: pd.DataFrame) -> list[dict]:
    """R002, R005, R007, R008 using peer benchmarking features."""
    evs: list[dict] = []
    f = feats.set_index("provider_id")
    c180 = claims[claims.service_date >= W180]
    c90 = claims[claims.service_date >= AS_OF - pd.Timedelta(days=89)]

    # ---- R002 upcoding -------------------------------------------------------------------------------------------
    for pid, r in f[f.high_cx_ratio_180d.notna()].iterrows():
        obs, med, z = r.high_cx_ratio_180d, r["peer_median__high_cx_ratio_180d"], r["peer_z__high_cx_ratio_180d"]
        n_em = int(r.em_claims_180d)
        pval = float(binom.sf(round(obs * n_em) - 1, n_em, min(max(med, 0.05), 0.95)))   # one-sided binomial tail vs peer median
        if obs >= 0.55 and obs - med >= 0.25 and pval < 0.001:
            cl = c180[(c180.provider_id == pid) & (c180.em_level == 5)].sort_values("paid_amount", ascending=False)
            evs.append(make_ev(
                rule_id="R002_UPCODING", severity="CRITICAL" if obs >= 0.85 else "HIGH" if obs >= 0.70 else "MEDIUM", source_table="provider_features",
                source_row_id=pid, claim_ids=cl.claim_id.tolist(), claim_count=len(cl), provider_id=pid, feature="high_complexity_visit_ratio_180d",
                observed=obs, expected=med, unit="ratio", ts=AS_OF,
                explanation=(f"{pid}: {obs:.0%} of evaluation/management visits in the last 180 days are high-complexity (level 4-5) versus a peer median of {med:.0%} "
                             f"(robust z={z:.1f}, one-sided binomial p={pval:.1e}, peer group {r.peer_group}, n={int(r.peer_size)}). Peer deviation is a lead, not proof."),
                payload={"peer_group": r.peer_group, "peer_z": float(z), "em_claims_180d": n_em, "binomial_p_value": pval}))

    # ---- R005 excessive utilization --------------------------------------------------------------------------------
    for pid, r in f[(f.claims_90d >= 20)].iterrows():
        obs, med, z = r.claims_per_month_90d, r["peer_median__claims_per_month_90d"], r["peer_z__claims_per_month_90d"]
        ratio = obs / med if med > 0 else np.nan
        if ratio >= 2.0 and z >= 3.5:
            cl = c90[c90.provider_id == pid].sort_values("paid_amount", ascending=False)
            evs.append(make_ev(
                rule_id="R005_EXCESSIVE_UTILIZATION", severity="CRITICAL" if ratio >= 4 else "HIGH" if ratio >= 3 else "MEDIUM", source_table="provider_features",
                source_row_id=pid, claim_ids=cl.claim_id.tolist(), claim_count=len(cl), provider_id=pid, feature="claims_per_month_90d", observed=obs, expected=med, unit="claims/month",
                ts=AS_OF, explanation=(f"{pid} submitted {obs:.1f} claims/month over the last 90 days versus a peer median of {med:.1f} ({ratio:.1f}x, robust z={z:.1f}; "
                                       f"peer group {r.peer_group}, n={int(r.peer_size)}). Utilization is compared within specialty/region/facility type so legitimate high-volume specialties are not penalized."),
                payload={"peer_group": r.peer_group, "ratio": float(ratio), "peer_z": float(z), "paid_90d": float(r.paid_90d)}))

    # ---- R007 referral concentration -------------------------------------------------------------------------------
    rec = referrals[referrals.referral_date >= W180]
    for pid, r in f[f.ref_in_n_180d >= 20].iterrows():
        sh, med = r.ref_in_top_share_180d, r["peer_median__ref_in_top_share_180d"]
        if sh >= 0.50:
            src = r.ref_in_top_referrer
            rr = rec[(rec.target_provider_id == pid) & (rec.referring_provider_id == src)]
            cl = claims[(claims.provider_id == pid) & (claims.referring_provider_id == src) & (claims.service_date >= W180)]
            evs.append(make_ev(
                rule_id="R007_REFERRAL_CONCENTRATION", severity="CRITICAL" if sh >= 0.80 else "HIGH" if sh >= 0.65 else "MEDIUM", source_table="referrals",
                source_row_id=rr.referral_id.iloc[0], claim_ids=cl.claim_id.tolist(), claim_count=len(cl), provider_id=pid,
                feature="top_referrer_share_180d", observed=sh, expected=med if med == med else 0.3, unit="share", ts=AS_OF,
                explanation=(f"{src} accounts for {sh:.0%} of the {int(r.ref_in_n_180d)} referrals received by {pid} in the last 180 days "
                             f"(peer median top-referrer share {0 if med != med else med:.0%}). Concentration is an investigation lead, not proof of improper arrangement."),
                payload={"direction": "inbound", "top_referrer": src, "referral_ids": rr.referral_id.tolist()[:50], "total_referrals": int(r.ref_in_n_180d)}))
    for pid, r in f[f.ref_out_n_180d >= 20].iterrows():
        sh, med = r.ref_out_top_share_180d, r["peer_median__ref_out_top_share_180d"]
        if sh >= 0.60:
            tgt = r.ref_out_top_target
            rr = rec[(rec.referring_provider_id == pid) & (rec.target_provider_id == tgt)]
            evs.append(make_ev(
                rule_id="R007_REFERRAL_CONCENTRATION", severity="CRITICAL" if sh >= 0.85 else "HIGH" if sh >= 0.70 else "MEDIUM", source_table="referrals",
                source_row_id=rr.referral_id.iloc[0], claim_ids=[], claim_count=0, provider_id=pid, feature="top_target_share_180d", observed=sh,
                expected=med if med == med else 0.4, unit="share", ts=AS_OF,
                explanation=(f"{pid} routes {sh:.0%} of its {int(r.ref_out_n_180d)} outbound referrals in the last 180 days to {tgt} "
                             f"(peer median {0 if med != med else med:.0%}). Concentration is an investigation lead, not proof."),
                payload={"direction": "outbound", "top_target": tgt, "referral_ids": rr.referral_id.tolist()[:50], "total_referrals": int(r.ref_out_n_180d)}))

    # ---- R008 network expansion --------------------------------------------------------------------------------------
    for pid, r in f.iterrows():
        new, prior = r.new_connections_90d, r.prior_connections
        if new >= 8 and new / max(prior, 1) >= 0.75:
            evs.append(make_ev(
                rule_id="R008_NETWORK_EXPANSION", severity="CRITICAL" if new >= 15 else "HIGH" if new >= 11 else "MEDIUM", source_table="provider_features", source_row_id=pid,
                claim_ids=[], claim_count=0, provider_id=pid, feature="new_connections_90d", observed=new, expected=max(float(prior) * 0.25, 1.0), unit="connections", ts=AS_OF,
                explanation=(f"{pid} gained {int(new)} new provider/facility connections in the last 90 days versus {int(prior)} existing connections "
                             f"({new / max(prior, 1):.1f}x growth). Rapid network growth is a lead, not proof."),
                payload={"new_connections_90d": int(new), "prior_connections": int(prior)}))
    return evs
