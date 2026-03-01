# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Iterable, Optional

TZ_LOCAL = ZoneInfo("America/Sao_Paulo")


def _upper(s: str) -> str:
    return (s or "").upper()


def _to_local(dt: datetime) -> datetime:
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_LOCAL)


def _is_noise_check(name: str, noise_tokens: Optional[Iterable[str]] = None) -> bool:
    n = _upper(name)
    if "SELFTEST" in n:
        return True
    for tok in (noise_tokens or []):
        t = _upper(tok)
        if t and t in n:
            return True
    return False


def filter_events(events: list, noise_tokens: Optional[Iterable[str]] = None) -> list:
    out = []
    for e in events or []:
        ck = getattr(e, "check", "") or ""
        if not _is_noise_check(ck, noise_tokens):
            out.append(e)
    return out


def filter_latest(latest: dict, noise_tokens: Optional[Iterable[str]] = None) -> dict:
    return {k: v for k, v in (latest or {}).items() if not _is_noise_check(k, noise_tokens)}


def events_for_key(events: list, key_sub: str) -> list:
    k = _upper(key_sub)
    out = []
    for e in events or []:
        ck = _upper(getattr(e, "check", ""))
        if k and k in ck:
            out.append(e)
    return out


def slice_window_from_24h(evs_24h: list, now: datetime, window: str, hours: int | None = None) -> list:
    # compat: algumas rotas antigas chamam slice_window_from_24h(..., hours=N)
    if hours is not None:
        window = f"{int(hours)}h"
    """
    Recorta uma janela dentro de 24h: ex. '24h', '12h', '6h', '3h', '2h', '1h'.
    Se vier algo fora do padrão, devolve evs_24h (fail-safe).
    """
    w = (window or "").strip().lower()
    m = re.match(r"^(\d+)\s*([hd])$", w)
    if not m:
        return evs_24h or []

    n = int(m.group(1))
    unit = m.group(2)

    if unit == "d":
        # dentro de 24h, '1d' == 24h; qualquer coisa maior mantém 24h
        return evs_24h or []

    # horas
    hours = max(1, min(24, n))
    now_l = _to_local(now)
    since = now_l - timedelta(hours=hours)

    out = []
    for e in evs_24h or []:
        ts = getattr(e, "ts", None)
        if not isinstance(ts, datetime):
            continue
        if _to_local(ts) >= since:
            out.append(e)
    return out
