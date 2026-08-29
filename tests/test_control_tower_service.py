import http.client
import json
import threading
from pathlib import Path

from factory_cloud.control_tower_service import make_server


def _request(port: int, method: str, path: str, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    encoded = None if body is None else json.dumps(body).encode("utf-8")
    final_headers = dict(headers or {})
    if encoded is not None:
        final_headers.setdefault("content-type", "application/json")
        final_headers.setdefault("content-length", str(len(encoded)))
    conn.request(method, path, body=encoded, headers=final_headers)
    response = conn.getresponse()
    raw = response.read().decode("utf-8")
    payload = json.loads(raw) if raw else None
    result = {
        "status": response.status,
        "payload": payload,
        "cache": response.getheader("cache-control"),
        "allow_origin": response.getheader("access-control-allow-origin"),
    }
    conn.close()
    return result


def _running_server(tmp_path: Path, environ=None):
    server = make_server("127.0.0.1", 0, environ=environ or {}, runtime_dir=tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, server.server_address[1]


def test_http_service_exposes_health_and_single_global_dispatch(tmp_path: Path):
    server, thread, port = _running_server(tmp_path)
    try:
        health = _request(port, "GET", "/health")
        assert health["status"] == 200
        assert health["payload"] == {"ok": True, "service": "global-control-tower"}
        assert health["cache"] == "no-store"

        dispatched = _request(port, "POST", "/v1/dispatch", {"scope": "all"})
        assert dispatched["status"] == 202
        batch = dispatched["payload"]
        assert batch["scope"] == "all"
        assert batch["batch_id"]
        assert batch["items"]
        assert all("chat_url" not in item and "conversation_url" not in item for item in batch["items"])

        loaded = _request(port, "GET", f"/v1/batches/{batch['batch_id']}")
        assert loaded["status"] == 200
        assert loaded["payload"]["batch_id"] == batch["batch_id"]
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_http_service_rejects_non_object_json(tmp_path: Path):
    server, thread, port = _running_server(tmp_path)
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        raw = b"[]"
        conn.request("POST", "/v1/dispatch", body=raw, headers={"content-type": "application/json", "content-length": str(len(raw))})
        response = conn.getresponse()
        assert response.status == 400
        assert json.loads(response.read().decode("utf-8"))["error"] == "invalid_json_body"
        conn.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_api_bearer_token_is_required_when_configured_but_health_stays_readable(tmp_path: Path):
    server, thread, port = _running_server(tmp_path, {"FACTORY_CONTROL_TOKEN": "tower-secret"})
    try:
        assert _request(port, "GET", "/health")["status"] == 200
        denied = _request(port, "POST", "/v1/dispatch", {"scope": "all"})
        assert denied["status"] == 401
        assert denied["payload"] == {"error": "unauthorized"}
        allowed = _request(
            port,
            "POST",
            "/v1/dispatch",
            {"scope": "all"},
            {"authorization": "Bearer tower-secret"},
        )
        assert allowed["status"] == 202
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_cross_origin_requests_are_allowlisted_not_wildcarded(tmp_path: Path):
    origin = "https://founder-control.example.test"
    server, thread, port = _running_server(
        tmp_path,
        {
            "FACTORY_CONTROL_TOKEN": "tower-secret",
            "FACTORY_CONTROL_ALLOWED_ORIGIN": origin,
        },
    )
    try:
        denied = _request(
            port,
            "POST",
            "/v1/dispatch",
            {"scope": "all"},
            {"authorization": "Bearer tower-secret", "origin": "https://evil.example.test"},
        )
        assert denied["status"] == 403
        assert denied["payload"] == {"error": "origin_not_allowed"}

        allowed = _request(
            port,
            "POST",
            "/v1/dispatch",
            {"scope": "all"},
            {"authorization": "Bearer tower-secret", "origin": origin},
        )
        assert allowed["status"] == 202
        assert allowed["allow_origin"] == origin
        assert allowed["allow_origin"] != "*"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
