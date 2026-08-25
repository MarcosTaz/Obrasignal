import international_coverage_audit as audit
from international_audit_provenance import _pr_numbers


def _rows(result):
    return {row["ISO3"]: row for row in result["countries"]}


def test_capability_states_are_exposed_without_promotion():
    result = audit.run_audit()
    capabilities = {item["name"]: item for item in result["capabilities"]}
    assert capabilities["SIGNAL"]["state"] == "ENABLED"
    assert capabilities["EVIDENCE"]["state"] == "EXPERIMENT"
    assert capabilities["OFFICE"]["state"] == "RESEARCH"
    assert result["capability_summary"]["ENABLED"] >= 1
    assert result["capability_summary"]["RESEARCH"] >= 1


def test_repository_research_can_be_distinguished_from_implementation():
    result = audit.run_audit()
    ukraine = _rows(result)["UKR"]
    assert ukraine["IMPLEMENTED"] is False
    assert ukraine["RESEARCH_ONLY"] is True
    assert any("UKRAINE" in path.upper() for path in ukraine["RESEARCH_EVIDENCE"])
    assert "Ukraine" in result["research_only_countries"]


def test_common_word_iso3_cannot_create_research_evidence():
    result = audit.run_audit()
    uae = _rows(result)["ARE"]
    assert uae["RESEARCH_ONLY"] is False
    assert uae["RESEARCH_EVIDENCE"] == []
    assert "United Arab Emirates" not in result["research_only_countries"]


def test_broad_scope_document_does_not_make_country_research_only():
    result = audit.run_audit()
    portugal = _rows(result)["PRT"]
    assert "INTERNATIONAL_SCOPE.md" not in portugal["RESEARCH_EVIDENCE"]


def test_pr_reference_parser_is_explicit_and_bounded():
    assert _pr_numbers("Merge pull request #192 from branch") == (192,)
    assert _pr_numbers("feat: coverage audit (#193)") == (193,)
    assert _pr_numbers("issue #194 is not a PR claim") == ()


def test_country_pr_fields_are_deterministic_sorted_integer_lists():
    result = audit.run_audit()
    for row in result["countries"]:
        assert row["PR"] == sorted(set(row["PR"]))
        assert all(isinstance(value, int) and value > 0 for value in row["PR"])
    assert result["explicit_pr_references"] == sorted(set(result["explicit_pr_references"]))
