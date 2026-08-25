"""Executable cross-owner API compatibility observations.

This module is governance-only. It observes executable producer/consumer source
and fingerprints the observed contract. It does not define business behavior or
replace domain, persistence, Auth, or client ownership.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path("contracts/public_contract_registry.json")

COMPATIBILITY_CLASSES = {
    "ADDITIVE_SAFE",
    "ADDITIVE_RISKY",
    "SEMANTIC_CHANGE",
    "BREAKING",
    "SECURITY_RELEVANT",
    "TENANT_RELEVANT",
    "UNKNOWN",
}


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _state(condition: bool, value: str) -> str:
    return value if condition else "UNKNOWN"


def observe_opportunity_workflow(root: Path = Path(".")) -> dict[str, Any]:
    """Observe the current workflow API and known cross-owner consumers.

    Deliberately records only compatibility-significant surface semantics.
    """
    api = _read(root, "api.py")
    mobile = _read(root, "mobile/src/api.js")
    auth_e2e = _read(root, ".github/workflows/authenticated-e2e.yml")

    route_literal = '@bp.route("/opportunities/<int:opportunity_id>/workflow", methods=["GET", "POST"])'
    route = (
        "/api/v1/opportunities/<int:opportunity_id>/workflow"
        if route_literal in api
        else "UNKNOWN"
    )

    get_shape = _state(
        'return jsonify({"workflow": workflow, "account_id": identity.account_id, "generated_at": _iso_now()})'
        in api,
        "workflow_envelope",
    )
    post_shape = _state(
        'return jsonify({"ok": True, "workflow": workflow, "account_id": identity.account_id, "generated_at": _iso_now()})'
        in api,
        "ok_workflow_envelope",
    )
    tenant = _state(
        "identity = request.obrasignal_identity" in api
        and "get_workflow(c, identity.account_id" in api
        and "set_workflow(\n            c,\n            identity.account_id," in api,
        "authenticated_account_id",
    )
    not_found = _state(
        'return jsonify({"error": "not_found"}), 404' in api,
        "404:not_found",
    )
    validation = _state(
        'except ValueError as exc:\n        return jsonify({"error": str(exc)}), 400' in api,
        "400:error_string",
    )
    request_fields = []
    if 'payload.get("status")' in api:
        request_fields.append("status")
    if 'payload.get("note")' in api:
        request_fields.append("note")

    mobile_read = _state(
        "workflow:(id)=>readWhenReady(`/opportunities/${encodeURIComponent(id)}/workflow`)"
        in mobile,
        "raw_envelope",
    )
    mobile_write = _state(
        "setWorkflow:(id,status,note)=>writeWhenReady(`/opportunities/${encodeURIComponent(id)}/workflow`"
        in mobile
        and "JSON.stringify({status,note:note||null})" in mobile,
        "status_note",
    )

    if (
        "workflow=json.load(open('/tmp/workflow.json'))" in auth_e2e
        and "assert workflow.get('status')" in auth_e2e
    ):
        auth_read = "flat_workflow_fields"
    elif (
        "/tmp/workflow.json" in auth_e2e
        and ".get('workflow')" in auth_e2e
        and "get('status')" in auth_e2e
    ):
        auth_read = "workflow_envelope"
    else:
        auth_read = "UNKNOWN"

    return {
        "contract": "opportunity_workflow.v1",
        "producer": {
            "route": route,
            "methods": ["GET", "POST"] if route != "UNKNOWN" else [],
            "get_shape": get_shape,
            "post_shape": post_shape,
            "tenant": tenant,
            "not_found": not_found,
            "validation": validation,
            "request_fields": sorted(request_fields),
        },
        "consumers": {
            "mobile_api": {"read": mobile_read, "write": mobile_write},
            "authenticated_e2e": {"read": auth_read},
        },
    }


def fingerprint(snapshot: dict[str, Any]) -> str:
    payload = json.dumps(
        snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def findings(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    producer = snapshot["producer"]
    consumers = snapshot["consumers"]

    if (
        producer["get_shape"] == "workflow_envelope"
        and consumers["authenticated_e2e"]["read"] == "flat_workflow_fields"
    ):
        result.append(
            {
                "id": "opportunity_workflow.auth_e2e.flat_response_parser",
                "classification": "BREAKING",
                "owner": "Auth/#289",
                "reason": (
                    "Provider returns workflow fields inside `workflow`, while the "
                    "Authenticated E2E consumer reads `status`/`note` at top level."
                ),
            }
        )

    unknown_paths = []
    if producer["route"] == "UNKNOWN":
        unknown_paths.append("producer.route")
    for key in ("get_shape", "post_shape", "tenant", "not_found", "validation"):
        if producer[key] == "UNKNOWN":
            unknown_paths.append(f"producer.{key}")
    if set(producer["request_fields"]) != {"status", "note"}:
        unknown_paths.append("producer.request_fields")
    for consumer, contract in consumers.items():
        for key, value in contract.items():
            if value == "UNKNOWN":
                unknown_paths.append(f"consumers.{consumer}.{key}")

    if unknown_paths:
        result.append(
            {
                "id": "opportunity_workflow.surface_unknown",
                "classification": "UNKNOWN",
                "owner": "Contract Governance",
                "reason": "Unrecognized compatibility surface: " + ", ".join(sorted(unknown_paths)),
            }
        )
    return result


def load_registry(root: Path = Path(".")) -> dict[str, Any]:
    return json.loads(_read(root, str(REGISTRY_PATH)))


def evaluate_snapshot(
    snapshot: dict[str, Any], entry: dict[str, Any]
) -> dict[str, Any]:
    actual_fingerprint = fingerprint(snapshot)
    actual_findings = findings(snapshot)
    actual_ids = {item["id"] for item in actual_findings}
    acknowledged_ids = {
        item["id"] for item in entry.get("acknowledged_findings", [])
    }
    unacknowledged = sorted(actual_ids - acknowledged_ids)
    resolved_without_ack = sorted(acknowledged_ids - actual_ids)
    fingerprint_changed = actual_fingerprint != entry["expected_fingerprint"]

    return {
        "contract": snapshot["contract"],
        "fingerprint": actual_fingerprint,
        "expected_fingerprint": entry["expected_fingerprint"],
        "fingerprint_changed": fingerprint_changed,
        "findings": actual_findings,
        "unacknowledged_findings": unacknowledged,
        "resolved_without_acknowledgement": resolved_without_ack,
        "review_required": bool(
            fingerprint_changed or unacknowledged or resolved_without_ack
        ),
    }


def audit(root: Path = Path(".")) -> dict[str, Any]:
    registry = load_registry(root)
    if registry.get("authority") != "observation_only":
        raise ValueError("Contract registry must remain observation_only")
    snapshot = observe_opportunity_workflow(root)
    entry = registry["contracts"][snapshot["contract"]]
    return evaluate_snapshot(snapshot, entry)


def main() -> int:
    result = audit()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2 if result["review_required"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
