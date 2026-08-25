"""Repository-state international coverage auditor for ObraSignal.

This module audits what the repository can prove. It does not perform network I/O
and it deliberately does not promote a market/source just because research exists.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
from pathlib import Path
from typing import Any

UNKNOWN = "UNKNOWN"

COUNTRY_INDEX: dict[str, tuple[str, str]] = {
    "EU": ("EU", "EU"),
    "European Union": ("EU", "EU"),
    "Portugal": ("PT", "PRT"),
    "Spain": ("ES", "ESP"),
    "France": ("FR", "FRA"),
    "Germany": ("DE", "DEU"),
    "Italy": ("IT", "ITA"),
    "Switzerland": ("CH", "CHE"),
    "United Kingdom": ("GB", "GBR"),
    "Netherlands": ("NL", "NLD"),
    "Poland": ("PL", "POL"),
    "Brazil": ("BR", "BRA"),
    "Canada": ("CA", "CAN"),
    "United States": ("US", "USA"),
    "Colombia": ("CO", "COL"),
    "Chile": ("CL", "CHL"),
    "Austria": ("AT", "AUT"),
    "Belgium": ("BE", "BEL"),
    "Bulgaria": ("BG", "BGR"),
    "Croatia": ("HR", "HRV"),
    "Cyprus": ("CY", "CYP"),
    "Czech Republic": ("CZ", "CZE"),
    "Denmark": ("DK", "DNK"),
    "Estonia": ("EE", "EST"),
    "Finland": ("FI", "FIN"),
    "Greece": ("GR", "GRC"),
    "Hungary": ("HU", "HUN"),
    "Iceland": ("IS", "ISL"),
    "Ireland": ("IE", "IRL"),
    "Latvia": ("LV", "LVA"),
    "Liechtenstein": ("LI", "LIE"),
    "Lithuania": ("LT", "LTU"),
    "Luxembourg": ("LU", "LUX"),
    "Malta": ("MT", "MLT"),
    "Norway": ("NO", "NOR"),
    "Romania": ("RO", "ROU"),
    "Slovakia": ("SK", "SVK"),
    "Slovenia": ("SI", "SVN"),
    "Sweden": ("SE", "SWE"),
    "Dominican Republic": ("DO", "DOM"),
    "Ecuador": ("EC", "ECU"),
    "Guatemala": ("GT", "GTM"),
    "Honduras": ("HN", "HND"),
    "Paraguay": ("PY", "PRY"),
    "Peru": ("PE", "PER"),
    "South Africa": ("ZA", "ZAF"),
    "Uruguay": ("UY", "URY"),
    "Korea": ("KR", "KOR"),
    "South Korea": ("KR", "KOR"),
}

ISO3_TO_COUNTRY = {iso3: country for country, (_, iso3) in COUNTRY_INDEX.items()}
ISO3_TO_COUNTRY.update({"GBR": "United Kingdom", "USA": "United States", "KOR": "South Korea"})

COUNTRY_ALIASES = {
    "UK": "United Kingdom",
    "Great Britain": "United Kingdom",
    "United States of America": "United States",
    "USA": "United States",
    "Czechia": "Czech Republic",
    "KOR": "South Korea",
}

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
    "United States": ("us_sam", "samgov", "us_sam"),
    "Uruguay": ("uruguay", "arce", "uy_arce"),
}


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


def _file_blob(path: Path) -> str:
    return _slug(str(path.with_suffix("")))


def _matches_token(path: Path, token: str) -> bool:
    token = _slug(token)
    blob = _file_blob(path)
    if not token:
        return False
    if len(token) <= 2:
        parts = blob.split("_")
        return token in parts
    return token in blob


def _repo_files(repo_root: Path) -> tuple[Path, ...]:
    ignored = {".git", ".pytest_cache", "__pycache__", "node_modules", ".mypy_cache"}
    files = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored for part in path.parts):
            continue
        files.append(path.relative_to(repo_root))
    return tuple(sorted(files, key=lambda p: str(p)))


def _country_tokens(country: str, iso2: str, iso3: str, sources: list[str]) -> tuple[str, ...]:
    tokens = {_slug(country), iso3.lower(), iso2.lower()}
    tokens.update(FILE_TOKENS.get(country, ()))
    for source in sources:
        tokens.add(source.lower())
    return tuple(sorted(t for t in tokens if t and t != "unknown"))


def _matched_files(files: tuple[Path, ...], tokens: tuple[str, ...], *, suffix: str | None = None, contains: str | None = None) -> tuple[str, ...]:
    matches = []
    for path in files:
        if suffix and not str(path).endswith(suffix):
            continue
        if contains and contains.lower() not in str(path).lower():
            continue
        if any(_matches_token(path, token) for token in tokens):
            matches.append(str(path))
    return tuple(sorted(set(matches)))


def _market_rows() -> dict[str, dict[str, Any]]:
    registry = _safe_import("market_scope_registry")
    rows: dict[str, dict[str, Any]] = {}
    if not registry:
        return rows
    for attr in ("_BUILD", "_SHARED", "_HOLD", "_REMOVE"):
        for country, scope in dict(getattr(registry, attr, {}) or {}).items():
            canonical = _canonical_country(country)
            rows[canonical] = {
                "status": getattr(scope, "status", attr.strip("_")),
                "reason": getattr(scope, "reason", ""),
                "infrastructure": getattr(scope, "infrastructure", ""),
                "priority": getattr(scope, "priority", None),
                "reopen_condition": getattr(scope, "reopen_condition", ""),
            }
    if hasattr(registry, "MARKETS"):
        for country, scope in dict(getattr(registry, "MARKETS") or {}).items():
            rows.setdefault(_canonical_country(country), dict(scope))
    return rows


def _source_rows() -> dict[str, dict[str, Any]]:
    registry = _safe_import("source_registry")
    if not registry:
        return {}
    return {str(k): dict(v) for k, v in dict(getattr(registry, "SOURCES", {}) or {}).items()}


def _shared_family_rows() -> dict[str, str]:
    registry = _safe_import("shared_source_families")
    families: dict[str, str] = {}
    if not registry:
        return families
    for family in dict(getattr(registry, "FAMILIES", {}) or {}).values():
        for member in getattr(family, "members", ()) or ():
            families[str(member)] = getattr(family, "family_id", "")
    return families


def _aggregate(values: list[str], *, green: str = "GREEN", verified: str = "VERIFIED") -> str:
    clean = [str(v or "").strip().upper() for v in values if str(v or "").strip()]
    if not clean:
        return UNKNOWN
    if any(v in {"RED", "BLOCKED"} for v in clean):
        return "RED"
    if any(v in {"YELLOW", "CREDENTIAL_REQUIRED", "UNKNOWN"} for v in clean):
        return "YELLOW"
    if all(v in {green, verified, "ACTIVE", "READY"} for v in clean):
        return green if green in clean else verified
    return ",".join(sorted(set(clean)))


def _bool_from_signals(signal_types: set[str], signal: str) -> bool:
    return signal.upper() in signal_types


def _repo_evidence_for(country: str, iso2: str, iso3: str, source_names: list[str], files: tuple[Path, ...]) -> dict[str, Any]:
    tokens = _country_tokens(country, iso2, iso3, source_names)
    code = _matched_files(files, tokens, suffix=".py")
    tests = _matched_files(files, tokens, suffix=".py", contains="test")
    runtime = tuple(path for path in code if path.endswith("_runtime.py") or "/runtime" in path)
    evidence = _matched_files(files, tokens, suffix=".md", contains="EVIDENCE")
    workflows = tuple(
        str(path)
        for path in files
        if str(path).startswith(".github/workflows/")
        and str(path).endswith((".yml", ".yaml"))
        and any(_matches_token(path, token) for token in tokens)
    )
    return {
        "code": code,
        "tests": tests,
        "runtime": runtime,
        "evidence": evidence,
        "workflows": workflows,
    }


def run_audit(repo_root: str | Path | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root or Path(__file__).resolve().parent)
    files = _repo_files(repo_root)
    markets = _market_rows()
    sources = _source_rows()
    source_families = _shared_family_rows()

    countries = set(markets)
    for meta in sources.values():
        countries.add(_canonical_country(str(meta.get("country") or "")))

    source_by_country: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for name, meta in sources.items():
        country = _canonical_country(str(meta.get("country") or ""))
        source_by_country.setdefault(country, []).append((name, meta))

    rows: list[dict[str, Any]] = []
    contradictions: list[str] = []
    missing: list[str] = []

    source_ids = {}
    for name, meta in sources.items():
        source_id = meta.get("source_id")
        if source_id in source_ids:
            contradictions.append(f"duplicate_source_id:{source_id}:{source_ids[source_id]},{name}")
        source_ids[source_id] = name
        if meta.get("status") in {"ready", "active"} and not meta.get("adapter"):
            contradictions.append(f"{name}:ready_or_active_without_adapter")
        if meta.get("status") == "planned" and meta.get("adapter") and meta.get("machine_access") == "CREDENTIAL_REQUIRED":
            missing.append(f"{name}:planned_source_has_code_claim_but_is_credential_gated")

    for country in sorted(c for c in countries if c):
        iso2, iso3 = COUNTRY_INDEX.get(country, ("", ""))
        country_sources = sorted(source_by_country.get(country, []), key=lambda x: x[0])
        source_names = [name for name, _ in country_sources]
        source_meta = [meta for _, meta in country_sources]
        market = markets.get(country, {})
        status = str(market.get("status") or "UNSCOPED")
        signal_types = sorted({sig for meta in source_meta for sig in meta.get("signal_types", ())})
        rights = _aggregate([meta.get("legal_reuse", "") for meta in source_meta], green="GREEN")
        machine_access = _aggregate([meta.get("machine_access", "") for meta in source_meta], green="VERIFIED", verified="VERIFIED")
        repo_evidence = _repo_evidence_for(country, iso2, iso3, source_names, files)

        implemented = bool(repo_evidence["code"] or any(meta.get("adapter") and meta.get("status") in {"active", "ready"} for meta in source_meta))
        tested = bool(repo_evidence["tests"])
        runtime_wired = bool(repo_evidence["runtime"] or any(meta.get("status") == "active" for meta in source_meta))
        live_validated = bool(repo_evidence["evidence"] or repo_evidence["workflows"] or any(meta.get("status") == "active" for meta in source_meta))
        credential_gated = any(str(meta.get("machine_access")) == "CREDENTIAL_REQUIRED" or str(meta.get("status")) in {"planned", "opt_in"} for meta in source_meta)
        production_path = (
            bool(source_meta)
            and all(meta.get("status") == "active" for meta in source_meta)
            and rights == "GREEN"
            and machine_access == "VERIFIED"
            and (runtime_wired or status == "SHARED")
        )
        gated = credential_gated or not production_path

        known_gaps: list[str] = []
        if not source_meta and status in {"BUILD", "SHARED"}:
            known_gaps.append("MARKET_SCOPED_WITHOUT_NAMED_SOURCE_REGISTRY_ENTRY")
            missing.append(f"{country}:market_scoped_without_named_source")
        if source_meta and status == "UNSCOPED":
            known_gaps.append("SOURCE_WITHOUT_MARKET_SCOPE")
            contradictions.append(f"{country}:source_without_market_scope:{','.join(source_names)}")
        if implemented and not tested:
            known_gaps.append("IMPLEMENTED_WITHOUT_MATCHED_TEST_FILE")
            missing.append(f"{country}:implemented_without_matched_test")
        if implemented and not runtime_wired:
            known_gaps.append("IMPLEMENTED_WITHOUT_MATCHED_RUNTIME_WIRING")
        if credential_gated:
            known_gaps.append("CREDENTIAL_OR_OPT_IN_GATE")
        if not live_validated:
            known_gaps.append("NO_REPO_LIVE_VALIDATION_EVIDENCE")
        if rights != "GREEN" and source_meta:
            known_gaps.append(f"RIGHTS_{rights}")
        if machine_access != "VERIFIED" and source_meta:
            known_gaps.append(f"MACHINE_ACCESS_{machine_access}")

        family_memberships = sorted(filter(None, (source_families.get(name) for name in source_names)))
        rows.append({
            "COUNTRY": country,
            "ISO2": iso2 or UNKNOWN,
            "ISO3": iso3 or UNKNOWN,
            "MARKET_CLASSIFICATION": status,
            "SOURCES": source_names,
            "SOURCE_FAMILIES": family_memberships,
            "SIGNAL_TYPES": signal_types,
            "CONSTRUCTION_COVERAGE": "REPO_SOURCE_GENERIC_PROCUREMENT" if source_meta else UNKNOWN,
            "PROCUREMENT_PLAN": _bool_from_signals(set(signal_types), "PROCUREMENT_PLAN"),
            "TENDER": _bool_from_signals(set(signal_types), "TENDER"),
            "AWARD": _bool_from_signals(set(signal_types), "AWARD"),
            "CONTRACT": _bool_from_signals(set(signal_types), "CONTRACT"),
            "MACHINE_ACCESS": machine_access,
            "RIGHTS": rights,
            "IMPLEMENTED": implemented,
            "TESTED": tested,
            "LIVE_VALIDATED": live_validated,
            "RUNTIME_WIRED": runtime_wired,
            "PRODUCTION_PATH": production_path,
            "GATED": gated,
            "PR": UNKNOWN,
            "KNOWN_GAPS": sorted(set(known_gaps)),
            "PROVENANCE": {
                "market_registry": bool(market),
                "source_registry": source_names,
                "matched_code_files": list(repo_evidence["code"]),
                "matched_test_files": list(repo_evidence["tests"]),
                "matched_runtime_files": list(repo_evidence["runtime"]),
                "matched_evidence_docs": list(repo_evidence["evidence"]),
                "matched_live_workflows": list(repo_evidence["workflows"]),
            },
        })

    rows = sorted(rows, key=lambda row: (row["ISO3"], row["COUNTRY"]))
    contradictions = sorted(set(contradictions))
    missing = sorted(set(missing))
    summary = {
        "country_count": len(rows),
        "source_count": len(sources),
        "build_markets": sum(1 for row in rows if row["MARKET_CLASSIFICATION"] == "BUILD"),
        "shared_markets": sum(1 for row in rows if row["MARKET_CLASSIFICATION"] == "SHARED"),
        "hold_markets": sum(1 for row in rows if row["MARKET_CLASSIFICATION"] == "HOLD"),
        "implemented_countries": sum(1 for row in rows if row["IMPLEMENTED"]),
        "tested_countries": sum(1 for row in rows if row["TESTED"]),
        "runtime_wired_countries": sum(1 for row in rows if row["RUNTIME_WIRED"]),
        "production_path_countries": sum(1 for row in rows if row["PRODUCTION_PATH"]),
        "gated_countries": sum(1 for row in rows if row["GATED"]),
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


def _to_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# ObraSignal International Coverage Audit",
        "",
        "This report is generated from repository state only. It does not use chat memory or external research.",
        "",
        "## Summary",
        "",
    ]
    for key, value in audit["summary"].items():
        lines.append(f"- **{key}**: {value}")
    lines.extend(["", "## Countries", ""])
    lines.append("| Country | ISO3 | Market | Sources | Implemented | Tested | Runtime | Production | Gated | Gaps |")
    lines.append("|---|---:|---|---|---:|---:|---:|---:|---:|---|")
    for row in audit["countries"]:
        values = {
            **row,
            "SOURCES": ", ".join(row["SOURCES"]) or "-",
            "KNOWN_GAPS": ", ".join(row["KNOWN_GAPS"]) or "-",
        }
        lines.append(
            "| {COUNTRY} | {ISO3} | {MARKET_CLASSIFICATION} | {SOURCES} | {IMPLEMENTED} | {TESTED} | {RUNTIME_WIRED} | {PRODUCTION_PATH} | {GATED} | {KNOWN_GAPS} |".format(
                **values
            )
        )
    lines.extend(["", "## Contradictions", ""])
    lines.extend(f"- {item}" for item in audit["contradictions"] or ["None"])
    lines.extend(["", "## Missing integrations", ""])
    lines.extend(f"- {item}" for item in audit["missing_integrations"] or ["None"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit ObraSignal international coverage from repository state.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true", help="Print deterministic machine-readable JSON.")
    parser.add_argument("--markdown", action="store_true", help="Print human-readable markdown.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when contradictions exist.")
    args = parser.parse_args(argv)

    audit = run_audit(args.repo_root)
    if args.markdown:
        print(_to_markdown(audit), end="")
    else:
        print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and audit["contradictions"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
