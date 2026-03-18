# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from .commands import (
    cmd_attendance_2h,
    cmd_status,
    cmd_timeline,
    cmd_analyze,
    cmd_where,
    cmd_supervisor_now,
    cmd_supervisor_summary,
    cmd_evidence_request,
    cmd_evidence_detail,
    cmd_evidence_ticket,
    cmd_dm_availability_today,
    cmd_dm_quality_today,
    cmd_dm_home,
    cmd_dm_unit,
)
from ..telegram_ui import build_dm_keyboard, build_group_keyboard


def _is_dm(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and getattr(chat, "type", "") == "private")


def _kb(update: Update):
    if _is_dm(update):
        return build_dm_keyboard()
    return build_group_keyboard()


def _has_n_params(fn, n: int) -> bool:
    try:
        return len(inspect.signature(fn).parameters) >= n
    except Exception:
        return True


async def _send_callback_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    q = update.callback_query
    if q and _is_dm(update):
        try:
            await q.edit_message_text(text=text, reply_markup=_kb(update), disable_web_page_preview=True)
            return
        except BadRequest as exc:
            if "Message is not modified" in str(exc):
                return
        except Exception:
            pass

    chat = update.effective_chat
    if chat:
        await context.bot.send_message(
            chat_id=chat.id,
            text=text,
            reply_markup=_kb(update),
            disable_web_page_preview=True,
        )


async def _route_evidence(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> bool:
    """Roteamento determinístico de evidências."""
    if data == "evm":
        await cmd_evidence_request(update, context, None)
        return True

    if data.startswith("evp:"):
        svc = data.split(":", 1)[1]
        if _has_n_params(cmd_evidence_request, 4):
            await cmd_evidence_request(update, context, svc, "24h")
        else:
            await cmd_evidence_request(update, context, svc)
        return True

    if data.startswith("evd:"):
        parts = data.split(":")
        svc = parts[1] if len(parts) > 1 else "TEL"
        win = parts[2] if len(parts) > 2 else "24h"
        await cmd_evidence_detail(update, context, svc, win, raw=False)
        return True

    if data.startswith("evr:"):
        parts = data.split(":")
        svc = parts[1] if len(parts) > 1 else "TEL"
        win = parts[2] if len(parts) > 2 else "24h"
        await cmd_evidence_detail(update, context, svc, win, raw=True)
        return True

    if data.startswith("evt:"):
        parts = data.split(":")
        svc = parts[1] if len(parts) > 1 else "TEL"
        win = parts[2] if len(parts) > 2 else "24h"
        if _has_n_params(cmd_evidence_ticket, 4):
            await cmd_evidence_ticket(update, context, svc, win)
        else:
            await cmd_evidence_ticket(update, context, svc)
        return True

    return False


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return

    data = (q.data or "").strip()

    try:
        await q.answer()
    except Exception:
        pass

    if await _route_evidence(update, context, data):
        return

    if data in {"home", "dm:home", "root"}:
        await cmd_dm_home(update, context)
        return

    if data.startswith("unit:"):
        unit = data.split(":", 1)[1] if ":" in data else "UN1"
        await cmd_dm_unit(update, context, unit)
        return

    if data in {"sup:now", "dm:panel", "panel"}:
        await cmd_supervisor_now(update, context, user_text="(callback)")
        return

    if data == "dm:avail_today":
        await cmd_dm_availability_today(update, context)
        return

    if data == "dm:qual_today":
        await cmd_dm_quality_today(update, context)
        return

    if data == "sup:24h":
        await cmd_supervisor_summary(update, context, window="24h")
        return

    if data == "sup:7d":
        await cmd_supervisor_summary(update, context, window="7d")
        return

    if data == "att:2h":
        await cmd_attendance_2h(update, context, user_text="(callback)")
        return

    if data == "where":
        await cmd_where(update, context)
        return

    if data == "status":
        await cmd_status(update, context)
        return

    if data.startswith("timeline:"):
        try:
            n = int(data.split(":", 1)[1])
        except Exception:
            n = 50
        context.args = [str(n)]
        await cmd_timeline(update, context)
        return

    if data.startswith("analyze:"):
        w = data.split(":", 1)[1]
        context.args = [w]
        await cmd_analyze(update, context)
        return

    await _send_callback_text(
        update,
        context,
        f"Ação não reconhecida: {data}\nUse os botões do painel, evidências, atendimento ou diagnóstico.",
    )
