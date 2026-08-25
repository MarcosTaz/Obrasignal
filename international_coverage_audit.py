"""Canonical CLI/public interface for the ObraSignal international coverage audit.

The internal core gathers repository evidence.  This public boundary applies the
strict path-token and final gating policy so callers have one canonical result.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import international_coverage_audit_core as _core


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _exact_path_token_match(path: Path, token: str) -> bool:
    """Match token segments contiguously; never match inside another word.

    Examples: ``AUT`` must not match ``auth`` and ``BASE`` must not match
    ``database``. Multi-segment tokens such as ``at_kerndaten`` still match
    filenames containing those exact adjacent segments.
    """
    wanted = tuple(part for part in _slug(token).split("_") if part)
    actual = tuple(part for part in _slug(str(path.with_suffix(""))).split("_") if part)
    if not wanted or len(wanted) > len(actual):
        return False
    width = len(wanted)
    return any(actual[index : index + width] == wanted for index in range(len(actual) - width + 1))


# The core is internal to this module. Install the canonical matcher before any
# audit runs so every provenance classification uses the same fail-closed rule.
_core._matches_token = _exact_path_token_match


def run_audit(repo_root=None):
    result = _core.run_audit(repo_root)
    missing = set(result["missing_integrations"])
    for row in result["countries"]:
        if row["MARKET_CLASSIFICATION"] not in {"BUILD", "SHARED"}:
            continue
        if row["PRODUCTION_PATH"]:
            continue
        gaps = set(row["KNOWN_GAPS"])
        gaps.add("NO_ACTIVE_PRODUCTION_SOURCE")
        row["KNOWN_GAPS"] = sorted(gaps)
        missing.add(f"{row['COUNTRY']}:no_active_production_source")
    result["missing_integrations"] = sorted(missing)
    result["summary"]["missing_integration_count"] = len(result["missing_integrations"])
    return result


def to_markdown(result):
    return _core.to_markdown(result)


# Backwards-compatible internal name from the first implementation.
_to_markdown = to_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit ObraSignal international coverage from repository state."
    )
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON.")
    parser.add_argument("--markdown", action="store_true", help="Print deterministic Markdown.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when repository contradictions are detected.",
    )
    args = parser.parse_args(argv)
    result = run_audit(args.repo_root)
    if args.markdown:
        print(to_markdown(result), end="")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if args.strict and result["contradictions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
