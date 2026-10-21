"""Canonical CLI/public interface for the ObraSignal international coverage audit.

The internal core gathers repository evidence. This public boundary applies the
strict path-token, final gating, repository-provenance and exact-head candidate
state policy so callers have one canonical result.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import international_coverage_audit_core as _core
from international_audit_provenance import enrich_audit
from international_portfolio_states import apply_state_contract


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
    result = enrich_audit(result, root)
    # This final pass deliberately overwrites the core's heuristic TESTED/LIVE
    # booleans. A workflow or evidence document is provenance, not successful
    # current exact-head execution proof.
    return apply_state_contract(result, root)


def to_markdown(result):
    lines = [
        "# ObraSignal International Coverage Audit",
        "",
        "Generated from repository state and explicit exact-head candidate evidence only; chat memory and external research are excluded.",
        "",
        "## Summary",
        "",
    ]
    lines.extend(f"- **{key}**: {value}" for key, value in result["summary"].items())

    candidate = result.get("candidate_evidence", {})
    lines.extend(["", "## Exact-head candidate evidence policy", ""])
    lines.append(f"- canonical main evidence SHA: `{candidate.get('canonical_main_sha') or 'UNKNOWN'}`")
    lines.append(f"- candidate count: {candidate.get('candidate_count', 0)}")
    lines.append(f"- policy: {candidate.get('proof_policy', '-')}")
    rejected = candidate.get("rejected_proofs", []) or []
    lines.append(f"- rejected stale/mismatched proofs: {len(rejected)}")
    lines.extend(f"  - {item}" for item in rejected)

    lines.extend(["", "## Source portfolio", ""])
    lines.append(
        "| Source | Country | Registered | Implemented | Tested | Live | Live result | Runtime | Production active | Ready | Planned | Rights gate | Machine gate | Credential gate | Completeness gate | Tech lab | Superseded | PR |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in result.get("source_portfolio", []):
        prs = ", ".join(f"#{value}" for value in row.get("CANDIDATE_PRS", [])) or "-"
        lines.append(
            f"| {row['SOURCE']} | {row['COUNTRY']} | {row['REGISTERED']} | {row['IMPLEMENTED']} | "
            f"{row['TESTED']} | {row['LIVE_VALIDATED']} | {row.get('LIVE_RESULT_KIND') or '-'} | "
            f"{row['RUNTIME_WIRED']} | {row['PRODUCTION_ACTIVE']} | {row['READY']} | {row['PLANNED']} | "
            f"{row['GATED_RIGHTS']} | {row['GATED_MACHINE_ACCESS']} | {row['GATED_CREDENTIAL']} | "
            f"{row['GATED_COMPLETENESS']} | {row['TECH_LAB']} | {row['SUPERSEDED']} | {prs} |"
        )

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
        "| Country | ISO2 | ISO3 | Market | Sources | Signals | Research only | PR | Registered | Implemented | Tested | Live | Runtime | Production active | Ready | Planned | Rights gate | Machine gate | Credential gate | Completeness gate | Tech lab | Gaps |"
    )
    lines.append("|---|---|---|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in result["countries"]:
        lines.append(
            "| {COUNTRY} | {ISO2} | {ISO3} | {MARKET_CLASSIFICATION} | {sources} | "
            "{signals} | {RESEARCH_ONLY} | {prs} | {REGISTERED} | {IMPLEMENTED} | {TESTED} | "
            "{LIVE_VALIDATED} | {RUNTIME_WIRED} | {PRODUCTION_ACTIVE} | {READY} | {PLANNED} | "
            "{GATED_RIGHTS} | {GATED_MACHINE_ACCESS} | {GATED_CREDENTIAL} | {GATED_COMPLETENESS} | "
            "{TECH_LAB} | {gaps} |".format(
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
    lines.extend(["", "## Supersession evidence", ""])
    supersession = result.get("candidate_evidence", {}).get("supersession", []) or []
    if supersession:
        for item in supersession:
            lines.append(
                f"- PR #{item.get('pr')}: {item.get('state', 'UNKNOWN')} by #{item.get('by_pr', '?')} — {item.get('scope', '')}"
            )
    else:
        lines.append("- None")
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
