from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
VALID_STATUS = {"PASS", "FAIL", "UNKNOWN"}
POLICY_PATH = Path(__file__).with_name("pilot_safe_policy.json")


class PilotSafeEvidenceError(RuntimeError):
    pass


def _critical_contracts(policy_path: str | Path = POLICY_PATH) -> dict[str, set[str]]:
    policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
    contracts = policy.get("evidence_contracts") or {}
    result: dict[str, set[str]] = {}
    for token, contract in contracts.items():
        proofs = contract.get("required_proofs", []) if isinstance(contract, dict) else []
        if not isinstance(proofs, list) or any(not isinstance(item, str) or not item.strip() for item in proofs):
            raise PilotSafeEvidenceError(f"invalid evidence contract: {token}")
        result[str(token)] = {item.strip() for item in proofs}
    return result


def load_evidence_manifest(
    path: str | Path,
    *,
    policy_path: str | Path = POLICY_PATH,
) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    factory_id = str(payload.get("factory_id") or "").strip()
    exact_source_head = str(payload.get("exact_source_head") or "").strip()
    if not factory_id:
        raise PilotSafeEvidenceError("factory_id required")
    if not _SHA_RE.fullmatch(exact_source_head):
        raise PilotSafeEvidenceError("exact_source_head must be a commit SHA")
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict) or not evidence:
        raise PilotSafeEvidenceError("evidence map required")
    critical_contracts = _critical_contracts(policy_path)
    for key, item in evidence.items():
        if not isinstance(item, dict):
            raise PilotSafeEvidenceError(f"invalid evidence item: {key}")
        status = item.get("status")
        if status not in VALID_STATUS:
            raise PilotSafeEvidenceError(f"invalid evidence status: {key}")
        refs = item.get("refs", [])
        if not isinstance(refs, list):
            raise PilotSafeEvidenceError(f"refs must be a list: {key}")
        if status == "PASS" and (not refs or any(not str(ref).strip() for ref in refs)):
            raise PilotSafeEvidenceError(f"PASS requires evidence refs: {key}")

        proofs = item.get("proofs", [])
        if not isinstance(proofs, list) or any(not isinstance(proof, str) or not proof.strip() for proof in proofs):
            raise PilotSafeEvidenceError(f"proofs must be a list of non-empty strings: {key}")
        if status == "PASS" and key in critical_contracts:
            missing = sorted(critical_contracts[key] - {proof.strip() for proof in proofs})
            if missing:
                raise PilotSafeEvidenceError(
                    f"critical PASS missing required subproofs for {key}: " + ", ".join(missing)
                )
    return payload


def passing_tokens(payload: dict[str, Any]) -> set[str]:
    return {
        key
        for key, item in payload["evidence"].items()
        if item.get("status") == "PASS"
    }
