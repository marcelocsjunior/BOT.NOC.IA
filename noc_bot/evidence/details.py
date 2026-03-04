# -*- coding: utf-8 -*-
from __future__ import annotations

import re

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional

TZ_LOCAL = ZoneInfo("America/Sao_Paulo")



_LOSS_RE = re.compile(r"loss=([0-9]+(?:\.[0-9]+)?)")
_RTT_RE  = re.compile(r"rtt=([0-9]+(?:\.[0-9]+)?)")

def _fmt_num1(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")

def _metrics_part(raw: str) -> str:
    raw = raw or ""
    m_loss = _LOSS_RE.search(raw)
    m_rtt = _RTT_RE.search(raw)
    if not (m_loss or m_rtt):
        return ""
    parts = []
    if m_loss:
        try:
            parts.append(f"loss={_fmt_num1(float(m_loss.group(1)))}%")
        except Exception:
            pass
    if m_rtt:
        try:
            parts.append(f"rtt={_fmt_num1(float(m_rtt.group(1)))}ms")
        except Exception:
            pass
    return (" | " + " | ".join(parts)) if parts else ""


def _upper(s: str) -> str:
    return (s or "").upper()




def _icon(state: str) -> str:
    st = _upper(state)
    if st == "UP":
        return "🟢"
    if st == "DOWN":
        return "🔴"
    return "⚪"


def _clean_cid(cid: str) -> str:
    c = (cid or "").strip()
    for sep in (" loss=", " rtt=", "| loss=", "| rtt="):
        if sep in c:
            c = c.split(sep, 1)[0].strip()
    return c
def _to_local(dt: datetime) -> datetime:
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_LOCAL)


def iso_local(dt: datetime) -> str:
    return _to_local(dt).isoformat(timespec="seconds")


def fmt_when_short(dt: datetime, now: datetime) -> str:
    d = _to_local(dt)
    n = _to_local(now)
    if d.date() == n.date():
        return f"hoje {d:%H:%M}"
    if d.date() == (n.date() - timedelta(days=1)):
        return f"ontem {d:%H:%M}"
    return d.strftime("%d/%m %H:%M")


def build_evidence_detail_text(
    evs_svc: list,
    now: datetime,
    *,
    raw: bool,
    svc_label: str,
    window: str,
    source: str,
    max_lines: int = 80,
) -> str:
    """
    raw=False -> "Evidência completa (organizada)"
    raw=True  -> "Evidência completa (operadora)" (raw line)
    """
    title = "Evidência completa (organizada)" if not raw else "Evidência completa (operadora)"
    hdr = f"{title} — {svc_label} (janela={window} | fonte={source})"
    lines = [hdr, ""]

    if not evs_svc:
        lines.append("Sem eventos na janela.")
        return "\n".join(lines)

    # pega só as últimas N linhas (igual ao comportamento atual)
    tail = evs_svc[-max_lines:]

    for e in tail:
        ts = getattr(e, "ts", None)
        if not isinstance(ts, datetime):
            continue

        cid = _clean_cid(str(getattr(e, "cid", "-") or ""))
        raw_s = str(getattr(e, "raw", "") or "")
        # limpa ruído de testes/execuções locais
        if raw_s and ("sudo:" in raw_s.lower()):
            continue
        if cid.upper().startswith("INJECT_") or ("INJECT_$(" in raw_s):
            continue

        metrics = _metrics_part(raw_s)

        if raw:
            lines.append(
                f"{iso_local(ts)} | {getattr(e,'check','-')} | {getattr(e,'state','-')} | {getattr(e,'host','-')}{metrics} | cid={cid or '-'}"
            )
        else:
            st = _upper(str(getattr(e, 'state', '-') or '-'))
            host = str(getattr(e, 'host', '-') or '-')
            lines.append(f"{_icon(st)} {fmt_when_short(ts, now)} | {st}{metrics} | host={host}")
            lines.append(f"   cid={cid or '-'}")
    if len(evs_svc) > max_lines:
        lines.append(f"... ({len(evs_svc) - max_lines} linhas anteriores omitidas)")

    return "\n".join(lines)
