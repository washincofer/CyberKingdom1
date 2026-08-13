from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .db import Database
from .errors import ApiError
from .service import GameService

ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = ROOT / "web"
DEFAULT_DB = ROOT / "backend" / "data" / "cyberkingdoms.db"


class Handler(BaseHTTPRequestHandler):
    server_version = "CyberKingdomsPrototype/0.1"

    @property
    def service(self) -> GameService:
        return self.server.service

    def _json_body(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 262144:
            raise ApiError(413, "VALIDATION_FAILED", "JSON body exceeds 256 KB.")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            raise ApiError(400, "VALIDATION_FAILED", "Invalid JSON.")
        if not isinstance(value, dict):
            raise ApiError(400, "VALIDATION_FAILED", "JSON body must be an object.")
        return value

    def _send_json(self, status: int, payload: dict):
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Correlation-Id", getattr(self, "correlation_id", ""))
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, path: str):
        target = WEB_ROOT / ("index.html" if path == "/" else path.lstrip("/"))
        try:
            target = target.resolve()
            if WEB_ROOT.resolve() not in target.parents and target != WEB_ROOT.resolve():
                raise FileNotFoundError
            data = target.read_bytes()
        except (FileNotFoundError, IsADirectoryError):
            return False
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        return True

    def _dispatch(self, method: str):
        path = urlparse(self.path).path
        if method == "GET" and not path.startswith("/api/") and not path.startswith("/internal/") and path != "/health":
            if self._serve_static(path):
                return
        body = self._json_body() if method in ("POST", "PUT", "PATCH") else {}
        idem = self.headers.get("Idempotency-Key", "")
        svc = self.service

        if method == "GET" and path == "/health": return self._send_json(200, svc.health())
        if method == "GET" and path == "/api/v1/me": return self._send_json(200, svc.me())
        if method == "GET" and path == "/api/v1/actions": return self._send_json(200, svc.list_actions())
        if method == "POST" and path == "/api/v1/public-jobs": return self._send_json(201, svc.queue_public_work(idem, int(body.get("duration_seconds", 2))))
        if method == "POST" and path == "/internal/reconcile": return self._send_json(200, svc.reconcile())
        if method == "GET" and path == "/internal/outbox": return self._send_json(200, svc.events())

        m = re.fullmatch(r"/api/v1/actions/([^/]+)", path)
        if m and method == "GET": return self._send_json(200, svc.get_action(m.group(1)))
        if m and method == "DELETE": return self._send_json(200, svc.cancel_action(m.group(1)))
        m = re.fullmatch(r"/api/v1/accounts/([^/]+)/balance", path)
        if m and method == "GET": return self._send_json(200, svc.balance(m.group(1)))
        m = re.fullmatch(r"/api/v1/accounts/([^/]+)/transactions", path)
        if m and method == "GET": return self._send_json(200, svc.transactions(m.group(1)))
        m = re.fullmatch(r"/api/v1/inventories/([^/]+)", path)
        if m and method == "GET": return self._send_json(200, svc.inventory(m.group(1)))
        m = re.fullmatch(r"/api/v1/markets/([^/]+)/listings", path)
        if m and method == "GET": return self._send_json(200, svc.listings(m.group(1)))
        m = re.fullmatch(r"/api/v1/market-listings/([^/]+)/purchase", path)
        if m and method == "POST": return self._send_json(200, svc.purchase(m.group(1), int(body.get("quantity", 1)), idem))
        m = re.fullmatch(r"/api/v1/items/([^/]+)/consume", path)
        if m and method == "POST": return self._send_json(200, svc.consume(m.group(1), int(body.get("quantity", 1)), idem))
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Route not found.")

    def _handle(self, method: str):
        self.correlation_id = self.headers.get("X-Correlation-Id", "corr-" + uuid.uuid4().hex[:16])
        try:
            self._dispatch(method)
        except ApiError as exc:
            self._send_json(exc.status, {"status": exc.status, "code": exc.code, "message": str(exc), "details": exc.details, "correlation_id": self.correlation_id})
        except (ValueError, TypeError):
            self._send_json(400, {"status": 400, "code": "VALIDATION_FAILED", "message": "Invalid request value.", "details": {}, "correlation_id": self.correlation_id})
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            self._send_json(500, {"status": 500, "code": "INTERNAL_ERROR", "message": "Internal error.", "details": {}, "correlation_id": self.correlation_id})

    def do_GET(self): self._handle("GET")
    def do_POST(self): self._handle("POST")
    def do_DELETE(self): self._handle("DELETE")
    def log_message(self, fmt, *args):
        print("[http] " + fmt % args)


def run(host="127.0.0.1", port=8080, db_path=None):
    db = Database(db_path or os.environ.get("CYBERKINGDOMS_DB", str(DEFAULT_DB)))
    db.initialize()
    server = ThreadingHTTPServer((host, port), Handler)
    server.service = GameService(db)
    print(f"CyberKingdoms SQLite Prototype v0.1 -> http://{host}:{port}")
    print(f"SQLite database -> {db.path}")
    server.serve_forever()


if __name__ == "__main__":
    run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8080")))
