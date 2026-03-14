# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

from ..ai_client import polish_with_ai
from ..config import (
    DM_ASSISTANT_ALLOWED_CHAT_IDS,
    DM_ASSISTANT_ENABLE_AI_FINISH,
    DM_ASSISTANT_ENABLED,
    DM_ASSISTANT_MAX_REPLY_LINES,
    DM_ASSISTANT_MIN_CONFIDENCE,
    DM_ASSISTANT_SHADOW_MODE,
    DM_ASSISTANT_STYLE,
    GROUP_REPLY_MENTION_ONLY,
)
from ..dm_intents import detect_intent
from ..dm_presenter import render_factual
from ..dm_queries import dispatch_query
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


def _norm_dm_text(s: str) -> str:
    t = (s or "").lower()
    t = (
        t.replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("ã", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )
    return " ".join(t.split())


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


async def _try_dm_consultive_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    text: str,
    t: str,
    tn: str,
) -> bool:
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

    if _is_reserved_flow_text(t, tn):
        return False

    intent_data = detect_intent(text, min_confidence=DM_ASSISTANT_MIN_CONFIDENCE)

    if intent_data["intent"] == "unknown":
        return False

    if intent_data["confidence"] < DM_ASSISTANT_MIN_CONFIDENCE:
        log.info(
            "DM_CONSULTIVE_SKIP unit=%s chat_id=%s reason=low_confidence intent=%s confidence=%.2f",
            intent_data["unit"],
            chat.id,
            intent_data["intent"],
            intent_data["confidence"],
        )
        return False

    query_result = dispatch_query(intent_data)
    presenter_output = render_factual(query_result)

    reply_text = presenter_output["text"]

    if DM_ASSISTANT_ENABLE_AI_FINISH and presenter_output["safe_for_ai_polish"]:
        polish_tone = DM_ASSISTANT_STYLE if DM_ASSISTANT_STYLE in ("light", "professional") else presenter_output["tone"]
        polished = await polish_with_ai(
            reply_text,
            tone=polish_tone,
            max_lines=DM_ASSISTANT_MAX_REPLY_LINES,
            severity=query_result["meta"]["severity"],
            source=query_result["meta"]["source"],
            stale=query_result["meta"]["stale"],
        )
        if polished.get("ok") and polished.get("text"):
            reply_text = polished["text"] or reply_text

    if DM_ASSISTANT_SHADOW_MODE:
        log.info(
            "DM_SHADOW unit=%s chat_id=%s raw_text=%r intent=%s service=%s period=%s confidence=%.2f "
            "fallback_reason=%s source=%s stale=%s would_reply=%r",
            intent_data["unit"],
            chat.id,
            text,
            intent_data["intent"],
            intent_data["service"],
            intent_data["period"],
            intent_data["confidence"],
            query_result["fallback_reason"],
            query_result["meta"]["source"],
            query_result["meta"]["stale"],
            reply_text,
        )
        return False

    await msg.reply_text(reply_text, disable_web_page_preview=True)
    log.info(
        "DM_CONSULTIVE_REPLY unit=%s chat_id=%s intent=%s service=%s period=%s source=%s stale=%s",
        intent_data["unit"],
        chat.id,
        intent_data["intent"],
        intent_data["service"],
        intent_data["period"],
        query_result["meta"]["source"],
        query_result["meta"]["stale"],
    )
    return True


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
            await cmd_dm_unit(update, context, "UN1")
            return
        if any(k in tn for k in ("un2", "barreiro")):
            await cmd_dm_unit(update, context, "UN2")
            return
        if any(k in tn for k in ("un3", "alipio", "alipio de mello", "alipio de melo")):
            await cmd_dm_unit(update, context, "UN3")
            return

    if await _try_dm_consultive_reply(update, context, text=text, t=t, tn=tn):
        return

    if _is_dm(update):
        if any(
            k in tn
            for k in (
                "lento",
                "lenta",
                "lentidao",
                "travando",
                "trava",
                "travou",
                "travamento",
                "caindo",
                "cai",
                "caiu",
                "cair",
                "queda",
                "quedas",
                "instavel",
                "instabilidade",
                "ruim",
                "reclama",
                "reclamacao",
                "telefonia",
                "telefone",
                "telef",
                "teledone",
                "voip",
                "sip",
                "escallo",
                "escalo",
                "ommini",
                "omminichanel",
                "internet",
                "rede",
                "link",
            )
        ):
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
        await cmd_dm_home(update, context)
        return

    await cmd_status(update, context)
