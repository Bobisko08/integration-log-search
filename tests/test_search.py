import base64
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_index import build_index, decode_payload  # noqa: E402
from search import connect, search, stats  # noqa: E402

ROWS = [
    {"timestamp": "2026-09-01T10:00:00", "process": "OrderImport", "status": "OK", "partner": "CarrierOne",
     "message_id": "m1", "correlation_id": "c1", "payload": base64.b64encode(b"<booking>BKG123456</booking>").decode()},
    {"timestamp": "2026-09-01T10:05:00", "process": "CustomsFiling", "status": "ERROR", "partner": "CarrierOne",
     "message_id": "m2", "correlation_id": "c1", "payload": "plain text step"},
    {"timestamp": "2026-09-01T11:00:00", "process": "OrderImport", "status": "OK", "partner": "ShipperXYZ",
     "message_id": "m3", "correlation_id": "c2", "payload": "<booking>BKG999999</booking>"},
]


def make_db(tmp_path):
    folder = tmp_path / "logs"
    folder.mkdir()
    with (folder / "export.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ROWS[0]))
        writer.writeheader()
        writer.writerows(ROWS)
    db_path = tmp_path / "logs.db"
    assert build_index(folder, db_path) == 3
    return connect(db_path)


def test_base64_payload_is_decoded():
    encoded = base64.b64encode(b"<booking>BKG123456</booking>").decode()
    assert decode_payload(encoded) == "<booking>BKG123456</booking>"
    assert decode_payload("not base64 at all!") == "not base64 at all!"


def test_search_finds_text_inside_encoded_payload(tmp_path):
    result = search(make_db(tmp_path), "BKG123456")
    assert [r["message_id"] for r in result["direct"]] == ["m1"]


def test_related_steps_share_the_correlation_id(tmp_path):
    result = search(make_db(tmp_path), "BKG123456")
    assert [r["message_id"] for r in result["related"]] == ["m2"]
    assert result["errors"] == 1


def test_all_words_must_match(tmp_path):
    db = make_db(tmp_path)
    assert len(search(db, "orderimport carrierone")["direct"]) == 1
    assert search(db, "orderimport nothing-like-this")["direct"] == []


def test_stats(tmp_path):
    assert stats(make_db(tmp_path))["rows"] == 3
