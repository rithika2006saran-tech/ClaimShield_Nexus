"""Investigation Copilot. Intent-routed, evidence-grounded answers built from the case context; optional LLM rewrite with strict citation validation.
Falls back to 'Insufficient evidence - human review required.' whenever the context cannot support an answer."""
from __future__ import annotations

import re

from ..brain import service as brain
from . import brief as B
from . import context as C
from .llm import get_llm

STOP = set("a an the of is are was were be to in on for and or what who why how which that this these those it its with by at as from do does did can could should would me us about tell show give".split())
INSUFFICIENT = "Insufficient evidence - human review required."
CITE = re.compile(r"\b(EV-\d{6})\b")
ID_RE = re.compile(r"\b(CLM-\d{6}|EV-\d{6}|CASE-\d+|INV-\d+|PRV-\d+|FAC-\d+)\b")

INTENTS = [
    ("missing", ["missing", "unknown", "limitation", "gap", "not know", "lack"]),
    ("forecast", ["30", "60", "90", "forecast", "future"]),
    ("evidence", ["evidence", "support", "ledger", "proof", "rule"]),
    ("why", ["why", "prioriti", "rank", "score"]),
    ("claims", ["claim"]),
    ("changed", ["change", "over time", "timeline", "escalat", "when", "evolv", "phase"]),
    ("connected", ["connect", "network", "facilit", "referral", "relationship", "linked"]),
    ("similar", ["similar", "histor", "previous", "past", "precedent", "memory"]),
    ("next", ["next", "should", "review", "recommend", "action", "do"]),
]


def _intent(q: str) -> str:
    ql = q.lower()
    for name, kws in INTENTS:
        if any(k in ql for k in kws):
            return name
    return "search"


def _line(text: str, ev: list[str]) -> str:
    return text + (" " + " ".join(f"[{e}]" for e in ev) if ev else "")


def _answer(ctx: dict, q: str, intent: str) -> tuple[list[str], list[str]]:
    c, a = ctx["case"], ctx["anchor"]
    groups = C.rule_groups(ctx)
    lines: list[str] = []
    cites: list[str] = []

    def add(t, ev=()):
        lines.append(_line(t, list(ev)))
        cites.extend(ev)

    if intent == "why":
        top = sorted(c["components"].items(), key=lambda kv: -kv[1])[:5]
        add(f"{c['case_id']} is ranked {c['review_priority']} (priority score {c['priority_score']:.2f}) because of: " + "; ".join(f"{B.COMP_LABEL[k]} {v:.2f}" for k, v in top) + ".",
            [e["evidence_id"] for e in C.by_type(ctx, "MODEL", a)[:1]])
        for r, v in list(groups.items())[:4]:
            add(f"{B.RULE_TITLES.get(r, r)}: {len(v)} finding(s), worst severity {v[0]['severity']}.", [v[0]["evidence_id"]])
    elif intent == "evidence":
        for r, v in groups.items():
            add(f"{r}: {v[0]['explanation']}", [e["evidence_id"] for e in v[:2]])
        if not groups:
            return [INSUFFICIENT], []
    elif intent == "claims":
        for r, v in list(groups.items())[:5]:
            cl = [x for e in v[:3] for x in e["claim_ids"]][:6]
            if cl:
                add(f"{r} claims: {', '.join(dict.fromkeys(cl))}.", [e["evidence_id"] for e in v[:3]])
        add(f"{c['claim_count']} claims are implicated in total (see the claims table in the workspace).", [])
    elif intent == "changed":
        tl = sorted(C.by_type(ctx, "TEMPORAL", a), key=lambda e: e["event_ts"])
        if not tl:
            return [INSUFFICIENT], []
        for e in tl:
            add(f"{e['event_ts']}: {e['explanation']}", [e["evidence_id"]])
        if ctx["timeline"]:
            add(f"Current phase: {ctx['timeline']['current_phase']} (escalation score {ctx['timeline']['escalation_score']}).", [])
    elif intent == "connected":
        net = C.by_type(ctx, "NETWORK")
        for e in net:
            add(e["explanation"], [e["evidence_id"]])
        add("Providers in case: " + ", ".join(c["provider_ids"]) + ". Network relationships are investigation leads, not proof.", [])
        if not net:
            return [INSUFFICIENT], []
    elif intent == "similar":
        if not ctx["similar"]:
            return [INSUFFICIENT], []
        for h in ctx["similar"][:3]:
            d = h["doc"]
            add(f"{h['id']} ({d.get('anchor_provider_id')}, {d.get('specialty')}): outcome {d.get('outcome')}; shared rules {', '.join(h.get('shared_rules') or []) or 'none'}. Similarity is behavioural and not conclusive.", [])
    elif intent == "missing":
        for x in c["limitations"]:
            add(x, [])
        add("Not available: clinical documentation, ownership data, claim adjudication history.", [])
    elif intent == "next":
        add("Suggested human review steps: (1) review the top-severity rule findings and their claims; (2) request supporting documentation for flagged claims; "
            "(3) examine the shared-facility and referral leads; (4) decide Escalate / Request Documentation / Monitor / Close. The system makes no automated decision.",
            [v[0]["evidence_id"] for v in list(groups.values())[:2]])
    elif intent == "forecast":
        fe = C.by_type(ctx, "FORECAST")
        if not fe:
            return [INSUFFICIENT], []
        lab = c["forecast_label"]
        add(f"30/60/90-day {lab}: {c['forecast_30d']:.2f} / {c['forecast_60d']:.2f} / {c['forecast_90d']:.2f}. "
            + ("Calibrated on a later chronological test period (synthetic data)." if lab == "probability" else "Not calibrated; interpret as an escalation index."), [e["evidence_id"] for e in fe])
    else:
        # free-text: hybrid retrieval over this case's evidence only
        q2 = " ".join(w for w in re.findall(r"[A-Za-z0-9_\-]+", q) if w.lower() not in STOP)
        if not q2:
            return [INSUFFICIENT], []
        res = brain.search(q2, "evidence", {"case_id": c["case_id"]}, 5)
        # require a lexical match: a semantic-only neighbour is not enough to ground an answer
        hits = [h for h in res["hits"] if h["id"] in ctx["allowed_ids"]["evidence"] and h["bm25_rank"] is not None]
        if not hits:
            return [INSUFFICIENT], []
        for h in hits[:4]:
            add(h["doc"]["text"][:260], [h["id"]])
    return lines, cites


def _validate(answer: str, ctx: dict) -> list[str]:
    al = ctx["allowed_ids"]
    allowed = al["evidence"] | al["claims"] | al["providers"] | al["facilities"] | al["cases"]
    return [i for i in ID_RE.findall(answer) if i not in allowed]


def ask(case_id: str, question: str, use_llm: bool = True) -> dict:
    ctx = C.build_context(case_id)
    if not ctx:
        return {"case_id": case_id, "answer": INSUFFICIENT, "citations": [], "mode": "deterministic", "error": "unknown case"}
    intent = _intent(question)
    lines, cites = _answer(ctx, question, intent)
    grounded = "\n".join(f"- {l}" for l in lines)
    mode, note = "deterministic-evidence-grounded", None
    answer = grounded
    llm = get_llm()
    if use_llm and llm.name != "none" and lines != [INSUFFICIENT]:
        try:
            out = llm.rewrite(question, grounded)
            bad = _validate(out or "", ctx)
            if out and not bad:
                answer, mode = out, f"llm:{llm.name}+validated"
            else:
                note = f"LLM output rejected (unknown IDs: {bad[:3]}); deterministic answer used"
        except Exception as e:  # noqa: BLE001
            note = f"LLM unavailable ({type(e).__name__}); deterministic answer used"
    cites = list(dict.fromkeys(cites))
    ev_by_id = {e["evidence_id"]: e for e in ctx["evidence"]}
    return {"case_id": case_id, "question": question, "intent": intent, "answer": answer, "mode": mode, "note": note,
            "citations": [{"evidence_id": i, "rule_id": ev_by_id[i]["rule_id"], "evidence_type": ev_by_id[i]["evidence_type"], "provider_id": ev_by_id[i]["provider_id"],
                           "claim_ids": ev_by_id[i]["claim_ids"][:5], "explanation": ev_by_id[i]["explanation"]} for i in cites if i in ev_by_id],
            "insufficient": lines == [INSUFFICIENT], "disclaimer": "Investigation lead for human review; not a finding of misconduct."}
