from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "production-browser-preflight.v1"
DEFAULT_PREFLIGHT = Path(__file__).with_name("web_production_browser_preflight.json")
PASS = "PASS"
NON_PASS = {"FAIL", "UNKNOWN", "BLOCKED_EXTERNAL"}
VALID_RESULTS = {PASS, *NON_PASS, "NOT_IN_SCOPE"}


class BrowserPreflightError(ValueError):
    """The production-browser preflight is malformed or permits false acceptance."""


@dataclass(frozen=True)
class BrowserPreflightResult:
    verdict: str
    blockers: tuple[str, ...]
    unknowns: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "blockers": list(self.blockers),
            "unknowns": list(self.unknowns),
        }


def load_preflight(path: Path | str = DEFAULT_PREFLIGHT) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BrowserPreflightError(f"cannot load browser preflight: {exc}") from exc
    if not isinstance(raw, dict):
        raise BrowserPreflightError("browser preflight root must be an object")
    return raw


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BrowserPreflightError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_item(item: Any, field: str) -> None:
    if not isinstance(item, dict):
        raise BrowserPreflightError(f"{field} must be an object")
    _require_string(item.get("id"), f"{field}.id")
    _require_string(item.get("requirement"), f"{field}.requirement")
    _require_string(item.get("owner"), f"{field}.owner")
    result = item.get("result")
    if result not in VALID_RESULTS:
        raise BrowserPreflightError(f"invalid {field}.result: {result}")
    if item.get("required") is not True and result != "NOT_IN_SCOPE":
        # Optional observations may be PASS/UNKNOWN/etc, but must say why they do not gate.
        _require_string(item.get("scope_note"), f"{field}.scope_note")
    if result != PASS:
        _require_string(item.get("reopen_condition"), f"{field}.reopen_condition")
    evidence = item.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise BrowserPreflightError(f"{field}.evidence must be a non-empty list")
    for evidence_item in evidence:
        _require_string(evidence_item, f"{field}.evidence")
    if item.get("conditional_skip") is True and item.get("required") is True:
        raise BrowserPreflightError(f"{field} required acceptance cannot use a conditional skip")


def _reject_secret_material(value: Any, path: str = "root") -> None:
    """Reject common accidental secret capture fields/values from committed evidence.

    Public configuration names are allowed. Secret *values*, bearer/JWT material and
    captured credentials are not valid preflight evidence.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in {
                "secret",
                "secret_value",
                "password",
                "access_token",
                "refresh_token",
                "authorization_header",
                "jwt",
            }:
                raise BrowserPreflightError(f"secret-bearing field is forbidden: {path}.{key}")
            _reject_secret_material(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_material(child, f"{path}[{index}]")
    elif isinstance(value, str):
        lowered = value.lower()
        if "bearer eyj" in lowered or value.count(".") >= 2 and value.startswith("eyJ"):
            raise BrowserPreflightError(f"token-like material is forbidden: {path}")


def validate_preflight(preflight: dict[str, Any]) -> None:
    _reject_secret_material(preflight)
    if preflight.get("contract_version") != CONTRACT_VERSION:
        raise BrowserPreflightError("unexpected contract_version")

    snapshot = preflight.get("snapshot")
    if not isinstance(snapshot, dict):
        raise BrowserPreflightError("snapshot must be an object")
    _require_string(snapshot.get("canonical_main"), "snapshot.canonical_main")
    _require_string(snapshot.get("observed_at"), "snapshot.observed_at")
    if snapshot.get("stale_if_main_moves") is not True:
        raise BrowserPreflightError("snapshot must become stale when main moves")

    policy = preflight.get("policy")
    if not isinstance(policy, dict):
        raise BrowserPreflightError("policy must be an object")
    for field in (
        "real_browser_observation_required",
        "exact_deployed_build_required",
        "unknown_fails_closed",
        "conditional_skip_fails_closed",
        "tenant_isolation_is_blocking",
        "evidence_must_be_privacy_safe",
        "saved_watch_is_conditional_scope",
        "operational_web_gate_is_not_commercial_completion",
    ):
        if policy.get(field) is not True:
            raise BrowserPreflightError(f"policy.{field} must remain true")

    config = preflight.get("config_requirements")
    journeys = preflight.get("journey_matrix")
    if not isinstance(config, list) or not config:
        raise BrowserPreflightError("config_requirements must be a non-empty list")
    if not isinstance(journeys, list) or not journeys:
        raise BrowserPreflightError("journey_matrix must be a non-empty list")

    ids: set[str] = set()
    for group_name, items in (("config_requirements", config), ("journey_matrix", journeys)):
        for index, item in enumerate(items):
            _validate_item(item, f"{group_name}[{index}]")
            item_id = item["id"]
            if item_id in ids:
                raise BrowserPreflightError(f"duplicate preflight id: {item_id}")
            ids.add(item_id)

    saved = next((item for item in journeys if item.get("id") == "SAVED_WATCH"), None)
    if saved is None or saved.get("required") is not False:
        raise BrowserPreflightError("SAVED_WATCH must remain explicitly non-blocking unless canonical scope changes")

    template = preflight.get("evidence_template")
    if not isinstance(template, dict):
        raise BrowserPreflightError("evidence_template must be an object")
    fields = template.get("required_fields")
    required_fields = {
        "timestamp",
        "browser_version",
        "os",
        "deployed_build_sha",
        "web_origin",
        "api_origin",
        "account_alias",
        "action",
        "expected",
        "observed",
        "result",
        "sanitized_artifact_ref",
        "owner",
        "reopen_condition",
    }
    if not isinstance(fields, list) or not required_fields.issubset(set(fields)):
        raise BrowserPreflightError("evidence_template.required_fields is incomplete")


def assert_current_main(preflight: dict[str, Any], current_main_sha: str) -> None:
    validate_preflight(preflight)
    observed = _require_string(current_main_sha, "current_main_sha")
    expected = preflight["snapshot"]["canonical_main"]
    if observed != expected:
        raise BrowserPreflightError(
            f"browser preflight is stale: canonical_main={expected}, observed current main={observed}"
        )


def audit_preflight(preflight: dict[str, Any]) -> BrowserPreflightResult:
    validate_preflight(preflight)
    blockers: list[str] = []
    unknowns: list[str] = []
    for item in [*preflight["config_requirements"], *preflight["journey_matrix"]]:
        if item.get("required") is not True:
            continue
        result = item["result"]
        if result == PASS:
            continue
        if result in {"UNKNOWN", "BLOCKED_EXTERNAL"}:
            unknowns.append(item["id"])
        else:
            blockers.append(item["id"])
    verdict = "GO" if not blockers and not unknowns else "NO_GO"
    return BrowserPreflightResult(verdict, tuple(blockers), tuple(unknowns))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed #68 production-browser preflight. Does not mutate config or authorize release."
    )
    parser.add_argument("--preflight", default=str(DEFAULT_PREFLIGHT))
    parser.add_argument("--current-main-sha", default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--require-go", action="store_true")
    args = parser.parse_args()

    try:
        preflight = load_preflight(args.preflight)
        if args.current_main_sha is not None:
            assert_current_main(preflight, args.current_main_sha)
        result = audit_preflight(preflight)
    except BrowserPreflightError as exc:
        print(f"BROWSER_PREFLIGHT_ERROR: {exc}")
        return 2

    payload = {
        "canonical_main": preflight["snapshot"]["canonical_main"],
        "current_main_verified": args.current_main_sha is not None,
        "result": result.as_dict(),
        "release_go": False,
    }
    if args.as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"canonical_main={payload['canonical_main']}")
        print(f"browser_preflight={result.verdict}")
        print(f"blockers={','.join(result.blockers) or '-'}")
        print(f"unknowns={','.join(result.unknowns) or '-'}")
        print("release_go=no; #68 operational browser acceptance is not commercial/release completion")

    if args.require_go and result.verdict != "GO":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
