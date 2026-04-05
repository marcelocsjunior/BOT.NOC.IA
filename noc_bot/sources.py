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


def _resolve_unit(unit: str | None = None) -> str:
    value = (unit or UNIT or "UN1").upper().strip()
    return value or "UN1"


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


def _read_last_log_ts(path: str, max_lines: int = 2000, unit: str | None = None) -> datetime | None:
    """Timestamp do último evento NOC parseável no log raw."""
    target_unit = _resolve_unit(unit)
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
            if ev and ev.unit == target_unit:
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
            return '"check"'
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


def _latest_from_log(max_tail_lines: int = 5000, unit: str | None = None) -> tuple[dict[str, NocEvent], datetime | None]:
    target_unit = _resolve_unit(unit)
    latest: dict[str, NocEvent] = {}
    last_ts: datetime | None = None
    try:
        with open(NOC_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-max_tail_lines:]
        for line in reversed(lines):
            ev = parse_line(line)
            if not ev or ev.unit != target_unit:
                continue
            if last_ts is None:
                last_ts = ev.ts.astimezone(timezone.utc)
            if ev.check not in latest:
                latest[ev.check] = ev
            if len(latest) >= 32:
                break
    except Exception:
        return {}, _read_last_log_ts(NOC_LOG_PATH, unit=target_unit)
    return latest, last_ts or _read_last_log_ts(NOC_LOG_PATH, unit=target_unit)


def get_latest_per_check(unit: str | None = None) -> tuple[dict[str, NocEvent], Snapshot]:
    """Último estado por check + snapshot (DB-first; fallback LOG se falhar/stale)."""
    target_unit = _resolve_unit(unit)
    last_db_ts: datetime | None = None
    latest: dict[str, NocEvent] = {}
    source = "DB"
    notes = "ok"

    check_col = _detect_check_col()
    raw_col = _detect_raw_col()

    try:
        rows = query_rows(
            f"SELECT ts, unit, device, {check_col} as chk, state, host, cid, {raw_col} as raw "
            f"FROM events WHERE unit=? ORDER BY ts DESC LIMIT 800",
            (target_unit,),
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
        log.warning("DB_READ_FAIL unit=%s db=%s", target_unit, NOC_DB_PATH, exc_info=True)

    last_log_ts = _read_last_log_ts(NOC_LOG_PATH, unit=target_unit)

    now = datetime.now(timezone.utc)
    freshness_s: int | None = None
    if last_db_ts:
        freshness_s = int((now - last_db_ts).total_seconds())
    elif last_log_ts:
        freshness_s = int((now - last_log_ts).total_seconds())

    db_mtime = _file_mtime(NOC_DB_PATH)
    if source == "DB":
        if db_mtime is None or (time.time() - db_mtime) > DB_FRESHNESS_S:
            if last_db_ts and (now - last_db_ts).total_seconds() > DB_EVENT_STALE_S:
                source = "LOG"
                notes = "db_stale_fallback_log"

    if source == "LOG":
        latest_log, last_ts = _latest_from_log(unit=target_unit)
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


def get_latest_filtered(unit: str | None = None) -> tuple[dict[str, NocEvent], Snapshot]:
    latest, snap = get_latest_per_check(unit=unit)
    return {k: v for k, v in (latest or {}).items() if not is_noise_check(k)}, snap


def get_last_n_events(n: int, unit: str | None = None) -> tuple[list[NocEvent], Snapshot]:
    """Últimos N eventos (DB-first; fallback LOG)."""
    target_unit = _resolve_unit(unit)
    _, snap = get_latest_per_check(unit=target_unit)
    out: list[NocEvent] = []

    if snap.source == "DB":
        check_col = _detect_check_col()
        raw_col = _detect_raw_col()
        try:
            rows = query_rows(
                f"SELECT ts, unit, device, {check_col} as chk, state, host, cid, {raw_col} as raw "
                f"FROM events WHERE unit=? ORDER BY ts DESC LIMIT ?",
                (target_unit, n),
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
            log.warning("DB_READ_FAIL get_last_n_events unit=%s", target_unit, exc_info=True)

    try:
        with open(NOC_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-5000:]
        for line in reversed(lines):
            ev = parse_line(line)
            if ev and ev.unit == target_unit:
                out.append(ev)
                if len(out) >= n:
                    break
        return out, snap
    except Exception:
        return [], snap


def get_events_window(window: str, unit: str | None = None) -> tuple[list[NocEvent], Snapshot, datetime, datetime]:
    w = (window or "24h").lower()
    now = datetime.now(timezone.utc)

    if w == "7d":
        since = now - timedelta(days=7)
    elif w == "30d":
        since = now - timedelta(days=30)
    else:
        since = now - timedelta(hours=24)

    target_unit = _resolve_unit(unit)
    _latest, snap = get_latest_per_check(unit=target_unit)
    evs_all, _ = get_last_n_events(5000, unit=target_unit)
    evs = [e for e in evs_all if e.ts >= since]
    evs.sort(key=lambda x: x.ts)
    return evs, snap, since, now


def snapshot(unit: str | None = None) -> Snapshot:
    _, snap = get_latest_per_check(unit=unit)
    return snap


def get_prefetch_before(window_start: datetime, check_name: str, unit: str | None = None) -> NocEvent | None:
    """Último evento antes do início da janela, para cálculo de duração/uptime."""
    target_unit = _resolve_unit(unit)
    check_col = _detect_check_col()
    raw_col = _detect_raw_col()
    try:
        rows = query_rows(
            f"SELECT ts, unit, device, {check_col} as chk, state, host, cid, {raw_col} as raw "
            f"FROM events WHERE unit=? AND {check_col}=? AND ts < ? "
            f"ORDER BY ts DESC LIMIT 1",
            (target_unit, check_name, window_start.isoformat()),
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
