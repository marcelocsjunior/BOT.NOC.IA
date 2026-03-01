# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
import socket
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .config import TZ_LOCAL, NOISE_TOKENS

def hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"

def clamp(n: int, a: int, b: int) -> int:
    return max(a, min(b, n))

def iso_local(dt) -> str:
    if not dt:
        return "-"
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_LOCAL).strftime("%Y-%m-%d %H:%M:%S%z")

def strip_mention(text: str, bot_username: str | None) -> str:
    if not text:
        return ""
    if not bot_username:
        return text
    return re.sub(rf"@{re.escape(bot_username)}\b", "", text, flags=re.I).strip()

def is_mention_or_reply(update, bot_id: int, bot_username: str | None) -> bool:
    msg = getattr(update, "effective_message", None)
    if not msg:
        return False

    if getattr(msg, "reply_to_message", None):
        replied = msg.reply_to_message
        from_user = getattr(replied, "from_user", None)
        if from_user and getattr(from_user, "id", None) == bot_id:
            return True

    txt = getattr(msg, "text", "") or ""
    if bot_username and re.search(rf"@{re.escape(bot_username)}\b", txt, flags=re.I):
        return True

    entities = getattr(msg, "entities", None) or []
    for ent in entities:
        if getattr(ent, "type", "") == "mention":
            return True
    return False

def split_telegram_chunks(text: str, limit: int = 3900) -> list[str]:
    if not text:
        return [""]
    out, s = [], text
    while len(s) > limit:
        cut = s.rfind("\n", 0, limit)
        if cut < 0:
            cut = limit
        out.append(s[:cut].rstrip("\n"))
        s = s[cut:].lstrip("\n")
    out.append(s)
    return out


# =====================================================================================
# Helpers NOC (centralizados) — usados por handlers, evidências e painéis.
# =====================================================================================

def upper(s: str) -> str:
    return (s or "").upper()


def to_local(dt):
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_LOCAL)


def is_noise_check(name: str) -> bool:
    n = upper(name)
    if "SELFTEST" in n:
        return True
    return any(tok in n for tok in NOISE_TOKENS)


def filter_latest(latest: dict) -> dict:
    return {k: v for k, v in (latest or {}).items() if not is_noise_check(k)}


def filter_events(events: list) -> list:
    return [e for e in (events or []) if not is_noise_check(getattr(e, "check", ""))]


def fmt_when_short(ts, now) -> str:
    ts_l = to_local(ts)
    now_l = to_local(now)
    if not ts_l or not now_l:
        return "-"
    d_ts, d_now = ts_l.date(), now_l.date()
    if d_ts == d_now:
        return ts_l.strftime("%H:%M")
    if d_ts == (d_now - timedelta(days=1)):
        return "ontem " + ts_l.strftime("%H:%M")
    return ts_l.strftime("%d/%m %H:%M")


def fmt_when_abs(ts) -> str:
    ts_l = to_local(ts)
    return ts_l.strftime("%d/%m/%Y %H:%M") if ts_l else "-"


def fmt_dur(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    s = int(round(seconds))
    if s < 0:
        return "-"
    if s < 60:
        return f"~{s}s"
    m, s2 = divmod(s, 60)
    if m < 60:
        return f"~{m}m{s2:02d}s"
    h, m2 = divmod(m, 60)
    return f"~{h}h{m2:02d}m"


def dur_bucket_pt(seconds: float | None) -> str:
    if seconds is None:
        return "em andamento"
    s = int(round(seconds))
    if s < 60:
        return "blip"
    if s < 300:
        return "queda curta"
    if s < 900:
        return "queda breve"
    if s < 1800:
        return "queda moderada"
    return "queda prolongada"


def events_match(evs: list, include: str, *, must: str | None = None, exclude: str | None = None) -> list:
    inc = upper(include)
    must_u = upper(must) if must else None
    exc_u = upper(exclude) if exclude else None
    out = []
    for e in evs or []:
        ck = upper(getattr(e, "check", ""))
        if inc not in ck:
            continue
        if must_u and must_u not in ck:
            continue
        if exc_u and exc_u in ck:
            continue
        out.append(e)
    return out


def best_latest(latest: dict, include: str, *, must: str | None = None, exclude: str | None = None):
    inc = upper(include)
    must_u = upper(must) if must else None
    exc_u = upper(exclude) if exclude else None
    best = None
    for name, ev in (latest or {}).items():
        n = upper(name)
        if inc not in n:
            continue
        if must_u and must_u not in n:
            continue
        if exc_u and exc_u in n:
            continue
        if best is None or (getattr(ev, "ts", None) and getattr(best, "ts", None) and ev.ts > best.ts):
            best = ev
    return best


def events_with_state(evs: list, state: str) -> list:
    st = upper(state)
    return [e for e in (evs or []) if upper(getattr(e, "state", "")) == st]


def down_occurrences_with_dur(evs: list):
    if not evs:
        return []
    evs_sorted = sorted(evs, key=lambda x: x.ts)
    out = []
    open_down = None
    for e in evs_sorted:
        st = upper(getattr(e, "state", ""))
        if st == "DOWN":
            if open_down is None:
                open_down = e
            continue
        if st == "UP" and open_down is not None:
            dur = (e.ts - open_down.ts).total_seconds() if getattr(e, "ts", None) and getattr(open_down, "ts", None) else None
            out.append((open_down, dur))
            open_down = None
    if open_down is not None:
        out.append((open_down, None))
    return out


def unique_recent_cids(evs: list, limit: int = 5):
    seen, cids = set(), []
    for e in sorted(evs or [], key=lambda x: x.ts, reverse=True):
        cid = getattr(e, "cid", None) or ""
        if not cid or cid in seen:
            continue
        seen.add(cid)
        cids.append(cid)
        if len(cids) >= limit:
            break
    all_unique = len({(getattr(e, "cid", "") or "") for e in (evs or []) if (getattr(e, "cid", "") or "")})
    return cids, (all_unique > len(cids))


def is_unstable_recent(evs: list, now, hours: int = 3) -> bool:
    now_l = to_local(now)
    if not now_l:
        return False
    since = now_l - timedelta(hours=hours)
    recent = [e for e in (evs or []) if to_local(getattr(e, "ts", None)) and to_local(e.ts) >= since]
    if len(recent) < 3:
        return False
    changes = 0
    last = None
    for e in sorted(recent, key=lambda x: x.ts):
        st = upper(getattr(e, "state", ""))
        if last is not None and st != last:
            changes += 1
        last = st
    return changes >= 2


def slice_window_from_24h(evs_24h: list, now, window: str, *, hours: int = 3) -> list:
    now_l = to_local(now)
    if window == "3h" and now_l:
        since = now_l - timedelta(hours=hours)
        return [e for e in (evs_24h or []) if to_local(e.ts) and to_local(e.ts) >= since]
    return evs_24h or []
