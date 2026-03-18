# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import re
from typing import Literal, Optional, TypedDict, cast

from .ai_client import classify_dm_message_with_ai
from .config import (
    DM_ASSISTANT_CLASSIFIER_SHADOW_MODE,
    DM_ASSISTANT_ENABLE_AI_CLASSIFIER,
    DM_ASSISTANT_ENABLE_CLARIFY,
    DM_ASSISTANT_ENABLE_GENERAL_HELP,
    DM_ASSISTANT_ENABLE_SESSION_CONTEXT,
    DM_ASSISTANT_ENABLE_SOCIAL,
    DM_ASSISTANT_MIN_CONFIDENCE,
)
from .dm_intents import (
    IntentData,
    IntentName,
    PeriodKey,
    ServiceKey,
    build_intent_data,
    contains_noc_domain,
    detect_intent,
    detect_intent_name,
    extract_period,
    extract_service,
    extract_service_hits,
    looks_like_consult_question,
    looks_like_incident_report,
    looks_like_status_probe,
    normalize_text,
)
from .dm_session import ClarifyKind, clear_pending, open_clarify, peek_session

log = logging.getLogger(__name__)

RouteName = Literal["consult", "incident", "clarify", "social", "help", "none"]
DecisionSource = Literal["session", "deterministic", "ai", "none"]


class RouteDecision(TypedDict):
    handled: bool
    route: RouteName
    source: DecisionSource
    intent_data: Optional[IntentData]
    clarify_kind: Optional[ClarifyKind]
    clarify_text: Optional[str]
    reply_text: Optional[str]
    reason: str


def _decision(
    *,
    handled: bool,
    route: RouteName,
    source: DecisionSource,
    intent_data: Optional[IntentData] = None,
    clarify_kind: Optional[ClarifyKind] = None,
    clarify_text: Optional[str] = None,
    reply_text: Optional[str] = None,
    reason: str = "",
) -> RouteDecision:
    return {
        "handled": handled,
        "route": route,
        "source": source,
        "intent_data": intent_data,
        "clarify_kind": clarify_kind,
        "clarify_text": clarify_text,
        "reply_text": reply_text,
        "reason": reason,
    }


_GREETING_ONLY_PATTERN = re.compile(
    r"^(oi|ola|olá|bom dia|boa tarde|boa noite|e ai|e aí|opa|ol[aá],? boa tarde|oi,? boa tarde|oi,? bom dia|oi,? boa noite)[!. ]*$"
)

_SPEEDTEST_SITE_PATTERN = re.compile(r"\b(site|link|url|endereco|endereço)\b.*\b(speed\s*test|speedtest)\b")
_SPEEDTEST_WORD_PATTERN = re.compile(r"\b(speed\s*test|speedtest)\b")
_MEASURE_SPEED_PATTERN = re.compile(
    r"\b(como faco|como faço|como medir|medir)\b.*\b(velocidade|internet|rede)\b|\b(velocidade da internet|teste de velocidade)\b"
)

_SHORT_FOLLOWUPS = {"agora", "hoje", "ontem", "semana", "7d", "24h", "30d", "detalhes", "detalhe"}


def _is_short_followup(normalized_text: str) -> bool:
    return normalized_text in _SHORT_FOLLOWUPS


def _is_questionish(text: str, normalized_text: str) -> bool:
    return ("?" in (text or "")) or looks_like_consult_question(normalized_text, normalized=True)


def _service_scope_prompt(service: Optional[ServiceKey]) -> str:
    name = {
        "TEL": "da telefonia",
        "ESC": "da Escallo",
        "L1": "do Link 1",
        "L2": "do Link 2",
        "NET": "da internet",
        "VPN2": "da VPN UN2",
        "VPN3": "da VPN UN3",
    }.get(service or "", "desse serviço")
    return f"Você quer o status atual {name}, as falhas de hoje ou um resumo da semana?"


def _status_or_window_prompt(service: Optional[ServiceKey]) -> str:
    name = {
        "TEL": "da telefonia",
        "ESC": "da Escallo",
        "L1": "do Link 1",
        "L2": "do Link 2",
        "NET": "da internet",
        "VPN2": "da VPN UN2",
        "VPN3": "da VPN UN3",
    }.get(service or "", "do serviço")
    return f"Você quer saber o status atual {name} ou se houve falha hoje?"


def _service_select_prompt() -> str:
    return "Qual serviço você quer verificar: Link 1, Link 2, telefonia, Escallo ou internet?"


def _consult_or_incident_prompt() -> str:
    return "Você quer consultar o status agora ou está com incidente em andamento neste momento?"


def _generic_prompt() -> str:
    return "Você quer status atual, falhas de hoje ou resumo da semana?"


def _is_global_status_request(normalized_text: str) -> bool:
    return normalized_text in {
        "status",
        "status atual",
        "agora",
        "como esta",
        "como ta",
        "como ta agora",
        "como esta agora",
        "ta ok",
        "ta tudo bem",
        "tudo ok",
        "tudo bem",
    }


def _build_social_reply(text: str) -> str:
    normalized = normalize_text(text)
    if "boa tarde" in normalized:
        head = "Boa tarde."
    elif "bom dia" in normalized:
        head = "Bom dia."
    elif "boa noite" in normalized:
        head = "Boa noite."
    else:
        head = "Oi."
    return f"{head} Estou por aqui. Posso te ajudar com status da unidade, telefonia, links, Escallo ou alguma dúvida rápida."


def _build_help_reply(text: str) -> str:
    normalized = normalize_text(text)
    if _SPEEDTEST_SITE_PATTERN.search(normalized):
        return "Use este: https://www.speedtest.net/\nSe fizer o teste no Wi-Fi, o resultado pode variar mais. No cabo a leitura costuma ficar mais fiel."
    if _MEASURE_SPEED_PATTERN.search(normalized) or _SPEEDTEST_WORD_PATTERN.search(normalized):
        return (
            "Abra um teste de velocidade no navegador, de preferência sem downloads paralelos e na mesma rede do problema. "
            "O mais usado é o Speedtest: https://www.speedtest.net/"
        )
    return "Posso te orientar em dúvida rápida. Se for sobre internet, o caminho mais comum é medir no Speedtest e comparar cabo x Wi-Fi."


def _looks_like_social(text: str, normalized_text: str) -> bool:
    if not DM_ASSISTANT_ENABLE_SOCIAL:
        return False
    if not normalized_text:
        return False
    if _GREETING_ONLY_PATTERN.match(normalized_text):
        return True
    tokens = normalized_text.split()
    if len(tokens) <= 4 and any(g in normalized_text for g in ("oi", "olá", "ola", "boa tarde", "bom dia", "boa noite")):
        return True
    return False


def _looks_like_general_help(normalized_text: str) -> bool:
    if not DM_ASSISTANT_ENABLE_GENERAL_HELP:
        return False
    if not normalized_text:
        return False
    if _SPEEDTEST_SITE_PATTERN.search(normalized_text):
        return True
    if _MEASURE_SPEED_PATTERN.search(normalized_text):
        return True
    if _SPEEDTEST_WORD_PATTERN.search(normalized_text):
        return True
    return False


def _build_clarify(
    chat_id: int,
    *,
    kind: ClarifyKind,
    service: Optional[ServiceKey] = None,
    intent: Optional[IntentName] = None,
    period: PeriodKey = "unspecified",
    missing_slots: Optional[list[str]] = None,
    source: DecisionSource = "deterministic",
    reason: str = "",
    custom_text: Optional[str] = None,
) -> RouteDecision:
    if not DM_ASSISTANT_ENABLE_CLARIFY:
        return _decision(handled=False, route="none", source=source, reason=f"clarify_disabled:{reason}")

    if kind == "service_scope":
        clarify_text = custom_text or _service_scope_prompt(service)
    elif kind == "service_select":
        clarify_text = custom_text or _service_select_prompt()
    elif kind == "status_or_window":
        clarify_text = custom_text or _status_or_window_prompt(service)
    elif kind == "consult_or_incident":
        clarify_text = custom_text or _consult_or_incident_prompt()
    else:
        clarify_text = custom_text or _generic_prompt()

    open_clarify(
        chat_id,
        clarify_kind=kind,
        pending_route="consult",
        pending_intent=intent,
        pending_service=service,
        pending_period=period,
        missing_slots=missing_slots or [],
    )
    return _decision(
        handled=True,
        route="clarify",
        source=source,
        clarify_kind=kind,
        clarify_text=clarify_text,
        reason=reason or kind,
    )


def _build_intent_from_fields(
    *,
    text: str,
    intent: IntentName,
    service: Optional[ServiceKey],
    period: PeriodKey,
    source: str,
    confidence: float,
) -> IntentData:
    normalized_text = normalize_text(text)
    service_hits = extract_service_hits(normalized_text, normalized=True)
    entities = {
        "service_hits": service_hits,
        "service_hit_count": len(service_hits),
        "source": source,
    }
    return build_intent_data(
        text=text,
        normalized_text=normalized_text,
        intent=intent,
        service=service,
        period=period,
        confidence=confidence,
        fallback_reason="none",
        entities=entities,
    )


def _apply_session_context(chat_id: int, text: str, intent_data: IntentData) -> IntentData:
    if not DM_ASSISTANT_ENABLE_SESSION_CONTEXT:
        return intent_data
    sess = peek_session(chat_id)
    if not sess:
        return intent_data

    service = intent_data["service"]
    period = intent_data["period"]
    intent = intent_data["intent"]
    confidence = float(intent_data["confidence"])
    normalized_text = intent_data["normalized_text"]
    changed = False

    if service is None and sess.get("last_service") and (_is_short_followup(normalized_text) or normalized_text.startswith("e ")):
        service = cast(Optional[ServiceKey], sess.get("last_service"))
        changed = True

    if period == "unspecified" and sess.get("last_period") and normalized_text in {"e ai", "e aí", "e agora", "e hoje", "e ontem"}:
        period = cast(PeriodKey, sess.get("last_period") or "unspecified")
        changed = True

    if intent == "unknown" and sess.get("last_intent") and (_is_short_followup(normalized_text) or normalized_text.startswith("e ")):
        last_intent = cast(IntentName, sess.get("last_intent") or "unknown")
        if last_intent == "status_atual" and period in {"today", "yesterday", "24h", "7d", "30d", "week", "month"}:
            intent = "queda_servico_janela" if service else "resumo_periodo"
        else:
            intent = last_intent
        changed = True

    if changed:
        entities = dict(intent_data["entities"])
        entities["session_context_applied"] = True
        return build_intent_data(
            text=text,
            normalized_text=normalized_text,
            intent=intent,
            service=service,
            period=period,
            confidence=max(confidence, 0.78),
            fallback_reason="none",
            entities=entities,
        )

    return intent_data


def _resolve_from_session(chat_id: int, text: str) -> Optional[RouteDecision]:
    sess = peek_session(chat_id)
    if not sess or not sess.get("awaiting"):
        return None

    normalized_text = normalize_text(text)
    service = cast(Optional[ServiceKey], sess.get("pending_service"))
    pending_intent = cast(Optional[IntentName], sess.get("pending_intent"))
    pending_period = cast(PeriodKey, sess.get("pending_period") or "unspecified")
    kind = cast(ClarifyKind, sess.get("clarify_kind") or "generic")

    if kind == "consult_or_incident":
        if looks_like_incident_report(normalized_text, normalized=True) or re.search(r"\b(incidente|caiu|sem|parou|travando|travou|lento|instavel)\b", normalized_text):
            clear_pending(chat_id)
            return _decision(handled=True, route="incident", source="session", reason="clarify_consult_or_incident")
        if re.search(r"\b(status|consulta|consultar|ver|checar|agora|atual|ok)\b", normalized_text):
            intent_data = _build_intent_from_fields(text=text, intent="status_atual", service=service or "NET", period="now", source="session.consult_or_incident", confidence=0.86)
            clear_pending(chat_id)
            return _decision(handled=True, route="consult", source="session", intent_data=intent_data, reason="clarify_to_consult")
        return _build_clarify(chat_id, kind="consult_or_incident", service=service, source="session", reason="clarify_retry")

    if kind == "service_select":
        service_reply = extract_service(normalized_text, normalized=True)
        if service_reply:
            service = service_reply
            if pending_intent:
                period = pending_period if pending_period != "unspecified" else ("now" if pending_intent == "status_atual" else "today")
                intent_data = _build_intent_from_fields(text=text, intent=pending_intent, service=service, period=period, source="session.service_select", confidence=0.85)
                clear_pending(chat_id)
                return _decision(handled=True, route="consult", source="session", intent_data=intent_data, reason="service_selected")
            clear_pending(chat_id)
            return _build_clarify(chat_id, kind="service_scope", service=service, source="session", reason="service_then_scope")
        return _build_clarify(chat_id, kind="service_select", source="session", reason="service_select_retry")

    if kind in {"service_scope", "status_or_window", "generic"}:
        period = extract_period(normalized_text, normalized=True)

        if _is_global_status_request(normalized_text) and extract_service(normalized_text, normalized=True) is None:
            intent_data = _build_intent_from_fields(text=text, intent="status_atual", service=None, period="now", source=f"session.{kind}.global_status", confidence=0.86)
            clear_pending(chat_id)
            return _decision(handled=True, route="consult", source="session", intent_data=intent_data, reason="global_status_override")

        if any(token in normalized_text for token in ("agora", "atual", "status", "ok")):
            intent = "status_atual"
            period = "now"
        elif any(token in normalized_text for token in ("hoje", "24h", "falha", "quedas", "queda")):
            intent = "queda_servico_janela"
            period = "today" if period == "unspecified" else period
        elif any(token in normalized_text for token in ("semana", "7d", "resumo")):
            intent = "queda_servico_janela" if service else "resumo_periodo"
            period = "7d"
        elif pending_intent:
            intent = pending_intent
        else:
            intent = detect_intent_name(normalized_text, normalized=True)

        if service is None:
            service = extract_service(normalized_text, normalized=True) or cast(Optional[ServiceKey], sess.get("last_service"))

        if intent == "unknown" and looks_like_status_probe(normalized_text, normalized=True):
            intent = "status_atual"
            period = "now"

        if service and intent != "unknown":
            if period == "unspecified":
                period = "now" if intent == "status_atual" else "today"
            intent_data = _build_intent_from_fields(text=text, intent=intent, service=service, period=period, source=f"session.{kind}", confidence=0.84)
            clear_pending(chat_id)
            return _decision(handled=True, route="consult", source="session", intent_data=intent_data, reason="clarify_completed")

        if intent in {"status_atual", "resumo_periodo", "comparativo_servico"}:
            if period == "unspecified":
                period = "now" if intent == "status_atual" else "7d"
            intent_data = _build_intent_from_fields(text=text, intent=intent, service=service, period=period, source=f"session.{kind}", confidence=0.82)
            clear_pending(chat_id)
            return _decision(handled=True, route="consult", source="session", intent_data=intent_data, reason="clarify_completed_optional_service")

        if service is None:
            return _build_clarify(chat_id, kind="service_select", source="session", reason="clarify_missing_service_again")
        return _build_clarify(chat_id, kind=kind, service=service, source="session", reason="clarify_retry")

    return None


def _deterministic_social(text: str) -> Optional[RouteDecision]:
    normalized_text = normalize_text(text)
    if _looks_like_social(text, normalized_text):
        return _decision(handled=True, route="social", source="deterministic", reply_text=_build_social_reply(text), reason="social_greeting")
    return None


def _deterministic_help(text: str) -> Optional[RouteDecision]:
    normalized_text = normalize_text(text)
    if _looks_like_general_help(normalized_text):
        return _decision(handled=True, route="help", source="deterministic", reply_text=_build_help_reply(text), reason="general_help")
    return None


def _deterministic_consult(chat_id: int, text: str) -> Optional[RouteDecision]:
    intent_data = _apply_session_context(chat_id, text, detect_intent(text, min_confidence=DM_ASSISTANT_MIN_CONFIDENCE))
    normalized_text = intent_data["normalized_text"]
    service = intent_data["service"]
    intent = intent_data["intent"]
    period = intent_data["period"]

    if (
        service
        and intent == "status_atual"
        and period == "now"
        and not looks_like_status_probe(normalized_text, normalized=True)
        and (_is_questionish(text, normalized_text) or normalized_text.startswith("e "))
    ):
        return _build_clarify(
            chat_id,
            kind="service_scope",
            service=service,
            source="deterministic",
            reason="service_scope_question",
        )

    if intent != "unknown" and intent_data["confidence"] >= DM_ASSISTANT_MIN_CONFIDENCE:
        return _decision(handled=True, route="consult", source="deterministic", intent_data=intent_data, reason="deterministic_consult")

    if service and intent == "unknown":
        return _build_clarify(chat_id, kind="service_scope", service=service, source="deterministic", reason="service_without_intent")

    if service and intent == "queda_servico_janela" and period == "unspecified" and _is_questionish(text, normalized_text):
        return _build_clarify(chat_id, kind="status_or_window", service=service, source="deterministic", reason="question_needs_window")

    if intent_data["fallback_reason"] == "no_service":
        return _build_clarify(chat_id, kind="service_select", intent=intent if intent != "unknown" else None, period=period, source="deterministic", reason="missing_service")

    if intent_data["fallback_reason"] == "no_period" and service:
        return _build_clarify(chat_id, kind="service_scope", service=service, intent=intent if intent != "unknown" else None, source="deterministic", reason="missing_period")

    if intent == "unknown" and looks_like_status_probe(normalized_text, normalized=True) and contains_noc_domain(normalized_text, normalized=True):
        inferred_service = service or extract_service(normalized_text, normalized=True) or cast(Optional[ServiceKey], (peek_session(chat_id) or {}).get("last_service"))
        inferred = _build_intent_from_fields(text=text, intent="status_atual", service=inferred_service, period="now", source="deterministic.status_probe", confidence=0.77)
        return _decision(handled=True, route="consult", source="deterministic", intent_data=inferred, reason="status_probe")

    return None


def _deterministic_incident(text: str) -> Optional[RouteDecision]:
    normalized_text = normalize_text(text)

    if re.search(r"\b(caiu tudo|sem internet|parou agora|fora do ar agora|sem sistema)\b", normalized_text):
        return _decision(handled=True, route="incident", source="deterministic", reason="hard_incident_signal")

    if not contains_noc_domain(normalized_text, normalized=True):
        return None

    if looks_like_incident_report(normalized_text, normalized=True) and not _is_questionish(text, normalized_text):
        return _decision(handled=True, route="incident", source="deterministic", reason="strong_incident_signal")

    return None


def _should_call_ai(text: str, intent_data: IntentData) -> bool:
    if not DM_ASSISTANT_ENABLE_AI_CLASSIFIER:
        return False
    normalized_text = intent_data["normalized_text"]
    if not normalized_text:
        return False
    if _looks_like_social(text, normalized_text) or _looks_like_general_help(normalized_text):
        return True
    if not contains_noc_domain(normalized_text, normalized=True):
        return False
    if intent_data["intent"] == "unknown":
        return True
    if intent_data["confidence"] < DM_ASSISTANT_MIN_CONFIDENCE:
        return True
    if intent_data["fallback_reason"] in {"no_service", "no_period", "ambiguous_service"}:
        return True
    return False


def _ai_session_hint(chat_id: int) -> str:
    sess = peek_session(chat_id)
    if not sess:
        return ""
    return (
        f"last_service={sess.get('last_service')}; "
        f"last_intent={sess.get('last_intent')}; "
        f"last_period={sess.get('last_period')}; "
        f"last_route={sess.get('last_route')}; "
        f"awaiting={sess.get('awaiting')}; "
        f"clarify_kind={sess.get('clarify_kind')}"
    )


def _social_or_help_from_ai(text: str, route: str) -> RouteDecision:
    if route == "social":
        return _decision(handled=True, route="social", source="ai", reply_text=_build_social_reply(text), reason="ai_social")
    return _decision(handled=True, route="help", source="ai", reply_text=_build_help_reply(text), reason="ai_help")


async def _ai_fallback(chat_id: int, text: str) -> Optional[RouteDecision]:
    out = await classify_dm_message_with_ai(text, session_hint=_ai_session_hint(chat_id))
    if not out.get("ok"):
        return None

    if DM_ASSISTANT_CLASSIFIER_SHADOW_MODE:
        log.info("DM_AI_CLASSIFIER_SHADOW chat_id=%s text=%r out=%r", chat_id, text, out)
        return None

    if out["route"] in {"social", "help"}:
        return _social_or_help_from_ai(text, cast(str, out["route"]))

    if out["route"] == "incident" and out["confidence"] >= 0.70:
        return _decision(handled=True, route="incident", source="ai", reason="ai_incident")

    if out["route"] == "consult" and out.get("intent") and out["confidence"] >= 0.60:
        intent = cast(IntentName, out["intent"])
        service = cast(Optional[ServiceKey], out.get("service"))
        period = cast(PeriodKey, out.get("period") or "unspecified")
        if intent == "status_atual" and period == "unspecified":
            period = "now"
        if intent in {"queda_servico_janela", "contagem_falhas"} and period == "unspecified":
            period = "today"
        intent_data = _build_intent_from_fields(text=text, intent=intent, service=service, period=period, source="ai", confidence=float(out["confidence"]))
        return _decision(handled=True, route="consult", source="ai", intent_data=intent_data, reason="ai_consult")

    if out["route"] == "clarify":
        kind = cast(ClarifyKind, out.get("clarify_kind") or "generic")
        return _build_clarify(chat_id, kind=kind, service=cast(Optional[ServiceKey], out.get("service")), intent=cast(Optional[IntentName], out.get("intent")), period=cast(PeriodKey, out.get("period") or "unspecified"), source="ai", reason="ai_clarify", custom_text=cast(Optional[str], out.get("clarify_text") or None))

    return None


async def resolve_dm_route(chat_id: int, text: str) -> RouteDecision:
    session_decision = _resolve_from_session(chat_id, text)
    if session_decision:
        return session_decision

    social = _deterministic_social(text)
    if social:
        clear_pending(chat_id)
        return social

    help_decision = _deterministic_help(text)
    if help_decision:
        clear_pending(chat_id)
        return help_decision

    det_consult = _deterministic_consult(chat_id, text)
    if det_consult and det_consult["route"] == "consult":
        return det_consult

    det_incident = _deterministic_incident(text)
    if det_incident:
        clear_pending(chat_id)
        return det_incident

    if _should_call_ai(text, detect_intent(text, min_confidence=DM_ASSISTANT_MIN_CONFIDENCE)):
        ai_decision = await _ai_fallback(chat_id, text)
        if ai_decision:
            return ai_decision

    normalized_text = normalize_text(text)
    service = extract_service(normalized_text, normalized=True)

    if contains_noc_domain(normalized_text, normalized=True) and re.search(r"\b(ajuda|socorro|me ajuda)\b", normalized_text):
        return _build_clarify(chat_id, kind="consult_or_incident", service=service or "NET", source="deterministic", reason="help_needs_route")

    if service:
        return _build_clarify(chat_id, kind="service_scope", service=service, source="deterministic", reason="late_service_scope")

    if contains_noc_domain(normalized_text, normalized=True):
        if _is_questionish(text, normalized_text) and any(tok in normalized_text for tok in ("link", "internet", "rede")):
            return _build_clarify(chat_id, kind="status_or_window", service="NET", source="deterministic", reason="domain_question_without_window")
        return _build_clarify(chat_id, kind="service_select", source="deterministic", reason="domain_without_service")

    return _decision(handled=False, route="none", source="none", reason="no_route")
