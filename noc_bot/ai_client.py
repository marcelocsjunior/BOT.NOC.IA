# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Literal, Optional, TypedDict

import httpx

from .config import (
    AI_ENABLED,
    CF_ACCOUNT_ID,
    CF_AUTH_TOKEN,
    CF_AI_MODEL,
    AI_TIMEOUT_S,
    AI_CACHE_TTL_S,
    AI_RL_PER_MIN,
)

log = logging.getLogger(__name__)

_cache: dict[str, tuple[float, str]] = {}
_rl_bucket: list[float] = []


class AIPolishInput(TypedDict):
    factual_text: str
    tone: Literal["dry", "light", "professional"]
    max_lines: int
    severity: Optional[str]
    source: Literal["DB", "LOG", "NONE"]
    stale: bool


class AIPolishOutput(TypedDict):
    ok: bool
    text: Optional[str]


def _cache_get(key: str) -> str | None:
    now = time.time()
    v = _cache.get(key)
    if not v:
        return None
    exp, val = v
    if now > exp:
        _cache.pop(key, None)
        return None
    return val


def _cache_set(key: str, val: str) -> None:
    _cache[key] = (time.time() + AI_CACHE_TTL_S, val)


def _rl_allow() -> bool:
    now = time.time()
    while _rl_bucket and (now - _rl_bucket[0]) > 60:
        _rl_bucket.pop(0)
    if len(_rl_bucket) >= AI_RL_PER_MIN:
        return False
    _rl_bucket.append(now)
    return True


def _ai_ready() -> bool:
    return bool(AI_ENABLED and CF_ACCOUNT_ID and CF_AUTH_TOKEN)


async def _run_ai_payload(payload: dict) -> str | None:
    if not _ai_ready():
        return None
    if not _rl_allow():
        log.info("AI_SKIP reason=rate_limit")
        return None

    key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    cached = _cache_get(key)
    if cached:
        return cached

    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{CF_AI_MODEL}"
    headers = {"Authorization": f"Bearer {CF_AUTH_TOKEN}"}

    try:
        async with httpx.AsyncClient(timeout=AI_TIMEOUT_S) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            out = (data.get("result") or {}).get("response") or ""
            out = (out or "").strip()
            if out:
                _cache_set(key, out)
            return out or None
    except Exception as e:
        log.info("AI_ERROR err=%s", str(e))
        return None


async def ai_interpret(
    facts: dict,
    kpi_text: str,
    details: str,
    update=None,
    window: str = "24h",
    source: str = "DB",
) -> str | None:
    """
    Fluxo legado já usado pelo bot atual.
    Mantido por compatibilidade.
    """
    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você é um assistente de NOC. "
                    "Responda de forma curta, clara e conservadora. "
                    "Não invente fatos."
                ),
            },
            {"role": "user", "content": details},
        ]
    }
    return await _run_ai_payload(payload)


def _should_polish(inp: AIPolishInput) -> bool:
    if not _ai_ready():
        return False
    if not (inp.get("factual_text") or "").strip():
        return False
    if inp.get("stale", False):
        return False
    if inp.get("severity") in {"SEV1", "SEV2"}:
        return False
    if inp.get("source") == "LOG":
        return False
    return True


def _tone_instruction(tone: str) -> str:
    if tone == "dry":
        return "tom técnico, seco e direto"
    if tone == "professional":
        return "tom profissional, objetivo e corporativo"
    return "tom humano leve, objetivo e discreto"


async def polish_with_ai(
    factual_text: str,
    *,
    tone: Literal["dry", "light", "professional"] = "light",
    max_lines: int = 3,
    severity: Optional[str] = None,
    source: Literal["DB", "LOG", "NONE"] = "DB",
    stale: bool = False,
) -> AIPolishOutput:
    """
    Reescreve uma resposta factual sem alterar os fatos.
    A IA só entra se o contexto for seguro.
    """
    inp: AIPolishInput = {
        "factual_text": factual_text or "",
        "tone": tone,
        "max_lines": max_lines,
        "severity": severity,
        "source": source,
        "stale": stale,
    }

    if not _should_polish(inp):
        return {"ok": False, "text": None}

    prompt = (
        "Você é uma assistente de NOC.\n"
        f"Reescreva a resposta abaixo em { _tone_instruction(tone) }.\n"
        f"Limite: no máximo {max_lines} linhas.\n"
        "Regras obrigatórias:\n"
        "- não alterar números\n"
        "- não alterar horários\n"
        "- não alterar CID\n"
        "- não alterar severidade\n"
        "- não inferir causa raiz\n"
        "- não comparar períodos sem dado explícito\n"
        "- não inventar fatos\n"
        "- manter a resposta curta e útil\n"
        "- não usar humor se houver risco operacional\n\n"
        f"Resposta factual:\n{factual_text}\n\n"
        "Resposta final:"
    )

    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você é um assistente de NOC conservador. "
                    "Sua função é apenas reformular texto factual sem mudar o conteúdo."
                ),
            },
            {"role": "user", "content": prompt},
        ]
    }

    out = await _run_ai_payload(payload)
    if not out:
        return {"ok": False, "text": None}

    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if not lines:
        return {"ok": False, "text": None}

    final_text = "\n".join(lines[:max_lines]).strip()
    if not final_text:
        return {"ok": False, "text": None}

    return {"ok": True, "text": final_text}
