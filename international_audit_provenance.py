"""Repository provenance helpers for the international coverage audit.

No network access is performed. PR references are derived only from local git
history when commit messages contain an explicit pull-request reference.
Research evidence is derived conservatively from bounded repository text files.
"""
from __future__ import annotations

import importlib
import re
import subprocess
from collections import defaultdict
from pathlib import Path

_PR_PATTERNS = (
    re.compile(r"\b(?:PR|pull request)\s*#(\d+)\b", re.IGNORECASE),
    re.compile(r"\(#(\d+)\)\s*$"),
)
_REGIONAL_RESEARCH_NAME = re.compile(r"(?:research|gate)", re.IGNORECASE)
_COUNTRY_EVIDENCE_NAME = re.compile(r"evidence", re.IGNORECASE)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _pr_numbers(text: str) -> tuple[int, ...]:
    values = set()
    for pattern in _PR_PATTERNS:
        values.update(int(value) for value in pattern.findall(text or ""))
    return tuple(sorted(values))


def build_git_pr_index(repo_root: str | Path) -> dict[str, tuple[int, ...]]:
    """Return file -> explicit PR references from local git history."""
    root = Path(repo_root)
    if not (root / ".git").exists():
        return {}
    try:
        proc = subprocess.run(
            [
                "git",
                "-c",
                "core.quotepath=false",
                "log",
                "--no-renames",
                "--format=%x1e%s%x1f%b",
                "--name-only",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=12,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if proc.returncode != 0:
        return {}

    index: dict[str, set[int]] = defaultdict(set)
    for block in proc.stdout.split("\x1e"):
        if not block.strip():
            continue
        header, *rest = block.splitlines()
        if "\x1f" in header:
            subject, body_head = header.split("\x1f", 1)
        else:
            subject, body_head = header, ""
        body_lines = []
        files = []
        for line in rest:
            stripped = line.strip()
            if not stripped:
                continue
            if "/" in stripped or "." in Path(stripped).name:
                files.append(stripped)
            else:
                body_lines.append(stripped)
        refs = _pr_numbers("\n".join([subject, body_head, *body_lines]))
        if not refs:
            continue
        for path in files:
            index[path].update(refs)
    return {path: tuple(sorted(refs)) for path, refs in sorted(index.items())}


def _contains_country(text: str, country: str) -> bool:
    """Match country language only; ISO3 codes are unsafe in prose (e.g. ARE)."""
    phrases = {country}
    if country == "Ukraine":
        phrases.add("Ukrainian")
    if country == "United Kingdom":
        phrases.update(("United Kingdom", "UK"))
    if country == "United States":
        phrases.update(("United States", "USA"))
    if country == "South Korea":
        phrases.update(("South Korea", "Korea", "KONEPS"))
    for phrase in phrases:
        pattern = rf"(?<![A-Za-z0-9]){re.escape(phrase)}(?![A-Za-z0-9])"
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _country_specific_filename(path: Path, country: str, iso3: str) -> bool:
    stem = _slug(path.stem)
    country_slug = _slug(country)
    if country_slug and len(country_slug) > 4 and country_slug in stem:
        return True
    segments = tuple(part for part in stem.split("_") if part)
    if iso3 and iso3 != "UNKNOWN" and iso3.lower() in segments:
        return True
    special = {
        "United Kingdom": ("uk", "find_tender"),
        "United States": ("us", "sam"),
        "South Korea": ("korea", "koneps"),
        "Dominican Republic": ("dominican",),
        "South Africa": ("south_africa", "za"),
        "Côte d’Ivoire": ("ivoire",),
    }
    return any(_slug(token) in stem for token in special.get(country, ()))


def research_docs_for_country(repo_root: str | Path, country: str, iso3: str) -> tuple[str, ...]:
    """Return only defensible country-specific research/evidence documents.

    Country evidence documents must identify the country in their filename.
    Regional RESEARCH/GATE documents may qualify by explicitly naming the country
    in bounded text. Broad scope/portfolio documents never qualify by themselves.
    """
    root = Path(repo_root)
    matches = []
    for path in sorted(root.rglob("*.md"), key=lambda value: str(value)):
        if any(part in {".git", "node_modules"} for part in path.parts):
            continue
        regional = bool(_REGIONAL_RESEARCH_NAME.search(path.name))
        evidence = bool(_COUNTRY_EVIDENCE_NAME.search(path.name))
        if not regional and not evidence:
            continue
        try:
            if path.stat().st_size > 512_000:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        filename_specific = _country_specific_filename(path, country, iso3)
        if evidence and filename_specific:
            matches.append(str(path.relative_to(root)))
            continue
        if regional and _contains_country(text, country):
            matches.append(str(path.relative_to(root)))
    return tuple(sorted(set(matches)))


def capability_snapshot() -> tuple[list[dict], list[str]]:
    """Read capability lifecycle state without mutating or promoting it."""
    try:
        registry = importlib.import_module("capability_registry")
    except Exception as exc:
        return [], [f"capability_registry:import_failed:{type(exc).__name__}"]

    rows = []
    for name, spec in sorted(dict(getattr(registry, "CAPABILITIES", {}) or {}).items()):
        rows.append(
            {
                "name": str(name),
                "state": str(getattr(spec, "state", "UNKNOWN")),
                "health": str(getattr(spec, "health", "UNKNOWN")),
                "owner_domain": str(getattr(spec, "owner_domain", "")),
                "dependencies": list(getattr(spec, "dependencies", ()) or ()),
                "feature_flag": getattr(spec, "feature_flag", None),
                "kill_switch_required": bool(getattr(spec, "kill_switch_required", False)),
            }
        )
    return rows, []


def enrich_audit(result: dict, repo_root: str | Path) -> dict:
    """Add research-only, capability and explicit PR provenance deterministically."""
    root = Path(repo_root)
    pr_index = build_git_pr_index(root)
    capability_rows, capability_errors = capability_snapshot()

    research_only = []
    all_prs = set()
    for row in result.get("countries", []):
        research_docs = research_docs_for_country(root, row["COUNTRY"], row["ISO3"])
        row["RESEARCH_EVIDENCE"] = list(research_docs)
        row["RESEARCH_ONLY"] = bool(research_docs) and not bool(row.get("IMPLEMENTED"))
        if row["RESEARCH_ONLY"]:
            research_only.append(row["COUNTRY"])

        provenance = row.get("PROVENANCE", {})
        paths = set(research_docs)
        for key in (
            "matched_code_files",
            "matched_test_files",
            "matched_runtime_files",
            "matched_evidence_docs",
            "matched_live_workflows",
        ):
            paths.update(provenance.get(key, []) or [])
        refs = sorted({pr for path in paths for pr in pr_index.get(path, ())})
        row["PR"] = refs
        all_prs.update(refs)

    capability_summary = {}
    for item in capability_rows:
        capability_summary[item["state"]] = capability_summary.get(item["state"], 0) + 1

    contradictions = set(result.get("contradictions", []))
    contradictions.update(capability_errors)
    result["contradictions"] = sorted(contradictions)
    result["summary"]["contradiction_count"] = len(result["contradictions"])
    result["summary"]["research_only_countries"] = len(research_only)
    result["summary"]["explicit_pr_reference_count"] = len(all_prs)
    result["capabilities"] = capability_rows
    result["capability_summary"] = dict(sorted(capability_summary.items()))
    result["research_only_countries"] = sorted(research_only)
    result["explicit_pr_references"] = sorted(all_prs)
    result["pr_provenance"] = {
        "mode": "local_git_history_explicit_references_only",
        "history_available": bool((root / ".git").exists()),
        "indexed_file_count": len(pr_index),
    }
    return result
