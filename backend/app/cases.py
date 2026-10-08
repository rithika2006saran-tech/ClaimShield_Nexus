"""Case formation, evidence fusion and risk decomposition.

A case groups suspicious providers that are connected (referral flows, associations, shared members at a shared facility).
Risk is kept DECOMPOSED (rules, peer, model, anomaly, network, temporal, evidence strength, exposure, member impact)
and combined by a transparent weighted policy (config.PRIORITY_WEIGHTS). The score ranks investigation leads;
it never declares fraud.
"""
from __future__ import annotations

import json
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd

from . import config, db
from .evidence import SEVERITY_WEIGHT, make_ev
from .features import FEATURE_LABELS, PEER_METRICS
from .rules import RULES

AS_OF = pd.Timestamp(config.AS_OF)
MED_PLUS = ("MEDIUM", "HIGH", "CRITICAL")

PRIORITY_BANDS = [(0.70, "CRITICAL"), (0.55, "HIGH"), (0.40, "MEDIUM"), (0.0, "LOW")]

PATTERN_TAGS = {
    "R001_DUPLICATE": "duplicate billing", "R002_UPCODING": "upcoding", "R003_UNBUNDLING": "unbundling", "R004_IMPLAUSIBLE_SERVICE": "implausible service",
    "R005_EXCESSIVE_UTILIZATION": "excessive utilization", "R006_IMPOSSIBLE_TIMING": "impossible timing", "R007_REFERRAL_CONCENTRATION": "referral concentration",
    "R008_NETWORK_EXPANSION": "network expansion",
}


def band(score: float) -> str:
    return next(name for thr, name in PRIORITY_BANDS if score >= thr)


def _norm_log(x: float, cap: float) -> float:
    return float(np.clip(np.log10(1 + max(x, 0)) / np.log10(1 + cap), 0, 1))


def select_suspicious(rule_ev: pd.DataFrame, xgbs: dict, feats: pd.DataFrame) -> set[str]:
    """Providers worth case-level attention: a MEDIUM+ rule hit corroborated by the model or a second rule, or a very high model risk."""
    rm = rule_ev[rule_ev.severity.isin(MED_PLUS)]
    prov_rules = rm.groupby("provider_id").rule_id.nunique()
    cand = set(prov_rules.index) | {p for p, s in xgbs.items() if s >= 0.6}
    sus = {p for p in cand if (prov_rules.get(p, 0) >= 1 and (xgbs.get(p, 0) >= 0.30 or prov_rules.get(p, 0) >= 2)) or xgbs.get(p, 0) >= 0.60}
    return {p for p in sus if feats.loc[p, "claims_90d"] >= 8}


# ------------------------------------------------------------------------------------------------- implicated claims
def implicated_claims(c: pd.DataFrame, flags: pd.DataFrame, feats: pd.DataFrame, evid: pd.DataFrame, referrals: pd.DataFrame) -> pd.DataFrame:
    """Claims implicated by claim-level rules + referral concentration + upcoding; with the reason(s) and whether they count toward exposure."""
    f = flags.set_index("claim_id")
    base = c[["claim_id", "provider_id", "member_id", "paid_amount", "service_date", "procedure_code"]].copy()
    parts = []
    key = ["provider_id", "member_id", "procedure_code", "service_date"]
    dgrp = c[c.claim_id.isin(f.index[f.f_dup])].sort_values("claim_id")
    if len(dgrp):
        dgrp = dgrp.assign(_rank=dgrp.groupby(key).cumcount())
        parts.append(pd.DataFrame({"claim_id": dgrp.claim_id, "rule": "R001_DUPLICATE", "counts": dgrp._rank > 0}))
    for col, rule in (("f_unbundle", "R003_UNBUNDLING"), ("f_implaus", "R004_IMPLAUSIBLE_SERVICE"), ("f_timing", "R006_IMPOSSIBLE_TIMING")):
        ids = f.index[f[col]]
        parts.append(pd.DataFrame({"claim_id": ids, "rule": rule, "counts": True}))
    # provider-level claim links from stored evidence (R007 referral-linked claims, R002 high-complexity claims)
    pe = evid[evid.rule_id.isin(["R007_REFERRAL_CONCENTRATION", "R002_UPCODING"]) & (evid.claim_count > 0)]
    W180 = AS_OF - pd.Timedelta(days=179)
    for r in pe.itertuples():
        if r.rule_id == "R007_REFERRAL_CONCENTRATION" and r.payload.get("direction") == "inbound":
            cl = c[(c.provider_id == r.provider_id) & (c.referring_provider_id == r.payload["top_referrer"]) & (c.service_date >= W180)]
        elif r.rule_id == "R002_UPCODING":
            cl = c[(c.provider_id == r.provider_id) & (c.em_level == 5) & (c.service_date >= W180)]
        else:
            continue
        parts.append(pd.DataFrame({"claim_id": cl.claim_id, "rule": r.rule_id, "counts": True}))
    allp = pd.concat(parts, ignore_index=True)
    # legitimate-service claims referred by a concentrated source count as 'linked', not 'redundant'
    agg = allp.groupby("claim_id").agg(rules=("rule", lambda s: sorted(set(s))), counts=("counts", "max")).reset_index()
    out = agg.merge(base, on="claim_id", how="left")
    return out


# ------------------------------------------------------------------------------------------------------------ formation
def form_cases(prov: pd.DataFrame, edges: pd.DataFrame, suspicious: set[str], rule_providers: set[str]) -> tuple[list[list[str]], set[str]]:
    """Group suspicious providers into connected cases. A provider with a MEDIUM+ rule hit that is directly linked to a suspicious provider
    (for example the referral source) is pulled into the case so the investigator sees the whole relationship."""
    pe = edges[(edges.dst_type == "provider")]
    linked = []
    for r in pe.itertuples():
        if (r.edge_type == "associated_with") or (r.edge_type == "referred_to" and r.weight >= 5) or (r.edge_type == "shared_members" and r.weight >= 6):
            linked.append((r.src_id, r.dst_id))
    ext = set(suspicious)
    for a, b in linked:
        if a in suspicious and b in rule_providers:
            ext.add(b)
        if b in suspicious and a in rule_providers:
            ext.add(a)
    G = nx.Graph()
    G.add_nodes_from(ext)
    G.add_edges_from((a, b) for a, b in linked if a in ext and b in ext)
    return [sorted(c) for c in nx.connected_components(G)], ext


def network_severity(providers: list[str], edges: pd.DataFrame, suspicious: set[str], net: pd.DataFrame) -> dict:
    sub = edges[edges.src_id.isin(providers) & edges.dst_id.isin(providers) & (edges.dst_type == "provider")]
    n = len(providers)
    pairs = n * (n - 1) / 2
    linked = {tuple(sorted((r.src_id, r.dst_id))) for r in sub.itertuples()}
    density = len(linked) / pairs if pairs else 0.0
    wa = edges[(edges.edge_type == "works_at") & edges.src_id.isin(providers)]
    shared_fac = wa.groupby("dst_id").src_id.nunique()
    shared_fac = shared_fac[shared_fac >= 2]
    nbrs = set()
    for p in providers:
        ee = edges[((edges.src_id == p) | (edges.dst_id == p)) & (edges.dst_type == "provider") & (edges.edge_type != "works_at")]
        nbrs |= set(ee.src_id) | set(ee.dst_id)
    nbrs -= set(providers)
    nbr_susp = len(nbrs & suspicious) / max(len(nbrs), 1)
    n_norm = min(1.0, (n - 1) / 4)
    sev = 0.35 * n_norm + 0.25 * density + 0.20 * (1.0 if len(shared_fac) else 0.0) + 0.20 * min(1.0, nbr_susp * 3)
    flows = sub[sub.edge_type == "referred_to"].sort_values("weight", ascending=False)
    return {"severity": float(np.clip(sev, 0, 1)), "n_providers": n, "link_density": float(density), "shared_facilities": shared_fac.to_dict(),
            "suspicious_neighbor_share": float(nbr_susp), "top_referral_flows": [{"from": r.src_id, "to": r.dst_id, "referrals": int(r.weight)} for r in flows.head(5).itertuples()],
            "max_betweenness": float(net.loc[net.index.isin(providers), "betweenness"].max())}


def _limitations(label: str, model_only: bool, n_prov: int) -> list[str]:
    lim = [
        "Ownership and corporate-relationship data are unavailable; network relationships are investigation leads, not proof.",
        "Clinical documentation and diagnosis data are unavailable; medical necessity and coding accuracy were not assessed.",
        "Peer groups use specialty, region and facility type; patient acuity and case mix are not modeled, so peer deviation may have legitimate explanations.",
        f"30/60/90-day outputs are reported as {'calibrated probabilities (evaluated on a held-out chronological test period of synthetic data)' if label == 'probability' else 'escalation indices (calibration criteria not met)'}.",
        "All data are synthetic; model metrics describe synthetic-scenario detection and do not imply real-world performance.",
    ]
    if model_only:
        lim.append("No deterministic rule fired at MEDIUM or above for this case; the signal is model/behavioural only and needs human confirmation.")
    return lim


# ---------------------------------------------------------------------------------------------------------------- build
def build_cases(ctx: dict) -> dict:
    """ctx keys: claims, flags, feats, evid(DataFrame of rule evidence with ids), iso, xgb(dict pid->score), shap, net, edges, timelines(dict), forecast(DataFrame current),
    forecast_label, xgb_base_rate, referrals, providers"""
    c, flags, feats, evid = ctx["claims"], ctx["flags"], ctx["feats"].set_index("provider_id"), ctx["evid"]
    iso = ctx["iso"].set_index("provider_id")
    xgbs: dict[str, float] = ctx["xgb"]
    net = ctx["net"].set_index("provider_id")
    edges = ctx["edges"]
    rule_ev = evid[(evid.evidence_type == "RULE")]
    rm = rule_ev[rule_ev.severity.isin(MED_PLUS)]
    suspicious = select_suspicious(rule_ev, xgbs, feats)
    groups, suspicious = form_cases(ctx["providers"], edges, suspicious, set(rm.provider_id))

    impl = implicated_claims(c, flags, feats.reset_index(), evid, ctx["referrals"])
    impl = impl[impl.provider_id.isin(suspicious | set(sum(groups, [])))]

    # case id assignment: sequential by anchor id; the pinned hero case keeps its demo id
    def anchor_of(g):
        score = {p: 0.5 * xgbs.get(p, 0) + 0.3 * min(1, sum(SEVERITY_WEIGHT[s] for s in rm[rm.provider_id == p].groupby("rule_id").severity.agg(
            lambda x: max(x, key=lambda y: SEVERITY_WEIGHT[y]))) / 2.5) + 0.2 * float(iso.anomaly_score.get(p, 0)) for p in g}
        return max(g, key=lambda p: (score[p], impl[impl.provider_id == p].paid_amount.sum()))
    anchors = {tuple(g): anchor_of(g) for g in groups}
    order = sorted(groups, key=lambda g: anchors[tuple(g)])
    ids, seq = {}, 1000
    for g in order:
        if anchors[tuple(g)] == config.HERO_PROVIDER:
            ids[tuple(g)] = config.HERO_CASE_ID
            continue
        seq += 1
        while f"CASE-{seq}" == config.HERO_CASE_ID:
            seq += 1
        ids[tuple(g)] = f"CASE-{seq}"

    cases, case_claims, extra_ev = [], [], []
    tl = ctx["timelines"]
    fc = ctx["forecast"].set_index("provider_id")
    label = ctx["forecast_label"]
    for g in order:
        cid, anchor = ids[tuple(g)], anchors[tuple(g)]
        pe = rm[rm.provider_id.isin(g)]
        # --- exposure & claim set ---
        ic = impl[impl.provider_id.isin(g)]
        exposure_claims = ic[ic.counts]
        exposure = float(exposure_claims.paid_amount.sum())
        counted = set(exposure_claims.claim_id)
        for r in pe[pe.rule_id == "R005_EXCESSIVE_UTILIZATION"].itertuples():
            ratio = r.observed_value / r.expected_value if r.expected_value else 1
            win = c[(c.provider_id == r.provider_id) & (c.service_date >= AS_OF - pd.Timedelta(days=89))]
            exposure += max(0.0, float(win.paid_amount.sum()) * (1 - 1 / max(ratio, 1)) - float(win[win.claim_id.isin(counted)].paid_amount.sum()))
        for r in pe[pe.rule_id == "R002_UPCODING"].itertuples():
            w = c[(c.provider_id == r.provider_id) & (c.em_level >= 4) & (c.service_date >= AS_OF - pd.Timedelta(days=179)) & ~c.claim_id.isin(counted)]
            exposure += float(w.paid_amount.sum()) * max(0.0, 1 - r.expected_value / max(r.observed_value, 1e-6))
        members = ic.member_id.dropna().unique().tolist()
        # --- components ---
        rule_w = {rid: max(SEVERITY_WEIGHT[s] for s in pe[pe.rule_id == rid].severity) for rid in pe.rule_id.unique()}
        rule_score = min(1.0, sum(rule_w.values()) / 2.5)
        maxz = max([float(feats.loc[p, f"peer_z__{m}"]) for p in g for m in PEER_METRICS if m != "degree" and feats.loc[p, "claims_90d"] >= 8 and pd.notna(feats.loc[p, f"peer_z__{m}"])] or [0.0])
        peer_score = float(np.clip((maxz - 2.0) / 6.0, 0, 1))
        model_risk = max(xgbs.get(p, 0) for p in g)
        anomaly = max(float(iso.anomaly_score.get(p, 0)) for p in g)
        nsev = network_severity(g, edges, suspicious, net)
        temporal = max(float(tl[p]["escalation_score"]) for p in g if p in tl) if any(p in tl for p in g) else 0.0
        fam = sum([len(rule_w) > 0, maxz >= 3.5, model_risk >= 0.5, anomaly >= 0.9, nsev["severity"] >= 0.4, temporal >= 0.5])
        coverage = min(1.0, len(ic) / 25)
        ev_strength = 0.6 * fam / 6 + 0.4 * coverage
        comps = {"model_risk": model_risk, "rule_evidence": rule_score, "peer_deviation": peer_score, "network": nsev["severity"], "temporal": temporal, "anomaly": anomaly,
                 "evidence_strength": ev_strength, "exposure": _norm_log(exposure, 1e6), "member_impact": _norm_log(len(members), 400)}
        w = config.PRIORITY_WEIGHTS
        priority = float(sum(comps[k] * w[k] for k in w))
        # --- forecast: highest-risk provider in the case ---
        top_p = max(g, key=lambda p: float(fc.loc[p, "f90"]) if p in fc.index else 0)
        f30, f60, f90 = (float(fc.loc[top_p, f"f{h}"]) for h in (30, 60, 90))
        specialty = ctx["providers"].set_index("provider_id").loc[anchor, "specialty"]
        region = ctx["providers"].set_index("provider_id").loc[anchor, "region"]
        rule_ids = sorted(rule_w)
        patterns = [PATTERN_TAGS[r] for r in rule_ids]
        if nsev["shared_facilities"]:
            patterns.append("shared facility")
        if len(g) > 1:
            patterns.append("coordinated network")
        if temporal >= 0.5:
            patterns.append("temporal escalation")
        fac_ids = sorted(set(edges[(edges.edge_type == "works_at") & edges.src_id.isin(g)].dst_id))
        first = [pd.Timestamp(e["date"]) for p in g if p in tl for e in tl[p]["events"]]
        names = ", ".join(patterns[:5])
        summary = (f"{anchor} ({specialty}, {region}) is the anchor of a {len(g)}-provider connected case. Detected patterns: {names}. "
                   f"Potential exposure ${exposure:,.0f} across {len(members)} members. This is an investigation lead for human review.")
        cases.append({
            "case_id": cid, "anchor_provider_id": anchor, "provider_ids": g, "facility_ids": fac_ids, "member_count": len(members), "member_ids_sample": members[:50],
            "claim_ids": ic.sort_values("paid_amount", ascending=False).claim_id.tolist()[:200], "claim_count": int(len(ic)), "rule_hits": rule_ids, "patterns": patterns,
            "specialty": specialty, "model_score": model_risk, "anomaly_score": anomaly, "components": json.dumps({k: round(float(v), 4) for k, v in comps.items()}),
            "priority_score": priority, "review_priority": band(priority), "review_status": "PENDING", "potential_exposure": round(exposure, 2), "forecast_30d": f30,
            "forecast_60d": f60, "forecast_90d": f90, "forecast_label": label, "network_signals": json.dumps([nsev], default=db._json_default),
            "limitations": _limitations(label, len(rule_w) == 0, len(g)), "first_activity": min(first).date() if first else None, "as_of": AS_OF.date(), "summary": summary})
        for r in ic.itertuples():
            case_claims.append({"case_id": cid, "claim_id": r.claim_id, "provider_id": r.provider_id, "member_id": r.member_id, "paid_amount": r.paid_amount,
                                "service_date": r.service_date, "procedure_code": r.procedure_code, "rules": "|".join(r.rules), "counts_toward_exposure": bool(r.counts)})
        extra_ev += _case_evidence(cid, g, anchor, ctx, nsev, comps, top_p, (f30, f60, f90), label, tl)
    return {"cases": pd.DataFrame(cases), "case_claims": pd.DataFrame(case_claims), "extra_evidence": extra_ev, "suspicious": suspicious,
            "case_of_provider": {p: ids[tuple(g)] for g in order for p in g}}


def _case_evidence(cid, g, anchor, ctx, nsev, comps, top_p, fvals, label, tl) -> list[dict]:
    feats = ctx["feats"].set_index("provider_id")
    iso = ctx["iso"].set_index("provider_id")
    xgbs, shap = ctx["xgb"], ctx["shap"]
    out = []
    mv_x, mv_i = ctx["xgb_version"], ctx["if_version"]
    for p in sorted(g, key=lambda p: -xgbs.get(p, 0))[:6]:
        if xgbs.get(p, 0) >= 0.30:
            out.append(make_ev(rule_id=None, severity=None, source_table="provider_scores", source_row_id=p, claim_ids=[], provider_id=p, feature="xgboost_fwa_risk_score",
                               observed=xgbs[p], expected=ctx["xgb_base_rate"], unit="score", ts=AS_OF, evidence_type="MODEL", model_version=mv_x,
                               explanation=(f"XGBoost FWA risk score for {p} is {xgbs[p]:.2f} (population base rate of risky provider-months {ctx['xgb_base_rate']:.2f}). "
                                            "This is a supervised model output on synthetic scenarios, not a probability of fraud."), payload={"case_id": cid}))
        if float(iso.anomaly_score.get(p, 0)) >= 0.90:
            out.append(make_ev(rule_id=None, severity=None, source_table="provider_scores", source_row_id=p, claim_ids=[], provider_id=p, feature="isolation_forest_anomaly_percentile",
                               observed=float(iso.anomaly_score[p]), expected=0.5, unit="percentile", ts=AS_OF, evidence_type="ANOMALY", model_version=mv_i,
                               explanation=f"Isolation Forest anomaly score places {p} at the {iso.anomaly_score[p]:.0%} percentile of providers on raw behaviour features. Anomaly score is not a fraud probability.",
                               payload={"case_id": cid}))
        if p in shap and xgbs.get(p, 0) >= 0.30:
            for t in shap[p]["positive"][:3]:
                out.append(make_ev(rule_id=None, severity=None, source_table="provider_scores", source_row_id=p, claim_ids=[], provider_id=p, feature=t["feature"],
                                   observed=t["feature_value"], expected=None, unit="feature value", ts=AS_OF, evidence_type="SHAP", model_version=mv_x,
                                   explanation=f"SHAP attribution: '{t['label']}' (value {t['feature_value']:.2f}) pushed the XGBoost risk score up by {t['shap_value']:.2f} log-odds for {p}. Model attribution only; not evidence of misconduct.",
                                   payload={"shap_value": t["shap_value"], "case_id": cid}))
        # peer deviation evidence
        row = feats.loc[p]
        devs = sorted(((m, float(row[f"peer_z__{m}"])) for m in PEER_METRICS if m != "degree" and row.claims_90d >= 8 and pd.notna(row[f"peer_z__{m}"])), key=lambda x: -x[1])[:3]
        for m, z in devs:
            if z >= 3.0:
                out.append(make_ev(rule_id=None, severity="HIGH" if z >= 6 else "MEDIUM", source_table="provider_features", source_row_id=p, claim_ids=[], provider_id=p, feature=m,
                                   observed=float(row[m]), expected=float(row[f"peer_median__{m}"]), unit="peer comparison", ts=AS_OF, evidence_type="PEER",
                                   explanation=(f"{p} {m.replace('_', ' ')} = {row[m]:.2f} versus peer median {row[f'peer_median__{m}']:.2f} (robust z={z:.1f}, percentile {row[f'peer_pct__{m}']:.0%}; "
                                                f"peer group {row.peer_group}). Peer deviation alone does not establish misconduct."), payload={"peer_group": row.peer_group, "case_id": cid}))
    # network evidence
    for fid, n in nsev["shared_facilities"].items():
        provs = sorted(ctx["edges"][(ctx["edges"].edge_type == "works_at") & (ctx["edges"].dst_id == fid) & ctx["edges"].src_id.isin(g)].src_id)
        out.append(make_ev(rule_id=None, severity="MEDIUM", source_table="network_edges", source_row_id=fid, claim_ids=[], provider_id=anchor, facility_id=fid, feature="providers_sharing_facility",
                           observed=float(n), expected=1.0, unit="providers", ts=AS_OF, evidence_type="NETWORK",
                           explanation=f"{n} providers in this case ({', '.join(provs)}) are linked to facility {fid}. Shared facilities are investigation leads, not proof of coordination.",
                           payload={"providers": provs, "case_id": cid}))
    for fl in nsev["top_referral_flows"][:3]:
        out.append(make_ev(rule_id=None, severity="MEDIUM", source_table="referrals", source_row_id=f"{fl['from']}>{fl['to']}", claim_ids=[], provider_id=fl["from"], feature="referrals_between_case_providers",
                           observed=float(fl["referrals"]), expected=None, unit="referrals", ts=AS_OF, evidence_type="NETWORK",
                           explanation=f"{fl['from']} referred {fl['referrals']} members to {fl['to']}; both providers are in this case. Referral flow is a lead, not proof.", payload={"case_id": cid}))
    if len(g) > 1:
        out.append(make_ev(rule_id=None, severity="MEDIUM" if nsev["link_density"] < 0.6 else "HIGH", source_table="network_edges", source_row_id=anchor, claim_ids=[], provider_id=anchor,
                           feature="case_link_density", observed=nsev["link_density"], expected=0.0, unit="density", ts=AS_OF, evidence_type="NETWORK",
                           explanation=f"{nsev['link_density']:.0%} of possible provider pairs in this {len(g)}-provider case are directly linked by referrals, associations or shared members.",
                           payload={"case_id": cid}))
    # temporal evidence
    for p in ([anchor] + [x for x in g if x != anchor])[:3]:
        if p not in tl:
            continue
        for e in tl[p]["events"]:
            out.append(make_ev(rule_id=None, severity=None, source_table="provider_timeline", source_row_id=f"{p}:{e['indicator']}", claim_ids=e["claim_ids"], provider_id=p,
                               feature=e["indicator"].lower(), observed=e["observed"], expected=e["baseline"], unit=e["unit"], ts=pd.Timestamp(e["date"]), evidence_type="TEMPORAL",
                               explanation=f"{p} on {e['date']}: {e['phase']} - {e['description']}.", payload={"case_id": cid, "indicator": e["indicator"]}))
    # forecast evidence
    kind = "probability" if label == "probability" else "escalation index"
    for h, v in zip((30, 60, 90), fvals):
        out.append(make_ev(rule_id=None, severity=None, source_table="provider_forecast", source_row_id=f"{top_p}:{h}", claim_ids=[], provider_id=top_p, feature=f"forecast_{h}d",
                           observed=v, expected=None, unit=kind, ts=AS_OF, evidence_type="FORECAST", model_version=ctx["forecast_version"],
                           explanation=f"{h}-day {kind} for {top_p}: {v:.2f}. " + ("Calibrated on a held-out chronological test period (synthetic data)." if label == "probability"
                                                                                  else "Calibration criteria were not met; treat as a relative index."),
                           payload={"case_id": cid, "label": label}))
    return out
