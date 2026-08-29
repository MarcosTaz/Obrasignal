from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

MANIFEST_PATH = Path(__file__).with_name("shared_core_manifest.json")
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class SharedCoreError(RuntimeError):
    pass


def load_shared_core(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise SharedCoreError("shared core manifest must be an object")
    if not str(data.get("owner") or "").strip():
        raise SharedCoreError("shared core owner is required")
    if not str(data.get("compatibility_policy") or "").strip():
        raise SharedCoreError("compatibility policy is required")
    capabilities = data.get("capabilities")
    if not isinstance(capabilities, dict) or not capabilities:
        raise SharedCoreError("shared core capabilities are required")
    for capability_id, item in capabilities.items():
        if not str(capability_id).strip() or not isinstance(item, dict):
            raise SharedCoreError("invalid shared core capability entry")
        if not _SEMVER.fullmatch(str(item.get("version") or "")):
            raise SharedCoreError(f"invalid shared core version: {capability_id}")
        if not str(item.get("module") or "").strip():
            raise SharedCoreError(f"shared core module required: {capability_id}")
        consumers = item.get("consumers")
        if not isinstance(consumers, list) or len(set(consumers)) < 2:
            raise SharedCoreError(f"shared core requires at least two consumers: {capability_id}")
    return data
