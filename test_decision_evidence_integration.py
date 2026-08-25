import sqlite3

import pytest

import opportunity_match_pipeline as pipeline
from decision_evidence import (
    build_decision_evidence,
    customer_evidence_view,
    maybe_decision_evidence,
)
from decision_log import (
    MAX_FEATURES_JSON_BYTES,
    ensure_decision_table,
    latest_decision,
    record_decision,
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


def test_missing_source_field_remains_explicitly_missing_in_customer_contract():
    row = _row(deadline=None)
    profile = _profile(min_deadline_days=7)
    evaluation = _evaluation(row, profile)
    snapshot = build_decision_evidence("company-a", row, profile, evaluation, rule_version=RULE_VERSION, decided_at=DECIDED_AT)
    view = customer_evidence_view(snapshot)

    assert "deadline" in snapshot["missing_inputs"]
    assert "deadline" in view["missing"]


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
