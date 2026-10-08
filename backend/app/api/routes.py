"""REST API. All numbers are read from PostgreSQL / executed model runs; nothing is hard-coded."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .. import config, db
from ..ai import brief as B
from ..ai import context as C
from ..ai import copilot as P
from ..ai.llm import get_llm
from ..brain import service as brain
from ..graph import STORE
from .util import clean, jl

router = APIRouter(prefix="/api")

STATUS_OF = {"ESCALATE": "ESCALATED", "REQUEST_DOCUMENTATION": "DOCUMENTATION_REQUESTED", "MONITOR": "MONITORING", "CLOSE": "CLOSED"}


# ------------------------------------------------------------------------------------------------ models
class ReviewIn(BaseModel):
    decision: Literal["ESCALATE", "REQUEST_DOCUMENTATION", "MONITOR", "CLOSE"]
    rationale: str = Field(min_length=3, max_length=2000)
    reviewer: str = Field(default="siu.reviewer", min_length=1, max_length=80)


class CopilotIn(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    use_llm: bool = True


class SearchIn(BaseModel):
    query: str = ""
    index: Literal["cases", "evidence", "entities", "patterns", "review_memory"] = "cases"
    mode: Literal["hybrid", "bm25", "knn"] = "hybrid"
    filters: dict = Field(default_factory=dict)
    size: int = Field(default=10, ge=1, le=50)


def _case_or_404(case_id: str) -> dict:
    c = db.query_one("SELECT * FROM cases WHERE case_id=:c", {"c": case_id})
    if not c:
        raise HTTPException(404, f"Unknown case {case_id}")
    return c


CASE_LIST_COLS = ("case_id, anchor_provider_id, provider_ids, specialty, rule_hits, patterns, model_score, anomaly_score, priority_score, review_priority, review_status, "
                  "potential_exposure, member_count, claim_count, forecast_30d, forecast_60d, forecast_90d, forecast_label, summary, first_activity, as_of")


# ------------------------------------------------------------------------------------------------ system
@router.get("/health")
def health():
    ok_db = True
    try:
        db.query_one("SELECT 1")
    except Exception:
        ok_db = False
    n = db.query_one("SELECT count(*) n FROM cases")["n"] if ok_db and db.table_exists("cases") else 0
    return clean({"status": "ok" if ok_db and n else "degraded", "database": ok_db, "cases": n, "second_brain": brain.status() if ok_db else None,
                  "llm_provider": get_llm().name, "version": "1.0.0"})


@router.get("/command-center")
def command_center():
    ps = db.query_one("SELECT metrics, finished_at FROM model_runs WHERE run_type='pipeline_summary' ORDER BY run_id DESC LIMIT 1")
    if not ps:
        raise HTTPException(503, "Pipeline has not been run")
    m = jl(ps["metrics"])
    f = m["funnel"]
    steps = [("Claims", f["claims"], "All valid claims loaded into PostgreSQL"), ("Anomalies", f["anomalies"], f["definitions"]["anomalies"]),
             ("Suspicious Claims", f["suspicious_claims"], f["definitions"]["suspicious_claims"]), ("Connected Cases", f["connected_cases"], f["definitions"]["connected_cases"]),
             ("High-Risk Cases", f["high_risk_cases"], f["definitions"]["high_risk_cases"]),
             ("SIU Priorities", min(10, f["high_risk_cases"]), "Top cases for the default capacity of 10 (selectable 5/10/20)")]
    funnel = [{"stage": s, "count": c, "definition": d} for s, c, d in steps]
    counts = db.query_one("""SELECT (SELECT count(*) FROM claims) claims, (SELECT count(*) FROM providers) providers, (SELECT count(*) FROM members) members,
                             (SELECT count(*) FROM facilities) facilities, (SELECT count(*) FROM referrals) referrals, (SELECT count(*) FROM investigations) investigations,
                             (SELECT count(*) FROM quarantine) quarantined, (SELECT count(*) FROM evidence) evidence""")
    bands = db.query_rows("SELECT review_priority band, count(*) n, sum(potential_exposure) exposure FROM cases GROUP BY 1")
    status = db.query_rows("SELECT review_status status, count(*) n FROM cases GROUP BY 1")
    rules = db.query_rows("SELECT rule_id, severity, count(*) n FROM evidence WHERE evidence_type='RULE' GROUP BY 1,2 ORDER BY 1")
    exposure = db.query_one("SELECT COALESCE(sum(potential_exposure),0) e FROM cases")["e"]
    xgb = db.query_one("SELECT metrics, model_version FROM model_runs WHERE run_type='xgboost' ORDER BY run_id DESC LIMIT 1")
    fc = db.query_one("SELECT metrics FROM model_runs WHERE run_type='forecast' ORDER BY run_id DESC LIMIT 1")
    xm = jl(xgb["metrics"]) if xgb else {}
    top = db.query_rows(f"SELECT {CASE_LIST_COLS} FROM cases ORDER BY priority_score DESC LIMIT 5")
    return clean({"as_of": str(config.AS_OF), "dataset_version": config.DATASET_VERSION, "synthetic": True, "funnel": funnel, "critical_cases": f.get("critical_cases"),
                  "counts": counts, "bands": bands, "review_status": status, "rule_hits": rules, "total_potential_exposure": exposure,
                  "model_headline": {"xgboost": xm.get("xgboost"), "rules_only_baseline": xm.get("rules_only_baseline"), "isolation_forest_baseline": xm.get("isolation_forest_baseline"),
                                     "version": xgb["model_version"] if xgb else None, "split": xm.get("split")},
                  "forecast_label": jl(fc["metrics"]).get("output_label") if fc else None, "top_cases": top, "pipeline_stages": m.get("stages", []), "run_at": ps["finished_at"],
                  "second_brain": brain.status()})


@router.get("/models")
def models():
    out = {}
    for rt in ("rules", "isolation_forest", "xgboost", "forecast", "second_brain_index"):
        r = db.query_one("SELECT run_id, model_name, model_version, dataset_version, finished_at, metrics, params, notes FROM model_runs WHERE run_type=:t ORDER BY run_id DESC LIMIT 1", {"t": rt})
        if r:
            r["metrics"], r["params"] = jl(r["metrics"]), jl(r["params"])
            out[rt] = r
    return clean(out)


# ------------------------------------------------------------------------------------------------ queue
@router.get("/queue")
def queue(capacity: int = Query(10, ge=1, le=50), include_reviewed: bool = False, specialty: str | None = None, min_band: str | None = None):
    """Highest-value investigations for the chosen investigator capacity (5/10/20 in the UI)."""
    where, p = ["1=1"], {"cap": capacity}
    if not include_reviewed:
        where.append("review_status IN ('PENDING','MONITORING','DOCUMENTATION_REQUESTED','ESCALATED')")
    if specialty:
        where.append("specialty=:sp")
        p["sp"] = specialty
    if min_band:
        order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        where.append("review_priority = ANY(:bands)")
        p["bands"] = order[order.index(min_band.upper()):] if min_band.upper() in order else order
    rows = db.query_rows(f"SELECT {CASE_LIST_COLS}, components FROM cases WHERE {' AND '.join(where)} ORDER BY priority_score DESC, potential_exposure DESC LIMIT :cap", p)
    total = db.query_one(f"SELECT count(*) n FROM cases WHERE {' AND '.join(where)}", p)
    global_total = db.query_one("SELECT COALESCE(sum(potential_exposure),0) e FROM cases")
    for i, r in enumerate(rows, 1):
        r["rank"] = i
        r["components"] = jl(r["components"])
        r["top_drivers"] = [k for k, _ in sorted(r["components"].items(), key=lambda kv: -kv[1]) [:3]]
    sel = sum(float(r["potential_exposure"]) for r in rows)
    tot_e = float(global_total["e"])
    return clean({"capacity": capacity, "cases": rows, "selected_exposure": sel, "total_cases_available": total["n"], "total_exposure_available": tot_e,
                  "exposure_coverage": sel / tot_e if tot_e else 0, "weights": config.PRIORITY_WEIGHTS, "policy_version": config.PRIORITY_POLICY_VERSION,
                  "policy_note": "Ranking blends model risk, rule evidence, peer deviation, network, temporal escalation, anomaly, evidence strength, exposure and member impact - not model score alone."})


# ------------------------------------------------------------------------------------------------ case
@router.get("/cases")
def cases(limit: int = 100):
    return clean(db.query_rows(f"SELECT {CASE_LIST_COLS} FROM cases ORDER BY priority_score DESC LIMIT :l", {"l": limit}))


@router.get("/cases/{case_id}")
def case_detail(case_id: str):
    c = _case_or_404(case_id)
    for k in ("components", "network_signals"):
        c[k] = jl(c[k])
    c.pop("member_ids_sample", None)
    claim_ids = c.pop("claim_ids")
    provs = db.query_rows("""SELECT p.provider_id, p.display_label, p.name, p.specialty, p.region, f.facility_id primary_facility, s.xgb_risk, s.anomaly_score, n.degree, n.betweenness, n.community_id,
                             (SELECT count(*) FROM evidence e WHERE e.case_id=:c AND e.provider_id=p.provider_id AND e.evidence_type='RULE') rule_findings
                             FROM providers p LEFT JOIN facilities f ON f.facility_id=p.primary_facility_id LEFT JOIN provider_scores s USING(provider_id) LEFT JOIN provider_network n USING(provider_id)
                             WHERE p.provider_id = ANY(:p) ORDER BY s.xgb_risk DESC""", {"c": case_id, "p": c["provider_ids"]})
    ev_summary = db.query_rows("SELECT evidence_type, COALESCE(rule_id,'-') rule_id, count(*) n, max(CASE severity WHEN 'CRITICAL' THEN 4 WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 WHEN 'LOW' THEN 1 ELSE 0 END) sev "
                               "FROM evidence WHERE case_id=:c GROUP BY 1,2 ORDER BY 1,2", {"c": case_id})
    ctx = C.build_context(case_id)
    tl = ctx["timeline"] or {}
    mem = brain.search(" ".join(c["patterns"] + c["rule_hits"]), "review_memory", None, 5, mode="hybrid")
    mem_hits = [h for h in mem["hits"]]
    return clean({"case": c, "providers": provs, "weights": config.PRIORITY_WEIGHTS, "evidence_summary": ev_summary, "claim_count": len(claim_ids),
                  "timeline": {"provider_id": ctx["anchor"], "events": tl.get("events", []), "escalation_score": tl.get("escalation_score"), "current_phase": tl.get("current_phase"),
                               "active_indicators": tl.get("active_indicators")},
                  "forecast": {"label": c["forecast_label"], "d30": c["forecast_30d"], "d60": c["forecast_60d"], "d90": c["forecast_90d"],
                               "provider_id": next((e["provider_id"] for e in ctx["evidence"] if e["evidence_type"] == "FORECAST"), ctx["anchor"])},
                  "shap": ctx["shap"], "similar_cases": ctx["similar"], "reviews": ctx["reviews"], "reviewer_memory": mem_hits,
                  "responsible_ai": "Investigation lead for human review. Not a finding of misconduct. No automated denial or suspension."})


@router.get("/cases/{case_id}/evidence")
def case_evidence(case_id: str, type: str | None = None, rule_id: str | None = None, provider_id: str | None = None, q: str | None = None,
                  limit: int = Query(100, le=500), offset: int = 0):
    _case_or_404(case_id)
    w, p = ["case_id=:c"], {"c": case_id, "l": limit, "o": offset}
    for col, val in (("evidence_type", type), ("rule_id", rule_id), ("provider_id", provider_id)):
        if val:
            w.append(f"{col}=:{col}")
            p[col] = val
    if q:
        w.append("(explanation ILIKE :q OR :qq = ANY(claim_ids) OR evidence_id=:qq)")
        p["q"], p["qq"] = f"%{q}%", q
    where = " AND ".join(w)
    rows = db.query_rows(f"SELECT * FROM evidence WHERE {where} ORDER BY CASE severity WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END, evidence_id LIMIT :l OFFSET :o", p)
    total = db.query_one(f"SELECT count(*) n FROM evidence WHERE {where}", p)["n"]
    for r in rows:
        r["payload"] = jl(r["payload"])
    return clean({"total": total, "items": rows})


@router.get("/cases/{case_id}/claims")
def case_claims(case_id: str, limit: int = Query(100, le=500), offset: int = 0, rule: str | None = None):
    _case_or_404(case_id)
    p = {"c": case_id, "l": limit, "o": offset, "r": f"%{rule}%" if rule else "%"}
    rows = db.query_rows("""SELECT cc.claim_id, cc.provider_id, cc.member_id, cc.paid_amount, cc.service_date, cc.procedure_code, cc.rules, cc.counts_toward_exposure,
                            (SELECT array_agg(e.evidence_id) FROM evidence e WHERE e.case_id=cc.case_id AND cc.claim_id = ANY(e.claim_ids)) evidence_ids
                            FROM case_claims cc WHERE cc.case_id=:c AND COALESCE(cc.rules,'') LIKE :r ORDER BY cc.paid_amount DESC LIMIT :l OFFSET :o""", p)
    total = db.query_one("SELECT count(*) n FROM case_claims WHERE case_id=:c AND COALESCE(rules,'') LIKE :r", p)["n"]
    return clean({"total": total, "items": rows})


@router.get("/cases/{case_id}/network")
def case_network(case_id: str, hops: int = Query(1, ge=1, le=2), center: str | None = None):
    c = _case_or_404(case_id)
    STORE.ensure()
    risk = {r["provider_id"]: r["xgb_risk"] for r in db.query_rows("SELECT provider_id, xgb_risk FROM provider_scores")}
    ev_edges: dict[str, list[str]] = {}
    for e in db.query_rows("SELECT evidence_id, source_table, source_row_id FROM evidence WHERE case_id=:c AND source_table='referrals'", {"c": case_id}):
        a, _, b = e["source_row_id"].partition(">")
        ev_edges.setdefault(f"referred_to:{a}>{b}", []).append(e["evidence_id"])
    centers = [center] if center else [c["anchor_provider_id"]]
    g = STORE.ego(centers, hops=hops, risk=risk, evidence_edges=ev_edges, include_claims=False, case_providers=c["provider_ids"])
    fac_ev = {e["source_row_id"]: e["evidence_id"] for e in db.query_rows("SELECT evidence_id, source_row_id FROM evidence WHERE case_id=:c AND feature='providers_sharing_facility'", {"c": case_id})}
    for n in g["nodes"].values():
        if n["type"] == "facility" and n["id"] in fac_ev:
            n["evidence_ids"] = [fac_ev[n["id"]]]
    return clean({"case_id": case_id, "center": centers, "hops": hops, "nodes": list(g["nodes"].values()), "edges": list(g["edges"].values()),
                  "note": "Network relationships are investigation leads, not proof of misconduct.", "capped_at": 140})


@router.get("/cases/{case_id}/timeline")
def case_timeline(case_id: str, provider_id: str | None = None):
    c = _case_or_404(case_id)
    pid = provider_id or c["anchor_provider_id"]
    if pid not in c["provider_ids"]:
        raise HTTPException(400, "provider not in case")
    return clean(_timeline(pid, case_id))


def _timeline(pid: str, case_id: str | None = None) -> dict:
    r = db.query_one("SELECT payload FROM provider_timeline WHERE provider_id=:p", {"p": pid})
    if not r:
        raise HTTPException(404, "No timeline for provider")
    tl = jl(r["payload"])
    evmap = {}
    if case_id:
        for e in db.query_rows("SELECT evidence_id, source_row_id FROM evidence WHERE case_id=:c AND evidence_type='TEMPORAL' AND provider_id=:p", {"c": case_id, "p": pid}):
            evmap[e["source_row_id"]] = e["evidence_id"]
    for ev in tl["events"]:
        ev["evidence_id"] = evmap.get(f"{pid}:{ev['indicator']}")
    return tl


@router.get("/cases/{case_id}/brief")
def case_brief(case_id: str, format: Literal["json", "markdown"] = "json"):
    ctx = C.build_context(case_id)
    if not ctx:
        raise HTTPException(404, "Unknown case")
    b = B.generate(ctx)
    errs = B.validate(b, ctx)
    if errs:
        raise HTTPException(500, f"Brief failed citation validation: {errs[:3]}")
    b["validated"] = True
    if format == "markdown":
        b["markdown"] = B.to_markdown(b)
    return clean(b)


@router.get("/cases/{case_id}/similar")
def case_similar(case_id: str, size: int = Query(5, le=20)):
    _case_or_404(case_id)
    return clean(brain.similar_cases(case_id, size))


@router.post("/cases/{case_id}/copilot")
def case_copilot(case_id: str, body: CopilotIn):
    _case_or_404(case_id)
    return clean(P.ask(case_id, body.question, body.use_llm))


@router.get("/cases/{case_id}/reviews")
def case_reviews(case_id: str):
    _case_or_404(case_id)
    return clean(db.query_rows("SELECT * FROM review_actions WHERE case_id=:c ORDER BY review_id DESC", {"c": case_id}))


@router.post("/cases/{case_id}/review")
def submit_review(case_id: str, body: ReviewIn):
    """Human SIU decision. Stored in PostgreSQL (source of truth) and written to reviewer memory in the Second Brain."""
    c = _case_or_404(case_id)
    new = STATUS_OF[body.decision]
    with db.begin() as conn:
        from sqlalchemy import text
        rid = conn.execute(text("""INSERT INTO review_actions (case_id, decision, rationale, reviewer, prior_status, new_status, context)
                                    VALUES (:c,:d,:r,:v,:p,:n, CAST(:x AS jsonb)) RETURNING review_id"""),
                           {"c": case_id, "d": body.decision, "r": body.rationale, "v": body.reviewer, "p": c["review_status"], "n": new,
                            "x": '{"priority": "%s", "priority_score": %.4f}' % (c["review_priority"], c["priority_score"])}).scalar_one()
        conn.execute(text("UPDATE cases SET review_status=:n, updated_at=now() WHERE case_id=:c"), {"n": new, "c": case_id})
    row = db.query_one("SELECT * FROM review_actions WHERE review_id=:i", {"i": rid})
    mem = brain.record_review(row)
    return clean({"review": row, "case_status": new, "reviewer_memory": mem, "note": "Decision recorded by a human reviewer. The system took no automated action on claims or providers."})


# ------------------------------------------------------------------------------------------------ providers
@router.get("/providers")
def providers(q: str | None = None, specialty: str | None = None, limit: int = Query(50, le=200), sort: Literal["risk", "anomaly", "claims"] = "risk"):
    w, p = ["1=1"], {"l": limit}
    if q:
        w.append("(f.provider_id ILIKE :q OR f.name ILIKE :q OR f.display_label ILIKE :q)")
        p["q"] = f"%{q}%"
    if specialty:
        w.append("f.specialty=:s")
        p["s"] = specialty
    order = {"risk": "s.xgb_risk", "anomaly": "s.anomaly_score", "claims": "f.claims_per_month_90d"}[sort]
    rows = db.query_rows(f"""SELECT f.provider_id, f.display_label, f.name, f.specialty, f.region, f.claims_per_month_90d, s.xgb_risk, s.anomaly_score, f.degree,
                             (SELECT case_id FROM cases c WHERE f.provider_id = ANY(c.provider_ids) ORDER BY priority_score DESC LIMIT 1) case_id
                             FROM provider_features f JOIN provider_scores s USING(provider_id) WHERE {' AND '.join(w)} ORDER BY {order} DESC NULLS LAST LIMIT :l""", p)
    return clean(rows)


PEER_LABEL = {"claims_per_month_90d": "Claims / month", "paid_per_month_90d": "Paid / month", "avg_allowed_90d": "Average claim amount", "claims_per_member_90d": "Claims per member",
              "unique_members_90d": "Unique members", "unique_facilities_90d": "Unique facilities", "dup_rate_90d": "Duplicate rate", "high_cx_ratio_180d": "High-complexity ratio",
              "ref_in_top_share_180d": "Referral concentration (inbound)", "ref_out_top_share_180d": "Referral concentration (outbound)", "degree": "Network degree"}


@router.get("/providers/{provider_id}")
def provider_profile(provider_id: str):
    f = db.query_one("SELECT * FROM provider_features WHERE provider_id=:p", {"p": provider_id})
    if not f:
        raise HTTPException(404, "Unknown provider")
    s = db.query_one("SELECT xgb_risk, anomaly_score, anomaly_raw, shap FROM provider_scores WHERE provider_id=:p", {"p": provider_id}) or {}
    net = db.query_one("SELECT * FROM provider_network WHERE provider_id=:p", {"p": provider_id}) or {}
    fc = db.query_one("SELECT f30, f60, f90, label FROM provider_forecast WHERE provider_id=:p ORDER BY month_idx DESC LIMIT 1", {"p": provider_id})
    prov = db.query_one("SELECT p.*, fa.facility_type, fa.city facility_city FROM providers p LEFT JOIN facilities fa ON fa.facility_id=p.primary_facility_id WHERE p.provider_id=:p", {"p": provider_id})
    peers = []
    for m, label in PEER_LABEL.items():
        if f"peer_median__{m}" in f and f.get(m) is not None:
            peers.append({"metric": m, "label": label, "value": f[m], "peer_median": f[f"peer_median__{m}"], "z": f.get(f"peer_z__{m}"), "percentile": f.get(f"peer_pct__{m}"), "ratio": f.get(f"peer_ratio__{m}")})
    cases_ = db.query_rows("SELECT case_id, review_priority, priority_score, review_status FROM cases WHERE :p = ANY(provider_ids) ORDER BY priority_score DESC", {"p": provider_id})
    rules = db.query_rows("SELECT rule_id, severity, count(*) n FROM evidence WHERE provider_id=:p AND evidence_type='RULE' GROUP BY 1,2 ORDER BY 1", {"p": provider_id})
    lab = db.query_one("SELECT role FROM provider_labels WHERE provider_id=:p", {"p": provider_id})
    inv = db.query_rows("SELECT investigation_id, outcome, opened_date, patterns FROM investigations WHERE provider_id=:p", {"p": provider_id})
    tl = db.query_one("SELECT payload FROM provider_timeline WHERE provider_id=:p", {"p": provider_id})
    return clean({"provider": prov, "peer_group": f["peer_group"], "peer_size": f["peer_size"], "peer_benchmarks": peers, "scores": {"fwa_risk_score": s.get("xgb_risk"), "anomaly_score": s.get("anomaly_score")},
                  "shap": jl(s.get("shap")), "network": net, "forecast": fc, "cases": cases_, "rule_findings": rules, "historical_investigations": inv,
                  "timeline": jl(tl["payload"]) if tl else None,
                  "disclaimer": "Peer deviation, anomaly scores and SHAP attributions are investigation signals, not proof of misconduct. High utilization can be legitimate (e.g. oncology infusion cycles)."})


# ------------------------------------------------------------------------------------------------ network explorer
@router.get("/network/ego")
def network_ego(center: str, hops: int = Query(1, ge=1, le=2)):
    STORE.ensure()
    if center not in STORE.prov.index and center not in STORE.fac.index:
        raise HTTPException(404, "Unknown entity")
    risk = {r["provider_id"]: r["xgb_risk"] for r in db.query_rows("SELECT provider_id, xgb_risk FROM provider_scores")}
    g = STORE.ego([center], hops=hops, risk=risk, include_claims=False)
    return clean({"center": center, "hops": hops, "nodes": list(g["nodes"].values()), "edges": list(g["edges"].values()),
                  "note": "Network relationships are investigation leads, not proof of misconduct."})


@router.get("/network/path")
def network_path(a: str, b: str):
    import networkx as nx
    STORE.ensure()
    try:
        path = nx.shortest_path(STORE.G, a, b)
    except (nx.NodeNotFound, nx.NetworkXNoPath):
        return {"a": a, "b": b, "path": None, "length": None}
    common = sorted(set(STORE.G[a]) & set(STORE.G[b])) if a in STORE.G and b in STORE.G else []
    return {"a": a, "b": b, "path": path, "length": len(path) - 1, "common_neighbors": common[:25]}


# ------------------------------------------------------------------------------------------------ Second Brain
@router.get("/brain/status")
def brain_status():
    return clean(brain.status())


@router.post("/brain/search")
def brain_search(body: SearchIn):
    return clean(brain.search(body.query, body.index, body.filters, body.size, body.mode))


@router.get("/brain/memory")
def brain_memory():
    """Nexus Memory overview: historical investigations, patterns and reviewer memory."""
    patterns = db.query_rows("SELECT * FROM investigations LIMIT 0")  # keep schema touch cheap
    b = brain.get_backend()
    pats = [h.to_dict()["doc"] for h in b.filter_only("patterns", None, 20)]
    revs = [h.to_dict()["doc"] for h in b.filter_only("review_memory", None, 50)]
    outcomes = db.query_rows("SELECT outcome, count(*) n, COALESCE(sum(amount_identified),0) amount FROM investigations GROUP BY 1 ORDER BY 2 DESC")
    return clean({"status": brain.status(), "patterns": pats, "reviewer_memory": revs, "historical_outcomes": outcomes,
                  "historical_investigations": db.query_one("SELECT count(*) n FROM investigations")["n"]})


@router.post("/brain/reindex")
def brain_reindex():
    from ..brain import indexer
    return clean(indexer.index_all())
