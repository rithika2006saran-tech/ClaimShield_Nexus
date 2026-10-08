def test_hero_case(client):
    r = client.get("/api/cases/CASE-1024")
    assert r.status_code == 200
    d = r.json()
    c = d["case"]
    assert c["anchor_provider_id"] == "PRV-102" and "PRV-102" in c["provider_ids"]
    for rule in ("R001_DUPLICATE", "R005_EXCESSIVE_UTILIZATION", "R007_REFERRAL_CONCENTRATION", "R008_NETWORK_EXPANSION"):
        assert rule in c["rule_hits"]
    assert c["review_priority"] in ("CRITICAL", "HIGH")
    types = {r["evidence_type"] for r in d["evidence_summary"]}
    assert {"RULE", "PEER", "MODEL", "ANOMALY", "SHAP", "NETWORK", "TEMPORAL", "FORECAST"} <= types
    assert d["timeline"]["active_indicators"] >= 4 and len(d["timeline"]["events"]) >= 5
    assert d["forecast"]["d30"] <= d["forecast"]["d60"] <= d["forecast"]["d90"]
    assert d["forecast"]["label"] in ("probability", "escalation index")
    assert any(h["id"] == "INV-0087" for h in d["similar_cases"]), "historical similar investigation must be retrieved"
    assert sum(d["weights"].values()) > 0.99
    assert "facility" in " ".join(c["network_signals"][0]["shared_facilities"].keys()).lower() or c["network_signals"][0]["shared_facilities"]


def test_control_provider_not_flagged(client):
    for pid in ("PRV-777", "PRV-778"):
        d = client.get(f"/api/providers/{pid}").json()
        assert d["cases"] == [], f"{pid} (legitimate high-utilization control) must not be in a case"
        ratio = {m["metric"]: m for m in d["peer_benchmarks"]}["claims_per_month_90d"]["ratio"]
        assert ratio is not None
        assert not d["rule_findings"] or all(r["rule_id"] != "R001_DUPLICATE" for r in d["rule_findings"])


def test_provider_profile_has_peer_benchmarks(client):
    d = client.get("/api/providers/PRV-102").json()
    assert len(d["peer_benchmarks"]) >= 8 and "peer deviation" in d["disclaimer"].lower()
    assert d["scores"]["fwa_risk_score"] is not None and d["scores"]["anomaly_score"] is not None
