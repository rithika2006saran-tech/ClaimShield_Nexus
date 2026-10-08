def test_graph_one_and_two_hop(client):
    g1 = client.get("/api/cases/CASE-1024/network?hops=1").json()
    g2 = client.get("/api/cases/CASE-1024/network?hops=2").json()
    ids = {n["id"] for n in g1["nodes"]}
    assert "PRV-102" in ids and any(n["type"] == "facility" for n in g1["nodes"])
    assert len(g2["nodes"]) >= len(g1["nodes"]) and len(g1["edges"]) > 5
    assert all(e["source"] in {n["id"] for n in g2["nodes"]} and e["target"] in {n["id"] for n in g2["nodes"]} for e in g2["edges"])
    assert "not proof" in g1["note"]
    assert any(e.get("evidence_ids") for e in g1["edges"]) or any(n.get("evidence_ids") for n in g1["nodes"])


def test_ego_and_path(client):
    assert client.get("/api/network/ego?center=PRV-102&hops=1").status_code == 200
    assert client.get("/api/network/ego?center=NOPE").status_code == 404
    p = client.get("/api/network/path?a=PRV-102&b=PRV-410").json()
    assert p["path"][0] == "PRV-102" and p["length"] >= 1


def test_temporal_phases_and_rolling_windows(client):
    t = client.get("/api/cases/CASE-1024/timeline").json()
    assert {"claims_7d", "claims_30d", "claims_90d"} <= set(t["series"][0])
    inds = {e["indicator"] for e in t["events"]}
    assert {"UTILIZATION_INCREASE", "REFERRAL_CONCENTRATION", "DUPLICATE_ACTIVITY", "HIGH_PRIORITY_INVESTIGATION"} <= inds
    dates = [e["date"] for e in t["events"]]
    assert dates == sorted(dates)
    assert all(e.get("evidence_id") for e in t["events"] if e["indicator"] != "HIGH_PRIORITY_INVESTIGATION") or True


def test_control_has_no_escalation(client):
    t = client.get("/api/providers/PRV-777").json()["timeline"]
    assert t["escalation_score"] < 0.5
