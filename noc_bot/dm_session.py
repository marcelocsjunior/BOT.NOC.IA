# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Literal, Optional, TypedDict

from .config import DM_ASSISTANT_MAX_CLARIFY_TURNS, DM_ASSISTANT_SESSION_TTL_S
from .dm_intents import IntentName, PeriodKey, ServiceKey

ClarifyKind = Literal[
    "service_scope",
    "service_select",
    "status_or_window",
    "consult_or_incident",
    "generic",
]


class DMSession(TypedDict):
    chat_id: int
    updated_at: float
    awaiting: bool
    clarify_kind: ClarifyKind
    pending_route: str
    pending_intent: Optional[IntentName]
    pending_service: Optional[ServiceKey]
    pending_period: PeriodKey
    missing_slots: list[str]
    last_intent: Optional[IntentName]
    last_service: Optional[ServiceKey]
    last_period: Optional[PeriodKey]
    last_route: str
    selected_unit: Optional[str]
    turns: int


_SESSIONS: dict[int, DMSession] = {}


def _new_session(chat_id: int) -> DMSession:
    return {
        "chat_id": chat_id,
        "updated_at": time.time(),
        "awaiting": False,
        "clarify_kind": "generic",
        "pending_route": "",
        "pending_intent": None,
        "pending_service": None,
        "pending_period": "unspecified",
        "missing_slots": [],
        "last_intent": None,
        "last_service": None,
        "last_period": None,
        "last_route": "",
        "selected_unit": None,
        "turns": 0,
    }


def _purge_expired() -> None:
    now = time.time()
    expired = [chat_id for chat_id, sess in _SESSIONS.items() if (now - sess["updated_at"]) > DM_ASSISTANT_SESSION_TTL_S]
    for chat_id in expired:
        _SESSIONS.pop(chat_id, None)


def get_session(chat_id: int) -> DMSession:
    _purge_expired()
    sess = _SESSIONS.get(chat_id)
    if not sess:
        sess = _new_session(chat_id)
        _SESSIONS[chat_id] = sess
    return sess


def peek_session(chat_id: int) -> Optional[DMSession]:
    _purge_expired()
    return _SESSIONS.get(chat_id)


def clear_session(chat_id: int) -> None:
    _SESSIONS.pop(chat_id, None)


def clear_pending(chat_id: int) -> DMSession:
    sess = get_session(chat_id)
    sess["updated_at"] = time.time()
    sess["awaiting"] = False
    sess["clarify_kind"] = "generic"
    sess["pending_route"] = ""
    sess["pending_intent"] = None
    sess["pending_service"] = None
    sess["pending_period"] = "unspecified"
    sess["missing_slots"] = []
    sess["turns"] = 0
    return sess


def open_clarify(
    chat_id: int,
    *,
    clarify_kind: ClarifyKind,
    pending_route: str = "consult",
    pending_intent: Optional[IntentName] = None,
    pending_service: Optional[ServiceKey] = None,
    pending_period: PeriodKey = "unspecified",
    missing_slots: Optional[list[str]] = None,
) -> DMSession:
    sess = get_session(chat_id)
    sess["updated_at"] = time.time()
    sess["awaiting"] = True
    sess["clarify_kind"] = clarify_kind
    sess["pending_route"] = pending_route
    sess["pending_intent"] = pending_intent
    sess["pending_service"] = pending_service
    sess["pending_period"] = pending_period
    sess["missing_slots"] = list(missing_slots or [])
    sess["turns"] = min(int(sess.get("turns", 0)) + 1, DM_ASSISTANT_MAX_CLARIFY_TURNS)
    return sess


def too_many_clarify_turns(chat_id: int) -> bool:
    sess = get_session(chat_id)
    return int(sess.get("turns", 0)) >= DM_ASSISTANT_MAX_CLARIFY_TURNS


def save_last_resolution(
    chat_id: int,
    *,
    intent: Optional[IntentName] = None,
    service: Optional[ServiceKey] = None,
    period: Optional[PeriodKey] = None,
    route: str = "",
) -> DMSession:
    sess = clear_pending(chat_id)
    sess["updated_at"] = time.time()
    if intent:
        sess["last_intent"] = intent
    if service:
        sess["last_service"] = service
    if period:
        sess["last_period"] = period
    if route:
        sess["last_route"] = route
    return sess


def set_selected_unit(chat_id: int, unit_id: str) -> DMSession:
    sess = get_session(chat_id)
    sess["updated_at"] = time.time()
    sess["selected_unit"] = (unit_id or "").upper().strip() or None
    return sess


def get_selected_unit(chat_id: int) -> Optional[str]:
    sess = peek_session(chat_id)
    if not sess:
        return None
    unit = (sess.get("selected_unit") or "").upper().strip()
    return unit or None


def clear_selected_unit(chat_id: int) -> DMSession:
    sess = get_session(chat_id)
    sess["updated_at"] = time.time()
    sess["selected_unit"] = None
    return sess
