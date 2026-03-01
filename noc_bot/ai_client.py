# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass

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

async def ai_interpret(facts: dict, kpi_text: str, details: str, update=None, window: str = "24h", source: str = "DB") -> str | None:
    if not AI_ENABLED:
        return None
    if not CF_ACCOUNT_ID or not CF_AUTH_TOKEN:
        return None
    if not _rl_allow():
        return None

    payload = {
        "messages": [
            {"role": "system", "content": "Você é um assistente de NOC. Responda de forma curta, clara e conservadora. Não invente fatos."},
            {"role": "user", "content": details},
        ]
    }

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
