"""End-to-end pipeline orchestrator:

 synthetic claims -> ingestion -> feature intelligence -> FWA rules + evidence ledger -> ML (IF/XGBoost/SHAP) -> 30/60/90 forecast
 -> network intelligence -> temporal intelligence -> cases + risk fusion -> Nexus Second Brain index

Run:  python -m app.pipeline --reset
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

from . import cases as cases_mod
from . import config, datagen, db, evidence, features, forecast, graph, ingestion, loader, ml, rules, temporal


def _stage(name: str, log: list, t0: float, **info):
    dt = round(time.time() - t0, 1)
    log.append({"stage": name, "seconds": dt, **info})
    print(f"[pipeline] {name:<28} {dt:>6.1f}s  {json.dumps(info, default=str)[:160]}", flush=True)


def run(regenerate: bool = True, reset: bool = True, index_brain: bool = True) -> dict:
    log: list[dict] = []
    T = time.time()
    # ---------------------------------------------------------------- 1. data
    t = time.time()
    if regenerate or not (config.SYNTH_DIR / "claims.csv").exists():
        gen = datagen.generate()
    else:
        gen = json.loads((config.SYNTH_DIR / "generation_summary.json").read_text())
    _stage("generate_synthetic_data", log, t, claims=gen["claims_valid"], injected=gen["injected_fwa_claims"])
    t = time.time()
    ing = ingestion.ingest(reset=reset)
    _stage("ingest_postgres", log, t, loaded=ing["claims_loaded"], quarantined=ing["claims_quarantined"])
    for tbl in ("claim_flags", "provider_features", "provider_month_panel", "provider_scores", "provider_forecast", "provider_network", "network_edges", "provider_timeline"):
        db.execute(f"DROP TABLE IF EXISTS {tbl}")
    db.execute("DELETE FROM model_runs")

    # ---------------------------------------------------------------- 2. load + rules
    t = time.time()
    c, refs, rels, prov = loader.load_enriched(), loader.load_referrals(), loader.load_relationships(), loader.load_providers()
    labels = db.query_df("SELECT claim_id, injected_fwa FROM claim_labels")
    flags, ev_claim = rules.run_claim_level(c)
    dup_ids = rules.duplicate_claim_ids(c)
    feats = features.build_provider_features(c, refs, rels, prov, dup_ids)
    ev_prov = rules.run_provider_level(feats, c, refs)
    evid = evidence.persist(ev_claim + ev_prov, 1)
    by_rule = evid.rule_id.value_counts().to_dict()
    db.write_df(flags, "claim_flags")
    fcols = [x for x in feats.columns if x != "as_of"]
    db.write_df(feats[fcols].assign(as_of=str(config.AS_OF)), "provider_features")
    db.log_model_run("rules", "FWA rule engine R001-R008", config.RULE_VERSION, metrics={"evidence_by_rule": by_rule, "providers_with_hits": int(evid.provider_id.nunique())})
    _stage("rules_and_evidence", log, t, evidence_rows=len(evid), by_rule=by_rule)

    # ---------------------------------------------------------------- 3. ML
    t = time.time()
    panel = features.build_panel(c, refs, rels, prov, flags, labels)
    iso = ml.run_isolation_forest(feats)
    model, metrics, _ = ml.train_xgb_risk(panel)
    panel["xgb_risk"] = ml.score_panel(model, panel)
    cur = panel[panel.month_idx == config.N_MONTHS]
    xgbs = dict(zip(cur.provider_id, cur.xgb_risk.astype(float)))
    shap_all = ml.shap_top(model, cur)
    base_rate = float(panel[(panel.n_t3 > 0) & (panel.month_idx >= 4)].y_now.mean())
    keep = ["provider_id", "month_idx", "month_start", "n", "paid", "n_t3", "xgb_risk"] + features.MODEL_FEATURES
    db.write_df(panel[keep], "provider_month_panel")
    sc = iso.merge(pd.DataFrame({"provider_id": list(xgbs), "xgb_risk": list(xgbs.values())}), on="provider_id")
    sc["shap"] = sc.provider_id.map(lambda p: json.dumps(shap_all[p]))
    db.write_df(sc, "provider_scores", dtype={"shap": JSONB})
    _stage("ml_scoring", log, t, xgb_pr_auc=round(metrics["xgboost"]["pr_auc"], 3), rules_only_pr_auc=round(metrics["rules_only_baseline"]["pr_auc"], 3),
           if_baseline_pr_auc=round(metrics["isolation_forest_baseline"]["pr_auc"], 3))

    # ---------------------------------------------------------------- 4. forecast
    t = time.time()
    fscore, fres = forecast.train_and_score(panel)
    db.write_df(fscore, "provider_forecast")
    _stage("forecast_30_60_90", log, t, output_label=fres["output_label"])

    # ---------------------------------------------------------------- 5. network
    t = time.time()
    edges = graph.build_edges(c, refs, rels)
    net = graph.analyze(edges, prov)
    db.write_df(edges, "network_edges")
    db.write_df(net, "provider_network")
    _stage("network_graph", log, t, edges=len(edges), by_type=edges.edge_type.value_counts().to_dict())

    # ---------------------------------------------------------------- 6. temporal + cases
    t = time.time()
    rule_ev = evid[evid.evidence_type == "RULE"]
    sus = cases_mod.select_suspicious(rule_ev, xgbs, feats.set_index("provider_id"))
    conn = features.connection_events(refs, rels)
    tl = {p: temporal.provider_timeline(p, c, refs, conn, dup_ids) for p in sorted(sus)}
    # hero and controls always get timelines so the demo and the false-positive comparison are complete
    for p in [config.HERO_PROVIDER, *config.CONTROL_PROVIDERS]:
        if p not in tl:
            tl[p] = temporal.provider_timeline(p, c, refs, conn, dup_ids)
    db.write_df(pd.DataFrame({"provider_id": list(tl), "payload": [json.dumps(v, default=db._json_default) for v in tl.values()]}), "provider_timeline", dtype={"payload": JSONB})
    _stage("temporal_timelines", log, t, providers=len(tl))

    t = time.time()
    fcur = fscore[fscore.month_idx == config.N_MONTHS]
    ctx = {"claims": c, "flags": flags, "feats": feats, "evid": evid, "iso": iso, "xgb": xgbs, "shap": shap_all, "net": net, "edges": edges, "timelines": tl,
           "forecast": fcur, "forecast_label": fres["output_label"], "forecast_version": forecast.FORECAST_VERSION, "xgb_base_rate": base_rate,
           "xgb_version": ml.XGB_VERSION, "if_version": ml.IF_VERSION, "referrals": refs, "providers": prov}
    built = cases_mod.build_cases(ctx)
    cdf = built["cases"]
    arr_cols = ["provider_ids", "facility_ids", "member_ids_sample", "claim_ids", "rule_hits", "patterns", "limitations"]
    pg = cdf.copy()
    for col in arr_cols:
        pg[col] = pg[col].apply(lambda v: "{" + ",".join('"' + str(x).replace('"', "") + '"' for x in v) + "}")
    db.copy_df(pg, "cases", ["case_id", "anchor_provider_id", "provider_ids", "facility_ids", "member_count", "member_ids_sample", "claim_ids", "claim_count", "rule_hits", "patterns",
                             "specialty", "model_score", "anomaly_score", "components", "priority_score", "review_priority", "review_status", "potential_exposure",
                             "forecast_30d", "forecast_60d", "forecast_90d", "forecast_label", "network_signals", "limitations", "first_activity", "as_of", "summary"])
    cc = built["case_claims"]
    db.copy_df(cc, "case_claims", ["case_id", "claim_id", "provider_id", "member_id", "paid_amount", "service_date", "procedure_code", "rules", "counts_toward_exposure"])
    # extra (model/peer/network/temporal/forecast) evidence + attach rule evidence to cases
    extra = built["extra_evidence"]
    start = int(evid.evidence_id.str[3:].astype(int).max()) + 1
    ex_df = evidence.persist(extra, start)
    ex_df["case_id"] = ex_df.payload.apply(lambda d: d.get("case_id"))
    with db.begin() as conn_:
        conn_.execute(text("UPDATE evidence e SET case_id = x.case_id FROM (SELECT provider_id, unnest(ARRAY[case_id]) AS case_id FROM (SELECT unnest(provider_ids) AS provider_id, case_id FROM cases) q) x "
                           "WHERE e.provider_id = x.provider_id AND e.evidence_type = 'RULE'"))
        rows = [{"e": r.evidence_id, "c": r.case_id} for r in ex_df.itertuples() if r.case_id]
        conn_.execute(text("UPDATE evidence SET case_id = :c WHERE evidence_id = :e"), rows)
    _stage("cases_and_risk_fusion", log, t, cases=len(cdf), critical=int((cdf.review_priority == "CRITICAL").sum()), high=int((cdf.review_priority == "HIGH").sum()),
           extra_evidence=len(ex_df))

    # ---------------------------------------------------------------- 7. funnel ingredients
    c_if = c.provider_id.map(iso.set_index("provider_id").anomaly_score).fillna(0) >= 0.90
    price_z = c.groupby("procedure_code").allowed_amount.transform(lambda s: 0.6745 * (s - s.median()) / max((s - s.median()).abs().median(), 1e-6))
    anomaly_mask = c_if | c.claim_id.isin(flags[flags[["f_dup", "f_unbundle", "f_implaus", "f_timing"]].any(axis=1)].claim_id) | (price_z.abs() > 3.5) | c.claim_id.isin(set(cc.claim_id))
    funnel = {"claims": int(len(c)), "anomalies": int(anomaly_mask.sum()), "suspicious_claims": int(cc.claim_id.nunique()), "connected_cases": int(len(cdf)),
              "high_risk_cases": int(cdf.review_priority.isin(["HIGH", "CRITICAL"]).sum()), "critical_cases": int((cdf.review_priority == "CRITICAL").sum()),
              "definitions": {"anomalies": "claims with a claim-level rule flag, a >3.5 robust-z price outlier within procedure, or from a provider in the top 10% by Isolation Forest anomaly score, plus any claim implicated in a case",
                              "suspicious_claims": "distinct claims implicated by deterministic rules, referral-concentration or upcoding evidence inside a case",
                              "connected_cases": "groups of suspicious providers linked by referrals, associations or shared members",
                              "high_risk_cases": "cases with priority HIGH or CRITICAL under the SIU priority policy",
                              "siu_priorities": "top-K cases for the selected investigator capacity (5/10/20)"}}
    summary = {"stages": log, "funnel": funnel, "ingestion": ing, "generation": gen, "forecast_label": fres["output_label"], "total_seconds": round(time.time() - T, 1)}
    db.log_model_run("pipeline_summary", "ClaimShield Nexus pipeline", config.DATASET_VERSION, metrics=summary)
    if index_brain:
        t = time.time()
        from .brain import indexer
        res = indexer.index_all()
        summary["second_brain"] = res
        db.log_model_run("second_brain_index", "Nexus Second Brain", "brain-1.0.0", metrics=res)
        _stage("second_brain_index", log, t, **{k: v for k, v in res.items() if k in ("backend", "docs", "vector_mode")})
    print(f"[pipeline] complete in {time.time() - T:.1f}s", flush=True)
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="regenerate synthetic data and reload the database")
    ap.add_argument("--no-brain", action="store_true")
    a = ap.parse_args()
    run(regenerate=a.reset, reset=True, index_brain=not a.no_brain)
