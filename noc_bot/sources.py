# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone

from .config import NOC_DB_PATH, NOC_LOG_PATH, DB_FRESHNESS_S, DB_EVENT_STALE_S, UNIT
from .db import query_rows
from .log_parser import parse_line
from .models import NocEvent, Snapshot
from .utils import is_noise_check

log = logging.getLogger(__name__)


def _to_utc(ts: str | datetime) -> datetime:
    """Normaliza ts (str ISO ou datetime) para timezone.utc."""
    if isinstance(ts, datetime):
        dt = ts
    else:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _file_mtime(path: str) -> float | None:
    try:
        return os.path.getmtime(path)
    except Exception:
        return None


def _read_last_log_ts(path: str, max_lines: int = 2000) -> datetime | None:
    """Timestamp do último evento NOC parseável no log raw."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            step = 4096
            buf = b""
            pos = size
            while pos > 0 and buf.count(b"\n") < max_lines:
                pos = max(0, pos - step)
                f.seek(pos)
                buf = f.read(size - pos) + buf
                size = pos
            lines = buf.splitlines()[-max_lines:]
        for b in reversed(lines):
            try:
                line = b.decode("utf-8", errors="replace")
            except Exception:
                continue
            ev = parse_line(line)
            if ev and ev.unit == UNIT:
                return ev.ts.astimezone(timezone.utc)
    except Exception:
        return None
    return None


def _detect_check_col() -> str:
    """Auto-detect coluna do nome do check no schema (check_name vs check)."""
    try:
        cols = query_rows("PRAGMA table_info(events);")
        names = {str(r["name"]) for r in cols}
        if "check_name" in names:
            return "check_name"
        if "check" in names:
            return '"check"'  # quoted para sqlite
    except Exception:
        pass
    return "check_name"



def _detect_raw_col() -> str:
    """Auto-detect coluna raw no schema; fallback para '' (compatível)."""
    try:
        cols = query_rows("PRAGMA table_info(events);")
        names = {str(r["name"]) for r in cols}
        if "raw" in names:
            return "raw"
    except Exception:
        pass
    return "''"

def _latest_from_log(max_tail_lines: int = 5000) -> tuple[dict[str, NocEvent], datetime | None]:
    latest: dict[str, NocEvent] = {}
    last_ts: datetime | None = None
    try:
        with open(NOC_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-max_tail_lines:]
        for line in reversed(lines):
            ev = parse_line(line)
            if not ev or ev.unit != UNIT:
                continue
            if last_ts is None:
                last_ts = ev.ts.astimezone(timezone.utc)
            if ev.check not in latest:
                latest[ev.check] = ev
            if len(latest) >= 32:
                break
    except Exception:
        return {}, _read_last_log_ts(NOC_LOG_PATH)
    return latest, last_ts or _read_last_log_ts(NOC_LOG_PATH)


def get_latest_per_check() -> tuple[dict[str, NocEvent], Snapshot]:
    """Último estado por check + snapshot (DB-first; fallback LOG se falhar/stale)."""
    last_db_ts: datetime | None = None
    latest: dict[str, NocEvent] = {}
    source = "DB"
    notes = "ok"

    check_col = _detect_check_col()

    raw_col = _detect_raw_col()

    # 1) DB-first
    try:
        rows = query_rows(
            f"SELECT ts, unit, device, {check_col} as chk, state, host, cid, {raw_col} as raw "
            f"FROM events WHERE unit=? ORDER BY ts DESC LIMIT 800",
            (UNIT,),
        )
        for r in rows:
            if last_db_ts is None:
                last_db_ts = _to_utc(r["ts"])
            ck = r["chk"]
            if ck not in latest:
                latest[ck] = NocEvent(
                    ts=_to_utc(r["ts"]),
                    unit=r["unit"],
                    device=r["device"],
                    check=ck,
                    state=r["state"],
                    host=r["host"],
                    cid=r["cid"],
                    raw=((r["raw"] if ("raw" in r.keys()) else None) or ""),
                )
    except Exception:
        source = "LOG"
        notes = "db_read_failed"
        log.warning("DB_READ_FAIL unit=%s db=%s", UNIT, NOC_DB_PATH, exc_info=True)

    # 2) LOG timestamps
    last_log_ts = _read_last_log_ts(NOC_LOG_PATH)

    now = datetime.now(timezone.utc)
    freshness_s: int | None = None
    if last_db_ts:
        freshness_s = int((now - last_db_ts).total_seconds())
    elif last_log_ts:
        freshness_s = int((now - last_log_ts).total_seconds())

    # 3) staleness: se DB parou, cai pra LOG
    db_mtime = _file_mtime(NOC_DB_PATH)
    if source == "DB":
        if db_mtime is None or (time.time() - db_mtime) > DB_FRESHNESS_S:
            if last_db_ts and (now - last_db_ts).total_seconds() > DB_EVENT_STALE_S:
                source = "LOG"
                notes = "db_stale_fallback_log"

    # 4) se fonte final for LOG, latest coerente vem do LOG
    if source == "LOG":
        latest_log, last_ts = _latest_from_log()
        if latest_log:
            latest = latest_log
        if last_ts:
            last_log_ts = last_ts
        if freshness_s is None and last_log_ts:
            freshness_s = int((now - last_log_ts).total_seconds())

    snap = Snapshot(
        source=source,
        notes=notes,
        db_path=NOC_DB_PATH,
        log_path=NOC_LOG_PATH,
        last_db_ts=last_db_ts,
        last_log_ts=last_log_ts,
        freshness_s=freshness_s,
    )
    return latest, snap


def get_latest_filtered() -> tuple[dict[str, NocEvent], Snapshot]:
    latest, snap = get_latest_per_check()
    return {k: v for k, v in (latest or {}).items() if not is_noise_check(k)}, snap


def get_last_n_events(n: int) -> tuple[list[NocEvent], Snapshot]:
    """Últimos N eventos (DB-first; fallback LOG)."""
    _, snap = get_latest_per_check()
    out: list[NocEvent] = []

    if snap.source == "DB":
        check_col = _detect_check_col()
        raw_col = _detect_raw_col()
        try:
            rows = query_rows(
                f"SELECT ts, unit, device, {check_col} as chk, state, host, cid, {raw_col} as raw "
                f"FROM events WHERE unit=? ORDER BY ts DESC LIMIT ?",
                (UNIT, n),
            )
            for r in rows:
                out.append(
                    NocEvent(
                        ts=_to_utc(r["ts"]),
                        unit=r["unit"],
                        device=r["device"],
                        check=r["chk"],
                        state=r["state"],
                        host=r["host"],
                        cid=r["cid"],
                        raw=((r["raw"] if ("raw" in r.keys()) else None) or ""),
                    )
                )
            return out, snap
        except Exception:
            log.warning("DB_READ_FAIL get_last_n_events unit=%s", UNIT, exc_info=True)

    # LOG fallback
    try:
        with open(NOC_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-5000:]
        for line in reversed(lines):
            ev = parse_line(line)
            if ev and ev.unit == UNIT:
                out.append(ev)
                if len(out) >= n:
                    break
        return out, snap
    except Exception:
        return [], snap


def get_events_window(window: str) -> tuple[list[NocEvent], Snapshot, datetime, datetime]:
    w = (window or "24h").lower()
    now = datetime.now(timezone.utc)

    if w == "7d":
        since = now - timedelta(days=7)
    elif w == "30d":
        since = now - timedelta(days=30)
    else:
        since = now - timedelta(hours=24)

    _latest, snap = get_latest_per_check()
    evs_all, _ = get_last_n_events(5000)
    evs = [e for e in evs_all if e.ts >= since]
    evs.sort(key=lambda x: x.ts)
    return evs, snap, since, now


def snapshot() -> Snapshot:
    _, snap = get_latest_per_check()
    return snap


def get_prefetch_before(window_start: datetime, check_name: str) -> NocEvent | None:
    """Último evento antes do início da janela, para cálculo de duração/uptime."""
    check_col = _detect_check_col()
    raw_col = _detect_raw_col()
    try:
        rows = query_rows(
            f"SELECT ts, unit, device, {check_col} as chk, state, host, cid, {raw_col} as raw "
            f"FROM events WHERE unit=? AND {check_col}=? AND ts < ? "
            f"ORDER BY ts DESC LIMIT 1",
            (UNIT, check_name, window_start.isoformat()),
            limit=1,
        )
        if not rows:
            return None
        r = rows[0]
        return NocEvent(
            ts=_to_utc(r["ts"]),
            unit=r["unit"],
            device=r["device"],
            check=r["chk"],
            state=r["state"],
            host=r["host"],
            cid=r["cid"],
            raw=((r["raw"] if ("raw" in r.keys()) else None) or ""),
        )
    except Exception:
        return None
