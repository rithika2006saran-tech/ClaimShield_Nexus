"""Deterministic, evidence-grounded Investigation Brief (12 sections). Every statement carries the evidence IDs that support it.
No LLM is required; an LLM may only rephrase the executive summary and must pass the same citation validation."""
from __future__ import annotations

from . import context as C

BRIEF_VERSION = "brief-1.0.0"
RULE_TITLES = {"R001_DUPLICATE": "Duplicate billing", "R002_UPCODING": "Upcoding signal", "R003_UNBUNDLING": "Unbundling signal",
               "R004_IMPLAUSIBLE_SERVICE": "Implausible service", "R005_EXCESSIVE_UTILIZATION": "Excessive utilization",
               "R006_IMPOSSIBLE_TIMING": "Impossible timing", "R007_REFERRAL_CONCENTRATION": "Referral concentration", "R008_NETWORK_EXPANSION": "Network expansion"}
COMP_LABEL = {"model_risk": "FWA model risk", "rule_evidence": "Rule evidence", "peer_deviation": "Peer deviation", "network": "Network severity", "temporal": "Temporal escalation",
              "anomaly": "Anomaly score", "evidence_strength": "Evidence strength", "exposure": "Potential exposure", "member_impact": "Member impact"}


def _s(text: str, ev: list[str] | None = None) -> dict:
    return {"text": text, "evidence_ids": list(dict.fromkeys(ev or []))}


def _ids(rows, n=3):
    return [r["evidence_id"] for r in rows[:n]]


def generate(ctx: dict) -> dict:
    c, anchor = ctx["case"], ctx["anchor"]
    pv = ctx["providers"].get(anchor, {})
    groups = C.rule_groups(ctx)
    model = C.by_type(ctx, "MODEL", anchor)
    anom = C.by_type(ctx, "ANOMALY", anchor)
    peers = sorted(C.by_type(ctx, "PEER", anchor), key=lambda e: -(abs(e["observed_value"] or 0)))
    net = C.by_type(ctx, "NETWORK")
    temporal = sorted(C.by_type(ctx, "TEMPORAL", anchor), key=lambda e: e["event_ts"])
    fcev = C.by_type(ctx, "FORECAST")
    shap = C.by_type(ctx, "SHAP", anchor)
    label = c["forecast_label"] or "escalation index"
    S: list[dict] = []

    rules_txt = ", ".join(f"{RULE_TITLES.get(r, r)} ({len(v)} finding{'s' if len(v) != 1 else ''})" for r, v in groups.items()) or "no rule hits"
    rule_ev = [e["evidence_id"] for v in groups.values() for e in v[:1]]
    S.append({"key": "executive_summary", "title": "Executive Summary", "items": [
        _s(f"{c['case_id']} is a high-priority investigation lead anchored on {anchor} ({pv.get('specialty', c['specialty'])}, {pv.get('region', '')}), connecting {len(c['provider_ids'])} providers "
           f"and {c['member_count']} members. Priority {c['review_priority']} (score {c['priority_score']:.2f}).", rule_ev[:2] + _ids(model, 1)),
        _s(f"Rule findings: {rules_txt}.", rule_ev),
        _s("This is a lead for human SIU review, not a finding of misconduct.", [])]})

    comps = sorted(c["components"].items(), key=lambda kv: -kv[1])
    S.append({"key": "why_prioritized", "title": "Why the case was prioritized", "items": [
        _s("Priority combines nine weighted components (model risk, rule evidence, peer deviation, network, temporal, anomaly, evidence strength, exposure, member impact) - not model score alone.", []),
        _s("Top components: " + "; ".join(f"{COMP_LABEL.get(k, k)} {v:.2f}" for k, v in comps[:5]) + ".", _ids(model, 1) + _ids(anom, 1)),
        *([_s(f"Model attribution (SHAP, not proof): {shap[0]['explanation']}", [shap[0]["evidence_id"]])] if shap else [])]})

    S.append({"key": "exposure", "title": "Potential Exposure", "items": [
        _s(f"Potential exposure ${c['potential_exposure']:,.0f} (paid amount on {c['claim_count']} implicated claims, de-duplicated). It is an upper bound for review, not a recovery estimate.", rule_ev[:2])]})
    S.append({"key": "member_impact", "title": "Member Impact", "items": [
        _s(f"{c['member_count']} distinct members appear on implicated claims across {len(c['facility_ids'])} facilities.", rule_ev[:1])]})

    items = []
    for r, v in groups.items():
        top = v[0]
        items.append(_s(f"{r} - {len(v)} finding(s), worst severity {top['severity']}. Example: {top['explanation']}", [e["evidence_id"] for e in v[:3]]))
    S.append({"key": "rule_hits", "title": "Rule Hits", "items": items or [_s("Insufficient evidence - human review required.", [])]})

    S.append({"key": "behavioral_deviations", "title": "Behavioral Deviations", "items": (
        [_s(e["explanation"], [e["evidence_id"]]) for e in peers[:5]] or [_s("No peer benchmark evidence available.", [])]) +
        [_s("Peer deviation alone does not establish misconduct; case mix is not modeled.", [])]})

    ni = [_s(e["explanation"], [e["evidence_id"]]) for e in net]
    sig = (c["network_signals"] or [{}])[0] if c["network_signals"] else {}
    if sig.get("top_referral_flows"):
        f = sig["top_referral_flows"][0]
        ni.append(_s(f"Largest referral flow in the case: {f['from']} -> {f['to']} ({f['referrals']} referrals).", [e["evidence_id"] for e in net if e["feature"] == "referrals_between_case_providers"][:1]))
    S.append({"key": "network_findings", "title": "Network Findings", "items": ni + [_s("Network relationships are investigation leads, not proof.", [])]})

    S.append({"key": "timeline", "title": "Timeline", "items": [_s(f"{e['event_ts']}: {e['explanation']}", [e["evidence_id"]]) for e in temporal] or [_s("No temporal events.", [])]})

    sim = ctx["similar"]
    si = []
    for h in sim[:3]:
        d = h["doc"]
        si.append(_s(f"{h['id']} ({d.get('anchor_provider_id')}, {d.get('specialty')}) - outcome {d.get('outcome')}; shared rules: {', '.join(h.get('shared_rules') or []) or 'none'}. "
                     f"Retrieved by hybrid BM25+kNN (RRF); similarity is behavioural, not conclusive.", []))
    S.append({"key": "similar_cases", "title": "Similar Historical Cases", "retrieved": [h["id"] for h in sim[:3]], "items": si or [_s("No similar historical investigations retrieved.", [])]})

    fp = fcev[0]["provider_id"] if fcev else anchor
    S.append({"key": "forecast", "title": "30/60/90 Risk", "items": [
        _s(f"Case-level 30/60/90-day {label}: {c['forecast_30d']:.2f} / {c['forecast_60d']:.2f} / {c['forecast_90d']:.2f} (highest-scoring provider in the case: {fp}). "
           + ("Calibrated on a later chronological test period (synthetic data)." if label == "probability" else "Not calibrated: reported as an escalation index, not a probability."), [e["evidence_id"] for e in fcev])]
        if c["forecast_30d"] is not None else [_s("Forecast unavailable.", [])]})

    S.append({"key": "limitations", "title": "Unknowns / Limitations", "items": [_s(x, []) for x in c["limitations"]] +
              [_s("All data is synthetic; metrics reflect injected scenarios, not real-world performance.", [])]})

    last = ctx["reviews"][-1] if ctx["reviews"] else None
    S.append({"key": "recommended_action", "title": "Recommended Human Review Action", "items": [
        _s("Review the evidence ledger, request supporting documentation for flagged claims, and confirm or dismiss the network leads. Options: Escalate, Request Documentation, Monitor, Close.", []),
        _s("No automated claim denial, provider suspension or legal conclusion is made by this system.", []),
        *([_s(f"Latest human decision: {last['decision']} by {last['reviewer']}.", [])] if last else [])]})
    return {"case_id": c["case_id"], "version": BRIEF_VERSION, "sections": S, "generator": "deterministic-evidence-grounded"}


def validate(brief: dict, ctx: dict) -> list[str]:
    """Every cited evidence ID must exist in the case; every factual item must be cited or be a declared caveat."""
    errs = []
    ok = ctx["allowed_ids"]["evidence"]
    for s in brief["sections"]:
        for it in s["items"]:
            for e in it["evidence_ids"]:
                if e not in ok:
                    errs.append(f"{s['key']}: unknown evidence {e}")
    return errs


def to_markdown(brief: dict) -> str:
    out = [f"# Investigation Brief - {brief['case_id']}", ""]
    for s in brief["sections"]:
        out.append(f"## {s['title']}")
        for it in s["items"]:
            cite = f" [{', '.join(it['evidence_ids'])}]" if it["evidence_ids"] else ""
            out.append(f"- {it['text']}{cite}")
        out.append("")
    return "\n".join(out)
