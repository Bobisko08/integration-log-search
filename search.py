"""Search the log index.

A search works in two steps:
  1. Direct hits: rows that contain every word of the query.
  2. Related rows: every other row that shares a message id or correlation id
     with a direct hit. This turns "find the row with booking 4711" into
     "show me everything that happened to that booking", across processes.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from build_index import tokens

COLUMNS = ["id", "source_file", "timestamp", "process", "status", "partner", "message_id", "correlation_id", "payload"]


def connect(db_path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db


def _rows(db: sqlite3.Connection, ids: list[int]) -> list[dict]:
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    result = db.execute(f"SELECT {', '.join(COLUMNS)} FROM rows WHERE id IN ({marks}) ORDER BY timestamp", ids)
    return [dict(row) for row in result]


def search(db: sqlite3.Connection, query: str, limit: int = 300) -> dict:
    words = sorted(tokens(query))
    if not words:
        return {"query": query, "direct": [], "related": [], "errors": 0}

    # Rows that contain ALL the words: intersect the row ids found for each word.
    marks = ",".join("?" * len(words))
    direct_ids = [r[0] for r in db.execute(
        f"SELECT row_id FROM token_index WHERE token IN ({marks}) "
        f"GROUP BY row_id HAVING COUNT(DISTINCT token) = ? LIMIT ?", (*words, len(words), limit))]
    direct = _rows(db, direct_ids)

    message_ids = {r["message_id"] for r in direct if r["message_id"]}
    correlation_ids = {r["correlation_id"] for r in direct if r["correlation_id"]}
    related_ids: set[int] = set()
    for column, values in (("message_id", message_ids), ("correlation_id", correlation_ids)):
        values = list(values)
        for start in range(0, len(values), 500):  # SQLite limits the number of ? per query
            chunk = values[start:start + 500]
            related_ids.update(r[0] for r in db.execute(
                f"SELECT id FROM rows WHERE {column} IN ({','.join('?' * len(chunk))})", chunk))
    related = _rows(db, sorted(related_ids - set(direct_ids))[: limit * 5])

    errors = sum(1 for r in direct + related if (r["status"] or "").upper() in {"ERROR", "FAILED"})
    return {"query": query, "direct": direct, "related": related, "errors": errors}


def stats(db: sqlite3.Connection) -> dict:
    total = db.execute("SELECT COUNT(*) FROM rows").fetchone()[0]
    first, last = db.execute("SELECT MIN(timestamp), MAX(timestamp) FROM rows").fetchone()
    by_status = {row[0]: row[1] for row in db.execute("SELECT status, COUNT(*) FROM rows GROUP BY status")}
    return {"rows": total, "from": first, "to": last, "by_status": by_status}
