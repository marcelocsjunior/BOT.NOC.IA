# -*- coding: utf-8 -*-
import re
from telegram import Update
from telegram.ext import ContextTypes

from ..config import GROUP_REPLY_MENTION_ONLY
from ..utils import strip_mention, is_mention_or_reply
from .commands import (
    cmd_attendance_2h,
    cmd_status, cmd_timeline, cmd_analyze, cmd_where,
    cmd_supervisor_now, cmd_supervisor_summary,
    cmd_dm_home, cmd_dm_unit,
    cmd_evidence_request, detect_service_from_text,
    EVIDENCE_TRIGGERS,
)


def _norm_dm_text(s: str) -> str:
    # lower + remove acentos comuns (suficiente pro nosso gatilho)
    t = (s or "").lower()
    t = (t.replace("á","a").replace("à","a").replace("â","a").replace("ã","a")
           .replace("é","e").replace("ê","e")
           .replace("í","i")
           .replace("ó","o").replace("ô","o").replace("õ","o")
           .replace("ú","u")
           .replace("ç","c"))
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

async def on_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return

    chat = update.effective_chat
    bot = context.bot
    bot_username = bot.username
    bot_id = bot.id

    # Grupo: anti-ruído por menção/reply
    if chat and getattr(chat, "type", "") != "private" and GROUP_REPLY_MENTION_ONLY:
        if not is_mention_or_reply(update, bot_id, bot_username):
            return

    text = strip_mention(msg.text, bot_username).strip()
    t = text.lower()
    tn = _norm_dm_text(text)  # <- SEMPRE definido (acabou o NameError)

    # 1) Evidências (tem prioridade)
    if _looks_like_evidence(t):
        svc = detect_service_from_text(t)
        await cmd_evidence_request(update, context, svc)
        return

    # 1.1) DM: seleção de unidade (multi-unidades) por texto
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

    # 2) Reclamação operacional no DM -> Atendimento (2h)
    if _is_dm(update):
        if any(k in tn for k in (
            "lento","lenta","lentidao",
            "travando","trava","travou","travamento",
            "caindo","cai","caiu","cair","queda","quedas",
            "instavel","instabilidade","ruim",
            "reclama","reclamacao",
            # foco explícito também dispara atendimento
            "telefonia","telefone","telef","teledone","voip","sip",
            "escallo","escalo","ommini","omminichanel",
            "internet","rede","link"
        )):
            await cmd_attendance_2h(update, context, user_text=text)
            return

    # 3) Where/fonte
    if any(k in tn for k in ("where", "fonte", "db", "log")):
        await cmd_where(update, context)
        return

    # 4) Timeline
    if t.startswith(("timeline", "/timeline", "eventos", "logs", "log")):
        n = _parse_timeline_n(t)
        context.args = [n] if n else []
        await cmd_timeline(update, context)
        return

    # 5) Analyze
    if t.startswith(("analyze", "analise", "análise", "kpi", "/analyze")):
        w = _parse_window_arg(t)
        context.args = [w] if w else []
        await cmd_analyze(update, context)
        return

    # 6) DM default: resumo/tower
    if _is_dm(update):
        w = _summary_window_hint(t)
        if w:
            await cmd_supervisor_summary(update, context, window=w)
            return
        # default DM: Home multi-unidades (Clínica)
        await cmd_dm_home(update, context)
        return

    # 7) Grupo default
    await cmd_status(update, context)

