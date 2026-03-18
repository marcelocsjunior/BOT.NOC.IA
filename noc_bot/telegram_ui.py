# -*- coding: utf-8 -*-
from __future__ import annotations

"""UI pública do bot.

Mantém o contrato histórico importado por handlers/commands.py e callbacks.py,
mas agora expõe uma superfície mais alinhada à DM híbrida.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_dm_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🏥 Clínica", callback_data="home"), InlineKeyboardButton("🖥️ Painel agora", callback_data="sup:now")],
        [InlineKeyboardButton("🚑 Atendimento 2h", callback_data="att:2h"), InlineKeyboardButton("🧾 Evidências", callback_data="evm")],
        [InlineKeyboardButton("📊 Disponibilidade hoje", callback_data="dm:avail_today"), InlineKeyboardButton("📈 Qualidade hoje", callback_data="dm:qual_today")],
        [InlineKeyboardButton("🕒 Resumo 24h", callback_data="sup:24h"), InlineKeyboardButton("📅 Semana", callback_data="sup:7d")],
        [InlineKeyboardButton("🧠 Fonte / diagnóstico", callback_data="where")],
    ]
    return InlineKeyboardMarkup(rows)


def build_dm_home_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("UN1 — Eldorado", callback_data="unit:UN1")],
        [InlineKeyboardButton("UN2 — Barreiro", callback_data="unit:UN2"), InlineKeyboardButton("UN3 — Alípio", callback_data="unit:UN3")],
        [InlineKeyboardButton("🖥️ Painel UN1 agora", callback_data="sup:now")],
        [InlineKeyboardButton("🧠 Fonte / diagnóstico", callback_data="where")],
    ]
    return InlineKeyboardMarkup(rows)


def build_dm_unit_vpn_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🏥 Clínica", callback_data="home"), InlineKeyboardButton("🖥️ Painel UN1", callback_data="sup:now")],
        [InlineKeyboardButton("🧠 Fonte / diagnóstico", callback_data="where")],
    ]
    return InlineKeyboardMarkup(rows)


def build_group_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("Status", callback_data="status")],
        [InlineKeyboardButton("Analyze 24h", callback_data="analyze:24h"), InlineKeyboardButton("Analyze 7d", callback_data="analyze:7d")],
        [InlineKeyboardButton("Timeline 50", callback_data="timeline:50")],
        [InlineKeyboardButton("Evidências", callback_data="evm"), InlineKeyboardButton("Fonte (DB/LOG)", callback_data="where")],
    ]
    return InlineKeyboardMarkup(rows)


def build_root_keyboard() -> InlineKeyboardMarkup:
    return build_dm_keyboard()


def kb_evidence_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("📞 Telefonia", callback_data="evp:TEL"), InlineKeyboardButton("☁️ Escallo", callback_data="evp:ESC")],
        [InlineKeyboardButton("🌐 Link 1 (Mundivox)", callback_data="evp:L1"), InlineKeyboardButton("🌐 Link 2 (Valenet)", callback_data="evp:L2")],
        [InlineKeyboardButton("🌐 Internet (Qualidade)", callback_data="evp:NET")],
        [InlineKeyboardButton("🌐🔒 VPN UN2", callback_data="evp:VPN2"), InlineKeyboardButton("🌐🔒 VPN UN3", callback_data="evp:VPN3")],
        [InlineKeyboardButton("⬅️ Voltar ao painel", callback_data="sup:now")],
    ]
    return InlineKeyboardMarkup(rows)


def kb_evidence_actions(svc_code: str, window: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🧾 Texto pronto", callback_data=f"evt:{svc_code}:{window}")],
        [InlineKeyboardButton("📄 Evidência organizada", callback_data=f"evd:{svc_code}:{window}")],
        [InlineKeyboardButton("📋 Evidência operadora", callback_data=f"evr:{svc_code}:{window}")],
        [InlineKeyboardButton("🔁 Trocar serviço", callback_data="evm")],
    ]
    return InlineKeyboardMarkup(rows)
