"""LLM provider abstraction. The LLM never detects fraud: it only rephrases an already evidence-grounded answer.
Providers: none (default; deterministic), anthropic, openai. Any failure -> deterministic fallback."""
from __future__ import annotations

import httpx

from .. import config
from . import guardrails

SYSTEM = ("You are the ClaimShield Nexus Investigation Copilot. Rewrite the GROUNDED ANSWER for an SIU investigator using ONLY the facts and IDs it contains. "
          "Never add claim IDs, evidence IDs, case IDs, numbers or facts. Never state that a provider committed fraud; use 'investigation lead' wording. Keep every [EV-...] citation.")


class LLM:
    name = "none"

    def available(self) -> bool:
        return False

    def rewrite(self, question: str, grounded: str) -> str | None:
        return None


class Anthropic(LLM):
    name = "anthropic"

    def available(self):
        return bool(config.ANTHROPIC_API_KEY)

    def rewrite(self, question, grounded):
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=30, headers={"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
                       json={"model": config.ANTHROPIC_MODEL, "max_tokens": 700, "system": SYSTEM, "messages": [{"role": "user", "content": f"Question: {question}\n\nGROUNDED ANSWER:\n{grounded}"}]})
        r.raise_for_status()
        return r.json()["content"][0]["text"]


class OpenAI(LLM):
    name = "openai"

    def available(self):
        return bool(config.OPENAI_API_KEY)

    def rewrite(self, question, grounded):
        r = httpx.post("https://api.openai.com/v1/chat/completions", timeout=30, headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                       json={"model": config.OPENAI_MODEL, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Question: {question}\n\nGROUNDED ANSWER:\n{grounded}"}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

class Gemini(LLM):
    def available(self):
        return bool(config.GEMINI_API_KEY)

    def rewrite(self, question, grounded):
        r = httpx.post("https://generativelanguage.googleapis.com/v1beta/models/" + config.GEMINI_MODEL + ":generateContent?key=" + config.GEMINI_API_KEY,
                       timeout=30,
                       json={"contents": [{"parts": [{"text": f"System: {SYSTEM}\n\nQuestion: {question}\n\nGROUNDED ANSWER:\n{grounded}"}]}]})
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]


class GuardrailedLLM(LLM):
    def __init__(self, base: LLM):
        self.base = base
        self.name = base.name

    def available(self):
        return self.base.available()

    def rewrite(self, question, grounded):
        out = self.base.rewrite(question, grounded)
        if out:
            return guardrails.protect_privacy(out)
        return out

def get_llm() -> LLM:
    p = (config.LLM_PROVIDER or "none").lower()
    llm = {"anthropic": Anthropic, "openai": OpenAI, "gemini": Gemini}.get(p, LLM)()
    return GuardrailedLLM(llm) if llm.available() else LLM()
