"""Thin xAI (Grok) client — optional LLM backend for planning rationale,
VQA-fallback answer composition, and GIS code generation.

Design goal: every call site in this project already has a deterministic,
demo-safe fallback (PRD §7.2/§7.5 "graceful degradation"). This client is a
pure enhancement layer:

- `is_available()` is False whenever `XAI_API_KEY` is unset — every caller
  MUST check this (or just call `complete()` and handle `None`) and fall
  back to its existing deterministic logic. Nothing in the orchestration
  path may hard-depend on this module.
- Network/API failures never raise past this module: `complete()` catches
  everything and returns `None` so a flaky LLM call can't take down a job.
- No calls happen inside the code-execution sandbox — this module is used
  by agents to *generate* candidate text/code before the existing AST
  validator (`sandbox/validator.py`) and sandbox runner ever see it.
"""
from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger("satquery.llm_client")

XAI_BASE_URL = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1")
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4-fast")
_TIMEOUT_S = 20.0


def is_available() -> bool:
    return bool(os.environ.get("XAI_API_KEY"))


def complete(system: str, user: str, *, temperature: float = 0.0,
             max_tokens: int = 800) -> str | None:
    """One-shot chat completion. Returns the text, or None on any failure
    (missing key, network error, non-2xx, malformed response)."""
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        return None
    try:
        resp = httpx.post(
            f"{XAI_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={
                "model": XAI_MODEL,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=_TIMEOUT_S,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:  # noqa: BLE001 — must never propagate
        log.warning("xAI completion failed, falling back to deterministic path: %s", exc)
        return None
