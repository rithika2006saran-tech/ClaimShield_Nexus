import pytest
from app import db
from app.brain import indexer, service

CASE = "CASE-1033"


@pytest.fixture
def clean_case():
    c = db.query_one("SELECT case_id FROM cases ORDER BY priority_score ASC LIMIT 1")["case_id"]
    st = db.query_one("SELECT review_status FROM cases WHERE case_id=:c", {"c": c})["review_status"]
    yield c
    db.execute("DELETE FROM review_actions WHERE case_id=:c", {"c": c})
    db.execute("UPDATE cases SET review_status=:s WHERE case_id=:c", {"s": st, "c": c})
    indexer.index_all()


@pytest.mark.parametrize("decision,status", [("ESCALATE", "ESCALATED"), ("REQUEST_DOCUMENTATION", "DOCUMENTATION_REQUESTED"), ("MONITOR", "MONITORING"), ("CLOSE", "CLOSED")])
def test_human_decision_persists_and_becomes_memory(client, clean_case, decision, status):
    r = client.post(f"/api/cases/{clean_case}/review", json={"decision": decision, "rationale": "Unique-rationale-xyzzy documentation looks inconsistent", "reviewer": "tester"})
    assert r.status_code == 200 and r.json()["case_status"] == status
    assert db.query_one("SELECT review_status FROM cases WHERE case_id=:c", {"c": clean_case})["review_status"] == status
    assert db.query_one("SELECT count(*) n FROM review_actions WHERE case_id=:c", {"c": clean_case})["n"] >= 1
    hits = service.search("xyzzy", "review_memory", None, 5, mode="bm25")["hits"]
    assert hits and hits[0]["doc"]["case_id"] == clean_case and hits[0]["doc"]["decision"] == decision
    assert any(x["decision"] == decision for x in client.get(f"/api/cases/{clean_case}").json()["reviews"])


def test_reviewer_memory_survives_reindex(client, clean_case):
    client.post(f"/api/cases/{clean_case}/review", json={"decision": "MONITOR", "rationale": "persist-check-plugh", "reviewer": "tester"})
    indexer.index_all()
    assert service.search("plugh", "review_memory", None, 3, mode="bm25")["hits"]


def test_closed_cases_leave_default_queue(client, clean_case):
    client.post(f"/api/cases/{clean_case}/review", json={"decision": "CLOSE", "rationale": "no issue after documentation", "reviewer": "tester"})
    ids = [c["case_id"] for c in client.get("/api/queue?capacity=50").json()["cases"]]
    assert clean_case not in ids
    assert clean_case in [c["case_id"] for c in client.get("/api/queue?capacity=50&include_reviewed=true").json()["cases"]]


def test_invalid_decisions_rejected(client):
    assert client.post("/api/cases/CASE-1024/review", json={"decision": "DENY_CLAIMS", "rationale": "x" * 10}).status_code == 422
    assert client.post("/api/cases/CASE-1024/review", json={"decision": "ESCALATE", "rationale": ""}).status_code == 422
    assert client.post("/api/cases/CASE-9999/review", json={"decision": "ESCALATE", "rationale": "abc def"}).status_code == 404


def test_no_automated_decision_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert not any(w in p.lower() for p in paths for w in ("deny", "suspend", "terminate"))
