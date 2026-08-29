from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
VALID_STATUS = {"PASS", "FAIL", "UNKNOWN"}


class PilotSafeEvidenceError(RuntimeError):
    pass


def load_evidence_manifest(path: str | Path) -> dict[str, Any]:
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
    return payload


def passing_tokens(payload: dict[str, Any]) -> set[str]:
    return {
        key
        for key, item in payload["evidence"].items()
        if item.get("status") == "PASS"
    }
