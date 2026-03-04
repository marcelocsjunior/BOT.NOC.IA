# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import List, Tuple, Optional

from telegram import InlineKeyboardMarkup

from ..telegram_ui import kb_evidence_actions
from ..state import latest_state_and_instability, is_unstable_recent

try:
    from ..config import UNIT  # type: ignore
except Exception:
    UNIT = os.getenv("NOC_UNIT", "UN1") or "UN1"

TZ_LOCAL = ZoneInfo("America/Sao_Paulo")
MAX_CIDS = int(os.getenv("NOC_MAX_CIDS", "5") or "5")
UNSTABLE_HOURS = int(os.getenv("NOC_UNSTABLE_HOURS", "3") or "3")


# VPN: o coletor roda em UN1, mas a evidência precisa ficar "produto".
VPN_UNIT_LABELS = {
    "VPN_UN2": "UN2 — Barreiro",
    "VPN_UN3": "UN3 — Alípio de Mello",
}


def _vpn_monitored_label(svc) -> Optional[str]:
    k = _upper(getattr(svc, "key", "") or "")
    return VPN_UNIT_LABELS.get(k)


def _upper(s: str) -> str:
    return (s or "").upper()


def _to_local(dt: datetime) -> datetime:
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_LOCAL)


def _fmt_when_abs(dt: datetime) -> str:
    d = _to_local(dt)
    return d.strftime("%d/%m/%Y %H:%M")


def _fmt_when_short(dt: datetime, now: datetime) -> str:
    d = _to_local(dt)
    n = _to_local(now)
    if d.date() == n.date():
        return f"hoje {d:%H:%M}"
    if d.date() == (n.date() - timedelta(days=1)):
        return f"ontem {d:%H:%M}"
    return d.strftime("%d/%m %H:%M")


def _fmt_dur(seconds: Optional[float]) -> str:
    if seconds is None:
        return "-"
    s = int(max(0, seconds))
    if s < 60:
        return f"{s}s"
    m, ss = divmod(s, 60)
    if m < 60:
        return f"{m}m{ss:02d}s"
    h, mm = divmod(m, 60)
    return f"{h}h{mm:02d}m"


def _dur_bucket_pt(seconds: Optional[float]) -> str:
    if seconds is None:
        return "duração N/D"
    s = float(seconds)
    if s < 30:
        return "blip (<30s)"
    if s < 120:
        return "curto (30s–2m)"
    if s < 300:
        return "médio (2–5m)"
    if s < 900:
        return "alto (5–15m)"
    if s < 3600:
        return "crítico (15–60m)"
    return "severo (>1h)"


def _events_for_key(events: list, key_sub: str) -> list:
    k = _upper(key_sub)
    return [e for e in (events or []) if k and k in _upper(getattr(e, "check", ""))]


def _events_with_state(events: list, state: str) -> list:
    st = _upper(state)
    return [e for e in (events or []) if _upper(getattr(e, "state", "")) == st]


def _unique_recent_cids(events: list, limit: int = 5) -> Tuple[List[str], bool]:
    out: List[str] = []
    seen = set()
    for e in reversed(sorted(events or [], key=lambda x: getattr(x, "ts", datetime.min.replace(tzinfo=timezone.utc)))):
        cid = getattr(e, "cid", None) or "-"
        if cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
        if len(out) >= limit:
            break
    has_more = len(seen) > len(out)
    return out, has_more


def _down_occurrences_with_dur(evs: list) -> List[Tuple[object, Optional[float]]]:
    evs = sorted(evs or [], key=lambda x: getattr(x, "ts", datetime.min.replace(tzinfo=timezone.utc)))
    cur_down = None
    out: List[Tuple[object, Optional[float]]] = []
    for e in evs:
        st = _upper(getattr(e, "state", ""))
        if st == "DOWN" and cur_down is None:
            cur_down = e
            continue
        if st == "UP" and cur_down is not None:
            try:
                dur = (e.ts - cur_down.ts).total_seconds()
            except Exception:
                dur = None
            out.append((cur_down, dur))
            cur_down = None
    if cur_down is not None:
        out.append((cur_down, None))
    return out



def _clean_cid(cid: str) -> str:
    """Remove sujeira de métricas grudadas no cid (loss/rtt)."""
    c = (cid or "").strip()
    for sep in (" loss=", " rtt=", "| loss=", "| rtt="):
        if sep in c:
            c = c.split(sep, 1)[0].strip()
    return c

def build_evidence_compact(latest: dict, evs_24h: list, svc, now, window: str, dm: bool = False, source: str = "-", notes: str = "") -> Tuple[str, InlineKeyboardMarkup]:
    state_h, _ = latest_state_and_instability(latest, evs_24h, svc, now, hours=UNSTABLE_HOURS)
    evs_svc_all = _events_for_key(evs_24h, svc.key)
    evs_svc_down = _events_with_state(evs_svc_all, "DOWN")

    occ_all = _down_occurrences_with_dur(evs_svc_all)
    occ_recent = list(reversed(occ_all))[:3]
    osc_24h = len(occ_all)

    cids_down, has_more_down = _unique_recent_cids(evs_svc_down, limit=MAX_CIDS)
    cids_clean = []
    seen = set()
    for x in (cids_down or []):
        cx = _clean_cid(x)
        if not cx or cx in seen:
            continue
        seen.add(cx)
        cids_clean.append(cx)


    src = (source or "-").strip()
    nts = (notes or "").strip()
    src_disp = src
    if src.upper() == "LOG" and nts and nts.lower() != "ok":
        src_disp = f"LOG ⚠️ {nts}"
    mon = _vpn_monitored_label(svc)
    if mon:
        lines = [
            f"📎 Evidência — {svc.label}",
            f"Unidade monitorada: {mon}",
            f"Coletor: {UNIT}",
            f"Janela: últimas {window}",
            f"📦 Fonte: {src_disp}",
            f"Estado atual: {state_h}",
        ]
    else:
        lines = [
            f"📎 Evidência — {svc.label} ({UNIT})",
            f"Janela: últimas {window}",
            f"📦 Fonte: {src_disp}",
            f"Estado atual: {state_h}",
        ]

    if not dm:
        lines.append(f"Oscilações (24h): {osc_24h}")

    if occ_recent:
        lines.append("Ocorrências recentes:")
        for d, dur in occ_recent:
            if dm:
                lines.append(f"- {_fmt_when_short(d.ts, now)} — {_dur_bucket_pt(dur)}")
            else:
                lines.append(f"- {_fmt_when_short(d.ts, now)} — Indisponível {_fmt_dur(dur)} | cid={getattr(d, 'cid', '-')}")
        if (not dm) and (len(occ_all) > len(occ_recent)):
            lines.append("(demais disponíveis)")
    else:
        lines.append("Ocorrências: nenhuma na janela.")
        if (not dm) and evs_svc_all:
            last = sorted(evs_svc_all, key=lambda x: x.ts)[-1]
            lines.append(f"Último evento: {_fmt_when_short(last.ts, now)} | {_upper(getattr(last,'state','-'))} | cid={getattr(last,'cid','-')}")

    if dm:
        lines.append('IDs/Prova: use "Texto pronto (operadora)" (inclui 5 CIDs).')
    else:
        cid_line = ", ".join(cids_down) if cids_down else "-"
        if has_more_down:
            cid_line += " (há mais)"
        lines.append(f"CIDs (5 mais recentes): {cid_line}")

    return "\n".join(lines), kb_evidence_actions(svc.code, window)


def build_ticket_text(latest: dict, evs_24h: list, svc, now) -> str:
    state_h, _ = latest_state_and_instability(latest, evs_24h, svc, now, hours=UNSTABLE_HOURS)
    evs_svc_all = _events_for_key(evs_24h, svc.key)
    evs_svc_down = _events_with_state(evs_svc_all, "DOWN")

    occ_all = _down_occurrences_with_dur(evs_svc_all)
    occ_recent = list(reversed(occ_all))[:3]
    osc_24h = len(occ_all)

    subj_ts = occ_recent[0][0].ts if occ_recent else now
    subj_when = _fmt_when_abs(subj_ts)

    unstable_now = is_unstable_recent(evs_svc_all, now, hours=UNSTABLE_HOURS)
    instab_str = f"Instabilidade recente: últimas {UNSTABLE_HOURS}h" if unstable_now else f"Instabilidade recente: não detectada nas últimas {UNSTABLE_HOURS}h"

    cids_down, has_more_down = _unique_recent_cids(evs_svc_down, limit=MAX_CIDS)
    cids_clean = []
    seen = set()
    for x in (cids_down or []):
        cx = _clean_cid(x)
        if not cx or cx in seen:
            continue
        seen.add(cx)
        cids_clean.append(cx)

    last_bucket = _dur_bucket_pt(occ_recent[0][1]) if occ_recent else "-"

    mon = _vpn_monitored_label(svc)
    if mon:
        lines = [
            f"Assunto: Indisponibilidade/Instabilidade — {svc.subject} — {mon} — {subj_when} (BRT)",
            f"Unidade monitorada: {mon}",
            f"Coletor: {UNIT}",
            f"Serviço: {svc.subject}",
            f"Janela analisada: últimas 24h | {instab_str}",
            f"Estado atual: {state_h}",
            f"Resumo: {osc_24h} oscilações/24h; última ocorrência: {last_bucket}.",
            "Ocorrências (mais recentes):",
        ]
    else:
        lines = [
            f"Assunto: Indisponibilidade/Instabilidade — {svc.subject} — {UNIT} — {subj_when} (BRT)",
            f"Unidade: {UNIT}",
            f"Serviço: {svc.subject}",
            f"Janela analisada: últimas 24h | {instab_str}",
            f"Estado atual: {state_h}",
            f"Resumo: {osc_24h} oscilações/24h; última ocorrência: {last_bucket}.",
            "Ocorrências (mais recentes):",
        ]

    if occ_recent:
        for i, (d, dur) in enumerate(occ_recent, start=1):
            lines.append(f"{i}) {_fmt_when_abs(d.ts)} — {_dur_bucket_pt(dur)}")
        if len(occ_all) > len(occ_recent):
            lines.append("(demais disponíveis)")
    else:
        lines.append("Nenhuma ocorrência na janela de 24h.")
        if evs_svc_all:
            last = sorted(evs_svc_all, key=lambda x: x.ts)[-1]
            lines.append(f"Último evento observado: {_fmt_when_abs(last.ts)} — {_upper(getattr(last,'state','-'))} — cid={getattr(last,'cid','-')}")

    lines += [
        f"Evidências (CIDs DOWN — {MAX_CIDS} mais recentes):",
        *( [f"- {c}" for c in cids_clean] if cids_clean else ["- -"] ),
        *( ["(há mais disponíveis)"] if has_more_down else [] ),
        "Solicitação: verificar instabilidade/rota/serviço e retornar causa, ações corretivas e previsão.",
    ]
    return "\n".join(lines)
