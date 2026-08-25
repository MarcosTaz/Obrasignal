from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "production-customer-readiness.v1"
DEFAULT_MANIFEST = Path(__file__).with_name("production_readiness_manifest.json")
REQUIRED_GATES = (
    "AUTH",
    "TENANT",
    "DATA",
    "SOURCES",
    "WEB",
    "MOBILE",
    "NOTIFICATIONS",
    "BILLING",
    "EVALUATION",
    "PRIVACY",
    "RECOVERY",
    "SECURITY",
    "OBSERVABILITY",
    "GOLDEN",
    "CUSTOMER_PROOF",
)
VALID_CLASSIFICATIONS = {"PROVEN", "UNKNOWN", "DEFECT", "EXTERNAL", "READY"}
VALID_RELEASE_GATES = {"PASS", "NO_GO", "UNKNOWN"}
PASS_CLASSIFICATIONS = {"PROVEN", "READY"}


class ReadinessContractError(ValueError):
    """The readiness manifest is malformed, stale, or permits a false-ready state."""


@dataclass(frozen=True)
class TargetResult:
    target: str
    verdict: str
    blockers: tuple[str, ...]
    unknowns: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "verdict": self.verdict,
            "blockers": list(self.blockers),
            "unknowns": list(self.unknowns),
        }


def load_manifest(path: Path | str = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest_path = Path(path)
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReadinessContractError(f"cannot load readiness manifest: {exc}") from exc
    if not isinstance(raw, dict):
        raise ReadinessContractError("readiness manifest root must be an object")
    return raw


def _require_non_empty_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ReadinessContractError(f"{field} must be a non-empty string")


def _require_non_empty_string_list(value: Any, field: str) -> None:
    if not isinstance(value, list) or not value:
        raise ReadinessContractError(f"{field} must be a non-empty list")
    for item in value:
        _require_non_empty_string(item, field)


def validate_manifest(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if manifest.get("contract_version") != CONTRACT_VERSION:
        raise ReadinessContractError("unexpected contract_version")

    snapshot = manifest.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ReadinessContractError("snapshot must be an object")
    _require_non_empty_string(snapshot.get("canonical_main"), "snapshot.canonical_main")
    _require_non_empty_string(snapshot.get("observed_at"), "snapshot.observed_at")
    if snapshot.get("stale_if_main_moves") is not True:
        raise ReadinessContractError("snapshot must explicitly become stale when main moves")

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise ReadinessContractError("policy must be an object")
    for field in (
        "green_candidate_is_not_production_ready",
        "all_blocking_gates_must_pass",
        "candidate_only_evidence_cannot_pass_release",
        "unknown_fails_closed",
        "external_requires_explicit_reopen_condition",
    ):
        if policy.get(field) is not True:
            raise ReadinessContractError(f"policy.{field} must remain true")

    gates = manifest.get("gates")
    if not isinstance(gates, list):
        raise ReadinessContractError("gates must be a list")

    by_id: dict[str, dict[str, Any]] = {}
    for gate in gates:
        if not isinstance(gate, dict):
            raise ReadinessContractError("every gate must be an object")
        gate_id = gate.get("id")
        _require_non_empty_string(gate_id, "gate.id")
        if gate_id in by_id:
            raise ReadinessContractError(f"duplicate gate: {gate_id}")

        classification = gate.get("classification")
        release_gate = gate.get("release_gate")
        if classification not in VALID_CLASSIFICATIONS:
            raise ReadinessContractError(f"invalid classification for {gate_id}: {classification}")
        if release_gate not in VALID_RELEASE_GATES:
            raise ReadinessContractError(f"invalid release_gate for {gate_id}: {release_gate}")

        _require_non_empty_string(gate.get("owner"), f"{gate_id}.owner")
        _require_non_empty_string(gate.get("evidence_scope"), f"{gate_id}.evidence_scope")
        _require_non_empty_string_list(gate.get("evidence"), f"{gate_id}.evidence")
        _require_non_empty_string(gate.get("reopen_condition"), f"{gate_id}.reopen_condition")

        if release_gate == "PASS" and classification not in PASS_CLASSIFICATIONS:
            raise ReadinessContractError(
                f"{gate_id} cannot PASS with classification {classification}"
            )
        if release_gate == "PASS" and "CANDIDATE" in str(gate.get("evidence_scope")).upper():
            raise ReadinessContractError(
                f"{gate_id} cannot PASS from candidate-only/mixed candidate evidence"
            )
        if classification == "EXTERNAL" and not gate.get("reopen_condition"):
            raise ReadinessContractError(f"{gate_id} EXTERNAL requires a reopen condition")
        if release_gate != "PASS":
            remaining = gate.get("remaining")
            _require_non_empty_string_list(remaining, f"{gate_id}.remaining")

        by_id[gate_id] = gate

    if set(by_id) != set(REQUIRED_GATES):
        missing = sorted(set(REQUIRED_GATES) - set(by_id))
        extra = sorted(set(by_id) - set(REQUIRED_GATES))
        raise ReadinessContractError(f"gate inventory mismatch; missing={missing}, extra={extra}")

    targets = manifest.get("targets")
    if not isinstance(targets, dict) or not targets:
        raise ReadinessContractError("targets must be a non-empty object")
    for target, gate_ids in targets.items():
        _require_non_empty_string(target, "target")
        if not isinstance(gate_ids, list) or not gate_ids:
            raise ReadinessContractError(f"target {target} must select at least one gate")
        if len(gate_ids) != len(set(gate_ids)):
            raise ReadinessContractError(f"target {target} contains duplicate gates")
        unknown = sorted(set(gate_ids) - set(by_id))
        if unknown:
            raise ReadinessContractError(f"target {target} references unknown gates: {unknown}")

    return by_id


def assert_current_main(manifest: dict[str, Any], current_main_sha: str) -> None:
    """Reject a readiness snapshot as stale when the observed canonical main moved.

    The caller supplies the freshly observed SHA. This function never fetches GitHub,
    mutates repository state, or silently rebases evidence onto a newer main.
    """
    validate_manifest(manifest)
    _require_non_empty_string(current_main_sha, "current_main_sha")
    expected = manifest["snapshot"]["canonical_main"].strip()
    observed = current_main_sha.strip()
    if observed != expected:
        raise ReadinessContractError(
            "readiness snapshot is stale: "
            f"manifest canonical_main={expected}, observed current main={observed}; "
            "reconstruct and reconcile evidence before auditing release readiness"
        )


def audit_target(manifest: dict[str, Any], target: str) -> TargetResult:
    by_id = validate_manifest(manifest)
    targets = manifest["targets"]
    if target not in targets:
        raise ReadinessContractError(f"unknown readiness target: {target}")

    blockers: list[str] = []
    unknowns: list[str] = []
    for gate_id in targets[target]:
        release_gate = by_id[gate_id]["release_gate"]
        if release_gate == "NO_GO":
            blockers.append(gate_id)
        elif release_gate == "UNKNOWN":
            unknowns.append(gate_id)

    verdict = "GO" if not blockers and not unknowns else "NO_GO"
    return TargetResult(
        target=target,
        verdict=verdict,
        blockers=tuple(blockers),
        unknowns=tuple(unknowns),
    )


def audit_all(manifest: dict[str, Any]) -> list[TargetResult]:
    validate_manifest(manifest)
    return [audit_target(manifest, target) for target in manifest["targets"]]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed ObraSignal production/customer release readiness audit."
    )
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--target", default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument(
        "--current-main-sha",
        default=None,
        help=(
            "Freshly observed canonical main SHA. When supplied, the audit fails closed "
            "if it differs from snapshot.canonical_main."
        ),
    )
    parser.add_argument(
        "--require-go",
        action="store_true",
        help="Return exit code 1 unless the selected target is GO. Never use this as merge authorization.",
    )
    args = parser.parse_args()

    try:
        manifest = load_manifest(args.manifest)
        if args.current_main_sha is not None:
            assert_current_main(manifest, args.current_main_sha)
        results = (
            [audit_target(manifest, args.target)] if args.target else audit_all(manifest)
        )
    except ReadinessContractError as exc:
        print(f"READINESS_CONTRACT_ERROR: {exc}")
        return 2

    if args.as_json:
        payload = {
            "canonical_main": manifest["snapshot"]["canonical_main"],
            "current_main_verified": args.current_main_sha is not None,
            "results": [result.as_dict() for result in results],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"canonical_main={manifest['snapshot']['canonical_main']}")
        print(f"current_main_verified={'yes' if args.current_main_sha is not None else 'no'}")
        for result in results:
            print(
                f"{result.target}: {result.verdict}; "
                f"blockers={','.join(result.blockers) or '-'}; "
                f"unknowns={','.join(result.unknowns) or '-'}"
            )

    if args.require_go and any(result.verdict != "GO" for result in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
