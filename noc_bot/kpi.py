# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import datetime, timezone
from collections import defaultdict

from .models import NocEvent, Kpi
from .config import KNOWN_CHECKS, UNIT, severity_label
from .utils import iso_local
from .sources import get_prefetch_before

def _calc_for_check(events: list[NocEvent], window_start: datetime, window_end: datetime, pre: NocEvent | None) -> Kpi:
    events = sorted(events, key=lambda e: e.ts)

    last_state = pre.state if pre else None
    last_change = pre.ts if pre else None

    t_cursor = window_start
    up_s = 0
    down_s = 0
    flaps = 0

    def add_slice(state: str | None, dt_s: int):
        nonlocal up_s, down_s
        if not state or dt_s <= 0:
            return
        if state == "UP":
            up_s += dt_s
        elif state == "DOWN":
            down_s += dt_s

    for ev in events:
        t_ev = ev.ts.astimezone(timezone.utc)
        if t_ev < window_start:
            last_state = ev.state
            last_change = ev.ts
            continue
        if t_ev > window_end:
            break

        dt = int((t_ev - t_cursor).total_seconds())
        add_slice(last_state, dt)

        if last_state and ev.state != last_state:
            flaps += 1
            last_change = ev.ts
        elif last_state is None:
            last_change = ev.ts

        last_state = ev.state
        t_cursor = t_ev

    dt_end = int((window_end - t_cursor).total_seconds())
    add_slice(last_state, dt_end)

    ck = events[-1].check if events else (pre.check if pre else "UNKNOWN")
    return Kpi(
        window_label="",
        check=ck,
        up_s=up_s,
        down_s=down_s,
        flaps=flaps,
        last_state=last_state,
        last_change=last_change
    )

def compute_kpis(events: list[NocEvent], window: str, since: datetime, now: datetime) -> list[Kpi]:
    by_check: dict[str, list[NocEvent]] = defaultdict(list)
    for e in events:
        by_check[e.check].append(e)

    kpis: list[Kpi] = []
    for check, evs in by_check.items():
        pre = get_prefetch_before(since, check)
        kpi = _calc_for_check(evs, since, now, pre)
        kpi = Kpi(window_label=window, check=kpi.check, up_s=kpi.up_s, down_s=kpi.down_s, flaps=kpi.flaps, last_state=kpi.last_state, last_change=kpi.last_change)
        kpis.append(kpi)

    kpis.sort(key=lambda k: (k.down_s, k.flaps), reverse=True)
    return kpis

def deterministic_recommendation(kpis: list[Kpi], facts: dict, window: str) -> str:
    if not kpis:
        return "Recomendações: sem dados na janela."

    worst = kpis[0]
    sev = facts.get("severity_by_check", {}).get(worst.check, "SEV4")
    return f"Recomendações: priorizar {worst.check} ({sev}). Se instabilidade recorrente: aplicar debounce/cooldown na fonte (Netwatch)."

def build_noc_facts(latest: dict) -> dict:
    wan_m = None
    wan_v = None

    for ck, ev in latest.items():
        u = (ck or "").upper()
        if "MUNDIVOX" in u:
            wan_m = ev.state
        if "VALENET" in u:
            wan_v = ev.state

    sev_by = {}
    for ck, ev in latest.items():
        sev_by[ck] = severity_label(ck, wan_m, wan_v)

    return {
        "unit": UNIT,
        "wan_mundivox": wan_m,
        "wan_valenet": wan_v,
        "severity_by_check": sev_by,
    }

def format_status(latest: dict) -> str:
    lines = [f"Status {UNIT} (técnico)", ""]
    for ck, ev in sorted(latest.items(), key=lambda x: x[0]):
        lines.append(f"- {ck}: {ev.state} (last {iso_local(ev.ts)})")
    return "\n".join(lines)

def format_kpis(kpis: list[Kpi], window: str) -> str:
    lines = [f"KPI {UNIT} — janela {window}", ""]
    for k in kpis:
        lines.append(f"- {k.check}: down={k.down_s}s flaps={k.flaps} last={k.last_state}")
    return "\n".join(lines)
