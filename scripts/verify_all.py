#!/usr/bin/env python3
"""End-to-end demo-path verification against a RUNNING API (default http://127.0.0.1:8000).
Walks the full flow: funnel -> queue -> CASE-1024 -> evidence -> network -> timeline -> 30/60/90 -> Second Brain -> brief -> copilot -> human review -> reviewer memory.
Exit code 0 only if every check passes. The review step is reverted at the end so the demo state stays clean."""
from __future__ import annotations

import os
import sys
import time

import httpx

BASE = os.getenv("API_URL", "http://127.0.0.1:8000")
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = ""):
    results.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=60)
    h = c.get("/api/health").json()
    check("API healthy + database", h["status"] == "ok" and h["database"], f"cases={h['cases']}")
    check("Second Brain reachable", h["second_brain"] and sum(h["second_brain"]["indices"].values()) > 0, f"backend={h['second_brain']['backend']}")

    cc = c.get("/api/command-center").json()
    f = {x["stage"]: x["count"] for x in cc["funnel"]}
    check("Command Center funnel computed", f["Claims"] > 50000 and f["Claims"] >= f["Anomalies"] >= f["Suspicious Claims"] >= f["Connected Cases"] >= f["High-Risk Cases"] >= f["SIU Priorities"] > 0, str(f))

    for cap in (5, 10, 20):
        q = c.get(f"/api/queue?capacity={cap}").json()
        check(f"SIU queue capacity {cap}", len(q["cases"]) == min(cap, q["total_cases_available"]) and q["cases"][0]["case_id"] == "CASE-1024", f"exposure={q['selected_exposure']:.0f}")

    d = c.get("/api/cases/CASE-1024").json()
    cs = d["case"]
    check("CASE-1024 anchored on PRV-102", cs["anchor_provider_id"] == "PRV-102", f"{cs['review_priority']} {cs['priority_score']:.2f}")
    need = {"R001_DUPLICATE", "R005_EXCESSIVE_UTILIZATION", "R007_REFERRAL_CONCENTRATION", "R008_NETWORK_EXPANSION"}
    check("Hero rule hits (duplicate, utilization, referral concentration, network expansion)", need <= set(cs["rule_hits"]))
    types = {r["evidence_type"] for r in d["evidence_summary"]}
    check("Evidence ledger spans rule/peer/model/anomaly/shap/network/temporal/forecast", {"RULE", "PEER", "MODEL", "ANOMALY", "SHAP", "NETWORK", "TEMPORAL", "FORECAST"} <= types)
    ev = c.get("/api/cases/CASE-1024/evidence?type=RULE&limit=5").json()["items"][0]
    check("Evidence object contract", all(ev.get(k) not in (None, "") for k in ("source_table", "source_row_id", "rule_id", "feature", "event_ts", "rule_version", "explanation")) and ev["observed_value"] is not None)
    check("Shared facility lead", bool(cs["network_signals"][0]["shared_facilities"]), str(cs["network_signals"][0]["shared_facilities"]))
    g = c.get("/api/cases/CASE-1024/network?hops=1").json()
    g2 = c.get("/api/cases/CASE-1024/network?hops=2").json()
    check("Network graph 1-hop / 2-hop", len(g["nodes"]) > 8 and len(g2["nodes"]) >= len(g["nodes"]), f"{len(g['nodes'])}/{len(g2['nodes'])} nodes")
    t = c.get("/api/cases/CASE-1024/timeline").json()
    check("Temporal escalation timeline", t["active_indicators"] >= 4 and len(t["events"]) >= 5, t["current_phase"])
    fc = d["forecast"]
    check("30/60/90 forecast monotone + labelled", fc["d30"] <= fc["d60"] <= fc["d90"] and fc["label"] in ("probability", "escalation index"), f"{fc['label']} {fc['d30']:.2f}/{fc['d60']:.2f}/{fc['d90']:.2f}")
    check("Historical similar investigation retrieved (INV-0087)", any(x["id"] == "INV-0087" for x in d["similar_cases"]))
    ctl = [c.get(f"/api/providers/{p}").json() for p in ("PRV-777", "PRV-778")]
    check("Legitimate high-utilization controls not in any case", all(x["cases"] == [] for x in ctl))

    s = c.post("/api/brain/search", json={"query": "CASE-1024", "index": "cases", "mode": "bm25"}).json()
    check("Second Brain BM25 exact ID", s["hits"][0]["id"] == "CASE-1024")
    s = c.post("/api/brain/search", json={"query": "referral concentration duplicate billing shared facility", "index": "cases", "mode": "hybrid", "filters": {"kind": "historical_investigation"}}).json()
    check("Second Brain hybrid + filter + RRF", s["hits"] and s["hits"][0]["retrieval"]["method"].startswith("RRF") and all(x["doc"]["kind"] == "historical_investigation" for x in s["hits"]), f"backend={s['backend']}")

    b = c.get("/api/cases/CASE-1024/brief").json()
    check("Investigation Brief: 12 sections, citations validated", len(b["sections"]) == 12 and b["validated"])
    a = c.post("/api/cases/CASE-1024/copilot", json={"question": "Why was this case prioritized?"}).json()
    check("Copilot grounded answer with citations", not a["insufficient"] and len(a["citations"]) > 0, a["mode"])
    a = c.post("/api/cases/CASE-1024/copilot", json={"question": "Who is the president of France?"}).json()
    check("Copilot refuses without evidence", a["insufficient"] and "Insufficient evidence" in a["answer"])

    # human review on the lowest-priority case, then revert
    low = c.get("/api/cases?limit=100").json()[-1]["case_id"]
    before = c.get(f"/api/cases/{low}").json()["case"]["review_status"]
    r = c.post(f"/api/cases/{low}/review", json={"decision": "MONITOR", "rationale": "verify_all demo decision marker-zorp", "reviewer": "verify_all"}).json()
    check("Human review recorded", r["case_status"] == "MONITORING")
    m = c.post("/api/brain/search", json={"query": "marker-zorp", "index": "review_memory", "mode": "bm25"}).json()
    check("Reviewer memory retrievable", bool(m["hits"]) and m["hits"][0]["doc"]["case_id"] == low)
    # revert so the demo database stays clean
    from sqlalchemy import text
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
    try:
        from app import db
        db.execute("DELETE FROM review_actions WHERE reviewer='verify_all'")
        db.execute("UPDATE cases SET review_status=:s WHERE case_id=:c", {"s": before, "c": low})
        c.post("/api/brain/reindex")
        check("Demo state reverted", c.get(f"/api/cases/{low}").json()["case"]["review_status"] == before)
    except Exception as e:  # noqa: BLE001
        check("Demo state reverted", False, f"manual cleanup needed: {e}")

    mod = c.get("/api/models").json()
    check("Model metrics come from executed runs", mod["xgboost"]["metrics"]["xgboost"]["pr_auc"] > mod["xgboost"]["metrics"]["rules_only_baseline"]["pr_auc"])
    bad = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} checks passed")
    return 1 if bad else 0


if __name__ == "__main__":
    t0 = time.time()
    try:
        rc = main()
    except httpx.ConnectError:
        print(f"API not reachable at {BASE}. Start it with `make api` (or docker compose up).")
        rc = 2
    sys.exit(rc)
