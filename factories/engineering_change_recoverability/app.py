from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from auth import AuthError, bearer_principal, require_role, require_secret
from commercial_package import build_commercial_package
from engine import analyze_case
from production_security import load_production_config, readiness_snapshot
from store import CaseStore
from synthetic_cases import CASES

ROOT = Path(__file__).resolve().parent
STORE = CaseStore(os.getenv("ECE_DB_PATH", str(ROOT / "ece_factory.db")))

HTML = """<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Engineering Change Recoverability Assurance</title><style>
body{font-family:system-ui,sans-serif;background:#0f1115;color:#f4f5f7;margin:0}main{max-width:1120px;margin:auto;padding:32px}
.hero,.card{padding:20px;border:1px solid #2a3039;border-radius:16px;background:#151922}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-top:20px}
.muted{color:#9aa4b2}.pill{display:inline-block;padding:5px 9px;border:1px solid #39414e;border-radius:999px;font-size:12px}
.row{display:flex;justify-content:space-between;gap:12px;margin:8px 0}.flags{font-size:12px;color:#c7ced8}button{padding:8px 11px;border:0;border-radius:8px;font-weight:700}</style></head>
<body><main><section class='hero'><h1>Engineering Change Recoverability Assurance</h1><p class='muted'>Synthetic demonstration. Unknown stays unknown. Real-record routes require authentication.</p></section><div id='cards' class='grid'></div></main>
<script>
const money=(v,c)=>new Intl.NumberFormat('en',{style:'currency',currency:c==='MIXED'?'EUR':(c||'EUR'),maximumFractionDigits:0}).format(v||0);
async function load(){const r=await fetch('/api/cases');const d=await r.json();document.getElementById('cards').innerHTML=d.items.map(x=>`<section class="card"><h3>${x.change_id}</h3><div class="pill">${x.status}</div><div class="row"><span>Recoverable</span><strong>${money(x.recoverable_amount,x.currency)}</strong></div><div class="row"><span>Unknown</span><span>${money(x.unknown_amount,x.currency)}</span></div><div class="flags">${x.flags.join(' · ')}</div></section>`).join('')}
load();</script></body></html>"""


class PayloadTooLarge(ValueError):
    pass


class Handler(BaseHTTPRequestHandler):
    def _headers(self, content_type: str, length: int):
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")

    def _json(self, payload, status=200):
        body = json.dumps(payload, indent=2).encode()
        self.send_response(status)
        self._headers("application/json; charset=utf-8", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _principal(self):
        try:
            return bearer_principal(self.headers.get("Authorization"))
        except (AuthError, RuntimeError):
            return None

    def _payload(self):
        raw_length = self.headers.get("Content-Length", "0")
        try:
            size = int(raw_length)
        except ValueError as exc:
            raise ValueError("invalid_content_length") from exc
        max_size = int(os.getenv("ECE_MAX_BODY_BYTES", "1048576"))
        if size < 0:
            raise ValueError("invalid_content_length")
        if size > max_size:
            raise PayloadTooLarge("payload_too_large")
        body = self.rfile.read(size)
        return json.loads(body or b"{}")

    def _require_payload_scope(self, principal: dict, payload: dict):
        tenant = str(principal["tenant_id"])
        if str(payload.get("tenant_id") or "").strip() != tenant:
            raise PermissionError("TENANT_MISMATCH")
        return tenant

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._json({"ok": True, "service": "engineering-change-recoverability"})
            return
        if path == "/readyz":
            snapshot = readiness_snapshot(STORE)
            self._json(snapshot, 200 if snapshot["ready"] else 503)
            return
        if path == "/":
            body = HTML.encode()
            self.send_response(200)
            self._headers("text/html; charset=utf-8", len(body))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/cases":
            items = []
            for case in CASES:
                result = analyze_case(case)
                result["company"] = case.get("company")
                items.append(result)
            self._json({"items": items, "count": len(items), "mode": "synthetic_demo"})
            return
        if path.startswith("/api/synthetic/"):
            change_id = path.rsplit("/", 1)[-1]
            case = next((c for c in CASES if c.get("change_id") == change_id), None)
            if not case:
                self._json({"error": "not_found"}, 404)
                return
            self._json({"input": case, "analysis": analyze_case(case)})
            return
        if path.startswith("/api/records/"):
            principal = self._principal()
            if not principal:
                self._json({"error": "authentication_required"}, 401)
                return
            tenant = str(principal["tenant_id"])
            parts = [x for x in path.split("/") if x]
            if len(parts) < 3:
                self._json({"error": "not_found"}, 404)
                return
            change_id = parts[2]
            if len(parts) == 4 and parts[3] == "history":
                self._json({"case_history": STORE.history(tenant, change_id), "analysis_history": STORE.analysis_history(tenant, change_id)})
                return
            latest = STORE.latest_case(tenant, change_id)
            if not latest:
                self._json({"error": "not_found"}, 404)
                return
            self._json(latest)
            return
        self._json({"error": "not_found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self._payload()
        except PayloadTooLarge:
            self._json({"error": "payload_too_large"}, 413)
            return
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"error": "invalid_input", "detail": str(exc)}, 400)
            return
        if path == "/api/analyze":
            principal = self._principal()
            if not principal:
                self._json({"error": "authentication_required"}, 401)
                return
            try:
                self._require_payload_scope(principal, payload)
                result = analyze_case(payload)
            except PermissionError as exc:
                self._json({"error": "tenant_mismatch", "detail": str(exc)}, 403)
                return
            except ValueError as exc:
                self._json({"error": "invalid_input", "detail": str(exc)}, 400)
                return
            self._json(result)
            return
        if path == "/api/records":
            principal = self._principal()
            if not principal:
                self._json({"error": "authentication_required"}, 401)
                return
            try:
                tenant = self._require_payload_scope(principal, payload)
                result = analyze_case(payload)
                package = build_commercial_package(payload, result)
                snapshot = dict(result)
                snapshot["commercial_package"] = package
                persisted = STORE.save_evaluated_case(tenant, payload, snapshot)
            except PermissionError as exc:
                self._json({"error": "tenant_mismatch", "detail": str(exc)}, 403)
                return
            except ValueError as exc:
                self._json({"error": "invalid_input", "detail": str(exc)}, 400)
                return
            self._json({"saved": persisted["saved"], "analysis_saved": persisted["analysis_saved"], "analysis": result, "commercial_package": package}, 201)
            return
        self._json({"error": "not_found"}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/records/"):
            self._json({"error": "not_found"}, 404)
            return
        principal = self._principal()
        if not principal:
            self._json({"error": "authentication_required"}, 401)
            return
        try:
            require_role(principal, "OWNER")
        except AuthError:
            self._json({"error": "owner_required"}, 403)
            return
        parts = [x for x in path.split("/") if x]
        if len(parts) != 3:
            self._json({"error": "not_found"}, 404)
            return
        try:
            result = STORE.purge_change(str(principal["tenant_id"]), parts[2], actor_role=str(principal["role"]))
        except (ValueError, RuntimeError) as exc:
            self._json({"error": "purge_failed", "detail": str(exc)}, 409)
            return
        self._json({"ok": True, "purged": result})

    def log_message(self, fmt, *args):
        return


def run(host="127.0.0.1", port=8765):
    require_secret()
    if (os.getenv("ECE_ENV") or "development").strip().lower() == "production":
        load_production_config()
        ready = readiness_snapshot(STORE)
        if not ready["ready"]:
            raise RuntimeError("production readiness failed: " + ",".join(ready["reasons"]))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Engineering Change Recoverability: http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
