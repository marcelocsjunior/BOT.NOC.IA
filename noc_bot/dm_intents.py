# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Literal, Optional, TypedDict, cast

from .config import UNIT, SVCS

IntentName = Literal[
    "status_atual",
    "queda_servico_janela",
    "contagem_falhas",
    "ultimo_cid",
    "resumo_periodo",
    "comparativo_servico",
    "acao_recomendada",
    "unknown",
]

PeriodKey = Literal[
    "now",
    "today",
    "yesterday",
    "24h",
    "7d",
    "30d",
    "week",
    "month",
    "unspecified",
]

FallbackReason = Literal[
    "none",
    "no_intent",
    "no_service",
    "no_period",
    "ambiguous_intent",
    "ambiguous_service",
    "low_confidence",
    "out_of_scope",
]

ServiceKey = Literal["NET", "TEL", "L1", "L2", "ESC", "VPN2", "VPN3"]


class IntentData(TypedDict):
    version: str
    unit: str
    raw_text: str
    normalized_text: str
    intent: IntentName
    service: Optional[ServiceKey]
    period: PeriodKey
    confidence: float
    fallback_reason: FallbackReason
    entities: Dict[str, Any]


_PERIOD_PATTERNS: list[tuple[PeriodKey, re.Pattern[str]]] = [
    ("now", re.compile(r"\b(agora|nesse momento|neste momento|atualmente)\b")),
    ("today", re.compile(r"\b(hoje)\b")),
    ("yesterday", re.compile(r"\b(ontem)\b")),
    ("24h", re.compile(r"\b(24h|ultimas 24h|ultimas vinte e quatro horas)\b")),
    ("7d", re.compile(r"\b(7d|7 dias|ultimos 7 dias|semana|essa semana)\b")),
    ("30d", re.compile(r"\b(30d|30 dias|ultimos 30 dias|mes|esse mes)\b")),
]

_INTENT_PATTERNS: list[tuple[IntentName, re.Pattern[str]]] = [
    ("ultimo_cid", re.compile(r"\b(ultimo|ultima|cid|codigo|id)\b")),
    (
        "comparativo_servico",
        re.compile(r"\b(mais problemas|mais problematico|pior|mais instavel|mais quedas)\b"),
    ),
    (
        "contagem_falhas",
        re.compile(r"\b(quantas|quantos|numero|total)\b.*\b(falhas|quedas|ocorrencias|incidentes)\b"),
    ),
    ("resumo_periodo", re.compile(r"\b(resumo|sumario|relatorio|como foi)\b")),
    ("acao_recomendada", re.compile(r"\b(o que fazer|recomendacao|recomenda|acao|procedimento|sugere)\b")),
    (
        "queda_servico_janela",
        re.compile(r"\b(caiu|queda|quedas|falha|falhas|indisponivel|instavel|instabilidade|flap|oscilacao)\b"),
    ),
    (
        "status_atual",
        re.compile(r"\b(status|como esta|ta tudo bem|tem algo estranho|tudo ok|tudo bem|ok ai|ok a[ií])\b"),
    ),
]

_STRICT_GLOBAL_STATUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^status(?: atual| geral)?[!??. ]*$"),
    re.compile(r"^painel(?: geral)?[!??. ]*$"),
    re.compile(r"^situacao atual[!??. ]*$"),
    re.compile(r"^visao geral[!??. ]*$"),
    re.compile(r"^como esta agora[!??. ]*$"),
]

_CONFIRM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^tem certeza[!??. ]*$"),
    re.compile(r"^certeza[!??. ]*$"),
    re.compile(r"^confirma[!??. ]*$"),
    re.compile(r"^confere[!??. ]*$"),
    re.compile(r"^serio[!??. ]*$"),
]

_OUT_OF_SCOPE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(speed\s*test|speedtest)\b"),
    re.compile(r"\b(site|link|url|endereco|endereço)\b.*\b(speed\s*test|speedtest)\b"),
]

_COMPLAINT_PATTERN = re.compile(
    r"\b("
    r"lento|lenta|lentidao|travando|trava|travou|travamento|"
    r"caindo|cai|caiu|cair|queda|quedas|falha|falhas|instavel|instabilidade|"
    r"ruim|reclama|reclamacao"
    r")\b"
)

_PERIOD_REQUIRED: set[IntentName] = {
    "queda_servico_janela",
    "contagem_falhas",
    "resumo_periodo",
}

_SERVICE_OPTIONAL: set[IntentName] = {
    "status_atual",
    "resumo_periodo",
    "comparativo_servico",
}

_MIN_CONFIDENCE_DEFAULT = 0.60


def _normalize_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_text(text: str) -> str:
    return _normalize_text(text)


def _compile_alias_pattern(alias_norm: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(alias_norm)}(?!\w)")


def _build_service_patterns() -> dict[str, list[re.Pattern[str]]]:
    patterns: dict[str, list[re.Pattern[str]]] = {}

    for code, svc in SVCS.items():
        aliases_raw = [
            svc.code,
            svc.key,
            svc.label,
            svc.subject,
            *svc.aliases,
        ]

        aliases_norm: list[str] = []
        for alias in aliases_raw:
            alias_norm = _normalize_text(alias)
            if alias_norm and alias_norm not in aliases_norm:
                aliases_norm.append(alias_norm)

        patterns[code] = [_compile_alias_pattern(alias) for alias in aliases_norm]

    return patterns


_SERVICE_PATTERNS = _build_service_patterns()


def _extract_service_hits(normalized_text: str) -> list[str]:
    hits: list[str] = []

    for code, patterns in _SERVICE_PATTERNS.items():
        if any(pattern.search(normalized_text) for pattern in patterns):
            hits.append(code)

    return hits


def extract_service_hits(text: str, *, normalized: bool = False) -> list[str]:
    normalized_text = text if normalized else _normalize_text(text)
    return _extract_service_hits(normalized_text)


def _extract_service(normalized_text: str) -> Optional[ServiceKey]:
    hits = _extract_service_hits(normalized_text)
    if len(hits) == 1:
        return cast(ServiceKey, hits[0])
    return None


def extract_service(text: str, *, normalized: bool = False) -> Optional[ServiceKey]:
    normalized_text = text if normalized else _normalize_text(text)
    return _extract_service(normalized_text)


def _extract_period(normalized_text: str) -> PeriodKey:
    for period_key, pattern in _PERIOD_PATTERNS:
        if pattern.search(normalized_text):
            return period_key
    return "unspecified"


def _detect_intent_name(normalized_text: str) -> IntentName:
    for intent_name, pattern in _INTENT_PATTERNS:
        if pattern.search(normalized_text):
            return intent_name

    if "de novo" in normalized_text and any(
        token in normalized_text for token in ("caiu", "queda", "instavel", "instabilidade")
    ):
        return "queda_servico_janela"

    return "unknown"


def is_strict_global_status_request(text: str, *, normalized: bool = False) -> bool:
    normalized_text = text if normalized else _normalize_text(text)
    return any(pattern.match(normalized_text) for pattern in _STRICT_GLOBAL_STATUS_PATTERNS)



def is_confirmation_request(text: str, *, normalized: bool = False) -> bool:
    normalized_text = text if normalized else _normalize_text(text)
    return any(pattern.match(normalized_text) for pattern in _CONFIRM_PATTERNS)



def is_out_of_scope_request(text: str, *, normalized: bool = False) -> bool:
    normalized_text = text if normalized else _normalize_text(text)
    return any(pattern.search(normalized_text) for pattern in _OUT_OF_SCOPE_PATTERNS)



def looks_like_complaint(text: str, *, normalized: bool = False) -> bool:
    normalized_text = text if normalized else _normalize_text(text)
    return bool(_COMPLAINT_PATTERN.search(normalized_text))



def detect_intent(text: str, min_confidence: float = _MIN_CONFIDENCE_DEFAULT) -> IntentData:
    normalized_text = _normalize_text(text)
    service_hits = _extract_service_hits(normalized_text)
    service = cast(Optional[ServiceKey], service_hits[0]) if len(service_hits) == 1 else None
    period = _extract_period(normalized_text)
    intent = _detect_intent_name(normalized_text)

    if is_strict_global_status_request(normalized_text, normalized=True):
        intent = "status_atual"
        service = None
        service_hits = []
        if period == "unspecified":
            period = "now"

    if intent == "unknown" and service is not None and not looks_like_complaint(normalized_text, normalized=True):
        intent = "status_atual"
        if period == "unspecified":
            period = "now"

    if intent == "status_atual" and period == "unspecified":
        period = "now"

    if intent == "comparativo_servico" and period == "unspecified":
        period = "7d"

    has_cid_word = bool(re.search(r"\b(cid|codigo|id)\b", normalized_text))
    has_compare_word = bool(re.search(r"\b(pior|mais problemas|mais instavel|mais quedas)\b", normalized_text))
    has_status_word = bool(re.search(r"\b(status|como esta|tem algo estranho|tudo ok|tudo bem|ok ai|ok a[ií])\b", normalized_text))
    is_service_probe = bool(service is not None and intent == "status_atual")

    entities: Dict[str, Any] = {
        "service_hits": service_hits,
        "service_hit_count": len(service_hits),
        "has_cid_word": has_cid_word,
        "has_compare_word": has_compare_word,
        "has_status_word": has_status_word,
        "is_service_probe": is_service_probe,
        "is_strict_global_status": is_strict_global_status_request(normalized_text, normalized=True),
        "is_confirmation": is_confirmation_request(normalized_text, normalized=True),
        "is_out_of_scope": is_out_of_scope_request(normalized_text, normalized=True),
    }

    confidence = 0.0
    fallback_reason: FallbackReason = "none"

    if not normalized_text:
        fallback_reason = "out_of_scope"
    elif intent == "unknown":
        fallback_reason = "no_intent"
    elif len(service_hits) > 1 and intent not in _SERVICE_OPTIONAL:
        fallback_reason = "ambiguous_service"
        confidence = 0.30
    elif service is None and intent not in _SERVICE_OPTIONAL:
        fallback_reason = "no_service"
        confidence = 0.35
    elif period == "unspecified" and intent in _PERIOD_REQUIRED:
        fallback_reason = "no_period"
        confidence = 0.40
    else:
        confidence = 0.72

        if service is not None or intent in _SERVICE_OPTIONAL:
            confidence += 0.10

        if period != "unspecified" or intent not in _PERIOD_REQUIRED:
            confidence += 0.10

        if has_cid_word or has_compare_word or has_status_word or is_service_probe:
            confidence += 0.05

        confidence = min(confidence, 0.98)

        if confidence < min_confidence:
            fallback_reason = "low_confidence"

    return {
        "version": "dm.intent.v2",
        "unit": UNIT,
        "raw_text": text or "",
        "normalized_text": normalized_text,
        "intent": intent,
        "service": service,
        "period": period,
        "confidence": round(confidence, 2),
        "fallback_reason": fallback_reason,
        "entities": entities,
    }


_NOC_DOMAIN_TOKENS = (
    "status", "queda", "quedas", "falha", "falhas", "cid", "resumo", "instavel", "instabilidade",
    "telefonia", "telefone", "voip", "ramal", "escallo", "escalo", "internet", "rede",
    "link", "mundivox", "valenet", "vpn", "un1", "un2", "un3", "evidencia", "evidência",
)

_CONSULT_QUESTION_HINTS = ("qual", "quais", "como", "onde", "quando", "status", "ok", "agora", "hoje")

_INCIDENT_STRONG_PATTERN = re.compile(
    r"\b(caiu tudo|sem internet|sem sistema|parou agora|fora do ar agora|travando|travou|muito lento|muito lenta|indisponivel agora)\b"
)

_STATUS_PROBE_PATTERN = re.compile(
    r"\b(status|agora|atual|ok ai|ok a[ií]|ta ok|tudo ok|tudo bem|como esta|como ta)\b"
)


def extract_period(text: str, *, normalized: bool = False) -> PeriodKey:
    normalized_text = text if normalized else _normalize_text(text)
    return _extract_period(normalized_text)


def detect_intent_name(text: str, *, normalized: bool = False) -> IntentName:
    normalized_text = text if normalized else _normalize_text(text)
    return _detect_intent_name(normalized_text)


def build_intent_data(
    *,
    text: str,
    normalized_text: str,
    intent: IntentName,
    service: Optional[ServiceKey],
    period: PeriodKey,
    confidence: float,
    fallback_reason: FallbackReason,
    entities: Dict[str, Any],
) -> IntentData:
    return {
        "version": "dm.intent.v3",
        "unit": UNIT,
        "raw_text": text or "",
        "normalized_text": normalized_text,
        "intent": intent,
        "service": service,
        "period": period,
        "confidence": round(max(0.0, min(float(confidence), 0.99)), 2),
        "fallback_reason": fallback_reason,
        "entities": entities,
    }


def contains_noc_domain(text: str, *, normalized: bool = False) -> bool:
    normalized_text = text if normalized else _normalize_text(text)
    if not normalized_text:
        return False
    if extract_service(normalized_text, normalized=True) is not None:
        return True
    return any(token in normalized_text for token in _NOC_DOMAIN_TOKENS)


def looks_like_status_probe(text: str, *, normalized: bool = False) -> bool:
    normalized_text = text if normalized else _normalize_text(text)
    return bool(_STATUS_PROBE_PATTERN.search(normalized_text))


def looks_like_consult_question(text: str, *, normalized: bool = False) -> bool:
    normalized_text = text if normalized else _normalize_text(text)
    if not normalized_text:
        return False
    if looks_like_status_probe(normalized_text, normalized=True):
        return True
    if any(tok in normalized_text for tok in _CONSULT_QUESTION_HINTS):
        return True
    return normalized_text.endswith("?")


def looks_like_incident_report(text: str, *, normalized: bool = False) -> bool:
    normalized_text = text if normalized else _normalize_text(text)
    if not normalized_text:
        return False
    if bool(_INCIDENT_STRONG_PATTERN.search(normalized_text)):
        return True
    if looks_like_complaint(normalized_text, normalized=True) and not looks_like_consult_question(normalized_text, normalized=True):
        return True
    return False
