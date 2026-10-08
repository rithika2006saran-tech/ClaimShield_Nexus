import re

import pytest
from app.ai import brief as B, context as C, copilot as P
from app.ai import llm as L

BANNED = re.compile(r"committed fraud|is fraudulent|guilty|proved fraud|will be denied|suspend(ed)? the provider", re.I)


def test_brief_has_12_sections_and_valid_citations(client):
    b = client.get("/api/cases/CASE-1024/brief").json()
    assert len(b["sections"]) == 12 and b["validated"]
    keys = [s["key"] for s in b["sections"]]
    assert keys[0] == "executive_summary" and "forecast" in keys and "limitations" in keys and "recommended_action" in keys
    ctx = C.build_context("CASE-1024")
    assert B.validate(b, ctx) == []
    cited = {e for s in b["sections"] for it in s["items"] for e in it["evidence_ids"]}
    assert len(cited) >= 15 and cited <= ctx["allowed_ids"]["evidence"]
    assert not BANNED.search(str(b))


def test_brief_markdown(client):
    r = client.get("/api/cases/CASE-1024/brief?format=markdown").json()
    assert r["markdown"].startswith("# Investigation Brief - CASE-1024") and "EV-" in r["markdown"]


QUESTIONS = ["Why was this case prioritized?", "What evidence supports the investigation lead?", "Which claims are relevant?", "What changed over time?",
             "Which providers and facilities are connected?", "Are there similar historical cases?", "What evidence is missing?", "What should the investigator review next?"]


@pytest.mark.parametrize("q", QUESTIONS)
def test_copilot_answers_are_grounded(client, q):
    r = client.post("/api/cases/CASE-1024/copilot", json={"question": q}).json()
    assert not r["insufficient"] and r["mode"] == "deterministic-evidence-grounded"
    ctx = C.build_context("CASE-1024")
    assert P._validate(r["answer"], ctx) == [], "answer contains IDs outside the case context"
    assert {c["evidence_id"] for c in r["citations"]} <= ctx["allowed_ids"]["evidence"]
    assert not BANNED.search(r["answer"])


def test_copilot_refuses_without_evidence(client):
    r = client.post("/api/cases/CASE-1024/copilot", json={"question": "Who won the football world cup?"}).json()
    assert r["insufficient"] and "Insufficient evidence - human review required." in r["answer"]


def test_copilot_unknown_case(client):
    assert client.post("/api/cases/CASE-9999/copilot", json={"question": "why?"}).status_code == 404


def test_llm_output_with_invented_ids_is_rejected(monkeypatch):
    class Evil(L.LLM):
        name = "evil"
        def rewrite(self, q, g):
            return g + "\nAlso CLM-999999 and EV-999999 and CASE-4242 confirm it."
    monkeypatch.setattr(P, "get_llm", lambda: Evil())
    r = P.ask("CASE-1024", "Why was this case prioritized?")
    assert r["mode"] == "deterministic-evidence-grounded" and "rejected" in (r["note"] or "")
    assert "CLM-999999" not in r["answer"]


def test_llm_valid_output_accepted(monkeypatch):
    class Good(L.LLM):
        name = "good"
        def rewrite(self, q, g):
            return "Summary: " + g
    monkeypatch.setattr(P, "get_llm", lambda: Good())
    r = P.ask("CASE-1024", "Why was this case prioritized?")
    assert r["mode"] == "llm:good+validated"


def test_no_api_key_means_deterministic():
    assert L.get_llm().name == "none"
