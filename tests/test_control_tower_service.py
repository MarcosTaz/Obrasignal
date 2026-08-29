import http.client
import json
import threading
from pathlib import Path

from factory_cloud.control_tower_service import make_server


def _request(port: int, method: str, path: str, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    encoded = None if body is None else json.dumps(body).encode("utf-8")
    headers = {} if encoded is None else {"content-type": "application/json", "content-length": str(len(encoded))}
    conn.request(method, path, body=encoded, headers=headers)
    response = conn.getresponse()
    payload = json.loads(response.read().decode("utf-8"))
    status = response.status
    no_store = response.getheader("cache-control")
    conn.close()
    return status, payload, no_store


def test_http_service_exposes_health_and_single_global_dispatch(tmp_path: Path):
    server = make_server("127.0.0.1", 0, environ={}, runtime_dir=tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        status, payload, cache = _request(port, "GET", "/health")
        assert status == 200
        assert payload == {"ok": True, "service": "global-control-tower"}
        assert cache == "no-store"

        status, batch, _ = _request(port, "POST", "/v1/dispatch", {"scope": "all"})
        assert status == 202
        assert batch["scope"] == "all"
        assert batch["batch_id"]
        assert batch["items"]
        assert all("chat_url" not in item and "conversation_url" not in item for item in batch["items"])

        status, loaded, _ = _request(port, "GET", f"/v1/batches/{batch['batch_id']}")
        assert status == 200
        assert loaded["batch_id"] == batch["batch_id"]
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_http_service_rejects_oversize_or_non_object_json(tmp_path: Path):
    server = make_server("127.0.0.1", 0, environ={}, runtime_dir=tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
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
