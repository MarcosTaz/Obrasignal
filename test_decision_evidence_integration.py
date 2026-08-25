import sqlite3

import pytest

import opportunity_match_pipeline as pipeline
from decision_evidence import (
    attach_persistable_decision_evidence,
    build_decision_evidence,
    customer_evidence_view,
    maybe_decision_evidence,
)
from decision_log import (
    MAX_FEATURES_JSON_BYTES,
    ensure_decision_table,
    latest_decision,
    record_decision,
    validate_features_payload,
)


RULE_VERSION = "commercial-v2+lot-v1+capability-v2+economic-fit-v3"
DECIDED_AT = "2026-08-25T03:00:00+00:00"


def _row(**overrides):
    row = {
        "source": "TED",
        "external_id": "2026-S-1000",
        "title": "Reabilitação de escola",
        "description": "Obras de construção e reabilitação",
        "buyer": "Município",
        "country": "PRT",
        "cpv": "45214200",
        "value": "250000 EUR",
        "value_numeric": 250000,
        "deadline": "2026-09-30T12:00:00+00:00",
        "procedure_type": "OPEN",
        "url": "https://example.test/2026-S-1000",
        "publication_date": "2026-08-24T00:00:00+00:00",
        "source_updated_at": "2026-08-24T01:00:00+00:00",
        "last_observed": "2026-08-25T02:00:00+00:00",
    }
    row.update(overrides)
    return row


def _profile(**overrides):
    profile = {
        "activity": "Construção",
        "services": ["reabilitação", "construção"],
        "countries": ["PRT"],
        "cpv_prefixes": ["4521"],
        "min_value": 100000,
        "max_value": 500000,
        "economic_min_score": 50,
    }
    profile.update(overrides)
    return profile


def _evaluation(row=None, profile=None):
    return pipeline.evaluate_row(row or _row(), profile or _profile())


def test_decision_snapshot_is_account_scoped_replayable_and_customer_view_is_redacted():
    row = _row()
    profile = _profile()
    evaluation = _evaluation(row, profile)

    snapshot = build_decision_evidence(
        "company-a",
        row,
        profile,
        evaluation,
        rule_version=RULE_VERSION,
        decided_at=DECIDED_AT,
    )
    view = customer_evidence_view(snapshot)

    assert snapshot["state"] == "READY"
    assert snapshot["graph"]["tenant_id"] == "company-a"
    assert snapshot["explanation"]["claim"]["value"] == evaluation["decision"]
    assert any(item["type"] == "ASSUMPTION" for item in snapshot["explanation"]["assumptions"])
    assert any(edge["relation"] == "USES_ASSUMPTION" for edge in snapshot["graph"]["edges"])

    assert view["state"] == "READY"
    assert view["sources"]
    assert view["presentation_policy_version"] == "decision-evidence-customer-v1"
    assert "graph" not in view
    assert "assumptions" not in view
    serialized_view = repr(view)
    assert "normalized_capability" not in serialized_view
    assert "company_profile.snapshot" not in serialized_view


def test_same_decision_for_two_accounts_has_different_private_graph_identity():
    row = _row()
    profile = _profile()
    evaluation = _evaluation(row, profile)
    a = build_decision_evidence("company-a", row, profile, evaluation, rule_version=RULE_VERSION, decided_at=DECIDED_AT)
    b = build_decision_evidence("company-b", row, profile, evaluation, rule_version=RULE_VERSION, decided_at=DECIDED_AT)

    assert a["decision_claim_id"] != b["decision_claim_id"]
    assert a["graph"]["tenant_id"] == "company-a"
    assert b["graph"]["tenant_id"] == "company-b"


def test_missing_source_field_remains_explicitly_unknown_in_customer_contract():
    row = _row(deadline=None)
    profile = _profile(min_deadline_days=7)
    evaluation = _evaluation(row, profile)
    snapshot = build_decision_evidence("company-a", row, profile, evaluation, rule_version=RULE_VERSION, decided_at=DECIDED_AT)
    view = customer_evidence_view(snapshot)

    assert "deadline" in snapshot["missing_inputs"]
    assert "deadline" in view["missing"]
    assert view["status"] == "UNKNOWN"
    assert view["confidence"] == "UNKNOWN"


def test_missing_company_specialization_remains_explicitly_unknown():
    profile = {
        "countries": ["PRT"],
        "min_value": 100000,
        "max_value": 500000,
    }
    row = _row()
    evaluation = _evaluation(row, profile)
    snapshot = build_decision_evidence("company-a", row, profile, evaluation, rule_version=RULE_VERSION, decided_at=DECIDED_AT)
    view = customer_evidence_view(snapshot)

    assert "company_specialization" in snapshot["missing_inputs"]
    assert "company_specialization" in view["missing"]
    assert view["status"] == "UNKNOWN"
    assert view["confidence"] == "UNKNOWN"


def test_customer_contract_propagates_lineage_conflict_instead_of_claiming_supported():
    snapshot = {
        "contract_version": "evidence.v1",
        "state": "READY",
        "decision_claim_id": "cl-decision",
        "missing_inputs": [],
        "explanation": {
            "status": "SUPPORTED",
            "confidence": "HIGH",
            "evidence": [],
            "conflicts": [{"left": "cl-a", "right": "cl-b"}],
            "missing": [],
            "model_version": "evidence-graph-v1",
            "policy_version": "evidence-policy-v1",
        },
    }
    view = customer_evidence_view(snapshot)
    assert view["status"] == "CONFLICT"
    assert view["confidence"] == "LOW"
    assert view["conflict_count"] == 1


def test_customer_provenance_preserves_publisher_reference_and_filters_unsafe_urls():
    row = _row(
        publisher="Publications Office of the European Union",
        source_reference="native-ref-1000",
        url="javascript:alert(1)",
    )
    evaluation = _evaluation(row, _profile())
    snapshot = build_decision_evidence("company-a", row, _profile(), evaluation, rule_version=RULE_VERSION, decided_at=DECIDED_AT)
    view = customer_evidence_view(snapshot)

    assert view["sources"]
    assert {item["publisher"] for item in view["sources"]} == {"Publications Office of the European Union"}
    assert {item["source_reference"] for item in view["sources"]} == {"native-ref-1000"}
    assert all(item["source_url"] is None for item in view["sources"])
    assert "javascript:" not in repr(view)


def test_customer_provenance_allows_only_absolute_http_source_urls():
    unsafe_values = (
        "data:text/html,boom",
        "file:///tmp/x",
        "/relative",
        "custom:thing",
        "https:///missing-host",
        "https://example.test/ok\njavascript:alert(1)",
    )
    for unsafe in unsafe_values:
        row = _row(url=unsafe)
        evaluation = _evaluation(row, _profile())
        snapshot = build_decision_evidence("company-a", row, _profile(), evaluation, rule_version=RULE_VERSION, decided_at=DECIDED_AT)
        assert all(item["source_url"] is None for item in customer_evidence_view(snapshot)["sources"])

    row = _row(url="https://example.test/source")
    evaluation = _evaluation(row, _profile())
    snapshot = build_decision_evidence("company-a", row, _profile(), evaluation, rule_version=RULE_VERSION, decided_at=DECIDED_AT)
    assert {item["source_url"] for item in customer_evidence_view(snapshot)["sources"]} == {"https://example.test/source"}


def test_enabled_evidence_marks_contract_invalid_source_as_unavailable(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "true")
    row = _row(publication_date="not-a-date")
    evaluation = _evaluation(_row(), _profile())

    snapshot = maybe_decision_evidence(
        "company-a",
        row,
        _profile(),
        evaluation,
        rule_version=RULE_VERSION,
        decided_at=DECIDED_AT,
    )

    assert snapshot == {
        "contract_version": "evidence.v1",
        "state": "UNAVAILABLE",
        "reason": "evidence_contract_rejected",
    }


def test_evidence_rollout_is_backward_compatible_and_kill_switch_is_immediate(monkeypatch):
    row = _row()
    evaluation = _evaluation(row, _profile())

    monkeypatch.delenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", raising=False)
    monkeypatch.delenv("OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1", raising=False)
    assert maybe_decision_evidence("company-a", row, _profile(), evaluation, rule_version=RULE_VERSION) is None

    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "true")
    assert maybe_decision_evidence("company-a", row, _profile(), evaluation, rule_version=RULE_VERSION)["state"] == "READY"

    monkeypatch.setenv("OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1", "true")
    assert maybe_decision_evidence("company-a", row, _profile(), evaluation, rule_version=RULE_VERSION) is None


def test_malformed_rollout_configuration_degrades_to_disabled(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "sometimes")
    row = _row()
    evaluation = _evaluation(row, _profile())
    assert maybe_decision_evidence("company-a", row, _profile(), evaluation, rule_version=RULE_VERSION) is None


def test_decision_log_rejects_blank_tenant_and_unbounded_features_without_partial_insert():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)

    with pytest.raises(ValueError, match="account_id"):
        record_decision(conn, "TED", "x", "REVIEW", "reason", account_id="")
    assert conn.execute("SELECT COUNT(*) FROM opportunity_decisions").fetchone()[0] == 0

    oversized = {"blob": "x" * (MAX_FEATURES_JSON_BYTES + 1)}
    with pytest.raises(ValueError, match="maximum serialized size"):
        record_decision(conn, "TED", "x", "REVIEW", "reason", features=oversized, account_id="company-a")
    assert conn.execute("SELECT COUNT(*) FROM opportunity_decisions").fetchone()[0] == 0


def test_oversized_evidence_degrades_without_losing_an_otherwise_valid_decision():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)
    features = {
        "explanation": {},
        "baseline": "b" * 390_000,
    }
    validate_features_payload(features)
    oversized_evidence = {
        "contract_version": "evidence.v1",
        "state": "READY",
        "decision_claim_id": "cl-test",
        "missing_inputs": [],
        "explanation": {
            "status": "SUPPORTED",
            "confidence": "HIGH",
            "evidence": [],
            "conflicts": [],
            "missing": [],
        },
        "graph": {"nodes": [{"metadata": "x" * 150_000}], "edges": []},
    }

    attach_persistable_decision_evidence(features, oversized_evidence)
    assert features["decision_evidence"] == {
        "contract_version": "evidence.v1",
        "state": "UNAVAILABLE",
        "reason": "evidence_payload_too_large",
    }
    assert features["explanation"]["evidence"]["state"] == "UNAVAILABLE"
    validate_features_payload(features)

    record_decision(
        conn,
        "TED",
        "bounded-1",
        "REVIEW",
        "reason",
        features=features,
        account_id="company-a",
    )
    persisted = latest_decision(conn, "TED", "bounded-1", account_id="company-a")
    assert persisted["decision"] == "REVIEW"
    assert persisted["features"]["decision_evidence"]["reason"] == "evidence_payload_too_large"


def test_evaluate_and_record_loads_profile_for_the_same_account_and_persists_evidence(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)
    seen_accounts = []

    def fake_load_profile(account_id="default"):
        seen_accounts.append(account_id)
        return _profile()

    monkeypatch.setattr(pipeline, "load_profile", fake_load_profile)
    monkeypatch.setenv("OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1", "true")
    evaluation = pipeline.evaluate_and_record(conn, _row(), account_id="company-b")
    persisted = latest_decision(conn, "TED", "2026-S-1000", account_id="company-b")

    assert seen_accounts == ["company-b"]
    assert persisted["decision"] == evaluation["decision"]
    assert persisted["features"]["decision_evidence"]["state"] == "READY"
    assert persisted["features"]["decision_evidence"]["graph"]["tenant_id"] == "company-b"
