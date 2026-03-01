# -*- coding: utf-8 -*-
import logging
import os
import re
import time

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from .config import TELEGRAM_TOKEN, BOT_VERSION, BUILD_ID
from .handlers.commands import (
    cmd_help, cmd_where, cmd_status, cmd_timeline, cmd_analyze, cmd_attendance_2h,
    cmd_dm_home,
    cmd_health,
)
from .handlers.callbacks import on_callback
from .handlers.chat import on_chat

LOG = logging.getLogger("noc-bot")

_ERR_COOLDOWN_S = 60
_last_err_by_chat: dict[int, float] = {}

# --- Redaction patterns ---
_RE_TG_URL = re.compile(r"(https?://api\.telegram\.org/bot)([^/\s]+)")
_RE_TG_TOKEN = re.compile(r"\b(\d{6,}:[A-Za-z0-9_-]{20,})\b")
_RE_BEARER = re.compile(r"(\bBearer\s+)([A-Za-z0-9._=-]{10,})", re.I)


def _sanitize(s: str) -> str:
    s = _RE_TG_URL.sub(r"\1[REDACTED]", s)
    s = _RE_TG_TOKEN.sub("[REDACTED]", s)
    s = _RE_BEARER.sub(r"\1[REDACTED]", s)
    tok = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN")
    if tok and tok in s:
        s = s.replace(tok, "[REDACTED]")
    return s


def _install_global_redaction() -> None:
    """
    Redaction definitivo:
    - Sanitiza no LogRecordFactory (global) ANTES de qualquer handler/formatter.
    - Zera record.args para evitar re-formatação com token.
    """
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        try:
            msg = record.getMessage()
            msg = _sanitize(msg)
            record.msg = msg
            record.args = ()
        except Exception:
            pass
        return record

    logging.setLogRecordFactory(record_factory)


async def on_error(update, context):
    LOG.exception("Unhandled exception", exc_info=context.error)

    try:
        cq = getattr(update, "callback_query", None)
        if cq:
            await cq.answer("⚠️ Erro interno. Tente novamente.", show_alert=False)
    except Exception:
        pass

    try:
        chat = getattr(update, "effective_chat", None)
        if not chat:
            return

        now = time.time()
        last = _last_err_by_chat.get(chat.id, 0.0)
        if now - last < _ERR_COOLDOWN_S:
            return
        _last_err_by_chat[chat.id] = now

        if getattr(chat, "type", "") == "private":
            await context.bot.send_message(
                chat_id=chat.id,
                text="⚠️ Erro interno no bot. Tente novamente em alguns segundos."
            )
    except Exception:
        pass


def setup_logging():
    _install_global_redaction()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    lvl = (os.getenv("NOC_HTTPX_LEVEL") or "INFO").upper()
    try:
        logging.getLogger("httpx").setLevel(getattr(logging, lvl, logging.INFO))
    except Exception:
        pass

    # BOT_VERSION já vem normalizado com "|build=..." (ou "unknown" se faltou env)
    LOG.info("starting noc-bot version=%s build=%s", BOT_VERSION, BUILD_ID)


def build_app() -> Application:
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_error_handler(on_error)

    app.add_handler(CommandHandler("help", cmd_help))

    # DM: ponto de entrada padrão
    app.add_handler(CommandHandler("start", cmd_dm_home))

    app.add_handler(CommandHandler("atendimento", cmd_attendance_2h))
    app.add_handler(CommandHandler("where", cmd_where))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(MessageHandler(filters.Regex(r"^/health(@\w+)?\b"), cmd_health))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("timeline", cmd_timeline))
    app.add_handler(CommandHandler("analyze", cmd_analyze))

    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_chat))

    return app


def main():
    setup_logging()
    app = build_app()
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()

