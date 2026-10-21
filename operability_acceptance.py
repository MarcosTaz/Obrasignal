from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "production-operability-acceptance.v1"
DEFAULT_OBSERVATION = Path(__file__).with_name("operability_acceptance_observation.json")
READY = "READY"


class OperabilityContractError(ValueError):
    """The operability observation is malformed or permits a false-ready claim."""


@dataclass(frozen=True)
class OperabilityResult:
    verdict: str
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict, "reasons": list(self.reasons)}


def load_observation(path: Path | str = DEFAULT_OBSERVATION) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OperabilityContractError(f"cannot load operability observation: {exc}") from exc
    if not isinstance(raw, dict):
        raise OperabilityContractError("operability observation root must be an object")
    return raw


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OperabilityContractError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_probe(probe: Any, field: str, valid_states: set[str]) -> dict[str, Any]:
    if not isinstance(probe, dict):
        raise OperabilityContractError(f"{field} must be an object")
    state = probe.get("state")
    if state not in valid_states:
        raise OperabilityContractError(f"invalid {field}.state: {state}")
    _require_string(probe.get("evidence"), f"{field}.evidence")
    return probe


def validate_observation(observation: dict[str, Any]) -> None:
    if observation.get("contract_version") != CONTRACT_VERSION:
        raise OperabilityContractError("unexpected contract_version")

    snapshot = observation.get("snapshot")
    if not isinstance(snapshot, dict):
        raise OperabilityContractError("snapshot must be an object")
    _require_string(snapshot.get("canonical_main"), "snapshot.canonical_main")
    _require_string(snapshot.get("observed_at"), "snapshot.observed_at")
    if snapshot.get("stale_if_main_moves") is not True:
        raise OperabilityContractError("snapshot must become stale when main moves")

    policy = observation.get("policy")
    if not isinstance(policy, dict):
        raise OperabilityContractError("policy must be an object")
    for field in (
        "liveness_is_not_readiness",
        "unknown_fails_closed",
        "degraded_fails_closed",
        "critical_dependency_unknown_fails_closed",
        "support_evidence_must_be_privacy_safe",
        "operability_ready_is_not_release_go",
    ):
        if policy.get(field) is not True:
            raise OperabilityContractError(f"policy.{field} must remain true")

    probes = observation.get("probes")
    if not isinstance(probes, dict):
        raise OperabilityContractError("probes must be an object")

    _validate_probe(probes.get("liveness"), "probes.liveness", {"UP", "DOWN", "UNKNOWN"})
    _validate_probe(
        probes.get("database"),
        "probes.database",
        {READY, "DEGRADED", "UNAVAILABLE", "UNKNOWN"},
    )
    _validate_probe(
        probes.get("worker"),
        "probes.worker",
        {READY, "DEGRADED", "STALLED", "UNAVAILABLE", "UNKNOWN"},
    )

    dependencies = probes.get("dependencies")
    if not isinstance(dependencies, list) or not dependencies:
        raise OperabilityContractError("probes.dependencies must be a non-empty list")
    for index, dependency in enumerate(dependencies):
        field = f"probes.dependencies[{index}]"
        if not isinstance(dependency, dict):
            raise OperabilityContractError(f"{field} must be an object")
        _require_string(dependency.get("name"), f"{field}.name")
        if dependency.get("critical") is not True:
            raise OperabilityContractError(f"{field}.critical must be true for this release gate")
        _validate_probe(
            dependency,
            field,
            {READY, "DEGRADED", "UNAVAILABLE", "UNKNOWN"},
        )

    correlation = probes.get("support_correlation")
    _validate_probe(
        correlation,
        "probes.support_correlation",
        {READY, "UNSAFE", "UNKNOWN"},
    )
    safety = correlation.get("safety") if isinstance(correlation, dict) else None
    if not isinstance(safety, dict):
        raise OperabilityContractError("probes.support_correlation.safety must be an object")
    required_safety = (
        "opaque_identifier",
        "excludes_bearer_jwt_secrets",
        "excludes_profile_notes_private_payloads",
        "excludes_raw_account_identifier",
    )
    if correlation.get("state") == READY:
        for field in required_safety:
            if safety.get(field) is not True:
                raise OperabilityContractError(
                    "support correlation cannot be READY without privacy-safe evidence: " + field
                )
    else:
        for field in required_safety:
            if safety.get(field) not in (True, False, None):
                raise OperabilityContractError(f"invalid support correlation safety flag: {field}")


def assert_current_main(observation: dict[str, Any], current_main_sha: str) -> None:
    validate_observation(observation)
    observed = _require_string(current_main_sha, "current_main_sha")
    expected = observation["snapshot"]["canonical_main"].strip()
    if observed != expected:
        raise OperabilityContractError(
            "operability observation is stale: "
            f"canonical_main={expected}, observed current main={observed}"
        )


def evaluate(observation: dict[str, Any]) -> OperabilityResult:
    validate_observation(observation)
    probes = observation["probes"]
    reasons: list[str] = []

    if probes["liveness"]["state"] != "UP":
        reasons.append(f"LIVENESS_{probes['liveness']['state']}")

    database_state = probes["database"]["state"]
    if database_state != READY:
        reasons.append(f"DATABASE_{database_state}")

    worker_state = probes["worker"]["state"]
    if worker_state != READY:
        reasons.append(f"WORKER_{worker_state}")

    for dependency in probes["dependencies"]:
        if dependency["state"] != READY:
            reasons.append(f"DEPENDENCY_{dependency['name']}_{dependency['state']}")

    correlation_state = probes["support_correlation"]["state"]
    if correlation_state != READY:
        reasons.append(f"SUPPORT_CORRELATION_{correlation_state}")

    return OperabilityResult(
        verdict="READY" if not reasons else "NO_GO",
        reasons=tuple(reasons),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed production operability acceptance. READY is not release GO."
    )
    parser.add_argument("--observation", default=str(DEFAULT_OBSERVATION))
    parser.add_argument("--current-main-sha", default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    try:
        observation = load_observation(args.observation)
        if args.current_main_sha is not None:
            assert_current_main(observation, args.current_main_sha)
        result = evaluate(observation)
    except OperabilityContractError as exc:
        print(f"OPERABILITY_CONTRACT_ERROR: {exc}")
        return 2

    payload = {
        "canonical_main": observation["snapshot"]["canonical_main"],
        "current_main_verified": args.current_main_sha is not None,
        "operability": result.as_dict(),
        "release_go": False,
    }
    if args.as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"canonical_main={payload['canonical_main']}")
        print(f"current_main_verified={'yes' if payload['current_main_verified'] else 'no'}")
        print(f"operability={result.verdict}; reasons={','.join(result.reasons) or '-'}")
        print("release_go=no; operability acceptance never authorizes merge/deploy/release")

    if args.require_ready and result.verdict != "READY":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
