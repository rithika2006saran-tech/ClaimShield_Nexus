import pytest
from app import db


@pytest.mark.parametrize("cap", [5, 10, 20])
def test_queue_capacity(client, cap):
    d = client.get(f"/api/queue?capacity={cap}").json()
    assert len(d["cases"]) == min(cap, d["total_cases_available"])
    scores = [c["priority_score"] for c in d["cases"]]
    assert scores == sorted(scores, reverse=True)
    assert d["cases"][0]["case_id"] == "CASE-1024"
    assert [c["rank"] for c in d["cases"]] == list(range(1, len(scores) + 1))


def test_queue_smaller_capacity_is_prefix_of_larger(client):
    a = [c["case_id"] for c in client.get("/api/queue?capacity=5").json()["cases"]]
    b = [c["case_id"] for c in client.get("/api/queue?capacity=10").json()["cases"]]
    assert b[:5] == a


def test_priority_is_not_model_score_alone(client):
    d = client.get("/api/queue?capacity=20").json()
    by_model = sorted(d["cases"], key=lambda c: -c["model_score"])
    assert [c["case_id"] for c in by_model] != [c["case_id"] for c in d["cases"]]


def test_funnel_is_computed_and_consistent(client):
    d = client.get("/api/command-center").json()
    f = {x["stage"]: x["count"] for x in d["funnel"]}
    assert f["Claims"] == db.query_one("SELECT count(*) n FROM claims")["n"]
    assert f["Connected Cases"] == db.query_one("SELECT count(*) n FROM cases")["n"]
    assert f["High-Risk Cases"] == db.query_one("SELECT count(*) n FROM cases WHERE review_priority IN ('HIGH','CRITICAL')")["n"]
    assert f["Claims"] >= f["Anomalies"] >= f["Suspicious Claims"] >= f["Connected Cases"] >= f["High-Risk Cases"] >= f["SIU Priorities"]
    assert d["synthetic"] is True
