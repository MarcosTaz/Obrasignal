"""Core engine for the deterministic ObraSignal international coverage audit."""
from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import Any

from international_country_codes import COUNTRY_ALIASES, COUNTRY_INDEX, ISO3_TO_COUNTRY

UNKNOWN = "UNKNOWN"

FILE_TOKENS = {
    "Austria": ("austria", "kerndaten", "at_kerndaten"),
    "Canada": ("canada", "canadabuys", "canada_buys", "ca_canadabuys"),
    "Chile": ("chile", "mercadopublico", "cl_mercadopublico"),
    "Colombia": ("colombia", "secop", "co_secop"),
    "Ecuador": ("ecuador", "sercop", "ec_sercop"),
    "Estonia": ("estonia", "rhr", "ee_rhr"),
    "France": ("france", "boamp", "decp"),
    "Germany": ("germany", "doe", "service_bund_de"),
    "Italy": ("italy", "anac", "it_anac"),
    "Latvia": ("latvia", "iub", "lv_iub"),
    "Lithuania": ("lithuania", "vpt", "lt_vpt"),
    "Netherlands": ("netherlands", "tenderned", "nl_tenderned"),
    "Paraguay": ("paraguay", "dncp", "py_dncp"),
    "Poland": ("poland", "bzp", "pl_bzp"),
    "South Africa": ("south_africa", "etenders", "za_etenders"),
    "South Korea": ("korea", "koneps", "kr_koneps"),
    "Switzerland": ("switzerland", "simap", "ch_simap"),
    "United Kingdom": ("uk", "find_tender", "uk_procurement"),
    "United States": ("us_sam", "samgov"),
    "Uruguay": ("uruguay", "arce", "uy_arce"),
}

# Only families with a concrete, active canonical source may be projected to
# member countries.  Strategic family membership alone is not executable proof.
SHARED_FAMILY_SOURCE = {"TED_EFORMS": "TED"}


def _safe_import(name: str):
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def _canonical_country(value: str) -> str:
    value = str(value or "").strip()
    return COUNTRY_ALIASES.get(value, ISO3_TO_COUNTRY.get(value.upper(), value))


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _segments(value: str) -> tuple[str, ...]:
    return tuple(part for part in _slug(value).split("_") if part)


def _matches_token(path: Path, token: str) -> bool:
    """Match short ISO tokens as path segments, never arbitrary substrings."""
    token = _slug(token)
    if not token:
        return False
    blob = _slug(str(path.with_suffix("")))
    if len(token) <= 3:
        return token in _segments(blob)
    return token in blob


def _is_test_file(path: str | Path) -> bool:
    path = Path(path)
    return "tests" in path.parts or path.name.startswith("test_")


def _repo_files(repo_root: Path) -> tuple[Path, ...]:
    ignored = {".git", ".pytest_cache", "__pycache__", "node_modules", ".mypy_cache"}
    files = []
    for path in repo_root.rglob("*"):
        if path.is_file() and not any(part in ignored for part in path.parts):
            files.append(path.relative_to(repo_root))
    return tuple(sorted(files, key=str))


def _matched_files(files, tokens, *, suffix=None, contains=None):
    matches = []
    for path in files:
        text = str(path)
        if suffix and not text.endswith(suffix):
            continue
        if contains and contains.lower() not in text.lower():
            continue
        if any(_matches_token(path, token) for token in tokens):
            matches.append(text)
    return tuple(sorted(set(matches)))


def _market_rows():
    registry = _safe_import("market_scope_registry")
    if not registry:
        return {}, ["market_scope_registry:import_failed"], {}
    rows = {}
    contradictions = []
    origins = {}
    for attr in ("_BUILD", "_SHARED", "_HOLD", "_REMOVE"):
        for raw_country, scope in dict(getattr(registry, attr, {}) or {}).items():
            country = _canonical_country(raw_country)
            if country in rows and origins[country] != raw_country:
                contradictions.append(
                    f"country_alias_duplicate:{country}:{origins[country]},{raw_country}"
                )
            origins[country] = raw_country
            rows[country] = {
                "status": getattr(scope, "status", attr.strip("_")),
                "reason": getattr(scope, "reason", ""),
                "infrastructure": getattr(scope, "infrastructure", ""),
                "priority": getattr(scope, "priority", None),
                "reopen_condition": getattr(scope, "reopen_condition", ""),
            }
    family_by_country = {}
    for family_id, members in dict(getattr(registry, "SHARED_FAMILIES", {}) or {}).items():
        for country in members:
            family_by_country[_canonical_country(country)] = str(family_id)
    return rows, contradictions, family_by_country


def _source_rows():
    registry = _safe_import("source_registry")
    if not registry:
        return {}
    return {str(k): dict(v) for k, v in dict(getattr(registry, "SOURCES", {}) or {}).items()}


def _code_family_rows():
    registry = _safe_import("shared_source_families")
    if not registry:
        return {}, ["shared_source_families:import_failed"]
    families = {}
    for family in dict(getattr(registry, "FAMILIES", {}) or {}).values():
        for member in getattr(family, "members", ()) or ():
            families[str(member)] = getattr(family, "family_id", "")
    violations = []
    audit_fn = getattr(registry, "audit_shared_families", None)
    if callable(audit_fn):
        violations.extend(f"shared_family:{item}" for item in audit_fn())
    return families, violations


def _aggregate(values, *, positive):
    clean = [str(v or "").strip().upper() for v in values if str(v or "").strip()]
    if not clean:
        return UNKNOWN
    if any(v in {"RED", "BLOCKED"} for v in clean):
        return "RED"
    if any(v in {"YELLOW", "CREDENTIAL_REQUIRED", "UNKNOWN"} for v in clean):
        return "YELLOW"
    if all(v == positive for v in clean):
        return positive
    return ",".join(sorted(set(clean)))


def _repo_evidence(country, iso2, iso3, source_names, files):
    tokens = {_slug(country), iso2.lower(), iso3.lower()}
    tokens.update(FILE_TOKENS.get(country, ()))
    tokens.update(name.lower() for name in source_names)
    tokens = tuple(sorted(t for t in tokens if t and t != "unknown"))

    python_matches = _matched_files(files, tokens, suffix=".py")
    tests = tuple(path for path in python_matches if _is_test_file(path))
    code = tuple(path for path in python_matches if not _is_test_file(path))
    runtime = tuple(
        path for path in code
        if path.endswith("_runtime.py") or "/runtime/" in path or path.endswith("/runtime.py")
    )
    evidence = _matched_files(files, tokens, suffix=".md", contains="EVIDENCE")
    workflows = tuple(
        sorted(
            {
                str(path)
                for path in files
                if str(path).startswith(".github/workflows/")
                and str(path).endswith((".yml", ".yaml"))
                and any(_matches_token(path, token) for token in tokens)
            }
        )
    )
    return {
        "code": code,
        "tests": tests,
        "runtime": runtime,
        "evidence": evidence,
        "workflows": workflows,
    }


def _source_is_production(meta):
    return (
        str(meta.get("status") or "").lower() == "active"
        and str(meta.get("legal_reuse") or "").upper() == "GREEN"
        and str(meta.get("machine_access") or "").upper() == "VERIFIED"
        and bool(meta.get("adapter"))
    )


def run_audit(repo_root: str | Path | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root or Path(__file__).resolve().parent)
    files = _repo_files(repo_root)
    markets, contradictions, market_shared_family = _market_rows()
    sources = _source_rows()
    code_families, family_violations = _code_family_rows()
    contradictions.extend(family_violations)
    missing = []

    source_by_country = {}
    source_ids = {}
    for name, meta in sources.items():
        country = _canonical_country(str(meta.get("country") or ""))
        source_by_country.setdefault(country, []).append((name, meta))
        source_id = str(meta.get("source_id") or "")
        if source_id and source_id in source_ids:
            contradictions.append(
                f"duplicate_source_id:{source_id}:{source_ids[source_id]},{name}"
            )
        if source_id:
            source_ids[source_id] = name
        if meta.get("status") in {"ready", "active"} and not meta.get("adapter"):
            contradictions.append(f"{name}:ready_or_active_without_adapter")
        if (
            meta.get("status") == "planned"
            and meta.get("adapter")
            and meta.get("machine_access") == "CREDENTIAL_REQUIRED"
        ):
            missing.append(f"{name}:planned_source_has_code_claim_but_is_credential_gated")

    countries = set(markets)
    countries.update(c for c in source_by_country if c and c != "European Union")
    rows = []

    for country in sorted(countries):
        iso2, iso3 = COUNTRY_INDEX.get(country, ("", ""))
        market = markets.get(country, {})
        status = str(market.get("status") or "UNSCOPED")
        actual_sources = sorted(source_by_country.get(country, []), key=lambda item: item[0])

        shared_market_family = market_shared_family.get(country, "")
        shared_source_name = SHARED_FAMILY_SOURCE.get(shared_market_family)
        effective_sources = list(actual_sources)
        if shared_source_name and shared_source_name in sources:
            if all(name != shared_source_name for name, _ in effective_sources):
                effective_sources.append((shared_source_name, sources[shared_source_name]))
        effective_sources.sort(key=lambda item: item[0])

        source_names = [name for name, _ in effective_sources]
        source_meta = [meta for _, meta in effective_sources]
        signal_types = sorted(
            {str(signal) for meta in source_meta for signal in meta.get("signal_types", ())}
        )
        rights = _aggregate(
            [meta.get("legal_reuse", "") for meta in source_meta], positive="GREEN"
        )
        machine_access = _aggregate(
            [meta.get("machine_access", "") for meta in source_meta], positive="VERIFIED"
        )
        evidence = _repo_evidence(country, iso2, iso3, source_names, files)

        shared_production = bool(
            shared_source_name
            and shared_source_name in sources
            and _source_is_production(sources[shared_source_name])
        )
        production_code_claim = any(
            meta.get("adapter") and meta.get("status") in {"active", "ready"}
            for _, meta in actual_sources
        )
        implemented = bool(evidence["code"] or production_code_claim or shared_production)
        tested = bool(evidence["tests"])
        runtime_wired = bool(
            evidence["runtime"]
            or any(meta.get("status") == "active" for _, meta in actual_sources)
            or shared_production
        )
        live_validated = bool(
            evidence["evidence"]
            or evidence["workflows"]
            or any(meta.get("status") == "active" for meta in source_meta)
        )
        production_path = any(_source_is_production(meta) for meta in source_meta)
        credential_gated = any(
            str(meta.get("machine_access") or "").upper() == "CREDENTIAL_REQUIRED"
            or str(meta.get("status") or "").lower() in {"planned", "opt_in"}
            for _, meta in actual_sources
        )
        gated = credential_gated or not production_path

        gaps = []
        if not iso2 or not iso3:
            gaps.append("ISO_CODE_MISSING")
            contradictions.append(f"{country}:missing_iso_code")
        if status in {"BUILD", "SHARED"} and not actual_sources and not shared_production:
            gaps.append("MARKET_SCOPED_WITHOUT_EXECUTABLE_SOURCE")
            missing.append(f"{country}:market_scoped_without_executable_source")
        if actual_sources and status == "UNSCOPED":
            gaps.append("SOURCE_WITHOUT_MARKET_SCOPE")
            contradictions.append(
                f"{country}:source_without_market_scope:"
                + ",".join(name for name, _ in actual_sources)
            )
        if implemented and not tested:
            gaps.append("IMPLEMENTED_WITHOUT_MATCHED_TEST_FILE")
            missing.append(f"{country}:implemented_without_matched_test")
        if implemented and not runtime_wired:
            gaps.append("IMPLEMENTED_WITHOUT_MATCHED_RUNTIME_WIRING")
            missing.append(f"{country}:implemented_without_matched_runtime")
        if credential_gated:
            gaps.append("CREDENTIAL_OR_OPT_IN_GATE")
        if status in {"BUILD", "SHARED"} and not live_validated:
            gaps.append("NO_REPO_LIVE_VALIDATION_EVIDENCE")
        if source_meta and rights != "GREEN":
            gaps.append(f"RIGHTS_{rights}")
        if source_meta and machine_access != "VERIFIED":
            gaps.append(f"MACHINE_ACCESS_{machine_access}")

        family_memberships = sorted(
            set(
                ([shared_market_family] if shared_market_family else [])
                + [code_families.get(name, "") for name, _ in effective_sources]
            )
            - {""}
        )
        rows.append(
            {
                "COUNTRY": country,
                "ISO2": iso2 or UNKNOWN,
                "ISO3": iso3 or UNKNOWN,
                "MARKET_CLASSIFICATION": status,
                "SOURCES": source_names,
                "SOURCE_FAMILIES": family_memberships,
                "SIGNAL_TYPES": signal_types,
                "CONSTRUCTION_COVERAGE": UNKNOWN,
                "PROCUREMENT_PLAN": "PROCUREMENT_PLAN" in signal_types,
                "TENDER": "TENDER" in signal_types,
                "AWARD": "AWARD" in signal_types,
                "CONTRACT": "CONTRACT" in signal_types,
                "MACHINE_ACCESS": machine_access,
                "RIGHTS": rights,
                "IMPLEMENTED": implemented,
                "TESTED": tested,
                "LIVE_VALIDATED": live_validated,
                "RUNTIME_WIRED": runtime_wired,
                "PRODUCTION_PATH": production_path,
                "GATED": gated,
                "PR": UNKNOWN,
                "KNOWN_GAPS": sorted(set(gaps)),
                "PROVENANCE": {
                    "market_registry": bool(market),
                    "source_registry": [name for name, _ in actual_sources],
                    "shared_market_family": shared_market_family or None,
                    "shared_source": shared_source_name if shared_production else None,
                    "matched_code_files": list(evidence["code"]),
                    "matched_test_files": list(evidence["tests"]),
                    "matched_runtime_files": list(evidence["runtime"]),
                    "matched_evidence_docs": list(evidence["evidence"]),
                    "matched_live_workflows": list(evidence["workflows"]),
                },
            }
        )

    rows.sort(key=lambda row: (row["ISO3"], row["COUNTRY"]))
    contradictions = sorted(set(contradictions))
    missing = sorted(set(missing))
    summary = {
        "country_count": len(rows),
        "source_count": len(sources),
        "build_markets": sum(r["MARKET_CLASSIFICATION"] == "BUILD" for r in rows),
        "shared_markets": sum(r["MARKET_CLASSIFICATION"] == "SHARED" for r in rows),
        "hold_markets": sum(r["MARKET_CLASSIFICATION"] == "HOLD" for r in rows),
        "implemented_countries": sum(r["IMPLEMENTED"] for r in rows),
        "tested_countries": sum(r["TESTED"] for r in rows),
        "runtime_wired_countries": sum(r["RUNTIME_WIRED"] for r in rows),
        "production_path_countries": sum(r["PRODUCTION_PATH"] for r in rows),
        "gated_countries": sum(r["GATED"] for r in rows),
        "contradiction_count": len(contradictions),
        "missing_integration_count": len(missing),
    }
    return {
        "audit_contract": "OBRASIGNAL_REPOSITORY_STATE_INTERNATIONAL_COVERAGE_AUDIT_V1",
        "repo_root": str(repo_root),
        "summary": summary,
        "countries": rows,
        "contradictions": contradictions,
        "missing_integrations": missing,
    }


def to_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# ObraSignal International Coverage Audit",
        "",
        "Generated from repository state only; chat memory and external research are excluded.",
        "",
        "## Summary",
        "",
    ]
    lines.extend(f"- **{key}**: {value}" for key, value in audit["summary"].items())
    lines.extend(["", "## Countries", ""])
    lines.append(
        "| Country | ISO2 | ISO3 | Market | Sources | Signals | Implemented | Tested | Live | Runtime | Production | Gated | Gaps |"
    )
    lines.append("|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|")
    for row in audit["countries"]:
        lines.append(
            "| {COUNTRY} | {ISO2} | {ISO3} | {MARKET_CLASSIFICATION} | {sources} | "
            "{signals} | {IMPLEMENTED} | {TESTED} | {LIVE_VALIDATED} | "
            "{RUNTIME_WIRED} | {PRODUCTION_PATH} | {GATED} | {gaps} |".format(
                **row,
                sources=", ".join(row["SOURCES"]) or "-",
                signals=", ".join(row["SIGNAL_TYPES"]) or "-",
                gaps=", ".join(row["KNOWN_GAPS"]) or "-",
            )
        )
    lines.extend(["", "## Contradictions", ""])
    lines.extend(f"- {item}" for item in audit["contradictions"] or ["None"])
    lines.extend(["", "## Missing integrations", ""])
    lines.extend(f"- {item}" for item in audit["missing_integrations"] or ["None"])
    return "\n".join(lines) + "\n"
