# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List, Literal, TypedDict

from .config import DM_ASSISTANT_HUMOR_ENABLED, SVCS
from .dm_intents import PeriodKey, ServiceKey
from .dm_queries import QueryResult
from .utils import fmt_dur, fmt_when_abs


class PresenterButton(TypedDict):
    id: str
    label: str


class PresenterOutput(TypedDict):
    text: str
    safe_for_ai_polish: bool
    buttons: List[PresenterButton]
    tone: Literal["dry", "light", "professional"]


def _svc_label(service: ServiceKey | None) -> str:
    if not service:
        return "serviço"
    svc = SVCS.get(service)
    return svc.label if svc else service


def _fmt_ts(ts: str | None) -> str:
    if not ts:
        return "-"
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return fmt_when_abs(dt)
    except Exception:
        return ts


def _join_lines(lines: List[str], max_lines: int = 3) -> str:
    clean = [ln.strip() for ln in lines if ln and str(ln).strip()]
    if not clean:
        return "Não consegui montar a resposta."
    return "\n".join(clean[:max_lines])


def _safe_for_ai(result: QueryResult) -> bool:
    meta = result["meta"]
    if not result["ok"]:
        return False
    if meta["stale"]:
        return False
    if meta["severity"] in {"SEV1", "SEV2"}:
        return False
    if meta["source"] == "LOG" and meta["stale"]:
        return False
    return True


def _base_buttons(result: QueryResult) -> List[PresenterButton]:
    intent = result["intent"]
    service = result["service"]
    buttons: List[PresenterButton] = []

    if service:
        buttons.append({"id": f"evidence:{service}", "label": "Evidência"})

    if intent in {"queda_servico_janela", "contagem_falhas", "ultimo_cid"} and service:
        buttons.append({"id": f"details:{service}", "label": "Ver detalhes"})

    if intent in {"queda_servico_janela", "acao_recomendada"} and service:
        buttons.append({"id": f"ticket:{service}", "label": "Texto pronto"})

    return buttons[:2]


def _period_phrase(period: PeriodKey) -> str:
    mapping = {
        "now": "agora",
        "today": "hoje",
        "yesterday": "ontem",
        "24h": "nas últimas 24h",
        "7d": "nos últimos 7 dias",
        "30d": "nos últimos 30 dias",
        "week": "nesta semana",
        "month": "neste mês",
        "unspecified": "na janela analisada",
    }
    return mapping.get(period, "na janela analisada")


def _summary_phrase(period: PeriodKey) -> str:
    mapping = {
        "now": "de agora",
        "today": "de hoje",
        "yesterday": "de ontem",
        "24h": "das últimas 24h",
        "7d": "dos últimos 7 dias",
        "30d": "dos últimos 30 dias",
        "week": "desta semana",
        "month": "deste mês",
        "unspecified": "da janela analisada",
    }
    return mapping.get(period, "da janela analisada")


def _render_status(result: QueryResult) -> str:
    service = result["service"]
    data = result["data"]

    if service:
        label = _svc_label(service)
        state = data.get("state", "UNKNOWN")
        since_ts = _fmt_ts(data.get("since_ts"))
        duration = fmt_dur(data.get("duration_sec"))

        if state == "DOWN":
            return _join_lines(
                [
                    f"{label} está DOWN.",
                    f"Desde: {since_ts}",
                    f"Duração: {duration}",
                ]
            )

        if state == "UP":
            return _join_lines(
                [
                    f"{label} está UP.",
                    f"Última alteração: {since_ts}",
                    f"Consulta: {_period_phrase(result['period'])}",
                ]
            )

        return _join_lines([f"{label}: estado atual desconhecido."])

    services = data.get("services", {})
    parts: List[str] = []

    order = ["L1", "L2", "TEL", "ESC", "VPN2", "VPN3"]
    for code in order:
        row = services.get(code)
        if not row:
            continue
        label = row.get("label", code)
        state = row.get("state", "UNKNOWN")
        parts.append(f"{label}: {state}")

    if not parts:
        return "Não encontrei status atual dos serviços."

    return _join_lines([" | ".join(parts)], max_lines=3)


def _render_failures(result: QueryResult) -> str:
    service = result["service"]
    label = _svc_label(service)
    data = result["data"]

    count = int(data.get("count", 0))
    last_down_ts = _fmt_ts(data.get("last_down_ts"))
    last_up_ts = _fmt_ts(data.get("last_up_ts"))
    last_duration = fmt_dur(data.get("last_duration_sec"))
    last_cid = data.get("last_cid")
    period_phrase = _period_phrase(result["period"])

    if count <= 0:
        return _join_lines([f"{label} não apresentou quedas {period_phrase}."])

    lines = [
        f"{label} teve {count} queda(s) {period_phrase}.",
        f"Última: {last_down_ts}" + (f" → {last_up_ts}" if last_up_ts != "-" else ""),
    ]

    extra = []
    if last_duration != "-":
        extra.append(f"duração {last_duration}")
    if last_cid:
        extra.append(f"CID {last_cid}")

    if extra:
        lines.append(" | ".join(extra))

    return _join_lines(lines)


def _render_failure_count(result: QueryResult) -> str:
    service = result["service"]
    label = _svc_label(service)
    data = result["data"]

    count = int(data.get("count", 0))
    top_events = data.get("top_events", [])
    period_phrase = _period_phrase(result["period"])

    if count <= 0:
        return _join_lines([f"Não encontrei falhas de {label} {period_phrase}."])

    first_line = f"Foram {count} falha(s) de {label} {period_phrase}."
    if not top_events:
        return _join_lines([first_line])

    last_ev = top_events[-1]
    ts = _fmt_ts(last_ev.get("ts"))
    cid = last_ev.get("cid")

    if cid:
        return _join_lines([first_line, f"Última: {ts}", f"CID: {cid}"])
    return _join_lines([first_line, f"Última: {ts}"])


def _render_last_cid(result: QueryResult) -> str:
    service = result["service"]
    label = _svc_label(service)
    data = result["data"]

    cid = data.get("cid")
    event_ts = _fmt_ts(data.get("event_ts"))
    state = data.get("state", "UNKNOWN")

    if not cid:
        return _join_lines([f"Não encontrei CID recente para {label}."])

    return _join_lines(
        [
            f"Último CID de {label}: {cid}.",
            f"Evento: {event_ts}",
            f"Estado: {state}",
        ]
    )


def _render_summary(result: QueryResult) -> str:
    data = result["data"]
    total_incidents = int(data.get("total_incidents", 0))
    services = data.get("services", {})
    summary_phrase = _summary_phrase(result["period"])

    if total_incidents <= 0:
        return _join_lines([f"Nenhum incidente encontrado {summary_phrase}."])

    lines = [f"Resumo {summary_phrase}: {total_incidents} incidente(s)."]

    ranked = []
    for code, row in services.items():
        ranked.append((code, int(row.get("count", 0)), int(row.get("total_down_sec", 0))))
    ranked.sort(key=lambda x: x[1], reverse=True)

    for code, count, down_sec in ranked[:2]:
        if count <= 0:
            continue
        lines.append(f"{_svc_label(code)}: {count} ocorrência(s), indisponível {fmt_dur(down_sec)}")

    return _join_lines(lines)


def _render_compare(result: QueryResult) -> str:
    data = result["data"]

    winner_service = data.get("winner_service")
    winner_count = int(data.get("winner_count", 0))
    runner_up_service = data.get("runner_up_service")
    runner_up_count = int(data.get("runner_up_count", 0))
    period_phrase = _period_phrase(result["period"])

    if not winner_service:
        return _join_lines(["Não consegui comparar os serviços nessa janela."])

    if winner_count <= 0:
        return _join_lines([f"Não encontrei ocorrências {period_phrase}."])

    if runner_up_service and winner_service != runner_up_service and winner_count == runner_up_count:
        return _join_lines(
            [
                f"Houve empate entre {_svc_label(winner_service)} e {_svc_label(runner_up_service)} {period_phrase}.",
                f"Ambos tiveram {winner_count} ocorrência(s).",
            ]
        )

    lines = [f"{_svc_label(winner_service)} teve {winner_count} ocorrência(s) {period_phrase}."]
    if runner_up_service and runner_up_service != winner_service:
        lines.append(f"{_svc_label(runner_up_service)} veio depois com {runner_up_count}.")
    return _join_lines(lines)


def _render_recommendation(result: QueryResult) -> str:
    service = result["service"]
    label = _svc_label(service)
    data = result["data"]

    service_state = data.get("service_state", "UNKNOWN")
    recommendation_text = data.get("recommendation_text", "Seguir monitoramento.")
    last_cid = data.get("last_cid")

    lines = [
        f"{label}: estado {service_state}.",
        recommendation_text,
    ]
    if last_cid:
        lines.append(f"Último CID: {last_cid}")

    return _join_lines(lines)


def _render_fallback(result: QueryResult) -> str:
    reason = result["fallback_reason"]

    if reason == "no_service":
        return "Não identifiquei o serviço. Pergunte por link1, link2, telefonia ou escallo."
    if reason == "no_period":
        return "Faltou a janela. Tente hoje, ontem, 24h, 7d ou 30d."
    if reason == "ambiguous_service":
        return "A pergunta citou mais de um serviço. Tente informar só um por vez."
    if reason == "no_intent":
        return "Não entendi a intenção. Posso ajudar com status, falhas, resumo ou CID."
    return "Não consegui responder com segurança. Tente reformular a pergunta."



def _should_add_light_humor(result: QueryResult) -> bool:
    meta = result["meta"]
    if not DM_ASSISTANT_HUMOR_ENABLED:
        return False
    if meta["stale"]:
        return False
    if meta["source"] != "DB":
        return False
    if meta["severity"] in {"SEV1", "SEV2", "SEV3"}:
        return False
    return result["intent"] in {"status_atual", "resumo_periodo"}


def _maybe_add_light_humor(result: QueryResult, text: str) -> str:
    if not _should_add_light_humor(result):
        return text

    data = result["data"]
    if result["intent"] == "status_atual" and not result["service"]:
        services = data.get("services", {})
        states = [str((row or {}).get("state", "UNKNOWN")).upper() for row in services.values()]
        if states and all(state == "UP" for state in states):
            return _join_lines([text, "Hoje o caos parece estar de folga."], max_lines=4)

    if result["intent"] == "status_atual" and result["service"] and str(data.get("state", "")).upper() == "UP":
        return _join_lines([text, "Sem novela de link por aqui."], max_lines=4)

    if result["intent"] == "resumo_periodo" and int(data.get("total_incidents", 0)) == 0:
        return _join_lines([text, "O caos corporativo não bateu ponto nessa janela."], max_lines=4)

    return text

def render_factual(result: QueryResult) -> PresenterOutput:
    intent = result["intent"]

    if not result["ok"]:
        text = _render_fallback(result)
        return {
            "text": _join_lines([text]),
            "safe_for_ai_polish": False,
            "buttons": [],
            "tone": "professional",
        }

    if intent == "status_atual":
        text = _render_status(result)
    elif intent == "queda_servico_janela":
        text = _render_failures(result)
    elif intent == "contagem_falhas":
        text = _render_failure_count(result)
    elif intent == "ultimo_cid":
        text = _render_last_cid(result)
    elif intent == "resumo_periodo":
        text = _render_summary(result)
    elif intent == "comparativo_servico":
        text = _render_compare(result)
    elif intent == "acao_recomendada":
        text = _render_recommendation(result)
    else:
        text = _render_fallback(result)

    tone: Literal["dry", "light", "professional"] = "professional"
    if result["meta"]["severity"] in {"SEV1", "SEV2"}:
        tone = "dry"
    elif result["intent"] in {"status_atual", "resumo_periodo"}:
        tone = "light"

    text = _maybe_add_light_humor(result, text)

    return {
        "text": _join_lines([text], max_lines=4),
        "safe_for_ai_polish": _safe_for_ai(result),
        "buttons": _base_buttons(result),
        "tone": tone,
    }
