"""Build a searchable SQLite index from integration log CSV exports.

Integration platforms (the middleware that passes orders, invoices and EDI
messages between systems) log every message step. Those logs are usually
exported as large CSV files that are slow to search by hand.

This script reads every CSV in a folder once and stores the rows in SQLite
with:
  * an inverted index (word -> rows) for fast full-text-style search,
  * separate indexes on message id and correlation id, so all the steps of
    one business transaction can be pulled together.

Payload columns are often Base64-encoded; they are decoded before indexing
so the text inside the message can be searched too.
"""

from __future__ import annotations

import base64
import binascii
import csv
import re
import sqlite3
import sys
from pathlib import Path

TOKEN_RE = re.compile(r"[A-Za-z0-9_.\-]{3,}")
ID_COLUMNS = ("message_id", "correlation_id")

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def decode_payload(value: str) -> str:
    """Return decoded text if the value is Base64, otherwise the value itself."""
    value = (value or "").strip()
    if len(value) < 16 or len(value) % 4 or not re.fullmatch(r"[A-Za-z0-9+/=]+", value):
        return value
    try:
        return base64.b64decode(value, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return value


def tokens(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text or "")}


SCHEMA = """
CREATE TABLE rows (
    id INTEGER PRIMARY KEY,
    source_file TEXT, timestamp TEXT, process TEXT, status TEXT, partner TEXT,
    message_id TEXT, correlation_id TEXT, payload TEXT
);
CREATE TABLE token_index (token TEXT NOT NULL, row_id INTEGER NOT NULL);
"""

INDEXES = """
CREATE INDEX idx_token ON token_index(token);
CREATE INDEX idx_message ON rows(message_id);
CREATE INDEX idx_correlation ON rows(correlation_id);
CREATE INDEX idx_time ON rows(timestamp);
"""


def build_index(csv_folder: Path, db_path: Path) -> int:
    if db_path.exists():
        db_path.unlink()
    db = sqlite3.connect(db_path)
    db.executescript(SCHEMA)
    count = 0
    for csv_path in sorted(csv_folder.glob("*.csv")):
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                payload = decode_payload(row.get("payload", ""))
                cursor = db.execute(
                    "INSERT INTO rows (source_file, timestamp, process, status, partner, message_id, correlation_id, payload) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (csv_path.name, row.get("timestamp"), row.get("process"), row.get("status"), row.get("partner"),
                     row.get("message_id"), row.get("correlation_id"), payload),
                )
                searchable = " ".join(str(v or "") for k, v in row.items() if k != "payload") + " " + payload
                db.executemany("INSERT INTO token_index (token, row_id) VALUES (?, ?)",
                               [(t, cursor.lastrowid) for t in tokens(searchable)])
                count += 1
    # Creating the indexes after loading is much faster than updating them row by row.
    db.executescript(INDEXES)
    db.commit()
    db.close()
    return count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Index integration log CSV exports into SQLite.")
    parser.add_argument("folder", type=Path, help="folder with CSV exports")
    parser.add_argument("--db", type=Path, default=Path("logs.db"))
    args = parser.parse_args()
    total = build_index(args.folder, args.db)
    print(f"indexed {total} log rows into {args.db}")
