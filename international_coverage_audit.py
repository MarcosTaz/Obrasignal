"""Canonical CLI/public interface for the ObraSignal international coverage audit.

The internal core gathers repository evidence. This public boundary applies the
strict path-token, final gating and repository-provenance policy so callers have
one canonical result.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import international_coverage_audit_core as _core
from international_audit_provenance import enrich_audit


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _exact_path_token_match(path: Path, token: str) -> bool:
    """Match token segments contiguously; never match inside another word."""
    wanted = tuple(part for part in _slug(token).split("_") if part)
    actual = tuple(part for part in _slug(str(path.with_suffix(""))).split("_") if part)
    if not wanted or len(wanted) > len(actual):
        return False
    width = len(wanted)
    return any(actual[index : index + width] == wanted for index in range(len(actual) - width + 1))


_core._matches_token = _exact_path_token_match


def run_audit(repo_root=None):
    root = Path(repo_root or Path(__file__).resolve().parent)
    result = _core.run_audit(root)
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
    return enrich_audit(result, root)


def to_markdown(result):
    lines = [
        "# ObraSignal International Coverage Audit",
        "",
        "Generated from repository state only; chat memory and external research are excluded.",
        "",
        "## Summary",
        "",
    ]
    lines.extend(f"- **{key}**: {value}" for key, value in result["summary"].items())
    lines.extend(["", "## Capability states", ""])
    if result.get("capabilities"):
        lines.append("| Capability | State | Health | Owner |")
        lines.append("|---|---|---|---|")
        for item in result["capabilities"]:
            lines.append(
                f"| {item['name']} | {item['state']} | {item['health']} | {item['owner_domain']} |"
            )
    else:
        lines.append("- None proven")

    lines.extend(["", "## Countries", ""])
    lines.append(
        "| Country | ISO2 | ISO3 | Market | Sources | Signals | Research only | PR | Implemented | Tested | Live | Runtime | Production | Gated | Gaps |"
    )
    lines.append("|---|---|---|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|")
    for row in result["countries"]:
        lines.append(
            "| {COUNTRY} | {ISO2} | {ISO3} | {MARKET_CLASSIFICATION} | {sources} | "
            "{signals} | {RESEARCH_ONLY} | {prs} | {IMPLEMENTED} | {TESTED} | "
            "{LIVE_VALIDATED} | {RUNTIME_WIRED} | {PRODUCTION_PATH} | {GATED} | {gaps} |".format(
                **row,
                sources=", ".join(row["SOURCES"]) or "-",
                signals=", ".join(row["SIGNAL_TYPES"]) or "-",
                prs=", ".join(f"#{value}" for value in row["PR"]) or "-",
                gaps=", ".join(row["KNOWN_GAPS"]) or "-",
            )
        )
    lines.extend(["", "## Research-only countries", ""])
    lines.extend(f"- {item}" for item in result.get("research_only_countries", []) or ["None"])
    lines.extend(["", "## Explicit PR references", ""])
    lines.extend(f"- #{item}" for item in result.get("explicit_pr_references", []) or ["None found in local git history"])
    lines.extend(["", "## Contradictions", ""])
    lines.extend(f"- {item}" for item in result["contradictions"] or ["None"])
    lines.extend(["", "## Missing integrations", ""])
    lines.extend(f"- {item}" for item in result["missing_integrations"] or ["None"])
    return "\n".join(lines) + "\n"


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
