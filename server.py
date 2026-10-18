"""Small local web server for searching the log index in a browser.

Uses only the Python standard library (http.server), so it runs on a
locked-down work laptop without installing anything.

    python server.py --db logs.db
    open http://127.0.0.1:8770
"""

from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from search import connect, search, stats

HERE = Path(__file__).resolve().parent


class Handler(SimpleHTTPRequestHandler):
    db = None  # set in main()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE / "web"), **kwargs)

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path == "/api/search":
            query = parse_qs(url.query).get("q", [""])[0][:200]
            self.send_json(search(self.db, query))
        elif url.path == "/api/stats":
            self.send_json(stats(self.db))
        else:
            super().do_GET()

    def log_message(self, fmt, *args):  # keep the console quiet
        pass


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Serve the log search page.")
    parser.add_argument("--db", type=Path, default=Path("logs.db"))
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()
    if not args.db.exists():
        raise SystemExit(f"{args.db} not found. Run build_index.py first.")

    Handler.db = connect(args.db)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Log search running at http://127.0.0.1:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
