# -*- coding: utf-8 -*-
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# =====================================================================================
# DM (supervisora) — UX ALTIS (contrato)
# =====================================================================================

def build_dm_keyboard() -> InlineKeyboardMarkup:
    """Teclado principal do DM (sempre no rodapé)."""
    rows = [
        # Multi-unidades: volta para Home (Clínica)
        [InlineKeyboardButton("⬅️ Clínica (início)", callback_data="home")],
        [InlineKeyboardButton("Atendimento (2h)", callback_data="att:2h")],
        [InlineKeyboardButton("🔄 Painel (Tempo real)", callback_data="sup:now")],
        [
            InlineKeyboardButton("📊 Disponibilidade Hoje", callback_data="dm:avail_today"),
            InlineKeyboardButton("📈 Qualidade Hoje", callback_data="dm:qual_today"),
        ],
        [
            InlineKeyboardButton("🕒 Resumo 24h", callback_data="sup:24h"),
            InlineKeyboardButton("📅 Semana", callback_data="sup:7d"),
        ],
        [
            InlineKeyboardButton("🧾 Evidências", callback_data="evm"),
            InlineKeyboardButton("🧠 Fonte (/where)", callback_data="where"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def build_dm_home_keyboard() -> InlineKeyboardMarkup:
    """Teclado da Home DM (multi-unidades)."""
    rows = [
        [InlineKeyboardButton("UN1 — Eldorado", callback_data="unit:UN1")],
        [InlineKeyboardButton("UN2 — Barreiro", callback_data="unit:UN2")],
        [InlineKeyboardButton("UN3 — Alípio de Mello", callback_data="unit:UN3")],
        [InlineKeyboardButton("🧠 Fonte (/where)", callback_data="where")],
    ]
    return InlineKeyboardMarkup(rows)


def build_dm_unit_vpn_keyboard() -> InlineKeyboardMarkup:
    """Teclado do detalhe UN2/UN3 (VPN)."""
    rows = [
        [InlineKeyboardButton("⬅️ Clínica (início)", callback_data="home")],
        [InlineKeyboardButton("🧠 Fonte (/where)", callback_data="where")],
    ]
    return InlineKeyboardMarkup(rows)


# =====================================================================================
# Grupo NOC — UX técnico
# =====================================================================================

def build_group_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("Status", callback_data="status")],
        [
            InlineKeyboardButton("Analyze 24h", callback_data="analyze:24h"),
            InlineKeyboardButton("Analyze 7d", callback_data="analyze:7d"),
        ],
        [InlineKeyboardButton("Timeline 50", callback_data="timeline:50")],
        [
            InlineKeyboardButton("Evidências", callback_data="evm"),
            InlineKeyboardButton("Fonte (/where)", callback_data="where"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def build_root_keyboard() -> InlineKeyboardMarkup:
    return build_dm_keyboard()


# =====================================================================================
# Evidências — menus
# =====================================================================================

def kb_evidence_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("Internet (Qualidade)", callback_data="evp:NET")],
        [InlineKeyboardButton("Telefonia", callback_data="evp:TEL")],
        [InlineKeyboardButton("Link 1 (Mundivox)", callback_data="evp:L1")],
        [InlineKeyboardButton("Link 2 (Valenet)", callback_data="evp:L2")],
        [InlineKeyboardButton("Escallo", callback_data="evp:ESC")],
        [InlineKeyboardButton("VPN UN2 (Barreiro)", callback_data="evp:VPN2")],
        [InlineKeyboardButton("VPN UN3 (Alípio de Mello)", callback_data="evp:VPN3")],
        [InlineKeyboardButton("⬅️ Voltar", callback_data="sup:now")],
    ]
    return InlineKeyboardMarkup(rows)


def kb_evidence_actions(svc_code: str, window: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🧾 Texto pronto (operadora)", callback_data=f"evt:{svc_code}:{window}")],
        [InlineKeyboardButton("📄 Evidência completa (organizada)", callback_data=f"evd:{svc_code}:{window}")],
        [InlineKeyboardButton("🧾 Evidência completa (operadora)", callback_data=f"evr:{svc_code}:{window}")],
        [InlineKeyboardButton("Trocar serviço", callback_data="evm")],
    ]
    return InlineKeyboardMarkup(rows)
