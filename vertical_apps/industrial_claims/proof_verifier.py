from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from vertical_apps.industrial_claims.proof import verify_proof_manifest


def verify_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    core = bundle.get("core_package")
    manifest = bundle.get("proof_manifest")
    if not isinstance(core, dict) or not isinstance(manifest, dict):
        return {"valid": False, "errors": ["BUNDLE_STRUCTURE_INVALID"], "warnings": []}
    return verify_proof_manifest(core, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline verifier for a CausLedger Proof Pack JSON bundle")
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.bundle.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(json.dumps({"valid": False, "errors": [f"BUNDLE_READ_FAILED:{exc}"]}, indent=2))
        return 2
    result = verify_bundle(payload)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
