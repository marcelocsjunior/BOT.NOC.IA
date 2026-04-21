#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

# Evita exigir segredo real só para teste local.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "DUMMY_TOKEN_FOR_DM_SMOKE")
os.environ.setdefault("NOC_DB_PATH", "/var/lib/noc/noc.db")
os.environ.setdefault("SQLITE_DB_PATH", "/var/lib/noc/noc.db")
os.environ.setdefault("NOC_DEFAULT_UNIT", "UN1")

from noc_bot.dm_router import resolve_dm_route
from noc_bot.dm_queries_unit import dispatch_query
from noc_bot.dm_presenter import render_factual


DB_PATH = Path(os.environ.get("NOC_DB_PATH") or os.environ.get("SQLITE_DB_PATH") or "/var/lib/noc/noc.db")
REPORT_DIR = Path("/var/lib/noc/evidence")


CASES: list[dict[str, Any]] = [
    {
        "id": "DM-STATUS-UN2-TEL",
        "text": "UN2 telefone ok?",
        "unit": "UN2",
        "intent": "status_atual",
        "service": "TEL",
        "period": "now",
        "must_contain": ["Sem evidência", "Telefonia", "UN2"],
        "must_not_contain": ["funcionando normalmente", "está UP", "não apresentou quedas"],
    },
    {
        "id": "DM-STATUS-UN3-TEL",
        "text": "UN3 telefone ok?",
        "unit": "UN3",
        "intent": "status_atual",
        "service": "TEL",
        "period": "now",
        "must_contain": ["Sem evidência", "Telefonia", "UN3"],
        "must_not_contain": ["funcionando normalmente", "está UP", "não apresentou quedas"],
    },
    {
        "id": "DM-STATUS-UN2-L1",
        "text": "UN2 link1 ok?",
        "unit": "UN2",
        "intent": "status_atual",
        "service": "L1",
        "period": "now",
        "must_contain": ["Sem evidência", "Link 1", "UN2"],
        "must_not_contain": ["funcionando normalmente", "está UP", "não apresentou quedas"],
    },
    {
        "id": "DM-STATUS-UN3-L1",
        "text": "UN3 link1 ok?",
        "unit": "UN3",
        "intent": "status_atual",
        "service": "L1",
        "period": "now",
        "must_contain": ["Sem evidência", "Link 1", "UN3"],
        "must_not_contain": ["funcionando normalmente", "está UP", "não apresentou quedas"],
    },
    {
        "id": "DM-STATUS-UN2-L2",
        "text": "UN2 link2 ok?",
        "unit": "UN2",
        "intent": "status_atual",
        "service": "L2",
        "period": "now",
        "must_contain": ["Sem evidência", "Link 2", "UN2"],
        "must_not_contain": ["funcionando normalmente", "está UP", "não apresentou quedas"],
    },
    {
        "id": "DM-STATUS-UN3-L2",
        "text": "UN3 link2 ok?",
        "unit": "UN3",
        "intent": "status_atual",
        "service": "L2",
        "period": "now",
        "must_contain": ["Sem evidência", "Link 2", "UN3"],
        "must_not_contain": ["funcionando normalmente", "está UP", "não apresentou quedas"],
    },
    {
        "id": "DM-STATUS-UN2-ESC",
        "text": "UN2 escallo ok?",
        "unit": "UN2",
        "intent": "status_atual",
        "service": "ESC",
        "period": "now",
        "must_contain": ["Sem evidência", "ESCALLO", "UN2"],
        "must_not_contain": ["atualmente ativo", "funcionando normalmente", "está UP", "não apresentou quedas"],
    },
    {
        "id": "DM-STATUS-UN3-ESC",
        "text": "UN3 escallo ok?",
        "unit": "UN3",
        "intent": "status_atual",
        "service": "ESC",
        "period": "now",
        "must_contain": ["Sem evidência", "ESCALLO", "UN3"],
        "must_not_contain": ["atualmente ativo", "funcionando normalmente", "está UP", "não apresentou quedas"],
    },
    {
        "id": "DM-FALHA-UN2-TEL",
        "text": "UN2 telefonia teve falha hoje?",
        "unit": "UN2",
        "intent": "queda_servico_janela",
        "service": "TEL",
        "period": "today",
        "must_contain": ["Sem evidência", "Telefonia", "UN2"],
        "must_not_contain": ["não apresentou quedas", "funcionando normalmente", "está UP"],
    },
    {
        "id": "DM-FALHA-UN3-TEL",
        "text": "UN3 telefonia teve falha hoje?",
        "unit": "UN3",
        "intent": "queda_servico_janela",
        "service": "TEL",
        "period": "today",
        "must_contain": ["Sem evidência", "Telefonia", "UN3"],
        "must_not_contain": ["não apresentou quedas", "funcionando normalmente", "está UP"],
    },
    {
        "id": "DM-FALHA-UN2-L1",
        "text": "UN2 link1 teve falha hoje?",
        "unit": "UN2",
        "intent": "queda_servico_janela",
        "service": "L1",
        "period": "today",
        "must_contain": ["Sem evidência", "Link 1", "UN2"],
        "must_not_contain": ["não apresentou quedas", "funcionando normalmente", "está UP"],
    },
    {
        "id": "DM-FALHA-UN3-L2",
        "text": "UN3 link2 teve falha hoje?",
        "unit": "UN3",
        "intent": "queda_servico_janela",
        "service": "L2",
        "period": "today",
        "must_contain": ["Sem evidência", "Link 2", "UN3"],
        "must_not_contain": ["não apresentou quedas", "funcionando normalmente", "está UP"],
    },
]


def detect_unit(text: str) -> str:
    tn = text.lower()
    if "un2" in tn or "barreiro" in tn:
        return "UN2"
    if "un3" in tn or "alipio" in tn or "alípio" in tn:
        return "UN3"
    if "un1" in tn or "eldorado" in tn or "matriz" in tn:
        return "UN1"
    return "UN1"


def db_units() -> dict[str, int]:
    if not DB_PATH.exists():
        return {}
    con = sqlite3.connect(str(DB_PATH))
    try:
        rows = con.execute("SELECT unit, COUNT(*) FROM events GROUP BY unit ORDER BY unit").fetchall()
        return {str(unit): int(count) for unit, count in rows}
    finally:
        con.close()


def apply_selected_unit(intent_data: dict[str, Any], unit: str) -> dict[str, Any]:
    updated = dict(intent_data)
    entities = dict(updated.get("entities") or {})
    updated["unit"] = unit
    entities["selected_unit"] = unit
    updated["entities"] = entities
    return updated


def contains_all(text: str, needles: list[str]) -> list[str]:
    low = text.lower()
    missing = []
    for n in needles:
        if n.lower() not in low:
            missing.append(n)
    return missing


def contains_any(text: str, needles: list[str]) -> list[str]:
    low = text.lower()
    found = []
    for n in needles:
        if n.lower() in low:
            found.append(n)
    return found


async def run_case(idx: int, case: dict[str, Any]) -> dict[str, Any]:
    text = case["text"]
    expected_unit = case["unit"]
    chat_id = 880000 + idx

    decision = await resolve_dm_route(chat_id, text)
    intent_data = decision.get("intent_data")

    result: dict[str, Any] = {
        "case": case["id"],
        "text": text,
        "pass": True,
        "errors": [],
        "warnings": [],
        "route": decision.get("route"),
        "reason": decision.get("reason"),
        "intent": None,
        "service": None,
        "period": None,
        "unit": expected_unit,
        "source": None,
        "stale": None,
        "reply": "",
    }

    if decision.get("route") != "consult" or not intent_data:
        result["pass"] = False
        result["errors"].append(f"route esperado consult, recebido {decision.get('route')} reason={decision.get('reason')}")
        return result

    intent_data = apply_selected_unit(dict(intent_data), expected_unit)

    result["intent"] = intent_data.get("intent")
    result["service"] = intent_data.get("service")
    result["period"] = intent_data.get("period")

    for key in ("intent", "service", "period"):
        if case.get(key) != intent_data.get(key):
            result["pass"] = False
            result["errors"].append(f"{key} esperado {case.get(key)!r}, recebido {intent_data.get(key)!r}")

    query_result = dispatch_query(intent_data)
    rendered = render_factual(query_result)
    reply = rendered["text"]

    result["source"] = query_result["meta"].get("source")
    result["stale"] = query_result["meta"].get("stale")
    result["reply"] = reply

    missing = contains_all(reply, case.get("must_contain", []))
    forbidden = contains_any(reply, case.get("must_not_contain", []))

    if missing:
        result["pass"] = False
        result["errors"].append(f"texto obrigatório ausente: {missing}")

    if forbidden:
        result["pass"] = False
        result["errors"].append(f"texto proibido encontrado: {forbidden}")

    # Proteção extra: UN2/UN3 não podem responder com frase afirmativa de OK.
    if expected_unit in {"UN2", "UN3"}:
        dangerous = [
            "funcionando normalmente",
            "está funcionando",
            "está up",
            "atualmente ativo",
            "não apresentou quedas",
            "operação normal",
        ]
        hit = contains_any(reply, dangerous)
        if hit:
            result["pass"] = False
            result["errors"].append(f"possível falso OK para {expected_unit}: {hit}")

    return result


async def main() -> int:
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = REPORT_DIR / f"dm_smoke_{now}.txt"

    units = db_units()

    results = []
    for idx, case in enumerate(CASES, start=1):
        results.append(await run_case(idx, case))

    passed = sum(1 for r in results if r["pass"])
    failed = len(results) - passed

    lines: list[str] = []
    lines.append("======================================================================")
    lines.append("ALTIS/NOC - DM SMOKE TEST")
    lines.append("======================================================================")
    lines.append(f"DATE={datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"DB={DB_PATH}")
    lines.append(f"DB_UNITS={units}")
    lines.append(f"TOTAL={len(results)} PASS={passed} FAIL={failed}")
    lines.append("")

    if "UN2" not in units:
        lines.append("[WARN] DB ainda não tem eventos unit=UN2")
    if "UN3" not in units:
        lines.append("[WARN] DB ainda não tem eventos unit=UN3")
    lines.append("")

    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        lines.append("----------------------------------------------------------------------")
        lines.append(f"{status} {r['case']}")
        lines.append(f"TEXT={r['text']}")
        lines.append(f"ROUTE={r['route']} REASON={r['reason']}")
        lines.append(f"UNIT={r['unit']} INTENT={r['intent']} SERVICE={r['service']} PERIOD={r['period']}")
        lines.append(f"SOURCE={r['source']} STALE={r['stale']}")
        lines.append("REPLY=" + str(r["reply"]).replace("\n", " | "))

        if r["errors"]:
            for e in r["errors"]:
                lines.append(f"ERROR={e}")
        if r["warnings"]:
            for w in r["warnings"]:
                lines.append(f"WARN={w}")

    lines.append("")
    lines.append("======================================================================")
    lines.append("RESULTADO FINAL")
    lines.append("======================================================================")
    lines.append(f"PASS={passed}")
    lines.append(f"FAIL={failed}")
    lines.append(f"REPORT={report}")

    text = "\n".join(lines)
    report.write_text(text, encoding="utf-8")

    print(text)
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
