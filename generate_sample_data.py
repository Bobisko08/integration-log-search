"""Create fake integration log CSV exports.

Each business transaction (for example one booking) gets a correlation id and
passes through several processes. Payloads are Base64-encoded XML, as many
integration platforms store them. Everything here is invented.
"""

import base64
import csv
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

PARTNERS = ["CarrierOne", "PortTerminalA", "CustomsGateway", "WarehouseNorth", "ShipperXYZ"]
FLOW = ["OrderImport", "BookingRequest", "BookingConfirmation", "CustomsFiling", "InvoiceExport"]
FIELDS = ["timestamp", "process", "status", "partner", "message_id", "correlation_id", "payload"]


def payload(booking: str, container: str, process: str) -> str:
    # Like real systems, not every step carries every reference: the customs and
    # invoice steps only know the container, so a search for the booking number
    # finds them through the shared correlation id instead.
    refs = f"<booking>{booking}</booking>" if process in {"OrderImport", "BookingRequest", "BookingConfirmation"} else ""
    if process != "OrderImport":
        refs += f"<container>{container}</container>"
    xml = f"<message><process>{process}</process>{refs}</message>"
    return base64.b64encode(xml.encode()).decode()


def generate(transactions: int = 3000, seed: int = 5) -> dict[str, list[dict]]:
    rng = random.Random(seed)
    files: dict[str, list[dict]] = {}
    start = datetime(2026, 8, 1)
    for _ in range(transactions):
        correlation = str(uuid.UUID(int=rng.getrandbits(128)))
        booking = f"BKG{rng.randint(100000, 999999)}"
        container = f"{rng.choice(['MSKU', 'CMAU', 'TGHU', 'OOLU'])}{rng.randint(1000000, 9999999)}"
        partner = rng.choice(PARTNERS)
        moment = start + timedelta(minutes=rng.randint(0, 60 * 24 * 60))
        steps = FLOW[: rng.randint(2, len(FLOW))]
        for process in steps:
            moment += timedelta(seconds=rng.randint(5, 900))
            failed = rng.random() < 0.03
            row = {
                "timestamp": moment.isoformat(timespec="seconds"),
                "process": process,
                "status": "ERROR" if failed else "OK",
                "partner": partner,
                "message_id": str(uuid.UUID(int=rng.getrandbits(128)))[:18],
                "correlation_id": correlation,
                "payload": payload(booking, container, process),
            }
            files.setdefault(f"log_export_{moment:%Y_%m}.csv", []).append(row)
            if failed:
                break
    return files


if __name__ == "__main__":
    out = Path("sample_data")
    out.mkdir(exist_ok=True)
    total = 0
    for name, rows in generate().items():
        with (out / name).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        total += len(rows)
    print(f"wrote {total} log rows to {out}/")
