# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..config import TZ_LOCAL, UNIT, SVCS
from ..sources import get_prefetch_before
from ..utils import filter_events
from ..state import quality_term, is_quality_bad


# =====================================================================================
# Legacy helpers (mantidos para compat)
# =====================================================================================

def _upper(s: str) -> str:
    return (s or "").upper()


def _to_local(dt, tz_local):
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz_local)


def _is_noise_check(name: str, noise_tokens) -> bool:
    n = _upper(name)
    if "SELFTEST" in n:
        return True
    for tok in (noise_tokens or []):
        if tok and tok in n:
            return True
    return False


def _filter_latest(latest: dict, noise_tokens) -> dict:
    return {k: v for k, v in (latest or {}).items() if not _is_noise_check(k, noise_tokens)}


def _filter_events(events: list, noise_tokens) -> list:
    out = []
    for e in events or []:
        ck = getattr(e, "check", "") or ""
        if not _is_noise_check(ck, noise_tokens):
            out.append(e)
    return out


def _find_latest_for_key(latest: dict, key_sub: str):
    k = _upper(key_sub)
    for name, ev in (latest or {}).items():
        if k in _upper(name):
            return ev
    return None


def _events_for_key(events: list, key_sub: str) -> list:
    k = _upper(key_sub)
    return [e for e in (events or []) if k in _upper(getattr(e, "check", ""))]


def _is_unstable_recent(evs: list, now, tz_local, hours: int = 3) -> bool:
    now_l = _to_local(now, tz_local)
    if not now_l:
        return False
    since = now_l - timedelta(hours=hours)
    w = [e for e in (evs or []) if _to_local(getattr(e, "ts", None), tz_local) and _to_local(e.ts, tz_local) >= since]
    if any(_upper(getattr(e, "state", "")) == "DOWN" for e in w):
        return True
    return len(w) >= 2


def _state_icon(cur_state: str | None, unstable: bool) -> str:
    s = _upper(cur_state or "")
    if s == "DOWN":
        return "🔴"
    if unstable:
        return "⚠️"
    return "✅"


def _state_icon_word(cur_state: str | None, unstable: bool):
    s = _upper(cur_state or "")
    if s == "DOWN":
        return ("🔴", "Indisponível")
    if unstable:
        return ("⚠️", "Instável")
    return ("✅", "OK")


def build_panel_un1(
    latest: dict,
    events_lookback: list,
    now,
    *,
    svcs: dict,
    panel_label: str,
    panel_legend: str,
    tz_local,
    noise_tokens,
    unstable_hours: int = 3,
    dm: bool = False,
) -> str:
    """Painel legado (compat): grupo técnico e evidências."""
    latest = _filter_latest(latest, noise_tokens)
    evs = _filter_events(events_lookback, noise_tokens)

    l1 = svcs.get("L1")
    l2 = svcs.get("L2")
    tel = svcs.get("TEL")
    esc = svcs.get("ESC")

    def _svc_icon(svc):
        if not svc:
            return "⚪"
        ev = _find_latest_for_key(latest, getattr(svc, "key", ""))
        u = _is_unstable_recent(_events_for_key(evs, getattr(svc, "key", "")), now, tz_local, unstable_hours)
        return _state_icon(getattr(ev, "state", None) if ev else None, u)

    i_l1 = _svc_icon(l1)
    i_l2 = _svc_icon(l2)
    i_tel = _svc_icon(tel)
    i_esc = _svc_icon(esc)

    if not dm:
        return panel_label.format(L1=i_l1, L2=i_l2, TEL=i_tel, ESC=i_esc) + "\n" + panel_legend

    def _svc_word(svc):
        if not svc:
            return ("⚪", "N/D")
        ev = _find_latest_for_key(latest, getattr(svc, "key", ""))
        u = _is_unstable_recent(_events_for_key(evs, getattr(svc, "key", "")), now, tz_local, unstable_hours)
        return _state_icon_word(getattr(ev, "state", None) if ev else None, u)

    e1, w1 = _svc_word(l1)
    e2, w2 = _svc_word(l2)
    e3, w3 = _svc_word(tel)
    e4, w4 = _svc_word(esc)

    return "\n".join(
        [
            f"🌐1 Mundivox (Prim) {e1} {w1}",
            f"🌐2 Valenet (Sec) {e2} {w2}",
            f"📞 Telefonia {e3} {w3}",
            f"☁️ Escallo {e4} {w4}",
        ]
    )


# =====================================================================================
# DM UX v2 — ALTIS
# =====================================================================================

DM_TITLE_DEFAULT = "ALTIS — Supervisão tecnológica com IA integrada"



def _assistant_footer(kind: str = "general") -> list[str]:
    if kind == "home":
        return [
            "",
            '💬 Fale do seu jeito: "telefone ok aí?", "teve problema hoje?", "qual é o site do speed test?"',
        ]
    if kind == "vpn":
        return [
            "",
            '💬 Você pode perguntar: "VPN caiu?" ou "teve falha hoje?"',
        ]
    if kind == "quality":
        return [
            "",
            "💬 Próximo passo: peça a evidência do serviço ou pergunte se houve falha hoje.",
        ]
    if kind == "availability":
        return [
            "",
            '💬 Você pode seguir com: "telefone ok aí?" ou "me manda a evidência".', 
        ]
    return [
        "",
        '💬 Você pode perguntar naturalmente: "telefone ok aí?", "teve problema hoje?" ou "qual é o site do speed test?"', 
    ]


@dataclass(frozen=True)
class Pct:
    pct: float | None
    down_min: int | None
    last_state: str | None


def _fmt_pct(p: float | None) -> str:
    if p is None:
        return "N/D"
    return f"{p:.1f}".replace(".", ",") + "%"


def _start_of_today_utc(now_utc: datetime) -> datetime:
    nloc = now_utc.astimezone(TZ_LOCAL)
    start_loc = nloc.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_loc.astimezone(timezone.utc)


def _latest_by(latest: dict, include: str, *, must: str | None = None, exclude: str | None = None):
    inc = _upper(include)
    must_u = _upper(must) if must else None
    exc_u = _upper(exclude) if exclude else None
    best = None
    for name, ev in (latest or {}).items():
        n = _upper(name)
        if inc and inc not in n:
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


def _calc_pct_for_check(check_name: str, events_all: list, start_utc: datetime, end_utc: datetime, *, up_state: str = "UP") -> Pct:
    """Percentual por duração (tempo em UP / total), com seed prefetch."""
    if not check_name:
        return Pct(None, None, None)

    # filtra eventos do check na janela
    evs = []
    for e in events_all or []:
        if getattr(e, "check", None) != check_name:
            continue
        ts = getattr(e, "ts", None)
        if not ts:
            continue
        t = ts.astimezone(timezone.utc)
        if t < start_utc or t > end_utc:
            continue
        evs.append(e)

    evs.sort(key=lambda x: x.ts)

    # seed state via prefetch (DB). Se não houver prefetch e não houver evento, N/D.
    pre = get_prefetch_before(start_utc, check_name)
    last_state = _upper(getattr(pre, "state", "") if pre else "") or None

    if not evs and last_state is None:
        return Pct(None, None, None)

    t_cursor = start_utc
    up_s = 0
    down_s = 0

    def add_slice(state: str | None, seconds: int):
        nonlocal up_s, down_s
        if not state or seconds <= 0:
            return
        if state == up_state:
            up_s += seconds
        else:
            down_s += seconds

    # percorre eventos
    for ev in evs:
        t_ev = ev.ts.astimezone(timezone.utc)
        if t_ev < start_utc:
            last_state = _upper(getattr(ev, "state", "")) or last_state
            continue
        if t_ev > end_utc:
            break

        dt = int((t_ev - t_cursor).total_seconds())
        add_slice(last_state, dt)

        last_state = _upper(getattr(ev, "state", "")) or last_state
        t_cursor = t_ev

    # fecha janela
    dt_end = int((end_utc - t_cursor).total_seconds())
    add_slice(last_state, dt_end)

    total = up_s + down_s
    if total <= 0:
        return Pct(None, None, last_state)

    pct = 100.0 * (up_s / total)
    down_min = int(round(down_s / 60.0))
    return Pct(pct, down_min, last_state)

def _calc_quality_pct_guarded(quality_check: str, link_check: str, events_all: list, start_utc: datetime, end_utc: datetime, *, up_state: str = "UP") -> Pct:
    """Qualidade % apenas quando o link (availability) está UP.

    - Denominador: tempo em que link_check == UP e quality_check tem estado conhecido (UP/DOWN).
    - Numerador: tempo em que link_check == UP e quality_check == UP.
    - Se o link não ficou UP na janela (ou sem dados suficientes), retorna N/D.
    """
    if not quality_check or not link_check:
        return Pct(None, None, None)

    # eventos do link
    link_evs = []
    for e in events_all or []:
        if getattr(e, "check", None) != link_check:
            continue
        ts = getattr(e, "ts", None)
        if not ts:
            continue
        t = ts.astimezone(timezone.utc)
        if t < start_utc or t > end_utc:
            continue
        link_evs.append(e)
    link_evs.sort(key=lambda x: x.ts)

    pre_link = get_prefetch_before(start_utc, link_check)
    link_state = _upper(getattr(pre_link, "state", "") if pre_link else "") or None

    # eventos de qualidade
    q_evs = []
    for e in events_all or []:
        if getattr(e, "check", None) != quality_check:
            continue
        ts = getattr(e, "ts", None)
        if not ts:
            continue
        t = ts.astimezone(timezone.utc)
        if t < start_utc or t > end_utc:
            continue
        q_evs.append(e)
    q_evs.sort(key=lambda x: x.ts)

    pre_q = get_prefetch_before(start_utc, quality_check)
    q_state = _upper(getattr(pre_q, "state", "") if pre_q else "") or None

    # sem seed e sem evento -> N/D
    if (link_state is None and not link_evs) or (q_state is None and not q_evs):
        # ainda pode haver UP do link, mas qualidade totalmente desconhecida: N/D
        return Pct(None, None, q_state)

    i = 0
    j = 0
    t_cursor = start_utc

    good_s = 0
    bad_s = 0
    known_s = 0  # somente onde qualidade tem estado conhecido

    def add_slice(dt: int):
        nonlocal good_s, bad_s, known_s
        if dt <= 0:
            return
        if link_state != up_state:
            return
        if q_state is None:
            return
        known_s += dt
        if q_state == up_state:
            good_s += dt
        else:
            bad_s += dt

    while True:
        t_next = None
        if i < len(link_evs):
            t_next = link_evs[i].ts.astimezone(timezone.utc)
        if j < len(q_evs):
            tq = q_evs[j].ts.astimezone(timezone.utc)
            if t_next is None or tq < t_next:
                t_next = tq
        if t_next is None:
            break
        if t_next < start_utc:
            # atualiza estados e segue
            while i < len(link_evs) and link_evs[i].ts.astimezone(timezone.utc) < start_utc:
                link_state = _upper(getattr(link_evs[i], "state", "")) or link_state
                i += 1
            while j < len(q_evs) and q_evs[j].ts.astimezone(timezone.utc) < start_utc:
                q_state = _upper(getattr(q_evs[j], "state", "")) or q_state
                j += 1
            t_cursor = start_utc
            continue
        if t_next > end_utc:
            break

        add_slice(int((t_next - t_cursor).total_seconds()))

        # aplica todos eventos do link nesse timestamp
        while i < len(link_evs) and link_evs[i].ts.astimezone(timezone.utc) == t_next:
            link_state = _upper(getattr(link_evs[i], "state", "")) or link_state
            i += 1
        # aplica todos eventos de qualidade nesse timestamp
        while j < len(q_evs) and q_evs[j].ts.astimezone(timezone.utc) == t_next:
            q_state = _upper(getattr(q_evs[j], "state", "")) or q_state
            j += 1

        t_cursor = t_next

    add_slice(int((end_utc - t_cursor).total_seconds()))

    if known_s <= 0:
        return Pct(None, None, q_state)

    pct = 100.0 * (good_s / known_s)
    down_min = int(round(bad_s / 60.0))
    return Pct(pct, down_min, q_state)


def _icon_for(av_state: str | None, q_term: str) -> str:
    s = _upper(av_state or "")
    if s == "DOWN":
        return "🔴"
    if is_quality_bad(q_term):
        return "⚠️"
    if s == "UP":
        return "✅"
    return "⚪"


def _impact(inet_down: bool, tel_down: bool, esc_down: bool, any_bad_quality: bool, one_link_down: bool = False) -> str:
    if inet_down:
        return "operação com indisponibilidade de Internet"
    if tel_down:
        return "operação com indisponibilidade de Telefonia"
    if esc_down:
        return "operação com indisponibilidade no Escallo"
    if one_link_down and any_bad_quality:
        return "operação com redundância ativa (instável)"
    if one_link_down:
        return "operação com redundância ativa"
    if any_bad_quality:
        return "operação com instabilidade"
    return "operação normal"
def build_dm_panel_un1_v2(latest: dict, events_recent: list, now_utc: datetime, *, title: str = DM_TITLE_DEFAULT) -> str:
    """Painel DM (tela principal) — sempre formatado e sem parágrafos."""
    start_utc = _start_of_today_utc(now_utc)
    end_utc = now_utc.astimezone(timezone.utc)

    # usa só eventos parseáveis/sem ruído
    evs_all = filter_events(events_recent or [])

    # checks de disponibilidade (sem QUALITY)
    ev_l1 = _latest_by(latest, "MUNDIVOX", exclude="QUALITY")
    ev_l2 = _latest_by(latest, "VALENET", exclude="QUALITY")
    ev_tel = _latest_by(latest, "VOIP", exclude="QUALITY")
    ev_esc = _latest_by(latest, "ESCALLO", exclude="QUALITY")

    ck_l1 = getattr(ev_l1, "check", "") if ev_l1 else ""
    ck_l2 = getattr(ev_l2, "check", "") if ev_l2 else ""
    ck_tel = getattr(ev_tel, "check", "") if ev_tel else ""
    ck_esc = getattr(ev_esc, "check", "") if ev_esc else ""

    p_l1 = _calc_pct_for_check(ck_l1, evs_all, start_utc, end_utc)
    p_l2 = _calc_pct_for_check(ck_l2, evs_all, start_utc, end_utc)
    p_tel = _calc_pct_for_check(ck_tel, evs_all, start_utc, end_utc)
    p_esc = _calc_pct_for_check(ck_esc, evs_all, start_utc, end_utc)

    # checks de qualidade
    # Internet: por operadora (anti-contingência) — QUALITY_L1 / QUALITY_L2
    p_q_l1 = _calc_quality_pct_guarded("QUALITY_L1", ck_l1, evs_all, start_utc, end_utc)
    p_q_l2 = _calc_quality_pct_guarded("QUALITY_L2", ck_l2, evs_all, start_utc, end_utc)

    # Qualidade dos demais serviços (como já era)
    ev_tel_q = _latest_by(latest, "VOIP", must="QUALITY")
    ev_esc_q = _latest_by(latest, "ESCALLO", must="QUALITY")

    ck_tel_q = getattr(ev_tel_q, "check", "") if ev_tel_q else ""
    ck_esc_q = getattr(ev_esc_q, "check", "") if ev_esc_q else ""

    p_tel_q = _calc_pct_for_check(ck_tel_q, evs_all, start_utc, end_utc)
    p_esc_q = _calc_pct_for_check(ck_esc_q, evs_all, start_utc, end_utc)

    term_l1 = quality_term(p_q_l1.pct)
    term_l2 = quality_term(p_q_l2.pct)
    term_tel = quality_term(p_tel_q.pct)
    term_esc = quality_term(p_esc_q.pct)

    # estados atuais
    s_l1 = _upper(getattr(ev_l1, "state", "")) if ev_l1 else None
    s_l2 = _upper(getattr(ev_l2, "state", "")) if ev_l2 else None
    s_tel = _upper(getattr(ev_tel, "state", "")) if ev_tel else None
    s_esc = _upper(getattr(ev_esc, "state", "")) if ev_esc else None

    inet_down = (s_l1 == "DOWN" and s_l2 == "DOWN")
    one_link_down = (s_l1 == "DOWN") != (s_l2 == "DOWN")
    tel_down = (s_tel == "DOWN")
    esc_down = (s_esc == "DOWN")

    # regra anti-contingência: qualidade só conta se o link está UP
    bad_l1 = (s_l1 == "UP") and is_quality_bad(term_l1)
    bad_l2 = (s_l2 == "UP") and is_quality_bad(term_l2)
    any_bad_q = bad_l1 or bad_l2 or is_quality_bad(term_tel) or is_quality_bad(term_esc)

    head = "🔴" if (inet_down or tel_down or esc_down) else ("🟠" if (any_bad_q or one_link_down) else "🟢")
    impact = _impact(inet_down, tel_down, esc_down, any_bad_q, one_link_down)

    # labels (operadoras)
    l1_label = "Link 1 — Mundivox"
    l2_label = "Link 2 — Valenet"

    # estado Internet (texto — reduz ruído visual)
    if inet_down:
        inet_mode = "Indisponível"
    elif (bad_l1 or bad_l2):
        inet_mode = "Instável"
    elif one_link_down:
        inet_mode = "Backup ativo"
    else:
        inet_mode = "Online"

    # ícones por linha
    i_l1 = _icon_for(s_l1, term_l1)
    i_l2 = _icon_for(s_l2, term_l2)
    i_tel = _icon_for(s_tel, term_tel)
    i_esc = _icon_for(s_esc, term_esc)

    def q_part(pct: float | None, term: str | None) -> str:
        if pct is None:
            return "N/D qualidade — N/D"
        t = term or "N/D"
        return f"{_fmt_pct(pct)} qualidade — {t}"

    def today_line(state: str | None, up_pct: float | None, q_pct: float | None, term: str | None) -> str:
        base = f"Hoje: {_fmt_pct(up_pct)} up | {q_part(q_pct, term)}"
        if (state or "") == "DOWN":
            return f"Agora: FORA 🔴\n{base}"
        return base

    q1_pct = p_q_l1.pct if s_l1 == "UP" else None
    q2_pct = p_q_l2.pct if s_l2 == "UP" else None
    q1_term = term_l1 if s_l1 == "UP" else None
    q2_term = term_l2 if s_l2 == "UP" else None

    lines = [
        f"{head} {title}",
        "",
        f"🌐 Internet — {inet_mode}",
        "",
        f"↳ {l1_label} {i_l1}",
        today_line(s_l1, p_l1.pct, q1_pct, q1_term),
        "",
        f"↳ {l2_label} {i_l2}",
        today_line(s_l2, p_l2.pct, q2_pct, q2_term),
        "",
        f"📞 Telefonia {i_tel}",
        today_line(s_tel, p_tel.pct, p_tel_q.pct, term_tel),
        "",
        f"☁️ Escallo {i_esc}",
        today_line(s_esc, p_esc.pct, p_esc_q.pct, term_esc),
        "",
        f"Impacto: {impact}.",
    ]
    lines += _assistant_footer("general")
    return "\n".join(lines)

def build_dm_followup_block(service: str, *, q_pct: float | None, q_term_str: str, now_ok: bool = True, incident_now: bool = False) -> str:
    """Follow-up padrão (sem parágrafo): 3 linhas + CTA."""
    svc = (service or "serviço").strip()

    if incident_now:
        status = "incidente ativo 🔴"
    else:
        status = "sem queda total ✅" if now_ok else "atenção ⚠️"

    q_pct_s = _fmt_pct(q_pct)
    qt = q_term_str or "N/D"

    lines = [
        f"📌 Situação agora: {status}",
        f"⚠️ Sinal: {svc} — {q_pct_s} ({qt}) hoje" if q_pct is not None else f"⚠️ Sinal: {svc} — {qt} hoje",
        "➡️ Ação: gerar evidência do serviço",
        "",
        f"🧾 Digite: evidência {svc.lower()}",
    ]
    return "\n".join(lines)


def _dm_today_metrics(latest: dict, events_recent: list, now_utc: datetime):
    """Retorna métricas usadas nas views DM (painel/qualidade/disponibilidade)."""
    start_utc = _start_of_today_utc(now_utc)
    end_utc = now_utc.astimezone(timezone.utc)
    evs_all = filter_events(events_recent or [])

    ev_l1 = _latest_by(latest, "MUNDIVOX", exclude="QUALITY")
    ev_l2 = _latest_by(latest, "VALENET", exclude="QUALITY")
    ev_tel = _latest_by(latest, "VOIP", exclude="QUALITY")
    ev_esc = _latest_by(latest, "ESCALLO", exclude="QUALITY")

    ck_l1 = getattr(ev_l1, "check", "") if ev_l1 else ""
    ck_l2 = getattr(ev_l2, "check", "") if ev_l2 else ""
    ck_tel = getattr(ev_tel, "check", "") if ev_tel else ""
    ck_esc = getattr(ev_esc, "check", "") if ev_esc else ""

    p_l1 = _calc_pct_for_check(ck_l1, evs_all, start_utc, end_utc)
    p_l2 = _calc_pct_for_check(ck_l2, evs_all, start_utc, end_utc)
    p_tel = _calc_pct_for_check(ck_tel, evs_all, start_utc, end_utc)
    p_esc = _calc_pct_for_check(ck_esc, evs_all, start_utc, end_utc)

    # Qualidade Internet por operadora (anti-contingência)
    p_q_l1 = _calc_quality_pct_guarded("QUALITY_L1", ck_l1, evs_all, start_utc, end_utc)
    p_q_l2 = _calc_quality_pct_guarded("QUALITY_L2", ck_l2, evs_all, start_utc, end_utc)

    # Qualidade dos demais serviços
    ev_tel_q = _latest_by(latest, "VOIP", must="QUALITY")
    ev_esc_q = _latest_by(latest, "ESCALLO", must="QUALITY")

    ck_tel_q = getattr(ev_tel_q, "check", "") if ev_tel_q else ""
    ck_esc_q = getattr(ev_esc_q, "check", "") if ev_esc_q else ""

    p_tel_q = _calc_pct_for_check(ck_tel_q, evs_all, start_utc, end_utc)
    p_esc_q = _calc_pct_for_check(ck_esc_q, evs_all, start_utc, end_utc)

    s_l1 = _upper(getattr(ev_l1, "state", "")) if ev_l1 else None
    s_l2 = _upper(getattr(ev_l2, "state", "")) if ev_l2 else None
    s_tel = _upper(getattr(ev_tel, "state", "")) if ev_tel else None
    s_esc = _upper(getattr(ev_esc, "state", "")) if ev_esc else None

    inet_down = (s_l1 == "DOWN" and s_l2 == "DOWN")

    return {
        "p_l1": p_l1,
        "p_l2": p_l2,
        "p_tel": p_tel,
        "p_esc": p_esc,
        "p_q_l1": p_q_l1,
        "p_q_l2": p_q_l2,
        "p_tel_q": p_tel_q,
        "p_esc_q": p_esc_q,
        "term_l1": quality_term(p_q_l1.pct),
        "term_l2": quality_term(p_q_l2.pct),
        "term_tel": quality_term(p_tel_q.pct),
        "term_esc": quality_term(p_esc_q.pct),
        "s_l1": s_l1,
        "s_l2": s_l2,
        "s_tel": s_tel,
        "s_esc": s_esc,
        "inet_down": inet_down,
    }

def build_dm_availability_today(latest: dict, events_recent: list, now_utc: datetime) -> str:
    """View DM: Disponibilidade Hoje (compacto e formatado)."""
    m = _dm_today_metrics(latest, events_recent, now_utc)
    head = "🔴" if (m["inet_down"] or m["s_tel"] == "DOWN" or m["s_esc"] == "DOWN") else "🟢"

    lines = [
        f"📊 {head} ALTIS — Disponibilidade Hoje",
        "",
        f"🌐 Link 1 (Mundivox): {_fmt_pct(m['p_l1'].pct)} up",
        f"🌐 Link 2 (Valenet): {_fmt_pct(m['p_l2'].pct)} up",
        f"📞 Telefonia: {_fmt_pct(m['p_tel'].pct)} up",
        f"☁️ Escallo: {_fmt_pct(m['p_esc'].pct)} up",
    ]
    lines += _assistant_footer("availability")
    return "\n".join(lines)


def build_dm_quality_today(latest: dict, events_recent: list, now_utc: datetime) -> str:
    """View DM: Qualidade Hoje (por operadora) — compacto e formatado."""
    m = _dm_today_metrics(latest, events_recent, now_utc)

    bad_l1 = (m["s_l1"] == "UP") and is_quality_bad(m["term_l1"])
    bad_l2 = (m["s_l2"] == "UP") and is_quality_bad(m["term_l2"])
    any_bad = bad_l1 or bad_l2 or is_quality_bad(m["term_tel"]) or is_quality_bad(m["term_esc"])
    head = "🟠" if any_bad else "🟢"

    def _q_line(label: str, state: str | None, pct: float | None, term: str | None) -> str:
        if state != "UP":
            return f"{label}: N/D — N/D"
        if pct is None:
            return f"{label}: N/D — N/D"
        return f"{label}: {_fmt_pct(pct)} — {term or 'N/D'}"

    lines = [
        f"📈 {head} ALTIS — Qualidade Hoje",
        "",
        _q_line("🌐 Link 1 (Mundivox)", m["s_l1"], m["p_q_l1"].pct, m["term_l1"]),
        _q_line("🌐 Link 2 (Valenet)", m["s_l2"], m["p_q_l2"].pct, m["term_l2"]),
        f"📞 Telefonia: {_fmt_pct(m['p_tel_q'].pct)} — {m['term_tel']}",
        f"☁️ Escallo: {_fmt_pct(m['p_esc_q'].pct)} — {m['term_esc']}",
        "",
        "🧾 Prova: evidência <serviço> (ex.: evidência escallo)",
    ]
    lines += _assistant_footer("quality")
    return "\n".join(lines)


# =====================================================================================
# DM — Home multi-unidades (Clínica)
# =====================================================================================


def _emoji_now(state: str | None, flaps_2h: int) -> str:
    s = _upper(state or "")
    if s == "DOWN":
        return "🔴"
    if s == "UP" and flaps_2h >= 2:
        return "⚠️"
    if s == "UP":
        return "✅"
    return "—"


def build_dm_home_multiunit(latest: dict, flaps_2h: dict[str, int]) -> str:
    """Home DM: resumo Agora (✅/⚠️/🔴/—) por unidade."""
    # UN1
    ev_l1 = _latest_by(latest, "MUNDIVOX", exclude="QUALITY")
    ev_l2 = _latest_by(latest, "VALENET", exclude="QUALITY")
    ev_tel = _latest_by(latest, "VOIP", exclude="QUALITY")
    ev_esc = _latest_by(latest, "ESCALLO", exclude="QUALITY")

    ck_l1 = getattr(ev_l1, "check", "MUNDIVOX") if ev_l1 else "MUNDIVOX"
    ck_l2 = getattr(ev_l2, "check", "VALENET") if ev_l2 else "VALENET"
    ck_tel = getattr(ev_tel, "check", "VOIP") if ev_tel else "VOIP"
    ck_esc = getattr(ev_esc, "check", "ESCALLO") if ev_esc else "ESCALLO"

    s_l1 = _upper(getattr(ev_l1, "state", "")) if ev_l1 else None
    s_l2 = _upper(getattr(ev_l2, "state", "")) if ev_l2 else None
    s_tel = _upper(getattr(ev_tel, "state", "")) if ev_tel else None
    s_esc = _upper(getattr(ev_esc, "state", "")) if ev_esc else None

    inet_down = (s_l1 == "DOWN" and s_l2 == "DOWN")
    one_link_down = (s_l1 == "DOWN") != (s_l2 == "DOWN")

    if inet_down:
        inet_mode = "Indisponível"
    elif one_link_down:
        inet_mode = "Backup ativo"
    else:
        if (s_l1 == "UP" and flaps_2h.get(ck_l1, 0) >= 2) or (s_l2 == "UP" and flaps_2h.get(ck_l2, 0) >= 2):
            inet_mode = "Instável"
        else:
            inet_mode = "Online"

    # VPNs
    ev_vpn2 = _latest_by(latest, "VPN_UN2", exclude="QUALITY")
    ev_vpn3 = _latest_by(latest, "VPN_UN3", exclude="QUALITY")
    ck_vpn2 = getattr(ev_vpn2, "check", "VPN_UN2") if ev_vpn2 else "VPN_UN2"
    ck_vpn3 = getattr(ev_vpn3, "check", "VPN_UN3") if ev_vpn3 else "VPN_UN3"
    s_vpn2 = _upper(getattr(ev_vpn2, "state", "")) if ev_vpn2 else None
    s_vpn3 = _upper(getattr(ev_vpn3, "state", "")) if ev_vpn3 else None
    f_vpn2 = flaps_2h.get(ck_vpn2, 0)
    f_vpn3 = flaps_2h.get(ck_vpn3, 0)

    # banner
    banner = ""
    if s_vpn2 == "DOWN":
        banner = "🚨 Incidente ativo: UN2 — VPN 🔴"
    elif s_vpn3 == "DOWN":
        banner = "🚨 Incidente ativo: UN3 — VPN 🔴"
    elif inet_down:
        banner = "🚨 Incidente ativo: UN1 — Internet 🔴"
    elif s_tel == "DOWN":
        banner = "🚨 Incidente ativo: UN1 — Telefonia 🔴"
    elif s_esc == "DOWN":
        banner = "🚨 Incidente ativo: UN1 — Escallo 🔴"
    else:
        if any(v >= 2 for v in (flaps_2h.get(ck_l1, 0), flaps_2h.get(ck_l2, 0), flaps_2h.get(ck_tel, 0), flaps_2h.get(ck_esc, 0), f_vpn2, f_vpn3)):
            banner = "⚠️ Ocorrências (2h): instabilidade detectada"

    # head
    head = "🟢"
    if inet_down or s_tel == "DOWN" or s_esc == "DOWN" or s_vpn2 == "DOWN" or s_vpn3 == "DOWN":
        head = "🔴"
    elif inet_mode in ("Backup ativo", "Instável") or f_vpn2 >= 2 or f_vpn3 >= 2:
        head = "🟠"

    # impacto
    impact = "Impacto: operação normal."
    if inet_down:
        impact = "Impacto: operação com indisponibilidade de Internet."
    elif inet_mode == "Backup ativo":
        impact = "Impacto: operação com redundância ativa."
    elif inet_mode == "Instável":
        impact = "Impacto: operação com instabilidade."
    elif s_vpn2 == "DOWN" and s_vpn3 == "DOWN":
        impact = "Impacto: UN2/UN3 isoladas (VPN)."
    elif s_vpn2 == "DOWN":
        impact = "Impacto: UN2 isolada (VPN)."
    elif s_vpn3 == "DOWN":
        impact = "Impacto: UN3 isolada (VPN)."

    i_l1 = _emoji_now(s_l1, flaps_2h.get(ck_l1, 0))
    i_l2 = _emoji_now(s_l2, flaps_2h.get(ck_l2, 0))
    i_tel = _emoji_now(s_tel, flaps_2h.get(ck_tel, 0))
    i_esc = _emoji_now(s_esc, flaps_2h.get(ck_esc, 0))

    vpn2_line = "🌐🔒 VPN — N/D —" if s_vpn2 is None else ("🌐🔒 VPN — FORA 🔴" if s_vpn2 == "DOWN" else ("🌐🔒 VPN — Instável ⚠️" if (s_vpn2 == "UP" and f_vpn2 >= 2) else "🌐🔒 VPN — Conectada ✅"))
    vpn3_line = "🌐🔒 VPN — N/D —" if s_vpn3 is None else ("🌐🔒 VPN — FORA 🔴" if s_vpn3 == "DOWN" else ("🌐🔒 VPN — Instável ⚠️" if (s_vpn3 == "UP" and f_vpn3 >= 2) else "🌐🔒 VPN — Conectada ✅"))

    lines = [
        f"{head} ALTIS — Supervisão tecnológica com IA integrada",
        "(Tempo real)",
    ]
    if banner:
        lines += ["", banner]

    lines += [
        "",
        "UN1 — Eldorado",
        "",
        f"🌐 Internet — {inet_mode}",
        "",
        f"↳ Link 1 — Mundivox {i_l1}",
        f"↳ Link 2 — Valenet {i_l2}",
        "",
        f"📞 Telefonia {i_tel}",
        "",
        f"☁️ Escallo {i_esc}",
        "",
        "UN2 — Barreiro",
        "",
        vpn2_line,
        "",
        "UN3 — Alípio de Mello",
        "",
        vpn3_line,
        "",
        impact,
        "",
        "Digite o nome da unidade (ou apelido) ou clique no botão da unidade para detalhes.",
    ]
    lines += _assistant_footer("home")
    return "\n".join(lines).rstrip()


def build_dm_unit_vpn(unit_label: str, vpn_state: str | None, flaps_2h: int) -> str:
    s = _upper(vpn_state or "")
    head = "🟢"
    if s == "DOWN":
        head = "🔴"
    elif s == "UP" and flaps_2h >= 2:
        head = "🟠"

    vpn_line = "🌐🔒 VPN — N/D —"
    if s == "DOWN":
        vpn_line = "🌐🔒 VPN — FORA 🔴"
    elif s == "UP" and flaps_2h >= 2:
        vpn_line = "🌐🔒 VPN — Instável ⚠️"
    elif s == "UP":
        vpn_line = "🌐🔒 VPN — Conectada ✅"

    impact = "Impacto: operação normal."
    if s == "DOWN":
        impact = "Impacto: unidade isolada (VPN)."
    elif s == "UP" and flaps_2h >= 2:
        impact = "Impacto: instabilidade na VPN (monitorar)."

    lines = [
        f"{head} {unit_label} — Painel (Tempo real)",
        "",
        vpn_line,
        "",
        impact,
    ]
    lines += _assistant_footer("vpn")
    return "\n".join(lines).rstrip()
