# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Literal, Optional, TypedDict, cast

from .config import DB_EVENT_STALE_S, TZ_LOCAL, UNIT, SVCS
from .dm_intents import (
    FallbackReason,
    IntentData,
    IntentName,
    PeriodKey,
    ServiceKey,
)
from .models import NocEvent, Snapshot
from .sources import get_events_window, get_last_n_events, get_latest_filtered

SourceKind = Literal["DB", "LOG", "NONE"]


class QueryMeta(TypedDict):
    source: SourceKind
    stale: bool
    active_incident: bool
    recent_flap: bool
    last_event_ts: Optional[str]
    severity: Optional[str]


class QueryResult(TypedDict):
    version: str
    unit: str
    intent: IntentName
    service: Optional[ServiceKey]
    period: PeriodKey
    ok: bool
    meta: QueryMeta
    data: Dict[str, Any]
    fallback_reason: FallbackReason


def _dt_to_iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    return dt.astimezone(TZ_LOCAL).isoformat()


def _snapshot_stale(snap: Snapshot) -> bool:
    if snap.freshness_s is None:
        return True
    return snap.freshness_s > DB_EVENT_STALE_S


def _period_to_window(period: PeriodKey) -> str:
    if period in ("7d", "week"):
        return "7d"
    if period in ("30d", "month"):
        return "30d"
    return "24h"


def _period_label(period: PeriodKey) -> str:
    labels = {
        "now": "agora",
        "today": "hoje",
        "yesterday": "ontem",
        "24h": "últimas 24h",
        "7d": "últimos 7 dias",
        "30d": "últimos 30 dias",
        "week": "semana",
        "month": "mês",
        "unspecified": "janela padrão",
    }
    return labels.get(period, "janela padrão")


def _service_severity(service: Optional[ServiceKey], active_incident: bool) -> Optional[str]:
    if not service or not active_incident:
        return None
    if service == "L1":
        return "SEV1"
    if service in ("TEL", "ESC"):
        return "SEV2"
    if service == "L2":
        return "SEV3"
    return "SEV4"


def _event_tokens(ev: NocEvent) -> str:
    joined = " ".join(
        [
            ev.check or "",
            ev.host or "",
            ev.raw or "",
            ev.device or "",
        ]
    )
    return joined.upper()


def _event_matches_service(ev: NocEvent, service: ServiceKey) -> bool:
    svc = SVCS[service]
    hay = _event_tokens(ev)

    candidates = [
        svc.code,
        svc.key,
        svc.label,
        svc.subject,
        *svc.aliases,
    ]

    for item in candidates:
        if item and str(item).upper() in hay:
            return True

    # Ajustes pragmáticos para checks mais comuns
    if service == "TEL" and "VOIP" in hay:
        return True
    if service == "L1" and "MUNDIVOX" in hay:
        return True
    if service == "L2" and "VALENET" in hay:
        return True
    if service == "ESC" and "ESCALLO" in hay:
        return True
    if service == "VPN2" and ("VPN_UN2" in hay or "UN2" in hay or "BARREIRO" in hay):
        return True
    if service == "VPN3" and ("VPN_UN3" in hay or "UN3" in hay or "ALIPIO" in hay or "ALÍPIO" in hay):
        return True

    return False


def _filter_events_by_service(events: list[NocEvent], service: Optional[ServiceKey]) -> list[NocEvent]:
    if not service:
        return list(events)
    return [ev for ev in events if _event_matches_service(ev, service)]


def _filter_events_by_period(events: list[NocEvent], period: PeriodKey) -> list[NocEvent]:
    if period in ("24h", "7d", "30d", "week", "month", "unspecified"):
        return list(events)

    now_local = datetime.now(TZ_LOCAL)
    today_local = now_local.date()
    yesterday_local = (now_local - timedelta(days=1)).date()

    out: list[NocEvent] = []
    for ev in events:
        ev_date = ev.ts.astimezone(TZ_LOCAL).date()

        if period == "today" and ev_date == today_local:
            out.append(ev)
        elif period == "yesterday" and ev_date == yesterday_local:
            out.append(ev)
        elif period == "now":
            if ev.ts >= (now_local.astimezone(ev.ts.tzinfo) - timedelta(minutes=30)):
                out.append(ev)

    return out


def _latest_event_for_service(service: ServiceKey) -> tuple[Optional[NocEvent], Snapshot]:
    latest, snap = get_latest_filtered()
    events = sorted(latest.values(), key=lambda e: e.ts, reverse=True)
    svc_events = _filter_events_by_service(events, service)
    return (svc_events[0] if svc_events else None), snap


def _load_window_events(period: PeriodKey) -> tuple[list[NocEvent], Snapshot]:
    window = _period_to_window(period)
    events, snap, _since, _now = get_events_window(window)
    return events, snap


def _recent_flap(service: Optional[ServiceKey]) -> bool:
    events, _snap = _load_window_events("24h")
    events = _filter_events_by_service(events, service)
    cutoff = datetime.now(events[0].ts.tzinfo) - timedelta(minutes=30) if events else None
    recent = [ev for ev in events if cutoff and ev.ts >= cutoff]
    return len(recent) >= 3


def _last_down_event(events: list[NocEvent]) -> Optional[NocEvent]:
    downs = [ev for ev in events if (ev.state or "").upper() == "DOWN"]
    return downs[-1] if downs else None


def _next_up_after(events: list[NocEvent], down_ev: NocEvent) -> Optional[NocEvent]:
    for ev in events:
        if ev.ts > down_ev.ts and (ev.state or "").upper() == "UP":
            return ev
    return None


def _total_down_seconds(events: list[NocEvent]) -> int:
    total = 0
    events = sorted(events, key=lambda e: e.ts)
    open_down: Optional[NocEvent] = None

    for ev in events:
        state = (ev.state or "").upper()

        if state == "DOWN" and open_down is None:
            open_down = ev
        elif state == "UP" and open_down is not None:
            total += int((ev.ts - open_down.ts).total_seconds())
            open_down = None

    if open_down is not None:
        total += int((datetime.now(open_down.ts.tzinfo) - open_down.ts).total_seconds())

    return max(total, 0)


def _base_meta(
    snap: Snapshot,
    service: Optional[ServiceKey],
    events: list[NocEvent],
    latest_ev: Optional[NocEvent] = None,
) -> QueryMeta:
    latest_event_ts = latest_ev.ts if latest_ev else (events[-1].ts if events else None)
    active_incident = bool(latest_ev and (latest_ev.state or "").upper() == "DOWN")
    return {
        "source": cast(SourceKind, snap.source if snap.source in ("DB", "LOG") else "NONE"),
        "stale": _snapshot_stale(snap),
        "active_incident": active_incident,
        "recent_flap": _recent_flap(service),
        "last_event_ts": _dt_to_iso(latest_event_ts),
        "severity": _service_severity(service, active_incident),
    }


def _result(
    *,
    intent: IntentName,
    service: Optional[ServiceKey],
    period: PeriodKey,
    ok: bool,
    meta: QueryMeta,
    data: Dict[str, Any],
    fallback_reason: FallbackReason = "none",
) -> QueryResult:
    return {
        "version": "dm.query.v1",
        "unit": UNIT,
        "intent": intent,
        "service": service,
        "period": period,
        "ok": ok,
        "meta": meta,
        "data": data,
        "fallback_reason": fallback_reason,
    }


def query_status(service: Optional[ServiceKey], period: PeriodKey) -> QueryResult:
    if service:
        latest_ev, snap = _latest_event_for_service(service)
        meta = _base_meta(snap, service, [latest_ev] if latest_ev else [], latest_ev)

        if not latest_ev:
            return _result(
                intent="status_atual",
                service=service,
                period=period,
                ok=False,
                meta=meta,
                data={"state": "UNKNOWN", "since_ts": None, "duration_sec": None},
                fallback_reason="no_service",
            )

        duration_sec = int((datetime.now(latest_ev.ts.tzinfo) - latest_ev.ts).total_seconds())
        return _result(
            intent="status_atual",
            service=service,
            period=period,
            ok=True,
            meta=meta,
            data={
                "state": (latest_ev.state or "UNKNOWN").upper(),
                "since_ts": _dt_to_iso(latest_ev.ts),
                "duration_sec": duration_sec,
            },
        )

    latest, snap = get_latest_filtered()
    latest_events = sorted(latest.values(), key=lambda e: e.ts, reverse=True)
    summary: Dict[str, Dict[str, Any]] = {}

    for code in ("L1", "L2", "TEL", "ESC", "VPN2", "VPN3"):
        svc_code = cast(ServiceKey, code)
        svc_events = _filter_events_by_service(latest_events, svc_code)
        ev = svc_events[0] if svc_events else None
        summary[svc_code] = {
            "label": SVCS[svc_code].label,
            "state": (ev.state or "UNKNOWN").upper() if ev else "UNKNOWN",
            "since_ts": _dt_to_iso(ev.ts) if ev else None,
        }

    meta = _base_meta(snap, None, latest_events, latest_events[0] if latest_events else None)

    return _result(
        intent="status_atual",
        service=None,
        period=period,
        ok=True,
        meta=meta,
        data={"services": summary},
    )


def query_failures(service: ServiceKey, period: PeriodKey) -> QueryResult:
    events, snap = _load_window_events(period)
    svc_events = _filter_events_by_service(events, service)
    svc_events = _filter_events_by_period(svc_events, period)
    svc_events.sort(key=lambda e: e.ts)

    downs = [ev for ev in svc_events if (ev.state or "").upper() == "DOWN"]
    last_down = downs[-1] if downs else None
    last_up = _next_up_after(svc_events, last_down) if last_down else None
    last_duration_sec = (
        int((last_up.ts - last_down.ts).total_seconds()) if last_down and last_up else None
    )

    latest_ev, _snap2 = _latest_event_for_service(service)
    meta = _base_meta(snap, service, svc_events, latest_ev)

    return _result(
        intent="queda_servico_janela",
        service=service,
        period=period,
        ok=True,
        meta=meta,
        data={
            "count": len(downs),
            "window_label": _period_label(period),
            "last_down_ts": _dt_to_iso(last_down.ts) if last_down else None,
            "last_up_ts": _dt_to_iso(last_up.ts) if last_up else None,
            "last_duration_sec": last_duration_sec,
            "last_cid": last_down.cid if last_down else None,
        },
    )


def query_failure_count(service: ServiceKey, period: PeriodKey) -> QueryResult:
    events, snap = _load_window_events(period)
    svc_events = _filter_events_by_service(events, service)
    svc_events = _filter_events_by_period(svc_events, period)
    svc_events.sort(key=lambda e: e.ts)

    downs = [ev for ev in svc_events if (ev.state or "").upper() == "DOWN"]
    top_events = [
        {
            "ts": _dt_to_iso(ev.ts),
            "cid": ev.cid,
            "duration_sec": None,
        }
        for ev in downs[-5:]
    ]

    latest_ev, _snap2 = _latest_event_for_service(service)
    meta = _base_meta(snap, service, svc_events, latest_ev)

    return _result(
        intent="contagem_falhas",
        service=service,
        period=period,
        ok=True,
        meta=meta,
        data={
            "count": len(downs),
            "window_label": _period_label(period),
            "top_events": top_events,
        },
    )


def query_last_cid(service: ServiceKey, period: PeriodKey) -> QueryResult:
    events, snap = get_last_n_events(5000)
    svc_events = _filter_events_by_service(events, service)
    svc_events.sort(key=lambda e: e.ts)

    event_with_cid = None
    for ev in reversed(svc_events):
        if ev.cid:
            event_with_cid = ev
            break

    latest_ev, _snap2 = _latest_event_for_service(service)
    meta = _base_meta(snap, service, svc_events, latest_ev)

    return _result(
        intent="ultimo_cid",
        service=service,
        period=period,
        ok=event_with_cid is not None,
        meta=meta,
        data={
            "cid": event_with_cid.cid if event_with_cid else None,
            "event_ts": _dt_to_iso(event_with_cid.ts) if event_with_cid else None,
            "state": (event_with_cid.state or "UNKNOWN").upper() if event_with_cid else "UNKNOWN",
        },
        fallback_reason="none" if event_with_cid else "no_service",
    )


def query_period_summary(period: PeriodKey) -> QueryResult:
    events, snap = _load_window_events(period)
    events = _filter_events_by_period(events, period)
    events.sort(key=lambda e: e.ts)

    services_summary: Dict[str, Dict[str, Any]] = {}
    total_incidents = 0

    for code in ("L1", "L2", "TEL", "ESC", "VPN2", "VPN3"):
        svc_code = cast(ServiceKey, code)
        svc_events = _filter_events_by_service(events, svc_code)
        downs = [ev for ev in svc_events if (ev.state or "").upper() == "DOWN"]
        count = len(downs)
        total_down_sec = _total_down_seconds(svc_events)

        services_summary[svc_code] = {
            "count": count,
            "total_down_sec": total_down_sec,
        }
        total_incidents += count

    latest, _snap2 = get_latest_filtered()
    latest_events = sorted(latest.values(), key=lambda e: e.ts, reverse=True)
    meta = _base_meta(snap, None, events, latest_events[0] if latest_events else None)

    return _result(
        intent="resumo_periodo",
        service=None,
        period=period,
        ok=True,
        meta=meta,
        data={
            "total_incidents": total_incidents,
            "window_label": _period_label(period),
            "services": services_summary,
        },
    )


def query_most_unstable(period: PeriodKey) -> QueryResult:
    events, snap = _load_window_events(period)
    events = _filter_events_by_period(events, period)
    events.sort(key=lambda e: e.ts)

    counters: list[tuple[ServiceKey, int]] = []
    for code in ("L1", "L2", "TEL", "ESC", "VPN2", "VPN3"):
        svc_code = cast(ServiceKey, code)
        svc_events = _filter_events_by_service(events, svc_code)
        downs = [ev for ev in svc_events if (ev.state or "").upper() == "DOWN"]
        counters.append((svc_code, len(downs)))

    counters.sort(key=lambda item: item[1], reverse=True)
    winner_service, winner_count = counters[0]
    runner_up_service, runner_up_count = counters[1] if len(counters) > 1 else (winner_service, winner_count)

    latest, _snap2 = get_latest_filtered()
    latest_events = sorted(latest.values(), key=lambda e: e.ts, reverse=True)
    meta = _base_meta(snap, None, events, latest_events[0] if latest_events else None)

    return _result(
        intent="comparativo_servico",
        service=None,
        period=period,
        ok=True,
        meta=meta,
        data={
            "winner_service": winner_service,
            "winner_count": winner_count,
            "runner_up_service": runner_up_service,
            "runner_up_count": runner_up_count,
            "window_label": _period_label(period),
        },
    )


def query_recommendation(service: ServiceKey, period: PeriodKey) -> QueryResult:
    latest_ev, snap = _latest_event_for_service(service)
    meta = _base_meta(snap, service, [latest_ev] if latest_ev else [], latest_ev)

    service_state = (latest_ev.state or "UNKNOWN").upper() if latest_ev else "UNKNOWN"
    last_cid = latest_ev.cid if latest_ev else None

    if service_state == "DOWN":
        if service == "L1":
            code = "OPEN_PROVIDER_TICKET"
            text = "Acionar o provedor do Link 1 com o CID da última queda."
        elif service == "L2":
            code = "OPEN_PROVIDER_TICKET"
            text = "Acionar o provedor do Link 2 e acompanhar estabilidade do link primário."
        elif service in ("TEL", "ESC"):
            code = "CHECK_LOCAL_PATH"
            text = "Validar impacto no link e depois gerar evidência ou texto pronto para o fornecedor."
        else:
            code = "MONITOR_ONLY"
            text = "Monitorar e validar recorrência antes de escalar."
    else:
        code = "MONITOR_ONLY"
        text = "No momento o serviço não está em queda ativa. Seguir monitoramento."

    return _result(
        intent="acao_recomendada",
        service=service,
        period=period,
        ok=True,
        meta=meta,
        data={
            "service_state": service_state,
            "recommendation_code": code,
            "recommendation_text": text,
            "last_cid": last_cid,
        },
    )


def dispatch_query(intent_data: IntentData) -> QueryResult:
    intent = intent_data["intent"]
    service = intent_data["service"]
    period = intent_data["period"]

    if intent == "status_atual":
        return query_status(service, period)

    if intent == "queda_servico_janela":
        if not service:
            return _result(
                intent=intent,
                service=None,
                period=period,
                ok=False,
                meta={
                    "source": "NONE",
                    "stale": True,
                    "active_incident": False,
                    "recent_flap": False,
                    "last_event_ts": None,
                    "severity": None,
                },
                data={},
                fallback_reason="no_service",
            )
        return query_failures(service, period)

    if intent == "contagem_falhas":
        if not service:
            return _result(
                intent=intent,
                service=None,
                period=period,
                ok=False,
                meta={
                    "source": "NONE",
                    "stale": True,
                    "active_incident": False,
                    "recent_flap": False,
                    "last_event_ts": None,
                    "severity": None,
                },
                data={},
                fallback_reason="no_service",
            )
        return query_failure_count(service, period)

    if intent == "ultimo_cid":
        if not service:
            return _result(
                intent=intent,
                service=None,
                period=period,
                ok=False,
                meta={
                    "source": "NONE",
                    "stale": True,
                    "active_incident": False,
                    "recent_flap": False,
                    "last_event_ts": None,
                    "severity": None,
                },
                data={},
                fallback_reason="no_service",
            )
        return query_last_cid(service, period)

    if intent == "resumo_periodo":
        return query_period_summary(period)

    if intent == "comparativo_servico":
        return query_most_unstable(period)

    if intent == "acao_recomendada":
        if not service:
            return _result(
                intent=intent,
                service=None,
                period=period,
                ok=False,
                meta={
                    "source": "NONE",
                    "stale": True,
                    "active_incident": False,
                    "recent_flap": False,
                    "last_event_ts": None,
                    "severity": None,
                },
                data={},
                fallback_reason="no_service",
            )
        return query_recommendation(service, period)

    return _result(
        intent="unknown",
        service=service,
        period=period,
        ok=False,
        meta={
            "source": "NONE",
            "stale": True,
            "active_incident": False,
            "recent_flap": False,
            "last_event_ts": None,
            "severity": None,
        },
        data={},
        fallback_reason="no_intent",
    )
