from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, cast

from . import dm_queries as base
from .config import SVCS, TZ_LOCAL, UNIT
from .dm_intents import FallbackReason, IntentData, IntentName, PeriodKey, ServiceKey
from .models import NocEvent, Snapshot
from .sources import get_events_window, get_last_n_events, get_latest_filtered


QueryMeta = base.QueryMeta
QueryResult = base.QueryResult


def _resolve_query_unit(unit: Optional[str]) -> str:
    value = (unit or UNIT or "UN1").upper().strip()
    return value or "UN1"


def _latest_event_for_service(service: ServiceKey, unit: str) -> tuple[Optional[NocEvent], Snapshot]:
    latest, snap = get_latest_filtered(unit=unit)
    events = sorted(latest.values(), key=lambda e: e.ts, reverse=True)
    svc_events = base._filter_events_by_service(events, service)
    return (svc_events[0] if svc_events else None), snap


def _load_window_events(period: PeriodKey, unit: str) -> tuple[list[NocEvent], Snapshot]:
    window = base._period_to_window(period)
    events, snap, _since, _now = get_events_window(window, unit=unit)
    return events, snap


def _recent_flap(service: Optional[ServiceKey], unit: str) -> bool:
    events, _snap = _load_window_events("24h", unit)
    events = base._filter_events_by_service(events, service)
    cutoff = datetime.now(events[0].ts.tzinfo) - timedelta(minutes=30) if events else None
    recent = [ev for ev in events if cutoff and ev.ts >= cutoff]
    return len(recent) >= 3


def _base_meta(
    snap: Snapshot,
    service: Optional[ServiceKey],
    events: list[NocEvent],
    latest_ev: Optional[NocEvent] = None,
    unit: Optional[str] = None,
) -> QueryMeta:
    latest_event_ts = latest_ev.ts if latest_ev else (events[-1].ts if events else None)
    active_incident = bool(latest_ev and (latest_ev.state or "").upper() == "DOWN")
    return {
        "source": cast(base.SourceKind, snap.source if snap.source in ("DB", "LOG") else "NONE"),
        "stale": base._snapshot_stale(snap),
        "active_incident": active_incident,
        "recent_flap": _recent_flap(service, _resolve_query_unit(unit)),
        "last_event_ts": base._dt_to_iso(latest_event_ts),
        "severity": base._service_severity(service, active_incident),
    }


def _result(
    *,
    unit: str,
    intent: IntentName,
    service: Optional[ServiceKey],
    period: PeriodKey,
    ok: bool,
    meta: QueryMeta,
    data: Dict[str, Any],
    fallback_reason: FallbackReason = "none",
) -> QueryResult:
    target_unit = _resolve_query_unit(unit)
    enriched = dict(data or {})
    enriched.setdefault("service_label", base._service_label(service))
    enriched.setdefault("period_label", base._period_label(period))
    enriched.setdefault("evidence_available", bool(service))
    enriched.setdefault("suggested_cta", base._suggested_cta(intent, service, meta))
    enriched.setdefault("assistant_brief", base._assistant_brief(intent, service, period, ok, meta))
    return {
        "version": "dm.query.v1",
        "unit": target_unit,
        "intent": intent,
        "service": service,
        "period": period,
        "ok": ok,
        "meta": meta,
        "data": enriched,
        "fallback_reason": fallback_reason,
    }


def query_status(service: Optional[ServiceKey], period: PeriodKey, unit: Optional[str] = None) -> QueryResult:
    target_unit = _resolve_query_unit(unit)
    if service:
        latest_ev, snap = _latest_event_for_service(service, target_unit)
        meta = _base_meta(snap, service, [latest_ev] if latest_ev else [], latest_ev, target_unit)
        if not latest_ev:
            return _result(unit=target_unit, intent="status_atual", service=service, period=period, ok=False, meta=meta, data={"state": "UNKNOWN", "since_ts": None, "duration_sec": None}, fallback_reason="no_service")
        duration_sec = int((datetime.now(latest_ev.ts.tzinfo) - latest_ev.ts).total_seconds())
        return _result(unit=target_unit, intent="status_atual", service=service, period=period, ok=True, meta=meta, data={"state": (latest_ev.state or "UNKNOWN").upper(), "since_ts": base._dt_to_iso(latest_ev.ts), "duration_sec": duration_sec})

    latest, snap = get_latest_filtered(unit=target_unit)
    latest_events = sorted(latest.values(), key=lambda e: e.ts, reverse=True)
    summary: Dict[str, Dict[str, Any]] = {}
    for code in ("L1", "L2", "TEL", "ESC", "VPN2", "VPN3"):
        svc_code = cast(ServiceKey, code)
        svc_events = base._filter_events_by_service(latest_events, svc_code)
        ev = svc_events[0] if svc_events else None
        summary[svc_code] = {"label": SVCS[svc_code].label, "state": (ev.state or "UNKNOWN").upper() if ev else "UNKNOWN", "since_ts": base._dt_to_iso(ev.ts) if ev else None}
    meta = _base_meta(snap, None, latest_events, latest_events[0] if latest_events else None, target_unit)
    return _result(unit=target_unit, intent="status_atual", service=None, period=period, ok=True, meta=meta, data={"services": summary})


def query_failures(service: ServiceKey, period: PeriodKey, unit: Optional[str] = None) -> QueryResult:
    target_unit = _resolve_query_unit(unit)
    events, snap = _load_window_events(period, target_unit)
    svc_events = base._filter_events_by_service(events, service)
    svc_events = base._filter_events_by_period(svc_events, period)
    svc_events.sort(key=lambda e: e.ts)
    downs = [ev for ev in svc_events if (ev.state or "").upper() == "DOWN"]
    last_down = downs[-1] if downs else None
    last_up = base._next_up_after(svc_events, last_down) if last_down else None
    last_duration_sec = int((last_up.ts - last_down.ts).total_seconds()) if last_down and last_up else None
    latest_ev, _snap2 = _latest_event_for_service(service, target_unit)
    meta = _base_meta(snap, service, svc_events, latest_ev, target_unit)
    return _result(unit=target_unit, intent="queda_servico_janela", service=service, period=period, ok=True, meta=meta, data={"count": len(downs), "window_label": base._period_label(period), "last_down_ts": base._dt_to_iso(last_down.ts) if last_down else None, "last_up_ts": base._dt_to_iso(last_up.ts) if last_up else None, "last_duration_sec": last_duration_sec, "last_cid": last_down.cid if last_down else None})


def query_failure_count(service: ServiceKey, period: PeriodKey, unit: Optional[str] = None) -> QueryResult:
    target_unit = _resolve_query_unit(unit)
    events, snap = _load_window_events(period, target_unit)
    svc_events = base._filter_events_by_service(events, service)
    svc_events = base._filter_events_by_period(svc_events, period)
    svc_events.sort(key=lambda e: e.ts)
    downs = [ev for ev in svc_events if (ev.state or "").upper() == "DOWN"]
    top_events = [{"ts": base._dt_to_iso(ev.ts), "cid": ev.cid, "duration_sec": None} for ev in downs[-5:]]
    latest_ev, _snap2 = _latest_event_for_service(service, target_unit)
    meta = _base_meta(snap, service, svc_events, latest_ev, target_unit)
    return _result(unit=target_unit, intent="contagem_falhas", service=service, period=period, ok=True, meta=meta, data={"count": len(downs), "window_label": base._period_label(period), "top_events": top_events})


def query_last_cid(service: ServiceKey, period: PeriodKey, unit: Optional[str] = None) -> QueryResult:
    target_unit = _resolve_query_unit(unit)
    events, snap = get_last_n_events(5000, unit=target_unit)
    svc_events = base._filter_events_by_service(events, service)
    svc_events.sort(key=lambda e: e.ts)
    event_with_cid = None
    for ev in reversed(svc_events):
        if ev.cid:
            event_with_cid = ev
            break
    latest_ev, _snap2 = _latest_event_for_service(service, target_unit)
    meta = _base_meta(snap, service, svc_events, latest_ev, target_unit)
    return _result(unit=target_unit, intent="ultimo_cid", service=service, period=period, ok=event_with_cid is not None, meta=meta, data={"cid": event_with_cid.cid if event_with_cid else None, "event_ts": base._dt_to_iso(event_with_cid.ts) if event_with_cid else None, "state": (event_with_cid.state or "UNKNOWN").upper() if event_with_cid else "UNKNOWN"}, fallback_reason="none" if event_with_cid else "no_service")


def query_period_summary(period: PeriodKey, unit: Optional[str] = None) -> QueryResult:
    target_unit = _resolve_query_unit(unit)
    events, snap = _load_window_events(period, target_unit)
    events = base._filter_events_by_period(events, period)
    events.sort(key=lambda e: e.ts)
    services_summary: Dict[str, Dict[str, Any]] = {}
    total_incidents = 0
    for code in ("L1", "L2", "TEL", "ESC", "VPN2", "VPN3"):
        svc_code = cast(ServiceKey, code)
        svc_events = base._filter_events_by_service(events, svc_code)
        downs = [ev for ev in svc_events if (ev.state or "").upper() == "DOWN"]
        count = len(downs)
        total_down_sec = base._total_down_seconds(svc_events)
        services_summary[svc_code] = {"count": count, "total_down_sec": total_down_sec}
        total_incidents += count
    latest, _snap2 = get_latest_filtered(unit=target_unit)
    latest_events = sorted(latest.values(), key=lambda e: e.ts, reverse=True)
    meta = _base_meta(snap, None, events, latest_events[0] if latest_events else None, target_unit)
    return _result(unit=target_unit, intent="resumo_periodo", service=None, period=period, ok=True, meta=meta, data={"total_incidents": total_incidents, "window_label": base._period_label(period), "services": services_summary})


def query_most_unstable(period: PeriodKey, unit: Optional[str] = None) -> QueryResult:
    target_unit = _resolve_query_unit(unit)
    events, snap = _load_window_events(period, target_unit)
    events = base._filter_events_by_period(events, period)
    events.sort(key=lambda e: e.ts)
    counters: list[tuple[ServiceKey, int]] = []
    for code in ("L1", "L2", "TEL", "ESC", "VPN2", "VPN3"):
        svc_code = cast(ServiceKey, code)
        svc_events = base._filter_events_by_service(events, svc_code)
        downs = [ev for ev in svc_events if (ev.state or "").upper() == "DOWN"]
        counters.append((svc_code, len(downs)))
    counters.sort(key=lambda item: item[1], reverse=True)
    winner_service, winner_count = counters[0]
    runner_up_service, runner_up_count = counters[1] if len(counters) > 1 else (winner_service, winner_count)
    latest, _snap2 = get_latest_filtered(unit=target_unit)
    latest_events = sorted(latest.values(), key=lambda e: e.ts, reverse=True)
    meta = _base_meta(snap, None, events, latest_events[0] if latest_events else None, target_unit)
    return _result(unit=target_unit, intent="comparativo_servico", service=None, period=period, ok=True, meta=meta, data={"winner_service": winner_service, "winner_count": winner_count, "runner_up_service": runner_up_service, "runner_up_count": runner_up_count, "window_label": base._period_label(period)})


def query_recommendation(service: ServiceKey, period: PeriodKey, unit: Optional[str] = None) -> QueryResult:
    target_unit = _resolve_query_unit(unit)
    latest_ev, snap = _latest_event_for_service(service, target_unit)
    meta = _base_meta(snap, service, [latest_ev] if latest_ev else [], latest_ev, target_unit)
    service_state = (latest_ev.state or "UNKNOWN").upper() if latest_ev else "UNKNOWN"
    last_cid = latest_ev.cid if latest_ev else None
    if service_state == "DOWN":
        if service == "L1":
            code, text = "OPEN_PROVIDER_TICKET", "Acionar o provedor do Link 1 com o CID da última queda."
        elif service == "L2":
            code, text = "OPEN_PROVIDER_TICKET", "Acionar o provedor do Link 2 e acompanhar estabilidade do link primário."
        elif service in ("TEL", "ESC"):
            code, text = "CHECK_LOCAL_PATH", "Validar impacto no link e depois gerar evidência ou texto pronto para o fornecedor."
        else:
            code, text = "MONITOR_ONLY", "Monitorar e validar recorrência antes de escalar."
    else:
        code, text = "MONITOR_ONLY", "No momento o serviço não está em queda ativa. Seguir monitoramento."
    return _result(unit=target_unit, intent="acao_recomendada", service=service, period=period, ok=True, meta=meta, data={"service_state": service_state, "recommendation_code": code, "recommendation_text": text, "last_cid": last_cid})


def dispatch_query(intent_data: IntentData) -> QueryResult:
    intent = intent_data["intent"]
    service = intent_data["service"]
    period = intent_data["period"]
    unit = _resolve_query_unit(intent_data.get("unit"))
    if intent == "status_atual":
        return query_status(service, period, unit=unit)
    if intent == "queda_servico_janela":
        if not service:
            return _result(unit=unit, intent=intent, service=None, period=period, ok=False, meta={"source": "NONE", "stale": True, "active_incident": False, "recent_flap": False, "last_event_ts": None, "severity": None}, data={}, fallback_reason="no_service")
        return query_failures(service, period, unit=unit)
    if intent == "contagem_falhas":
        if not service:
            return _result(unit=unit, intent=intent, service=None, period=period, ok=False, meta={"source": "NONE", "stale": True, "active_incident": False, "recent_flap": False, "last_event_ts": None, "severity": None}, data={}, fallback_reason="no_service")
        return query_failure_count(service, period, unit=unit)
    if intent == "ultimo_cid":
        if not service:
            return _result(unit=unit, intent=intent, service=None, period=period, ok=False, meta={"source": "NONE", "stale": True, "active_incident": False, "recent_flap": False, "last_event_ts": None, "severity": None}, data={}, fallback_reason="no_service")
        return query_last_cid(service, period, unit=unit)
    if intent == "resumo_periodo":
        return query_period_summary(period, unit=unit)
    if intent == "comparativo_servico":
        return query_most_unstable(period, unit=unit)
    if intent == "acao_recomendada":
        if not service:
            return _result(unit=unit, intent=intent, service=None, period=period, ok=False, meta={"source": "NONE", "stale": True, "active_incident": False, "recent_flap": False, "last_event_ts": None, "severity": None}, data={}, fallback_reason="no_service")
        return query_recommendation(service, period, unit=unit)
    return _result(unit=unit, intent="unknown", service=service, period=period, ok=False, meta={"source": "NONE", "stale": True, "active_incident": False, "recent_flap": False, "last_event_ts": None, "severity": None}, data={}, fallback_reason="no_intent")
