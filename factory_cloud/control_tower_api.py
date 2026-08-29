from __future__ import annotations

from typing import Any

from factory_cloud.global_dispatcher import GlobalDispatcher


def handle_request(
    dispatcher: GlobalDispatcher,
    *,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Small transport-neutral API boundary for the Founder Control Center.

    A web/desktop transport can call this contract without knowing per-Factory
    routes. The caller sends only one scope such as all, obrasignal or business.
    """
    method = method.upper().strip()
    if method == "POST" and path == "/v1/dispatch":
        payload = body or {}
        if not isinstance(payload, dict):
            return 400, {"error": "body_must_be_object"}
        scope = str(payload.get("scope") or "all").strip() or "all"
        try:
            batch = dispatcher.dispatch(scope)
        except Exception as exc:
            return 400, {"error": "dispatch_rejected", "type": type(exc).__name__}
        return 202, batch

    prefix = "/v1/batches/"
    if method == "GET" and path.startswith(prefix):
        batch_id = path[len(prefix):].strip()
        if not batch_id or "/" in batch_id:
            return 400, {"error": "invalid_batch_id"}
        try:
            batch = dispatcher.store.batch(batch_id)
        except KeyError:
            return 404, {"error": "batch_not_found"}
        return 200, batch

    return 404, {"error": "not_found"}
