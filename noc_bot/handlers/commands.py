# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from ..config import (
    BOT_VERSION,
    BUILD_ID,
    UNIT,
    TIMELINE_DEFAULT_N,
    MAX_TIMELINE_N,
    SVCS,
    Svc,
)
from ..utils import (
    hostname,
    clamp,
    iso_local,
    filter_latest,
    filter_events,
    upper,
    to_local,
    fmt_when_short,
    fmt_when_abs,
    fmt_dur,
    dur_bucket_pt,
    events_with_state,
    down_occurrences_with_dur,
    unique_recent_cids,
    is_unstable_recent,
    slice_window_from_24h,
    split_telegram_chunks,
)
from ..sources import snapshot, get_latest_filtered, get_last_n_events, get_events_window
from ..kpi import compute_kpis, deterministic_recommendation, build_noc_facts
from ..ai_client import ai_interpret
from ..telegram_ui import (
    build_dm_keyboard,
    build_dm_home_keyboard,
    build_dm_unit_vpn_keyboard,
    build_group_keyboard,
    kb_evidence_menu,
    kb_evidence_actions,
)
from ..state import (
    overall_state,
    choose_focus_service,
    latest_state_and_instability,
    svc_events_av,
    svc_events_q,
)
from ..ui.panels import (
    build_dm_panel_un1_v2,
    build_dm_followup_block,
    build_dm_availability_today,
    build_dm_quality_today,
    build_dm_home_multiunit,
    build_dm_unit_vpn,
)
from ..evidence.builder import build_evidence_compact, build_ticket_text
from ..evidence.details import build_evidence_detail_text


log = logging.getLogger(__name__)

TELEGRAM_SAFE = 3900
UNSTABLE_HOURS = 3
MAX_CIDS = 5

EVIDENCE_TRIGGERS = ("evidencia", "evidência", "evidências", "prova", "provas")




def _dm_natural_examples() -> str:
    return (
        'Exemplos DM: "telefone ok aí?" | "teve problema hoje?" | '
        '"me manda a evidência da telefonia" | "qual é o site do speed test?"'
    )

# =====================================================================================
# Low-level helpers (chat vs DM)
# =====================================================================================

def _is_dm(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and getattr(chat, "type", "") == "private")


def _kb(update: Update):
    return build_dm_keyboard() if _is_dm(update) else build_group_keyboard()


def _split(text: str) -> list[str]:
    try:
        return split_telegram_chunks(text or "", limit=TELEGRAM_SAFE)
    except Exception:
        return [text or ""]


async def _send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None):
    chat = update.effective_chat
    if not chat:
        return
    chunks = _split(text)
    for i, part in enumerate(chunks):
        rm = reply_markup if (i == len(chunks) - 1) else None
        await context.bot.send_message(
            chat_id=chat.id,
            text=part,
            reply_markup=rm,
            disable_web_page_preview=True,
        )


async def _send_dm_hub(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None):
    """DM: tenta editar a mesma mensagem quando vier de callback."""
    if not _is_dm(update):
        await _send(update, context, text, reply_markup=reply_markup)
        return

    q = update.callback_query
    if q and text and len(text) <= TELEGRAM_SAFE:
        try:
            await q.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
            return
        except BadRequest as e:
            # evita spam: clique repetido no mesmo botão pode gerar "Message is not modified"
            if "Message is not modified" in str(e):
                return
            pass
        except Exception:
            pass

    await _send(update, context, text, reply_markup=reply_markup)


# =====================================================================================
# Detectores
# =====================================================================================

def detect_service_from_text(text: str) -> Optional[str]:
    t = (text or "").lower()
    for code, svc in SVCS.items():
        for a in svc.aliases:
            if a in t:
                return code
    return None


def detect_window_override(text: str) -> Optional[str]:
    t = (text or "").lower()
    if "3h" in t or "3 h" in t or "3 horas" in t:
        return "3h"
    if "24h" in t or "24 h" in t or "24 horas" in t:
        return "24h"
    return None


def _choose_window_auto_24h(evs_24h: list, svc: Svc, now) -> str:
    # 3h só quando houver instabilidade recente (QUALITY quando aplicável)
    q = svc_events_q(evs_24h, svc)
    probe = q if q else svc_events_av(evs_24h, svc)
    return "3h" if is_unstable_recent(probe, now, hours=UNSTABLE_HOURS) else "24h"


# =====================================================================================
# /where (baseline: BOT_VERSION|build + BUILD_ID + SOURCE/freshness/paths)
# =====================================================================================

def _version_with_build() -> str:
    if "|build=" in (BOT_VERSION or ""):
        return BOT_VERSION
    if BUILD_ID:
        return f"{BOT_VERSION}|build={BUILD_ID}"
    return BOT_VERSION


async def cmd_where(update: Update, context: ContextTypes.DEFAULT_TYPE):
    snap = snapshot()
    ver = _version_with_build()
    txt = (
        f"BOT_VERSION={ver}\n"
        f"BUILD_ID={BUILD_ID or '-'}\n"
        f"HOST={hostname()}\n"
        f"UNIT={UNIT}\n"
        f"SOURCE={snap.source} ({snap.notes})\n"
        f"DB={snap.db_path}\n"
        f"LOG={snap.log_path}\n"
        f"last_db_ts={iso_local(snap.last_db_ts) if snap.last_db_ts else '-'}\n"
        f"last_log_ts={iso_local(snap.last_log_ts) if snap.last_log_ts else '-'}\n"
        f"freshness_s={snap.freshness_s if snap.freshness_s is not None else '-'}\n"
    )
    if _is_dm(update):
        await _send_dm_hub(update, context, txt, reply_markup=_kb(update))
    else:
        await _send(update, context, txt, reply_markup=_kb(update))


# =====================================================================================
# /help
# =====================================================================================

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "ALTIS — supervisão tecnológica com IA integrada\n"
        "/where — diagnóstico da fonte e do runtime\n"
        "/status — status (grupo=técnico | DM=supervisão)\n"
        "/timeline [N] — últimos N eventos\n"
        "/analyze [24h|7d|30d] — KPI + recomendação (determinístico)\n"
        "/atendimento — triagem 2h (DM)\n\n"
        "DM híbrida do ALTIS: você pode falar naturalmente.\n"
        f"{_dm_natural_examples()}\n"
    )
    await _send(update, context, txt, reply_markup=_kb(update))


# =====================================================================================
# /status
# =====================================================================================

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/status no DM = Torre de Controle (Agora)."""
    if _is_dm(update):
        await cmd_supervisor_now(update, context, user_text="status")
        return

    latest, _snap = get_latest_filtered()
    from ..kpi import format_status

    txt = format_status(latest)
    await _send(update, context, txt, reply_markup=_kb(update))


# =====================================================================================
# /timeline
# =====================================================================================

async def cmd_timeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    n = TIMELINE_DEFAULT_N
    if context.args:
        try:
            n = int(context.args[0])
        except Exception:
            n = TIMELINE_DEFAULT_N
    n = clamp(n, 1, MAX_TIMELINE_N)

    evs_raw, snap = get_last_n_events(n)
    evs = filter_events(evs_raw)

    lines = [f"Timeline {UNIT} — últimos {len(evs)} (fonte={snap.source})", ""]
    for e in evs:
        lines.append(f"{iso_local(e.ts)} | {e.check} | {e.state} | {e.host} | cid={e.cid}")
    # UX: timeline antigo->recente (mais novo perto do teclado)
    if len(lines) > 1:
        lines = [lines[0]] + list(reversed(lines[1:]))
    await _send(update, context, "\n".join(lines), reply_markup=_kb(update))


# =====================================================================================
# /analyze
# =====================================================================================

def _window_from_update_or_args(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    if context.args:
        w = (context.args[0] or "").strip().lower()
        if w in ("24h", "7d", "30d"):
            return w
    txt = (getattr(update.effective_message, "text", "") or "").lower()
    m = re.search(r"\b(24h|7d|30d)\b", txt)
    if m:
        return m.group(1)
    if "semana" in txt or "7 dias" in txt:
        return "7d"
    return "24h"


async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    window = _window_from_update_or_args(update, context)
    t0 = time.monotonic()

    events_raw, snap, since, now = get_events_window(window)
    events = filter_events(events_raw)

    kpis = compute_kpis(events, window, since, now)
    latest, _ = get_latest_filtered()
    facts = build_noc_facts(latest)
    det = deterministic_recommendation(kpis, facts, window)

    from ..kpi import format_kpis

    kpi_text = format_kpis(kpis, window)
    await _send(update, context, "\n".join([kpi_text, "", det]), reply_markup=_kb(update))

    log.info("ANALYZE_END unit=%s window=%s source=%s ms=%s", UNIT, window, snap.source, int((time.monotonic() - t0) * 1000))


# =====================================================================================
# DM — Torre de Controle
# =====================================================================================

def _dm_header(mode: str) -> str:
    if mode == "down":
        return "🔴 Torre de Controle — Agora (UN1)"
    if mode == "warn":
        return "🟠 Torre de Controle — Agora (UN1)"
    return "🟢 Torre de Controle — Agora (UN1)"


def _dm_updated_line(now) -> str:
    n = to_local(now)
    return f"Atualizado: {n.strftime('%d/%m %H:%M')}" if n else "Atualizado: -"


def _dm_focus_label(svc: Optional[Svc]) -> str:
    if not svc:
        return "serviço"
    return {
        "TEL": "Telefonia",
        "L1": "Link1 (Mundivox)",
        "L2": "Link2 (Valenet)",
        "ESC": "Escallo",
        "NET": "Internet (Qualidade)",
    }.get(svc.code, svc.label)


def _pick_recent_downs(evs: list, now, limit: int = 1, include_dur: bool = False) -> List[str]:
    downs = []
    for svc in (SVCS["L1"], SVCS["L2"], SVCS["TEL"], SVCS["ESC"]):
        occ = down_occurrences_with_dur(svc_events_av(evs, svc))
        for d, dur in occ:
            downs.append((d.ts, svc.label, d, dur))
    downs.sort(key=lambda x: x[0], reverse=True)
    out: List[str] = []
    for _, label, d, dur in downs[:limit]:
        if include_dur:
            out.append(f"- {fmt_when_short(d.ts, now)} — {label}: indisponível {fmt_dur(dur)}")
        else:
            out.append(f"- {fmt_when_short(d.ts, now)} — {label}: {dur_bucket_pt(dur)}")
    return out


def _dm_ai_suspicious(txt: str) -> bool:
    if not txt:
        return True
    if re.search(r"\d", txt):
        return True
    low = txt.lower()
    if any(w in low for w in ("downtime", "indispon", "flap", "down=", "queda", "instabil")):
        return True
    return False


async def _dm_ai_comment(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str, opener: str, panel: str, source: str) -> Optional[str]:
    if not _is_dm(update):
        return None
    try:
        latest, _ = get_latest_filtered()
        facts = build_noc_facts(latest)

        det_for_ai = (
            "Tarefa: responda em 1 frase curta, pt-BR, tom humano e direto.\n"
            "Regras: NÃO use números/horários/durações. NÃO diga que houve downtime/queda.\n"
            "NÃO repita o painel. NÃO invente causa.\n"
            f"Pergunta do usuário: {user_text}\n"
            f"Estado determinístico: {opener}\n"
            f"Painel: {panel}\n"
        )

        ai_txt = await ai_interpret(
            facts,
            "DM_CONTEXT",
            det_for_ai,
            update=update,
            window="24h",
            source=source,
        )
        ai_txt = (ai_txt or "").strip()
        if not ai_txt or _dm_ai_suspicious(ai_txt):
            log.info("AI_DM_SANITIZED unit=%s reason=suspicious", UNIT)
            return None
        return ai_txt
    except Exception:
        log.exception("AI_DM_ERROR unit=%s", UNIT)
        return None



async def cmd_supervisor_now(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str = ""):
    """DM: tela principal (painel IA + percentuais de Hoje)."""
    # Fonte/estado atual
    latest, snap = get_latest_filtered()
    # Eventos recentes (suficiente para compor a janela de Hoje, pois usamos prefetch para seed)
    evs_recent_raw, _ = get_last_n_events(5000)
    now = datetime.now(timezone.utc)

    panel_txt = build_dm_panel_un1_v2(latest, evs_recent_raw, now)
    await _send_dm_hub(update, context, panel_txt, reply_markup=_kb(update))


# =====================================================================================
# DM — Home multi-unidades (Clínica) + UN2/UN3 VPN
# =====================================================================================


def _flaps_map_last_hours(evs_raw: list, *, hours: int, now: datetime) -> dict[str, int]:
    """Mapa check->flaps em uma janela curta (ex.: 2h)."""
    since = now - timedelta(hours=hours)
    evs = [e for e in filter_events(evs_raw or []) if getattr(e, "ts", now) and e.ts >= since]
    try:
        kpis = compute_kpis(evs, f"{hours}h", since, now)
        return {k.check: int(k.flaps or 0) for k in kpis}
    except Exception:
        return {}


def _latest_state(latest: dict, check_name: str) -> str | None:
    """Obtém state mais recente por chave (match exato; fallback case-insensitive)."""
    if not latest:
        return None
    ev = latest.get(check_name)
    if not ev:
        for ck, e in latest.items():
            if (ck or "").upper() == (check_name or "").upper():
                ev = e
                break
    return getattr(ev, "state", None) if ev else None


async def cmd_dm_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """DM: Home multi-unidades (Clínica) — apenas Agora."""
    latest, _ = get_latest_filtered()
    evs_recent_raw, _ = get_last_n_events(5000)
    now = datetime.now(timezone.utc)
    flaps_2h = _flaps_map_last_hours(evs_recent_raw, hours=2, now=now)
    txt = build_dm_home_multiunit(latest, flaps_2h)
    await _send_dm_hub(update, context, txt, reply_markup=build_dm_home_keyboard())


async def cmd_dm_unit(update: Update, context: ContextTypes.DEFAULT_TYPE, unit_id: str):
    """DM: abre detalhe da unidade selecionada (UN1=detalhado; UN2/UN3=VPN)."""
    u = (unit_id or "").upper().strip()
    if u in ("UN1", "ELDORADO"):
        await cmd_supervisor_now(update, context, user_text="unit")
        return

    if u not in ("UN2", "UN3"):
        await cmd_dm_home(update, context)
        return

    latest, _ = get_latest_filtered()
    evs_recent_raw, _ = get_last_n_events(5000)
    now = datetime.now(timezone.utc)
    flaps_2h = _flaps_map_last_hours(evs_recent_raw, hours=2, now=now)

    check = "VPN_UN2" if u == "UN2" else "VPN_UN3"
    state = _latest_state(latest, check)
    flaps = int(flaps_2h.get(check, 0))

    label = "UN2 — Barreiro" if u == "UN2" else "UN3 — Alípio de Mello"
    txt = build_dm_unit_vpn(label, state, flaps)
    await _send_dm_hub(update, context, txt, reply_markup=build_dm_unit_vpn_keyboard())



async def cmd_dm_availability_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """DM: view compacta — Disponibilidade Hoje."""
    latest, _ = get_latest_filtered()
    evs_recent_raw, _ = get_last_n_events(5000)
    now = datetime.now(timezone.utc)
    txt = build_dm_availability_today(latest, evs_recent_raw, now)
    await _send_dm_hub(update, context, txt, reply_markup=_kb(update))


async def cmd_dm_quality_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """DM: view compacta — Qualidade Hoje."""
    latest, _ = get_latest_filtered()
    evs_recent_raw, _ = get_last_n_events(5000)
    now = datetime.now(timezone.utc)
    txt = build_dm_quality_today(latest, evs_recent_raw, now)
    await _send_dm_hub(update, context, txt, reply_markup=_kb(update))


async def cmd_supervisor_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, window: str = "24h"):
    w = window if window in ("24h", "7d") else "24h"
    evs_raw, snap, _since, now = get_events_window(w)
    evs = filter_events(evs_raw)
    latest, _ = get_latest_filtered()

    mode = overall_state(latest, evs, now, hours=UNSTABLE_HOURS)

    focus = choose_focus_service(latest, evs, now, hours=UNSTABLE_HOURS)
    focus_name = _dm_focus_label(focus)

    recent = _pick_recent_downs(evs, now, limit=1, include_dur=False)
    occ_line = "Ocorrências: nenhuma na janela." if not recent else ("Última ocorrência: " + recent[0].lstrip("- "))
    next_action = "Próxima ação: nenhuma." if mode == "ok" else f"Próxima ação: Evidências → {focus_name}."

    title = f"Resumo {w} — UN1"
    panel = build_dm_panel_un1_v2(latest, evs_raw, now, title=title)
    msg = "\n".join([panel, "", occ_line, next_action]).rstrip()

    if _is_dm(update):
        await _send_dm_hub(update, context, msg, reply_markup=_kb(update))
    else:
        await _send(update, context, msg, reply_markup=_kb(update))

async def cmd_evidence_request(update: Update, context: ContextTypes.DEFAULT_TYPE, svc_code: Optional[str]):
    if not svc_code:
        msg = (
            "📎 Evidências — selecione o serviço ou peça em linguagem natural (ex.: evidência telefonia)."
            if _is_dm(update)
            else "Qual evidência você quer?"
        )
        if _is_dm(update):
            await _send_dm_hub(update, context, msg, reply_markup=kb_evidence_menu())
        else:
            await _send(update, context, msg, reply_markup=kb_evidence_menu())
        return

    svc = SVCS.get(svc_code)
    if not svc:
        msg = "Não identifiquei o serviço. Selecione no menu ou diga algo como: evidência telefonia."
        if _is_dm(update):
            await _send_dm_hub(update, context, msg, reply_markup=kb_evidence_menu())
        else:
            await _send(update, context, msg, reply_markup=kb_evidence_menu())
        return

    t0 = time.monotonic()
    evs_24h_raw, snap, _since, now = get_events_window("24h")
    evs_24h = filter_events(evs_24h_raw)
    latest, _ = get_latest_filtered()

    w_override = detect_window_override(getattr(update.effective_message, "text", "") or "")
    window = w_override or _choose_window_auto_24h(evs_24h, svc, now)

    evidence_txt, evidence_kb = build_evidence_compact(
        latest, evs_24h, svc, now, window,
        dm=_is_dm(update),
        source=getattr(snap, "source", "-"),
        notes=getattr(snap, "notes", ""),
    )

    if _is_dm(update):
        await _send_dm_hub(update, context, evidence_txt, reply_markup=evidence_kb)
    else:
        await _send(update, context, evidence_txt, reply_markup=evidence_kb)

    # log CIDs
    base = svc_events_q(evs_24h, svc) if svc.code == "NET" else svc_events_av(evs_24h, svc)
    downs = events_with_state(base, "DOWN")
    cids, _ = unique_recent_cids(downs, limit=MAX_CIDS)
    log.info(
        "EVIDENCE_END unit=%s svc=%s window=%s source=%s ms=%s cids=%s",
        UNIT,
        svc.code,
        window,
        getattr(snap, "source", "-"),
        int((time.monotonic() - t0) * 1000),
        ",".join(cids) if cids else "-",
    )


async def cmd_evidence_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, svc_code: str, window: str, raw: bool):
    svc = SVCS.get(svc_code)
    if not svc:
        await _send(update, context, "Serviço inválido.", reply_markup=kb_evidence_menu())
        return

    evs_24h_raw, snap, _since, now = get_events_window("24h")
    evs_24h = filter_events(evs_24h_raw)
    evs_win = slice_window_from_24h(evs_24h, now, window, hours=UNSTABLE_HOURS)

    base = svc_events_q(evs_win, svc) if svc.code == "NET" else svc_events_av(evs_win, svc)
    evs_svc = sorted(base, key=lambda x: x.ts)

    txt = build_evidence_detail_text(
        evs_svc,
        now,
        raw=raw,
        svc_label=svc.label,
        window=window,
        source=getattr(snap, "source", "-"),
        max_lines=(40 if _is_dm(update) else 120),
    )

    # DM produto: evita entulho. Em callback, edita o card.

    if _is_dm(update):

        await _send_dm_hub(update, context, txt, reply_markup=kb_evidence_actions(svc.code, window))

    else:

        await _send(update, context, txt, reply_markup=kb_evidence_actions(svc.code, window))
async def cmd_evidence_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE, svc_code: str, window: str):
    svc = SVCS.get(svc_code)
    if not svc:
        if _is_dm(update):
            await _send_dm_hub(update, context, "Serviço inválido.", reply_markup=kb_evidence_menu())
        else:
            await _send(update, context, "Serviço inválido.", reply_markup=kb_evidence_menu())
        return

    evs_24h_raw, snap, _since, now = get_events_window("24h")
    evs_24h = filter_events(evs_24h_raw)
    evs_win = slice_window_from_24h(evs_24h, now, window, hours=UNSTABLE_HOURS)

    latest, _ = get_latest_filtered()
    txt = build_ticket_text(latest, evs_win, svc, now)

    if _is_dm(update):
        await _send_dm_hub(update, context, txt, reply_markup=kb_evidence_actions(svc.code, window))
    else:
        await _send(update, context, txt, reply_markup=kb_evidence_actions(svc.code, window))


# =====================================================================================
# Atendimento (2h) — triagem DM
# =====================================================================================

def _slice_last_minutes_utc(evs: list, now, minutes: int = 120) -> list:
    try:
        n = now
        if getattr(n, "tzinfo", None) is None:
            n = n.replace(tzinfo=timezone.utc)
        n = n.astimezone(timezone.utc)
        start = n - timedelta(minutes=minutes)
        out = [e for e in (evs or []) if getattr(e, "ts", None) and e.ts >= start]
        out.sort(key=lambda x: x.ts)
        return out
    except Exception:
        return evs or []


def _match_events(evs: list, key: str) -> list:
    k = upper(key)
    return [e for e in (evs or []) if k in upper(getattr(e, "check", ""))]


def _instability_flag(evs: list, key: str) -> tuple[bool, int, int]:
    lst = _match_events(evs, key)
    downs = sum(1 for e in lst if upper(getattr(e, "state", "")) == "DOWN")
    changes = 0
    last = None
    for e in lst:
        st = upper(getattr(e, "state", ""))
        if last is not None and st != last:
            changes += 1
        last = st
    return (downs > 0) or (changes >= 2), downs, changes


def _focus_from_text(t: str) -> str:
    tl = (t or "").lower()
    if any(x in tl for x in ("telefonia", "telefone", "telef", "ramal", "ligacao", "ligação", "voip", "sip")):
        return "TEL"
    if any(x in tl for x in ("escallo", "escalo", "ommini", "omminichanel", "futurotec")):
        return "ESC"
    if any(x in tl for x in ("internet", "rede", "link")):
        return "NET"
    return "NET"


def _label_focus(code: str) -> str:
    return {"TEL": "Telefonia", "ESC": "Escallo", "NET": "Internet"}.get(code, "Internet")



async def cmd_attendance_2h(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str = ""):
    """DM: triagem 2h (reclamação) — sempre formatado, sem parágrafo."""
    evs_24h_raw, _snap, _since, now = get_events_window("24h")
    evs_24h = filter_events(evs_24h_raw)
    evs_2h = _slice_last_minutes_utc(evs_24h, now, 120)
    latest, _ = get_latest_filtered()

    focus = _focus_from_text(user_text)
    focus_label = _label_focus(focus)

    # disponibilidade agora (sem QUALITY)
    av_tel = next((v for k, v in latest.items() if "VOIP" in upper(k) and "QUALITY" not in upper(k)), None)
    av_esc = next((v for k, v in latest.items() if "ESCALLO" in upper(k) and "QUALITY" not in upper(k)), None)
    av_l1 = next((v for k, v in latest.items() if "MUNDIVOX" in upper(k) and "QUALITY" not in upper(k)), None)

    tel_down = upper(getattr(av_tel, "state", "")) == "DOWN"
    esc_down = upper(getattr(av_esc, "state", "")) == "DOWN"
    l1_down = upper(getattr(av_l1, "state", "")) == "DOWN"

    # qualidade 2h (sinal)
    net_conf, _, _ = _instability_flag(evs_2h, "INTERNET QUALITY")
    voip_conf, _, _ = _instability_flag(evs_2h, "VOIP QUALITY")
    esc_conf, _, _ = _instability_flag(evs_2h, "ESCALLO QUALITY")

    if focus == "TEL":
        incident_now = tel_down
        confirmed_2h = voip_conf
        evidence_cmd = "telefonia"
    elif focus == "ESC":
        incident_now = esc_down
        confirmed_2h = esc_conf
        evidence_cmd = "escallo"
    else:
        incident_now = l1_down
        confirmed_2h = net_conf
        evidence_cmd = "internet"

    # ===== respostas (SEM parágrafo) =====
    if incident_now:
        title = f"🔴 ALTIS — Atendimento (2h) — {focus_label}"
        lines = [
            title,
            "",
            "📌 Situação agora: incidente ativo 🔴",
            f"⚠️ Sinal: {focus_label} indisponível",
            "➡️ Ação: gerar evidência do serviço",
            "",
            f"🧾 Digite: evidência {evidence_cmd}",
        ]
        await _send_dm_hub(update, context, "\n".join(lines), reply_markup=_kb(update))
        return

    if confirmed_2h:
        title = f"🟠 ALTIS — Atendimento (2h) — {focus_label}"
        lines = [
            title,
            "",
            "📌 Situação agora: sem queda total ✅",
            f"⚠️ Sinal: {focus_label} com instabilidade nas últimas 2h",
            "➡️ Ação: gerar evidência do serviço",
            "",
            f"🧾 Digite: evidência {evidence_cmd}",
        ]
        await _send_dm_hub(update, context, "\n".join(lines), reply_markup=_kb(update))
        return
    title = f"🟢 ALTIS — Atendimento (2h) — {focus_label}"
    if focus == "TEL":
        suspect = "Suspeita: operadora/SIP/PABX/ramais."
        next_step = "➡️ Próximo passo: gerar evidência da Telefonia"
        evidence_cmd = "telefonia"
    elif focus == "ESC":
        suspect = "Suspeita: aplicação/endpoint/ambiente."
        next_step = "➡️ Próximo passo: gerar evidência do Escallo"
        evidence_cmd = "escallo"
    else:
        suspect = "Suspeita: saturação interna ou sistema."
        next_step = "➡️ Próximo passo: checar tráfego/sistema + evidência de Internet"
        evidence_cmd = "internet"

    lines = [
        title,
        "",
        "📌 Situação agora: sem queda total ✅",
        "✅ Sinal: não confirmado nas últimas 2h",
        suspect,
        next_step,
        "",
        f"🧾 Digite: evidência {evidence_cmd}",
    ]
    await _send_dm_hub(update, context, "\n".join(lines), reply_markup=_kb(update))




async def cmd_health(update, context):
    import logging
    logging.getLogger(__name__).info("HEALTH_CMD chat_id=%s user_id=%s text=%r", getattr(getattr(update,'effective_chat',None),'id',None), getattr(getattr(update,'effective_user',None),'id',None), getattr(getattr(update,'effective_message',None),'text',None))
    """
    /health (Grupo NOC): painel rápido de saúde do pipeline (sem Markdown).
    Não altera contrato do /where.
    """
    import os, sqlite3, subprocess

    def is_active(unit: str) -> str:
        try:
            r = subprocess.run(
                ["systemctl", "is-active", unit],
                capture_output=True, text=True, timeout=2
            )
            out = (r.stdout or "").strip()
            return out if out else "N/D"
        except Exception:
            return "N/D"

    def read_integrity_last(path="/var/log/noc/integrity-last.txt") -> dict:
        d = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    d[k.strip()] = v.strip()
        except Exception:
            return {}
        return d

    def read_last_event(db_path="/var/lib/noc/noc.db"):
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=1)
            try:
                row = conn.execute(
                    "SELECT ts, unit, check_name, state, host, cid "
                    "FROM events ORDER BY id DESC LIMIT 1"
                ).fetchone()
            finally:
                conn.close()
            return row
        except Exception:
            return None

    host = os.uname().nodename
    bot_version = os.environ.get("BOT_VERSION", "N/D")
    build_id = os.environ.get("BUILD_ID", os.environ.get("BUILD", "N/D"))

    s_rsyslog = is_active("rsyslog")
    s_tailer = is_active("noc-sqlite-tailer")
    s_bot = is_active("telegram-bot")

    integrity = read_integrity_last()
    last_event = read_last_event()

    lines = []
    lines.append(f"🧪 HEALTH — UN1 | host={host}")
    lines.append(f"BOT_VERSION={bot_version} | BUILD_ID={build_id}")
    lines.append(f"Serviços: rsyslog={s_rsyslog} | tailer={s_tailer} | bot={s_bot}")
    lines.append("Paths: LOG=/var/log/mikrotik/un1.log | DB=/var/lib/noc/noc.db | STATE=/var/lib/noc/tailer.state.json")

    if last_event:
        ts, unit, check_name, state, h, cid = last_event
        lines.append(f"Last event: ts={ts} | check={check_name} | state={state} | host={h} | cid={cid}")
    else:
        lines.append("Last event: N/D")

    if integrity:
        lines.append(
            "Integrity: "
            f"RESULT={integrity.get('RESULT','N/D')} "
            f"ts={integrity.get('TS','N/D')} "
            f"baseline_rc={integrity.get('BASELINE_RC','N/D')} "
            f"releases_rc={integrity.get('RELEASES_RC','N/D')}"
        )
    else:
        lines.append("Integrity: N/D (sem /var/log/noc/integrity-last.txt)")

    text = "\n".join(lines)
    msg = update.effective_message
    if msg:
        await msg.reply_text(text, parse_mode=None, disable_web_page_preview=True)
