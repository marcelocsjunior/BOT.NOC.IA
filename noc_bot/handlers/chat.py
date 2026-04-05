# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional, cast

from telegram import Update
from telegram.ext import ContextTypes

from ..ai_client import compose_general_dm_reply, polish_with_ai
from ..config import (
    DM_ASSISTANT_ALLOWED_CHAT_IDS,
    DM_ASSISTANT_ENABLE_AI_FINISH,
    DM_ASSISTANT_ENABLE_AI_GENERAL,
    DM_ASSISTANT_ENABLE_DM_ROUTER,
    DM_ASSISTANT_ENABLED,
    DM_ASSISTANT_MAX_REPLY_LINES,
    DM_ASSISTANT_MIN_CONFIDENCE,
    DM_ASSISTANT_SHADOW_MODE,
    DM_ASSISTANT_STYLE,
    GROUP_REPLY_MENTION_ONLY,
    UNIT,
)
from ..dm_intents import (
    IntentData,
    PeriodKey,
    ServiceKey,
    detect_intent,
    extract_service,
    is_confirmation_request,
    is_out_of_scope_request,
    is_strict_global_status_request,
    normalize_text,
)
from ..dm_presenter import render_factual
from ..dm_router import resolve_dm_route
from ..dm_session import get_selected_unit, save_last_resolution, set_selected_unit
from ..dm_queries_unit import dispatch_query
from ..utils import is_mention_or_reply, strip_mention
from .commands import (
    EVIDENCE_TRIGGERS,
    cmd_analyze,
    cmd_attendance_2h,
    cmd_dm_home,
    cmd_dm_unit,
    cmd_evidence_request,
    cmd_status,
    cmd_supervisor_summary,
    cmd_timeline,
    cmd_where,
    detect_service_from_text,
)

log = logging.getLogger(__name__)

_DM_USEFUL_CONTEXT_KEY = "dm_consultive_last_context"
_DM_USEFUL_CONTEXT_TTL_S = 15 * 60
_OOS_HINT = (
    "Isso foge do escopo operacional deste bot. "
    "Aqui eu respondo status, falhas, CID, resumo e evidências de link1, link2, telefonia e escallo."
)
_OOS_NOC_TOKENS = (
    "status",
    "queda",
    "falha",
    "cid",
    "resumo",
    "evidencia",
    "evidência",
    "timeline",
    "log",
    "db",
    "fonte",
    "telefon",
    "telefone",
    "voip",
    "ramal",
    "escallo",
    "escalo",
    "link",
    "mundivox",
    "valenet",
    "internet",
    "vpn",
    "un1",
    "un2",
    "un3",
)
_OOS_QUESTION_HINTS = ("qual", "quais", "como", "onde", "quando", "site", "link", "url")


def _norm_dm_text(s: str) -> str:
    return normalize_text(s)


def _is_dm(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and getattr(chat, "type", "") == "private")


def _looks_like_evidence(t: str) -> bool:
    tl = (t or "").lower()
    return any(k in tl for k in EVIDENCE_TRIGGERS)


def _summary_window_hint(t: str) -> str | None:
    tl = (t or "").lower()
    if any(x in tl for x in ("semana", "7d", "7 dias")):
        return "7d"
    if any(x in tl for x in ("24h", "24 horas", "hoje", "queda hoje", "alguma queda", "ocorreu alguma queda", "resumo")):
        return "24h"
    return None


def _parse_window_arg(text: str) -> str | None:
    tl = (text or "").lower()
    m = re.search(r"\b(24h|7d|30d)\b", tl)
    if m:
        return m.group(1)
    if "semana" in tl or "7 dias" in tl:
        return "7d"
    if "30 dias" in tl:
        return "30d"
    if "24 horas" in tl:
        return "24h"
    return None


def _parse_timeline_n(text: str) -> str | None:
    tl = (text or "").lower()
    m = re.search(r"(?:^|\s)(?:/timeline|timeline)\s*([0-9]{1,5})", tl)
    if m:
        return m.group(1)
    for tok in tl.split():
        if tok.isdigit():
            return tok
    return None


def _dm_assistant_allowed(chat_id: int) -> bool:
    if not DM_ASSISTANT_ALLOWED_CHAT_IDS:
        return True
    return chat_id in DM_ASSISTANT_ALLOWED_CHAT_IDS


def _is_reserved_flow_text(t: str, tn: str) -> bool:
    if not t:
        return False
    if t.startswith("/"):
        return True
    if t.startswith(("timeline", "/timeline", "eventos", "logs", "log")):
        return True
    if t.startswith(("analyze", "analise", "análise", "kpi", "/analyze")):
        return True
    if any(k in tn for k in ("where", "fonte", "db", "log")):
        return True
    return False


def _save_dm_useful_context(context: ContextTypes.DEFAULT_TYPE, *, route: str, service: Optional[str], user_text: str, intent: str | None = None, period: str | None = None) -> None:
    if not service:
        return
    context.chat_data[_DM_USEFUL_CONTEXT_KEY] = {
        "route": route,
        "service": service,
        "intent": intent,
        "period": period,
        "user_text": user_text,
        "saved_at": time.time(),
    }


def _get_dm_useful_context(context: ContextTypes.DEFAULT_TYPE) -> Optional[dict[str, Any]]:
    raw = context.chat_data.get(_DM_USEFUL_CONTEXT_KEY)
    if not isinstance(raw, dict):
        return None
    saved_at = raw.get("saved_at")
    if not isinstance(saved_at, (int, float)):
        context.chat_data.pop(_DM_USEFUL_CONTEXT_KEY, None)
        return None
    if (time.time() - float(saved_at)) > _DM_USEFUL_CONTEXT_TTL_S:
        context.chat_data.pop(_DM_USEFUL_CONTEXT_KEY, None)
        return None
    service = raw.get("service")
    route = raw.get("route")
    if not isinstance(service, str) or not isinstance(route, str):
        context.chat_data.pop(_DM_USEFUL_CONTEXT_KEY, None)
        return None
    return raw


def _build_context_intent_data(text: str, saved: dict[str, Any]) -> IntentData:
    service = cast(Optional[ServiceKey], saved.get("service"))
    intent = cast(str, saved.get("intent") or "status_atual")
    period = cast(PeriodKey, saved.get("period") or "now")
    normalized_text = normalize_text(text)
    return {
        "version": "dm.intent.ctx.v1",
        "unit": UNIT,
        "raw_text": text or "",
        "normalized_text": normalized_text,
        "intent": cast(Any, intent),
        "service": service,
        "period": period,
        "confidence": 0.99,
        "fallback_reason": "none",
        "entities": {
            "resolved_from": "last_useful_context",
            "service_hits": [service] if service else [],
            "service_hit_count": 1 if service else 0,
            "is_confirmation": True,
        },
    }


def _apply_selected_unit(chat_id: int, intent_data: IntentData) -> IntentData:
    selected_unit = get_selected_unit(chat_id)
    if not selected_unit:
        return intent_data
    updated = dict(intent_data)
    updated["unit"] = selected_unit
    entities = dict(intent_data.get("entities") or {})
    entities["selected_unit"] = selected_unit
    updated["entities"] = entities
    return cast(IntentData, updated)


def _looks_like_out_of_scope_dm_question(text: str, tn: str) -> bool:
    if is_out_of_scope_request(tn, normalized=True):
        return True
    if not any(token in tn for token in _OOS_QUESTION_HINTS):
        return False
    if any(token in tn for token in _OOS_NOC_TOKENS):
        return False
    if "?" not in text and not any(token in tn for token in ("site", "link", "url")):
        return False
    return True


async def _reply_dm_general(update: Update, *, user_text: str, fallback_text: str, mode: str) -> bool:
    msg = update.effective_message
    if not msg:
        return False
    reply_text = (fallback_text or "").strip()
    if DM_ASSISTANT_ENABLE_AI_GENERAL:
        ai_reply = await compose_general_dm_reply(user_text, mode=cast(Any, mode), fallback_text=reply_text, max_lines=max(2, min(DM_ASSISTANT_MAX_REPLY_LINES + 1, 4)), severity=None)
        if ai_reply.get("ok") and ai_reply.get("text"):
            reply_text = str(ai_reply.get("text") or reply_text)
    if not reply_text:
        return False
    await msg.reply_text(reply_text, disable_web_page_preview=True)
    return True


async def _try_dm_router_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, *, text: str, t: str, tn: str) -> bool:
    if not _is_dm(update):
        return False
    if not DM_ASSISTANT_ENABLED or not DM_ASSISTANT_ENABLE_DM_ROUTER:
        return False
    if _is_reserved_flow_text(t, tn):
        return False
    chat = update.effective_chat
    if not chat or not _dm_assistant_allowed(chat.id):
        return False
    decision = await resolve_dm_route(chat.id, text)
    if not decision.get("handled"):
        return False
    route = str(decision.get("route") or "")
    if route == "consult" and decision.get("intent_data"):
        intent_data = cast(IntentData, decision["intent_data"])
        ok = await _reply_dm_consultive_from_intent(update, context, text=text, intent_data=intent_data)
        if ok:
            save_last_resolution(chat.id, intent=cast(Any, intent_data.get("intent")), service=cast(Any, intent_data.get("service")), period=cast(Any, intent_data.get("period")), route="consult")
        return ok
    if route == "incident":
        svc = detect_service_from_text(t)
        if svc:
            _save_dm_useful_context(context, route="attendance", service=svc, user_text=text, intent="status_atual", period="24h")
            save_last_resolution(chat.id, service=cast(Any, svc), route="incident")
        await cmd_attendance_2h(update, context, user_text=text)
        return True
    if route == "clarify":
        msg = update.effective_message
        clarify_text = str(decision.get("clarify_text") or "").strip()
        if not msg or not clarify_text:
            return False
        await msg.reply_text(clarify_text, disable_web_page_preview=True)
        return True
    if route in {"social", "help"}:
        return await _reply_dm_general(update, user_text=text, fallback_text=str(decision.get("reply_text") or ""), mode=route)
    return False


async def _reply_out_of_scope(update: Update) -> bool:
    msg = update.effective_message
    if not msg:
        return False
    await msg.reply_text(_OOS_HINT, disable_web_page_preview=True)
    return True


async def _reply_dm_consultive_from_intent(update: Update, context: ContextTypes.DEFAULT_TYPE, *, text: str, intent_data: IntentData) -> bool:
    if not _is_dm(update):
        return False
    if not DM_ASSISTANT_ENABLED:
        return False
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or not msg or not text.strip():
        return False
    if not _dm_assistant_allowed(chat.id):
        return False
    if intent_data["intent"] == "unknown":
        return False
    if intent_data["confidence"] < DM_ASSISTANT_MIN_CONFIDENCE:
        log.info("DM_CONSULTIVE_SKIP unit=%s chat_id=%s reason=low_confidence intent=%s confidence=%.2f", intent_data["unit"], chat.id, intent_data["intent"], intent_data["confidence"])
        return False
    effective_intent_data = _apply_selected_unit(chat.id, intent_data)
    query_result = dispatch_query(effective_intent_data)
    presenter_output = render_factual(query_result)
    reply_text = presenter_output["text"]
    if DM_ASSISTANT_ENABLE_AI_FINISH and presenter_output["safe_for_ai_polish"]:
        polish_tone = DM_ASSISTANT_STYLE if DM_ASSISTANT_STYLE in ("light", "professional") else presenter_output["tone"]
        polished = await polish_with_ai(reply_text, tone=polish_tone, max_lines=DM_ASSISTANT_MAX_REPLY_LINES, severity=query_result["meta"]["severity"], source=query_result["meta"]["source"], stale=query_result["meta"]["stale"])
        if polished.get("ok") and polished.get("text"):
            reply_text = polished["text"] or reply_text
    if query_result["ok"] and effective_intent_data["service"]:
        _save_dm_useful_context(context, route="consultive", service=effective_intent_data["service"], user_text=text, intent=effective_intent_data["intent"], period=effective_intent_data["period"])
    if DM_ASSISTANT_SHADOW_MODE:
        log.info("DM_SHADOW unit=%s chat_id=%s raw_text=%r intent=%s service=%s period=%s confidence=%.2f fallback_reason=%s source=%s stale=%s would_reply=%r", effective_intent_data["unit"], chat.id, text, effective_intent_data["intent"], effective_intent_data["service"], effective_intent_data["period"], effective_intent_data["confidence"], query_result["fallback_reason"], query_result["meta"]["source"], query_result["meta"]["stale"], reply_text)
        return False
    await msg.reply_text(reply_text, disable_web_page_preview=True)
    log.info("DM_CONSULTIVE_REPLY unit=%s chat_id=%s intent=%s service=%s period=%s source=%s stale=%s", effective_intent_data["unit"], chat.id, effective_intent_data["intent"], effective_intent_data["service"], effective_intent_data["period"], query_result["meta"]["source"], query_result["meta"]["stale"])
    return True


async def _try_dm_consultive_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, *, text: str, t: str, tn: str) -> bool:
    if not _is_dm(update):
        return False
    if not DM_ASSISTANT_ENABLED:
        return False
    if _is_reserved_flow_text(t, tn):
        return False
    intent_data = detect_intent(text, min_confidence=DM_ASSISTANT_MIN_CONFIDENCE)
    return await _reply_dm_consultive_from_intent(update, context, text=text, intent_data=intent_data)


async def _try_dm_confirmation_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, *, text: str, tn: str) -> bool:
    if not _is_dm(update):
        return False
    if not is_confirmation_request(tn, normalized=True):
        return False
    if extract_service(tn, normalized=True) is not None:
        return False
    saved = _get_dm_useful_context(context)
    if not saved:
        return False
    route = str(saved.get("route") or "")
    if route == "attendance":
        await cmd_attendance_2h(update, context, user_text=str(saved.get("user_text") or ""))
        return True
    if route != "consultive":
        return False
    intent_data = _build_context_intent_data(text, saved)
    return await _reply_dm_consultive_from_intent(update, context, text=text, intent_data=intent_data)


async def on_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return
    chat = update.effective_chat
    bot = context.bot
    bot_username = bot.username
    bot_id = bot.id
    if chat and getattr(chat, "type", "") != "private" and GROUP_REPLY_MENTION_ONLY:
        if not is_mention_or_reply(update, bot_id, bot_username):
            return
    text = strip_mention(msg.text, bot_username).strip()
    t = text.lower()
    tn = _norm_dm_text(text)
    if _looks_like_evidence(t):
        svc = detect_service_from_text(t)
        await cmd_evidence_request(update, context, svc)
        return
    if _is_dm(update):
        if any(k in tn for k in ("un1", "eldorado", "matriz")):
            if chat:
                set_selected_unit(chat.id, "UN1")
            await cmd_dm_unit(update, context, "UN1")
            return
        if any(k in tn for k in ("un2", "barreiro")):
            if chat:
                set_selected_unit(chat.id, "UN2")
            await cmd_dm_unit(update, context, "UN2")
            return
        if any(k in tn for k in ("un3", "alipio", "alipio de mello", "alipio de melo")):
            if chat:
                set_selected_unit(chat.id, "UN3")
            await cmd_dm_unit(update, context, "UN3")
            return
    if _is_dm(update) and is_strict_global_status_request(tn, normalized=True):
        await cmd_status(update, context)
        return
    if await _try_dm_router_reply(update, context, text=text, t=t, tn=tn):
        return
    if await _try_dm_consultive_reply(update, context, text=text, t=t, tn=tn):
        return
    if await _try_dm_confirmation_reply(update, context, text=text, tn=tn):
        return
    if _is_dm(update):
        if any(k in tn for k in ("lento", "lenta", "lentidao", "travando", "trava", "travou", "travamento", "caindo", "cai", "caiu", "cair", "queda", "quedas", "instavel", "instabilidade", "ruim", "reclama", "reclamacao", "telefonia", "telefone", "telef", "teledone", "voip", "sip", "escallo", "escalo", "ommini", "omminichanel", "internet", "rede", "link")):
            svc = detect_service_from_text(t)
            if svc:
                _save_dm_useful_context(context, route="attendance", service=svc, user_text=text, intent="status_atual", period="24h")
            await cmd_attendance_2h(update, context, user_text=text)
            return
    if any(k in tn for k in ("where", "fonte", "db", "log")):
        await cmd_where(update, context)
        return
    if t.startswith(("timeline", "/timeline", "eventos", "logs", "log")):
        n = _parse_timeline_n(t)
        context.args = [n] if n else []
        await cmd_timeline(update, context)
        return
    if t.startswith(("analyze", "analise", "análise", "kpi", "/analyze")):
        w = _parse_window_arg(t)
        context.args = [w] if w else []
        await cmd_analyze(update, context)
        return
    if _is_dm(update):
        w = _summary_window_hint(t)
        if w:
            await cmd_supervisor_summary(update, context, window=w)
            return
        if _looks_like_out_of_scope_dm_question(text, tn):
            await _reply_out_of_scope(update)
            return
        await cmd_dm_home(update, context)
        return
    await cmd_status(update, context)
