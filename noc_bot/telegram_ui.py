# -*- coding: utf-8 -*-
"""Shim de UI.

Contrato:
- handlers/commands.py importa teclados daqui (build_dm_keyboard, kb_evidence_menu, ...)
- A fonte de verdade fica em noc_bot/ui/keyboards.py para evitar drift.
"""

from .ui.keyboards import (  # noqa: F401
    build_dm_keyboard,
    build_dm_home_keyboard,
    build_dm_unit_vpn_keyboard,
    build_group_keyboard,
    build_root_keyboard,
    kb_evidence_menu,
    kb_evidence_actions,
)
