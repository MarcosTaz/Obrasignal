from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from engine import analyze_case
from store import CaseStore
from auth import AuthError, bearer_tenant, require_secret
from commercial_package import build_commercial_package

ROOT = Path(__file__).resolve().parent
CASES = json.loads((ROOT / "synthetic_cases.json").read_text())
STORE = CaseStore(os.getenv("ECE_DB_PATH", str(ROOT / "ece_factory.db")))

HTML = """<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Engineering Change Recoverability Assurance</title>
<style>
body{font-family:Inter,system-ui,sans-serif;background:#0f1115;color:#f4f5f7;margin:0}main{max-width:1120px;margin:auto;padding:32px}.hero{padding:28px;border:1px solid #2a3039;border-radius:18px;background:#151922}.eyebrow{color:#9aa4b2;text-transform:uppercase;letter-spacing:.14em;font-size:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-top:20px}.card{border:1px solid #2a3039;border-radius:14px;padding:18px;background:#151922}.money{font-size:28px;font-weight:700}.muted{color:#9aa4b2}.pill{display:inline-block;padding:5px 9px;border:1px solid #39414e;border-radius:999px;font-size:12px}.row{display:flex;justify-content:space-between;gap:12px;margin:8px 0}.flags{font-size:12px;color:#c7ced8}button{background:#f4f5f7;color:#0f1115;border:0;border-radius:9px;padding:9px 12px;font-weight:700;cursor:pointer}pre{white-space:pre-wrap;background:#0c0f13;padding:12px;border-radius:10px;overflow:auto}</style></head>
<body><main><section class='hero'><div class='eyebrow'>Independent recoverability assurance — assisted prototype</div><h1>Engineering changes should not silently become margin leakage.</h1><p class='muted'>This prototype keeps technical change, evidenced cost, causality, mitigation, entitlement, notice and payment truth separate. Unknown stays unknown.</p></section>
<div id='cards' class='grid'></div></main>
<script>
const money=(v,c)=>new Intl.NumberFormat('en',{style:'currency',currency:c||'EUR',maximumFractionDigits:0}).format(v||0);
async function load(){const r=await fetch('/api/cases');const data=await r.json();const root=document.getElementById('cards');root.innerHTML='';for(const item of data.items){const d=document.createElement('section');d.className='card';d.innerHTML=`<div class='eyebrow'>${item.company||item.tenant_id}</div><h3>${item.change_id}</h3><div class='pill'>${item.status}</div><div class='row'><span>Recoverable</span><strong>${money(item.recoverable_amount,item.currency)}</strong></div><div class='row'><span>Non-recoverable</span><span>${money(item.nonrecoverable_amount,item.currency)}</span></div><div class='row'><span>Unknown</span><span>${money(item.unknown_amount,item.currency)}</span></div><div class='row'><span>Mitigated</span><span>${money(item.mitigated_amount,item.currency)}</span></div><div class='row'><span>Prior payment</span><span>${money(item.prior_payment_amount,item.currency)}</span></div><div class='flags'>${item.flags.join(' · ')||'No exceptions'}</div><p><button data-id='${item.change_id}'>Inspect</button></p><pre id='p-${item.change_id}' style='display:none'></pre>`;root.appendChild(d)}document.querySelectorAll('button').forEach(b=>b.onclick=async()=>{const r=await fetch('/api/synthetic/'+encodeURIComponent(b.dataset.id));const x=await r.json();const p=document.getElementById('p-'+b.dataset.id);p.style.display=p.style.display==='none'?'block':'none';p.textContent=JSON.stringify(x,null,2)})}
load();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload, status=200):
        body = json.dumps(payload, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _tenant(self):
        try:
            return bearer_tenant(self.headers.get("Authorization"))
        except AuthError:
            return ""

    def _payload(self):
        size = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(size) or b"{}")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
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
            tenant = self._tenant()
            if not tenant:
                self._json({"error": "authentication_required"}, 401)
                return
            parts = [x for x in path.split("/") if x]
            if len(parts) < 3:
                self._json({"error": "not_found"}, 404)
                return
            change_id = parts[2]
            if len(parts) == 4 and parts[3] == "history":
                self._json({
                    "case_history": STORE.history(tenant, change_id),
                    "analysis_history": STORE.analysis_history(tenant, change_id),
                })
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
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"error": "invalid_input", "detail": str(exc)}, 400)
            return

        if path == "/api/analyze":
            try:
                result = analyze_case(payload)
            except ValueError as exc:
                self._json({"error": "invalid_input", "detail": str(exc)}, 400)
                return
            self._json(result)
            return

        if path == "/api/records":
            tenant = self._tenant()
            if not tenant:
                self._json({"error": "authentication_required"}, 401)
                return
            try:
                result = analyze_case(payload)
                package = build_commercial_package(payload, result)
                snapshot = dict(result)
                snapshot["commercial_package"] = package
                persisted = STORE.save_evaluated_case(tenant, payload, snapshot)
                saved = persisted["saved"]
                analysis_meta = persisted["analysis_saved"]
            except PermissionError as exc:
                self._json({"error": "tenant_mismatch", "detail": str(exc)}, 403)
                return
            except ValueError as exc:
                self._json({"error": "invalid_input", "detail": str(exc)}, 400)
                return
            self._json({"saved": saved, "analysis_saved": analysis_meta, "analysis": result, "commercial_package": package}, 201)
            return

        self._json({"error": "not_found"}, 404)

    def log_message(self, fmt, *args):
        return


def run(host="127.0.0.1", port=8765):
    require_secret()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Engineering Change Recoverability prototype: http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
