import json
from pathlib import Path

import international_coverage_audit as audit


REQUIRED_KEYS = {
    "COUNTRY",
    "ISO2",
    "ISO3",
    "MARKET_CLASSIFICATION",
    "SOURCES",
    "SIGNAL_TYPES",
    "PROCUREMENT_PLAN",
    "TENDER",
    "AWARD",
    "CONTRACT",
    "MACHINE_ACCESS",
    "RIGHTS",
    "IMPLEMENTED",
    "TESTED",
    "LIVE_VALIDATED",
    "RUNTIME_WIRED",
    "PRODUCTION_PATH",
    "GATED",
    "PR",
    "KNOWN_GAPS",
    "PROVENANCE",
}


def _by_iso3(result):
    return {row["ISO3"]: row for row in result["countries"]}


def test_audit_output_is_deterministic():
    first = audit.run_audit()
    second = audit.run_audit()
    assert json.dumps(first, sort_keys=True, ensure_ascii=False) == json.dumps(
        second, sort_keys=True, ensure_ascii=False
    )


def test_country_row_contract_is_stable():
    result = audit.run_audit()
    assert result["audit_contract"] == "OBRASIGNAL_REPOSITORY_STATE_INTERNATIONAL_COVERAGE_AUDIT_V1"
    assert result["countries"]
    assert REQUIRED_KEYS.issubset(result["countries"][0])
    assert result["countries"] == sorted(
        result["countries"], key=lambda row: (row["ISO3"], row["COUNTRY"])
    )


def test_source_backed_signal_depth_for_core_non_eu_sources():
    rows = _by_iso3(audit.run_audit())
    assert "CA_CANADABUYS" in rows["CAN"]["SOURCES"]
    assert rows["CAN"]["TENDER"] is True
    assert "US_SAM" in rows["USA"]["SOURCES"]
    assert rows["USA"]["TENDER"] is True
    assert rows["COL"]["PROCUREMENT_PLAN"] is True
    assert rows["COL"]["AWARD"] is True
    assert rows["COL"]["CONTRACT"] is True


def test_credential_or_planned_sources_are_gated_not_production():
    rows = _by_iso3(audit.run_audit())
    assert rows["CHL"]["GATED"] is True
    assert rows["CHL"]["PRODUCTION_PATH"] is False


def test_summary_matches_rows_and_lists_are_sorted():
    result = audit.run_audit()
    assert result["summary"]["country_count"] == len(result["countries"])
    assert result["summary"]["contradiction_count"] == len(result["contradictions"])
    assert result["summary"]["missing_integration_count"] == len(result["missing_integrations"])
    assert result["contradictions"] == sorted(result["contradictions"])
    assert result["missing_integrations"] == sorted(result["missing_integrations"])


def test_every_market_has_known_iso_identifiers():
    result = audit.run_audit()
    unknown = [
        row["COUNTRY"]
        for row in result["countries"]
        if row["ISO2"] == "UNKNOWN" or row["ISO3"] == "UNKNOWN"
    ]
    assert unknown == []


def test_short_iso_tokens_do_not_match_arbitrary_substrings():
    rows = _by_iso3(audit.run_audit())
    austria = rows["AUT"]["PROVENANCE"]
    all_paths = (
        austria["matched_code_files"]
        + austria["matched_test_files"]
        + austria["matched_runtime_files"]
        + austria["matched_live_workflows"]
    )
    assert not any("auth_" in path or "authenticated" in path for path in all_paths)


def test_test_files_never_count_as_code_or_runtime_provenance():
    result = audit.run_audit()
    for row in result["countries"]:
        for key in ("matched_code_files", "matched_runtime_files"):
            for value in row["PROVENANCE"][key]:
                path = Path(value)
                assert "tests" not in path.parts
                assert not path.name.startswith("test_")


def test_ted_shared_market_uses_concrete_shared_source_without_eu_scope_conflict():
    rows = _by_iso3(audit.run_audit())
    belgium = rows["BEL"]
    assert "TED" in belgium["SOURCES"]
    assert belgium["PROVENANCE"]["shared_market_family"] == "TED_EFORMS"
    assert belgium["PRODUCTION_PATH"] is True
    assert not any(item.startswith("European Union:source_without_market_scope") for item in audit.run_audit()["contradictions"])
