"""Local embedding for the Second Brain vector/kNN retrieval.

No external model download is required (works offline / behind restricted egress). Vectors are the concatenation of
  * a hashed bag of word uni/bi-grams (lexical-semantic signal), and
  * a structured FWA-signature block (rule patterns, structural flags, specialty, scale).
Both blocks are L2-normalised and weighted, then the whole vector is L2-normalised so cosine similarity applies.
If the optional `sentence-transformers` package and EMBEDDING_MODEL env var are present they can replace the text block;
the structured block is always used so 'similar behavioural pattern' retrieval stays meaningful.
"""
from __future__ import annotations

import hashlib
import math
import re

import numpy as np

DIM_TEXT, DIM_STRUCT = 96, 32
DIM = DIM_TEXT + DIM_STRUCT
VECTOR_MODE = "hashed-lexical+structured (local, no external model)"

RULE_IDS = ["R001_DUPLICATE", "R002_UPCODING", "R003_UNBUNDLING", "R004_IMPLAUSIBLE_SERVICE", "R005_EXCESSIVE_UTILIZATION", "R006_IMPOSSIBLE_TIMING",
            "R007_REFERRAL_CONCENTRATION", "R008_NETWORK_EXPANSION"]
PATTERN_KEYWORDS = {
    "R001_DUPLICATE": ["duplicate", "duplicated", "resubmission", "repeated same-day", "same-day billing"],
    "R002_UPCODING": ["upcoding", "high-complexity", "complexity visit"],
    "R003_UNBUNDLING": ["unbundling", "unbundled", "bundled", "components billed separately", "panel components"],
    "R004_IMPLAUSIBLE_SERVICE": ["implausible", "phantom", "after death", "inconsistent with member"],
    "R005_EXCESSIVE_UTILIZATION": ["excessive", "utilization", "claim volume", "above comparable peers", "high volume"],
    "R006_IMPOSSIBLE_TIMING": ["impossible timing", "could not be delivered", "16 h", "time available"],
    "R007_REFERRAL_CONCENTRATION": ["referral concentration", "referrals concentrated", "concentrated on a single", "referral source", "single partner"],
    "R008_NETWORK_EXPANSION": ["network expansion", "network growth", "rapid growth in connected", "connected providers"],
}
FLAG_KEYWORDS = {"shared_facility": ["shared facility", "same facility", "shared the same", "sharing facility"],
                 "coordinated": ["coordinated", "ring", "network of providers", "exchanged referrals", "connected case"],
                 "temporal": ["temporal escalation", "escalat", "behavioural phases", "over time"]}
OUTCOME_KEYWORDS = {"confirmed": ["confirmed", "overpayment", "recovery"], "no_issue": ["no issue", "closed without findings", "not substantiated"],
                    "documentation": ["documentation requested", "medical-record"], "monitored": ["monitoring", "monitored"]}
SPECIALTIES = ["Family Medicine", "Internal Medicine", "Cardiology", "Orthopedics", "Dermatology", "Radiology", "Laboratory", "Physical Therapy", "Oncology",
               "Behavioral Health", "Pain Management", "Obstetrics/Gynecology"]
_TOKEN = re.compile(r"[a-z0-9]+")


def _h(tok: str) -> int:
    return int.from_bytes(hashlib.md5(tok.encode()).digest()[:8], "little")


def _text_vec(text: str) -> np.ndarray:
    toks = _TOKEN.findall(text.lower())
    grams = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
    v = np.zeros(DIM_TEXT)
    counts: dict[str, int] = {}
    for g in grams:
        counts[g] = counts.get(g, 0) + 1
    for g, c in counts.items():
        h = _h(g)
        v[h % DIM_TEXT] += (1 if (h >> 32) & 1 else -1) * (1 + math.log(c))
    n = np.linalg.norm(v)
    return v / n if n else v


def _detect(text: str, table: dict[str, list[str]]) -> set[str]:
    t = text.lower()
    return {k for k, kws in table.items() if any(kw in t for kw in kws)}


def _struct_vec(rule_ids: set[str], flags: set[str], specialty: str | None, outcome: set[str], log_exposure: float | None, n_providers: int | None) -> np.ndarray:
    v = np.zeros(DIM_STRUCT)
    for i, r in enumerate(RULE_IDS):
        v[i] = 1.0 if r in rule_ids else 0.0
    for i, f in enumerate(["shared_facility", "coordinated", "temporal"]):
        v[8 + i] = 1.0 if f in flags else 0.0
    if specialty in SPECIALTIES:
        v[11 + SPECIALTIES.index(specialty) % 12] = 0.6
    for i, o in enumerate(["confirmed", "no_issue", "documentation", "monitored"]):
        v[23 + i] = 0.5 if o in outcome else 0.0
    if log_exposure is not None:
        v[27] = min(1.0, log_exposure / 6.0)
    if n_providers is not None:
        v[28] = min(1.0, (n_providers - 1) / 6.0)
    n = np.linalg.norm(v)
    return v / n if n else v


def embed_doc(text: str, rule_ids: list[str] | None = None, specialty: str | None = None, exposure: float | None = None, n_providers: int | None = None,
              outcome_text: str | None = None) -> list[float]:
    rules = set(rule_ids or []) | _detect(text, PATTERN_KEYWORDS)
    flags = _detect(text, FLAG_KEYWORDS)
    outcome = _detect((outcome_text or "") + " " + text, OUTCOME_KEYWORDS) if outcome_text is not None else set()
    vec = np.concatenate([0.55 * _text_vec(text), 0.85 * _struct_vec(rules, flags, specialty, outcome, math.log10(1 + exposure) if exposure else None, n_providers)])
    n = np.linalg.norm(vec)
    return (vec / n if n else vec).round(5).tolist()


def embed_query(text: str) -> list[float]:
    """Queries are embedded the same way; pattern keywords in the query populate the structured block."""
    return embed_doc(text)
