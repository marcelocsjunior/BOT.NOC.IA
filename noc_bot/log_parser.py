# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from zoneinfo import ZoneInfo

from .models import NocEvent

TZ_LOCAL = ZoneInfo("America/Sao_Paulo")

_RE_NOC = re.compile(
    r"NOC\|unit=(?P<unit>[^|]+)\|device=(?P<device>[^|]+)\|check=(?P<check>[^|]+)\|state=(?P<state>UP|DOWN)\|host=(?P<host>[^|]+)\|cid=(?P<cid>[^\s|]+)",
    re.I
)

def parse_line(line: str) -> NocEvent | None:
    if not line:
        return None
    m = _RE_NOC.search(line)
    if not m:
        return None

    ts = None
    try:
        # tenta ISO no começo da linha
        head = line.split(" ", 1)[0]
        ts = datetime.fromisoformat(head.replace("Z", "+00:00"))
    except Exception:
        ts = datetime.now(timezone.utc)

    if getattr(ts, "tzinfo", None) is None:
        ts = ts.replace(tzinfo=timezone.utc)

    return NocEvent(
        ts=ts.astimezone(timezone.utc),
        unit=m.group("unit"),
        device=m.group("device"),
        check=m.group("check"),
        state=m.group("state").upper(),
        host=m.group("host"),
        cid=m.group("cid"),
        raw=line.rstrip("\n"),
    )
