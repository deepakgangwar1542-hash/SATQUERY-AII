"""Thin LLM client — optional backend for planning rationale, VQA-fallback
answer composition, and GIS code generation.

Supports two OpenAI-compatible providers, checked in this priority order:

1. Groq (`GROQ_API_KEY`) — preferred when set.
2. xAI / Grok (`XAI_API_KEY`) — used if Groq is not configured.

Design goal: every call site in this project already has a deterministic,
demo-safe fallback (PRD §7.2/§7.5 "graceful degradation"). This client is a
pure enhancement layer:

- `is_available()` is False whenever neither key is set — every caller
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
from dataclasses import dataclass

import httpx

log = logging.getLogger("satquery.llm_client")

GROQ_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

XAI_BASE_URL = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1")
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4-fast")

_TIMEOUT_S = 20.0


@dataclass(frozen=True)
class _Provider:
    name: str
    api_key: str
    base_url: str
    model: str


def _active_provider() -> _Provider | None:
    """Groq first, then xAI. Returns None if neither key is configured."""
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        return _Provider("groq", groq_key, GROQ_BASE_URL, GROQ_MODEL)
    xai_key = os.environ.get("XAI_API_KEY")
    if xai_key:
        return _Provider("xai", xai_key, XAI_BASE_URL, XAI_MODEL)
    return None


def is_available() -> bool:
    return _active_provider() is not None


def complete(system: str, user: str, *, temperature: float = 0.0,
             max_tokens: int = 800) -> str | None:
    """One-shot chat completion. Returns the text, or None on any failure
    (missing key, network error, non-2xx, malformed response)."""
    provider = _active_provider()
    if provider is None:
        return None
    try:
        resp = httpx.post(
            f"{provider.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {provider.api_key}",
                     "Content-Type": "application/json"},
            json={
                "model": provider.model,
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
        log.warning("%s completion failed, falling back to deterministic path: %s",
                     provider.name, exc)
        return None
