# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class NocEvent:
    ts: datetime
    unit: str
    device: str
    check: str
    state: str
    host: str
    cid: str
    raw: str = ""

@dataclass(frozen=True)
class Snapshot:
    source: str
    notes: str
    db_path: str
    log_path: str
    last_db_ts: datetime | None
    last_log_ts: datetime | None
    freshness_s: int | None

@dataclass(frozen=True)
class Kpi:
    window_label: str
    check: str
    up_s: int
    down_s: int
    flaps: int
    last_state: str | None
    last_change: datetime | None
