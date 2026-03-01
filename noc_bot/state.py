# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

TZ_LOCAL = ZoneInfo("America/Sao_Paulo")

# tenta pegar SVCS do config (fonte de verdade do catálogo)
try:
    from .config import SVCS as _SVCS_DEFAULT  # type: ignore
except Exception:
    _SVCS_DEFAULT = {}


def _upper(s: str) -> str:
    return (s or "").upper()


def _to_local(dt):
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_LOCAL)


def _events_for_key(events: list, key_sub: str) -> list:
    k = _upper(key_sub)
    return [e for e in (events or []) if k and k in _upper(getattr(e, "check", ""))]


def _best_latest(latest: dict, key_sub: str, *, must: str | None = None, exclude: str | None = None):
    k = _upper(key_sub)
    must_u = _upper(must) if must else None
    exc_u = _upper(exclude) if exclude else None
    best = None
    for name, ev in (latest or {}).items():
        n = _upper(name)
        if k and k not in n:
            continue
        if must_u and must_u not in n:
            continue
        if exc_u and exc_u in n:
            continue
        if best is None:
            best = ev
        else:
            try:
                if getattr(ev, "ts", None) and getattr(best, "ts", None) and ev.ts > best.ts:
                    best = ev
            except Exception:
                pass
    return best


# ----------------------------
# Qualidade (labels comerciais)
# ----------------------------
# Regras acordadas no contrato de UX do DM.
QUALITY_BANDS = [
    (99.5, "Excelente"),
    (98.5, "Boa"),
    (97.0, "Aceitável"),
    (95.0, "Instável"),
    (-1e9, "Crítica"),
]


def quality_term(pct_ok: float | None) -> str:
    if pct_ok is None:
        return "N/D"
    for th, name in QUALITY_BANDS:
        if pct_ok >= th:
            return name
    return "N/D"


def is_quality_bad(term: str) -> bool:
    t = (term or "").strip()
    return t in ("Instável", "Crítica")


# ----------------------------
# EXPORTS esperados pelos handlers
# ----------------------------

def svc_events_av(events: list, svc) -> list:
    """Disponibilidade: eventos do serviço excluindo checks QUALITY."""
    key = getattr(svc, "key", "") or ""
    out = []
    for e in _events_for_key(events, key):
        if "QUALITY" not in _upper(getattr(e, "check", "")):
            out.append(e)
    return out


def svc_events_q(events: list, svc) -> list:
    """Qualidade: eventos do serviço onde o check contém QUALITY."""
    key = getattr(svc, "key", "") or ""
    out = []
    for e in _events_for_key(events, key):
        if "QUALITY" in _upper(getattr(e, "check", "")):
            out.append(e)
    return out


def is_unstable_recent(evs: list, now, hours: int = 3) -> bool:
    now_l = _to_local(now)
    if not now_l:
        return False
    since = now_l - timedelta(hours=hours)
    w = [e for e in (evs or []) if _to_local(getattr(e, "ts", None)) and _to_local(e.ts) >= since]
    if any(_upper(getattr(e, "state", "")) == "DOWN" for e in w):
        return True
    return len(w) >= 2


def latest_state_and_instability(latest: dict, evs_lookback: list, svc, now, hours: int = 3):
    # disponibilidade: pega latest do serviço excluindo QUALITY
    ev_latest = _best_latest(latest, getattr(svc, "key", ""), exclude="QUALITY")
    cur = _upper(getattr(ev_latest, "state", "") if ev_latest else "")
    unstable = is_unstable_recent(svc_events_av(evs_lookback, svc), now, hours)
    if cur == "DOWN":
        return ("Indisponível", "🔴")
    if unstable:
        return ("Instável", "⚠️")
    return ("OK", "✅")


def _normalize_svcs_and_hours(svcs, hours):
    # Se chamaram overall_state(..., hours) por engano na posição de svcs
    if isinstance(svcs, (int, float)) and (hours == 3 or hours is None):
        return (_SVCS_DEFAULT, int(svcs))
    if svcs is None:
        return (_SVCS_DEFAULT, hours)
    return (svcs, hours)


def overall_state(latest: dict, evs_24h: list, now, svcs=None, hours: int = 3) -> str:
    svcs, hours = _normalize_svcs_and_hours(svcs, hours)
    icons = []
    for svc in (svcs or {}).values():
        _, icon = latest_state_and_instability(latest, evs_24h, svc, now, hours)
        icons.append(icon)
    if "🔴" in icons:
        return "down"
    if "⚠️" in icons:
        return "warn"
    return "ok"


def choose_focus_service(latest: dict, evs_lookback: list, now, svcs=None, hours: int = 3):
    svcs, hours = _normalize_svcs_and_hours(svcs, hours)
    if not svcs:
        return None
    order_codes = ["L1", "L2", "TEL", "ESC"]
    order = [svcs[c] for c in order_codes if c in svcs] or list(svcs.values())

    for svc in order:
        ev = _best_latest(latest, getattr(svc, "key", ""), exclude="QUALITY")
        if _upper(getattr(ev, "state", "")) == "DOWN":
            return svc
    for svc in order:
        if is_unstable_recent(svc_events_av(evs_lookback, svc), now, hours):
            return svc
    return None
