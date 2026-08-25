"""Exact-head state contract for the canonical international coverage auditor.

This module does not query GitHub and does not mutate source/runtime state. It
combines canonical registry truth with an explicit candidate-evidence snapshot.
Candidate TESTED/LIVE_VALIDATED claims are accepted only when the recorded proof
head exactly equals the candidate head. A workflow file, evidence document or
historical successful run is never sufficient by itself.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_SHA = re.compile(r"^[0-9a-f]{40}$")
_EVIDENCE_FILE = "international_candidate_evidence.json"


def _clean_sha(value: Any) -> str:
    value = str(value or "").strip().lower()
    return value if _SHA.fullmatch(value) else ""


def load_candidate_evidence(repo_root: str | Path) -> dict:
    path = Path(repo_root) / _EVIDENCE_FILE
    if not path.exists():
        return {"schema_version": 1, "canonical_main_sha": "", "candidates": [], "supersession": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if int(data.get("schema_version", 0)) != 1:
        raise ValueError("unsupported international candidate evidence schema")
    if data.get("canonical_main_sha") and not _clean_sha(data.get("canonical_main_sha")):
        raise ValueError("invalid canonical_main_sha in international candidate evidence")
    return data


def _canonical_source_rows(result: dict) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for country in result.get("countries", []):
        registered = set(country.get("PROVENANCE", {}).get("source_registry", []) or [])
        effective = set(country.get("SOURCES", []) or [])
        for source in sorted(registered | effective):
            row = rows.setdefault(
                source,
                {
                    "SOURCE": source,
                    "COUNTRY": country.get("COUNTRY", "UNKNOWN"),
                    "REGISTERED": source in registered,
                    "IMPLEMENTED": False,
                    "TESTED": False,
                    "LIVE_VALIDATED": False,
                    "LIVE_RESULT_KIND": None,
                    "RUNTIME_WIRED": False,
                    "PRODUCTION_ACTIVE": False,
                    "READY": False,
                    "PLANNED": False,
                    "GATED_RIGHTS": False,
                    "GATED_MACHINE_ACCESS": False,
                    "GATED_CREDENTIAL": False,
                    "GATED_COMPLETENESS": False,
                    "TECH_LAB": False,
                    "SUPERSEDED": False,
                    "CANDIDATE_PRS": [],
                    "CANDIDATE_HEADS": [],
                    "QUALITY_RUNS": [],
                    "LIVE_RUNS": [],
                    "STATE_ORIGIN": ["canonical_repository"],
                },
            )
            # The country core is structural repository evidence, not successful
            # exact-head CI proof. It may establish implementation/runtime shape.
            row["IMPLEMENTED"] = row["IMPLEMENTED"] or bool(country.get("IMPLEMENTED"))
            row["RUNTIME_WIRED"] = row["RUNTIME_WIRED"] or bool(country.get("RUNTIME_WIRED"))
            row["PRODUCTION_ACTIVE"] = row["PRODUCTION_ACTIVE"] or bool(country.get("PRODUCTION_PATH"))
            row["GATED_RIGHTS"] = row["GATED_RIGHTS"] or str(country.get("RIGHTS", "")).upper() not in {"", "GREEN", "UNKNOWN"}
            machine = str(country.get("MACHINE_ACCESS", "")).upper()
            row["GATED_CREDENTIAL"] = row["GATED_CREDENTIAL"] or machine == "CREDENTIAL_REQUIRED"
            row["GATED_MACHINE_ACCESS"] = row["GATED_MACHINE_ACCESS"] or machine not in {"", "UNKNOWN", "VERIFIED", "CREDENTIAL_REQUIRED"}
    return rows


def _source_registry_meta() -> dict[str, dict]:
    try:
        import source_registry
    except Exception:
        return {}
    return {str(k): dict(v) for k, v in dict(getattr(source_registry, "SOURCES", {}) or {}).items()}


def _apply_registry_status(rows: dict[str, dict]) -> None:
    for source, meta in _source_registry_meta().items():
        row = rows.get(source)
        if not row:
            # A registry source may be outside the country universe projected by
            # the core; retain it rather than silently dropping canonical truth.
            row = rows.setdefault(
                source,
                {
                    "SOURCE": source,
                    "COUNTRY": str(meta.get("country") or "UNKNOWN"),
                    "REGISTERED": True,
                    "IMPLEMENTED": False,
                    "TESTED": False,
                    "LIVE_VALIDATED": False,
                    "LIVE_RESULT_KIND": None,
                    "RUNTIME_WIRED": False,
                    "PRODUCTION_ACTIVE": False,
                    "READY": False,
                    "PLANNED": False,
                    "GATED_RIGHTS": False,
                    "GATED_MACHINE_ACCESS": False,
                    "GATED_CREDENTIAL": False,
                    "GATED_COMPLETENESS": False,
                    "TECH_LAB": False,
                    "SUPERSEDED": False,
                    "CANDIDATE_PRS": [],
                    "CANDIDATE_HEADS": [],
                    "QUALITY_RUNS": [],
                    "LIVE_RUNS": [],
                    "STATE_ORIGIN": ["canonical_registry"],
                },
            )
        row["REGISTERED"] = True
        status = str(meta.get("status") or "").lower()
        row["READY"] = status == "ready"
        row["PLANNED"] = status == "planned"
        row["PRODUCTION_ACTIVE"] = (
            status == "active"
            and str(meta.get("legal_reuse") or "").upper() == "GREEN"
            and str(meta.get("machine_access") or "").upper() == "VERIFIED"
            and bool(meta.get("adapter"))
        )
        row["IMPLEMENTED"] = row["IMPLEMENTED"] or bool(meta.get("adapter"))
        row["RUNTIME_WIRED"] = row["RUNTIME_WIRED"] or status == "active"
        rights = str(meta.get("legal_reuse") or "").upper()
        machine = str(meta.get("machine_access") or "").upper()
        row["GATED_RIGHTS"] = row["GATED_RIGHTS"] or rights not in {"", "GREEN"}
        row["GATED_CREDENTIAL"] = row["GATED_CREDENTIAL"] or machine == "CREDENTIAL_REQUIRED"
        row["GATED_MACHINE_ACCESS"] = row["GATED_MACHINE_ACCESS"] or machine not in {"", "VERIFIED", "CREDENTIAL_REQUIRED"}


def _candidate_quality_exact(candidate: dict) -> bool:
    head = _clean_sha(candidate.get("head"))
    quality = dict(candidate.get("quality") or {})
    return bool(
        head
        and _clean_sha(quality.get("head")) == head
        and str(quality.get("status") or "").upper() == "SUCCESS"
    )


def _live_exact(candidate: dict, source: dict) -> bool:
    head = _clean_sha(candidate.get("head"))
    live = dict(source.get("live") or {})
    return bool(
        head
        and _clean_sha(live.get("head")) == head
        and str(live.get("status") or "").upper() == "SUCCESS"
    )


def _candidate_row(rows: dict[str, dict], source: dict) -> dict:
    key = str(source.get("source") or "").strip()
    if not key:
        raise ValueError("candidate source missing source key")
    return rows.setdefault(
        key,
        {
            "SOURCE": key,
            "COUNTRY": str(source.get("country") or "UNKNOWN"),
            "REGISTERED": False,
            "IMPLEMENTED": False,
            "TESTED": False,
            "LIVE_VALIDATED": False,
            "LIVE_RESULT_KIND": None,
            "RUNTIME_WIRED": False,
            "PRODUCTION_ACTIVE": False,
            "READY": False,
            "PLANNED": False,
            "GATED_RIGHTS": False,
            "GATED_MACHINE_ACCESS": False,
            "GATED_CREDENTIAL": False,
            "GATED_COMPLETENESS": False,
            "TECH_LAB": False,
            "SUPERSEDED": False,
            "CANDIDATE_PRS": [],
            "CANDIDATE_HEADS": [],
            "QUALITY_RUNS": [],
            "LIVE_RUNS": [],
            "STATE_ORIGIN": [],
        },
    )


def apply_state_contract(result: dict, repo_root: str | Path, *, evidence: dict | None = None) -> dict:
    evidence = evidence if evidence is not None else load_candidate_evidence(repo_root)
    rows = _canonical_source_rows(result)
    _apply_registry_status(rows)

    manifest_main = _clean_sha(evidence.get("canonical_main_sha"))
    rejected_proofs = []
    for candidate in evidence.get("candidates", []) or []:
        head = _clean_sha(candidate.get("head"))
        base_main = _clean_sha(candidate.get("base_main_sha"))
        quality_exact = _candidate_quality_exact(candidate)
        pr = int(candidate.get("pr")) if str(candidate.get("pr", "")).isdigit() else None
        candidate_current_main = bool(manifest_main and base_main == manifest_main)

        if not head:
            rejected_proofs.append(f"pr:{pr or 'unknown'}:invalid_candidate_head")
            continue
        if not candidate_current_main:
            rejected_proofs.append(f"pr:{pr or 'unknown'}:stale_main:{base_main or 'invalid'}")

        quality = dict(candidate.get("quality") or {})
        if quality and not quality_exact:
            rejected_proofs.append(f"pr:{pr or 'unknown'}:quality_head_mismatch_or_failure")

        for source in candidate.get("sources", []) or []:
            row = _candidate_row(rows, source)
            row["COUNTRY"] = str(source.get("country") or row["COUNTRY"])
            if pr is not None and pr not in row["CANDIDATE_PRS"]:
                row["CANDIDATE_PRS"].append(pr)
            if head not in row["CANDIDATE_HEADS"]:
                row["CANDIDATE_HEADS"].append(head)
            if "current_main_candidate" not in row["STATE_ORIGIN"]:
                row["STATE_ORIGIN"].append("current_main_candidate")

            row["IMPLEMENTED"] = row["IMPLEMENTED"] or bool(source.get("implemented"))
            # TESTED is an execution claim for candidates, so it requires both
            # source intent and a successful quality proof on the same exact head.
            row["TESTED"] = row["TESTED"] or bool(source.get("tested") and quality_exact and candidate_current_main)
            if quality_exact and candidate_current_main and quality.get("run_id") is not None:
                run_id = int(quality["run_id"])
                if run_id not in row["QUALITY_RUNS"]:
                    row["QUALITY_RUNS"].append(run_id)

            live = dict(source.get("live") or {})
            live_exact = _live_exact(candidate, source) and candidate_current_main
            if live and not live_exact:
                rejected_proofs.append(f"pr:{pr or 'unknown'}:{row['SOURCE']}:live_head_mismatch_or_failure")
            if live_exact:
                row["LIVE_VALIDATED"] = True
                row["LIVE_RESULT_KIND"] = str(live.get("result_kind") or "OBSERVED")
                if live.get("run_id") is not None:
                    run_id = int(live["run_id"])
                    if run_id not in row["LIVE_RUNS"]:
                        row["LIVE_RUNS"].append(run_id)

            row["RUNTIME_WIRED"] = row["RUNTIME_WIRED"] or bool(source.get("runtime_wired"))
            row["READY"] = row["READY"] or bool(source.get("ready"))
            row["PLANNED"] = row["PLANNED"] or bool(source.get("planned"))
            row["GATED_RIGHTS"] = row["GATED_RIGHTS"] or bool(source.get("gated_rights"))
            row["GATED_MACHINE_ACCESS"] = row["GATED_MACHINE_ACCESS"] or bool(source.get("gated_machine_access"))
            row["GATED_CREDENTIAL"] = row["GATED_CREDENTIAL"] or bool(source.get("gated_credential"))
            row["GATED_COMPLETENESS"] = row["GATED_COMPLETENESS"] or bool(source.get("gated_completeness"))
            row["TECH_LAB"] = row["TECH_LAB"] or bool(source.get("tech_lab"))

    supersession = list(evidence.get("supersession", []) or [])
    # PR-level supersession is reported separately; source rows are not marked
    # superseded unless an evidence entry explicitly names a source.
    for item in supersession:
        source = str(item.get("source") or "").strip()
        if source and source in rows:
            rows[source]["SUPERSEDED"] = True

    portfolio = []
    for source in sorted(rows):
        row = rows[source]
        row["CANDIDATE_PRS"] = sorted(set(row["CANDIDATE_PRS"]))
        row["CANDIDATE_HEADS"] = sorted(set(row["CANDIDATE_HEADS"]))
        row["QUALITY_RUNS"] = sorted(set(row["QUALITY_RUNS"]))
        row["LIVE_RUNS"] = sorted(set(row["LIVE_RUNS"]))
        row["STATE_ORIGIN"] = sorted(set(row["STATE_ORIGIN"]))
        portfolio.append(row)

    by_country: dict[str, list[dict]] = {}
    for row in portfolio:
        by_country.setdefault(row["COUNTRY"], []).append(row)
    for country in result.get("countries", []):
        source_rows = by_country.get(country.get("COUNTRY"), [])
        # Replace the old heuristic live/tested booleans with exact-head-aware
        # source state. Presence of workflow/docs alone cannot make these true.
        country["REGISTERED"] = any(row["REGISTERED"] for row in source_rows)
        country["IMPLEMENTED"] = any(row["IMPLEMENTED"] for row in source_rows) or bool(country.get("IMPLEMENTED"))
        country["TESTED"] = any(row["TESTED"] for row in source_rows)
        country["LIVE_VALIDATED"] = any(row["LIVE_VALIDATED"] for row in source_rows)
        country["RUNTIME_WIRED"] = any(row["RUNTIME_WIRED"] for row in source_rows) or bool(country.get("RUNTIME_WIRED"))
        country["PRODUCTION_ACTIVE"] = any(row["PRODUCTION_ACTIVE"] for row in source_rows)
        country["READY"] = any(row["READY"] for row in source_rows)
        country["PLANNED"] = any(row["PLANNED"] for row in source_rows)
        country["GATED_RIGHTS"] = any(row["GATED_RIGHTS"] for row in source_rows)
        country["GATED_MACHINE_ACCESS"] = any(row["GATED_MACHINE_ACCESS"] for row in source_rows)
        country["GATED_CREDENTIAL"] = any(row["GATED_CREDENTIAL"] for row in source_rows)
        country["GATED_COMPLETENESS"] = any(row["GATED_COMPLETENESS"] for row in source_rows)
        country["TECH_LAB"] = any(row["TECH_LAB"] for row in source_rows)
        country["SUPERSEDED"] = any(row["SUPERSEDED"] for row in source_rows)
        country["SOURCE_STATE_ROWS"] = [row["SOURCE"] for row in source_rows]

    result["source_portfolio"] = portfolio
    result["candidate_evidence"] = {
        "schema_version": evidence.get("schema_version"),
        "canonical_main_sha": manifest_main or None,
        "candidate_count": len(evidence.get("candidates", []) or []),
        "proof_policy": "candidate proof head must equal candidate head and candidate base_main_sha must equal manifest canonical_main_sha",
        "rejected_proofs": sorted(set(rejected_proofs)),
        "supersession": supersession,
    }
    summary = result.setdefault("summary", {})
    for key in (
        "REGISTERED", "IMPLEMENTED", "TESTED", "LIVE_VALIDATED", "RUNTIME_WIRED",
        "PRODUCTION_ACTIVE", "READY", "PLANNED", "GATED_RIGHTS",
        "GATED_MACHINE_ACCESS", "GATED_CREDENTIAL", "GATED_COMPLETENESS",
        "TECH_LAB", "SUPERSEDED",
    ):
        summary[f"source_{key.lower()}"] = sum(1 for row in portfolio if row[key])
    return result
