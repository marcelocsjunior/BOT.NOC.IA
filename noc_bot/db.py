# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
from typing import Iterable

from .config import NOC_DB_PATH

def connect_db(path: str | None = None) -> sqlite3.Connection:
    p = path or NOC_DB_PATH
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    return con

def query_rows(sql: str, params: tuple = (), limit: int | None = None) -> list[sqlite3.Row]:
    con = connect_db()
    try:
        cur = con.execute(sql, params)
        rows = cur.fetchall()
        if limit is not None:
            rows = rows[:limit]
        return rows
    finally:
        con.close()
