# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import Literal, Optional, TypedDict, cast

import httpx

from .config import (
    AI_ENABLED,
    AI_CACHE_TTL_S,
    AI_RL_PER_MIN,
    AI_TIMEOUT_S,
    CF_ACCOUNT_ID,
    CF_AI_MODEL,
    CF_AUTH_TOKEN,
    DM_ASSISTANT_ENABLE_AI_GENERAL,
)
from .dm_intents import IntentName, PeriodKey, ServiceKey

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


class AIClassifierOutput(TypedDict):
    ok: bool
    route: Literal["consult", "incident", "clarify", "social", "help", "none"]
    intent: Optional[IntentName]
    service: Optional[ServiceKey]
    period: PeriodKey
    confidence: float
    clarify_kind: Optional[str]
    clarify_text: Optional[str]


class AIGeneralReplyOutput(TypedDict):
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


def _strip_code_fences(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _extract_json_object(text: str) -> dict | None:
    raw = _strip_code_fences(text)
    if not raw:
        return None

    try:
        obj = json.loads(raw)
        return cast(dict, obj) if isinstance(obj, dict) else None
    except Exception:
        pass

    m = re.search(r"\{.*\}", raw, flags=re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return cast(dict, obj) if isinstance(obj, dict) else None
    except Exception:
        return None


def _normalize_route(v: object) -> Literal["consult", "incident", "clarify", "social", "help", "none"]:
    s = str(v or "").strip().lower()
    if s in {"consult", "incident", "clarify", "social", "help"}:
        return cast(Literal["consult", "incident", "clarify", "social", "help", "none"], s)
    return "none"


def _normalize_intent(v: object) -> Optional[IntentName]:
    s = str(v or "").strip().lower()
    allowed = {
        "status_atual",
        "queda_servico_janela",
        "contagem_falhas",
        "ultimo_cid",
        "resumo_periodo",
        "comparativo_servico",
        "acao_recomendada",
    }
    return cast(Optional[IntentName], s) if s in allowed else None


def _normalize_service(v: object) -> Optional[ServiceKey]:
    s = str(v or "").strip().upper()
    allowed = {"NET", "TEL", "L1", "L2", "ESC", "VPN2", "VPN3"}
    return cast(Optional[ServiceKey], s) if s in allowed else None


def _normalize_period(v: object) -> PeriodKey:
    s = str(v or "").strip().lower()
    allowed = {"now", "today", "yesterday", "24h", "7d", "30d", "week", "month", "unspecified"}
    if s in allowed:
        return cast(PeriodKey, s)
    return "unspecified"


async def classify_dm_message_with_ai(
    text: str,
    *,
    session_hint: str = "",
) -> AIClassifierOutput:
    """
    Classificação estruturada da fala humana.
    Não responde fatos. Só decide rota/intenção.
    """
    if not _ai_ready():
        return {
            "ok": False,
            "route": "none",
            "intent": None,
            "service": None,
            "period": "unspecified",
            "confidence": 0.0,
            "clarify_kind": None,
            "clarify_text": None,
        }

    prompt = (
        "Classifique a mensagem do usuário para um bot de NOC.\n"
        "Responda SOMENTE em JSON válido, sem markdown, sem texto extra.\n"
        "Campos obrigatórios:\n"
        "route: consult | incident | clarify | social | help | none\n"
        "intent: status_atual | queda_servico_janela | contagem_falhas | ultimo_cid | resumo_periodo | comparativo_servico | acao_recomendada | null\n"
        "service: NET | TEL | L1 | L2 | ESC | VPN2 | VPN3 | null\n"
        "period: now | today | yesterday | 24h | 7d | 30d | week | month | unspecified\n"
        "confidence: número entre 0 e 1\n"
        "clarify_kind: service_scope | service_select | status_or_window | consult_or_incident | generic | null\n"
        "clarify_text: string curta ou null\n\n"
        "Regras:\n"
        "- consult = pergunta/consulta factual\n"
        "- incident = problema atual em andamento\n"
        "- clarify = falta contexto\n"
        "- social = saudação ou abertura de conversa\n"
        "- help = ajuda simples e segura, sem fato operacional\n"
        "- não invente fatos\n"
        "- se não tiver certeza, use clarify\n"
        "- para frases como 'telefone ok aí' prefira consult/status_atual/TEL/now\n"
        "- para frases como 'oi, boa tarde' prefira social\n"
        "- para frases como 'qual é o site do speed test' prefira help\n"
        "- para frases como 'e escallo' prefira clarify/service_scope/ESC\n"
        "- para frases como 'me ajuda com a internet' prefira clarify/consult_or_incident/NET\n"
        "- para frases como 'caiu tudo agora' prefira incident\n"
        "- para frases comparativas como 'qual tá pior' prefira consult/comparativo_servico/7d\n"
        "- perguntas sobre passado (hoje, ontem, 24h, 7d, 30d) não são incident por padrão\n\n"
        f"Contexto prévio da conversa: {session_hint or 'nenhum'}\n"
        f"Mensagem do usuário: {text}\n"
    )

    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você é um classificador conservador de intenção para um bot de NOC. "
                    "Sua saída deve ser JSON puro e curto."
                ),
            },
            {"role": "user", "content": prompt},
        ]
    }

    out = await _run_ai_payload(payload)
    if not out:
        return {
            "ok": False,
            "route": "none",
            "intent": None,
            "service": None,
            "period": "unspecified",
            "confidence": 0.0,
            "clarify_kind": None,
            "clarify_text": None,
        }

    obj = _extract_json_object(out)
    if not obj:
        log.info("AI_CLASSIFIER_SKIP reason=invalid_json raw=%r", out)
        return {
            "ok": False,
            "route": "none",
            "intent": None,
            "service": None,
            "period": "unspecified",
            "confidence": 0.0,
            "clarify_kind": None,
            "clarify_text": None,
        }

    try:
        conf = float(obj.get("confidence", 0.0) or 0.0)
    except Exception:
        conf = 0.0
    conf = max(0.0, min(conf, 1.0))

    route = _normalize_route(obj.get("route"))
    clarify_kind = str(obj.get("clarify_kind") or "").strip() or None
    clarify_text = str(obj.get("clarify_text") or "").strip() or None

    return {
        "ok": route != "none",
        "route": route,
        "intent": _normalize_intent(obj.get("intent")),
        "service": _normalize_service(obj.get("service")),
        "period": _normalize_period(obj.get("period")),
        "confidence": round(conf, 2),
        "clarify_kind": clarify_kind,
        "clarify_text": clarify_text,
    }


async def compose_general_dm_reply(
    user_text: str,
    *,
    mode: Literal["social", "help"] = "help",
    fallback_text: str = "",
    max_lines: int = 3,
    severity: Optional[str] = None,
) -> AIGeneralReplyOutput:
    if not (DM_ASSISTANT_ENABLE_AI_GENERAL and _ai_ready()):
        return {"ok": False, "text": None}

    if severity in {"SEV1", "SEV2"}:
        humor_rule = "sem humor"
    else:
        humor_rule = "humor leve e discreto permitido, sem exagero"

    if mode == "social":
        task = (
            "Responda a saudação do usuário em pt-BR, de forma humana, curta e profissional. "
            "Ofereça ajuda com status da unidade, links, telefonia, Escallo ou dúvida rápida."
        )
    else:
        task = (
            "Responda a dúvida simples do usuário em pt-BR, de forma curta, útil e direta. "
            "Não invente fato operacional, não diga que verificou sistemas internos, e fique no tema da ajuda pedida."
        )

    prompt = (
        f"Tarefa: {task}\n"
        f"Limite: no máximo {max_lines} linhas.\n"
        f"Tom: humano, direto e colaborativo; {humor_rule}.\n"
        "Regras obrigatórias:\n"
        "- não inventar fatos operacionais\n"
        "- não afirmar que consultou DB, LOG ou monitoramento\n"
        "- não usar markdown desnecessário\n"
        "- não enrolar\n"
        "- responder em português do Brasil\n\n"
        f"Fallback base:\n{fallback_text or '-'}\n\n"
        f"Mensagem do usuário:\n{user_text}\n\n"
        "Resposta final:"
    )

    payload = {
        "messages": [
            {
                "role": "system",
                "content": "Você é uma assistente operacional humana, útil e conservadora.",
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
    return {"ok": bool(final_text), "text": final_text or None}
