import pytest

from factory_cloud.support_continuity import SupportContinuityError, SupportLedger


def test_support_incident_survives_restart_and_resolves_only_with_customer_update_and_evidence(tmp_path):
    path = tmp_path / "support.sqlite3"
    ledger = SupportLedger(path)
    incident = ledger.open(
        incident_id="synthetic-p0",
        severity="P0",
        owner_role="on_call",
        summary="synthetic outage for continuity testing",
    )
    assert incident.state == "OPEN"
    assert ledger.acknowledgement_target_minutes(incident.incident_id) == 15
    assert ledger.transition(incident.incident_id, "ACKNOWLEDGED").state == "ACKNOWLEDGED"
    assert ledger.transition(incident.incident_id, "INVESTIGATING").state == "INVESTIGATING"
    assert ledger.transition(incident.incident_id, "MITIGATED").state == "MITIGATED"

    restarted = SupportLedger(path)
    assert restarted.get(incident.incident_id).state == "MITIGATED"
    with pytest.raises(SupportContinuityError, match="customer update"):
        restarted.transition(incident.incident_id, "RESOLVED", evidence_ref="root-cause-report")

    restarted.record_customer_update(incident.incident_id, communication_evidence_ref="synthetic-update-1")
    resolved = restarted.transition(incident.incident_id, "RESOLVED", evidence_ref="synthetic-closure-proof")
    assert resolved.state == "RESOLVED"
    assert resolved.closure_evidence_hash is not None
    assert restarted.event_count(incident.incident_id) == 6


def test_support_state_machine_rejects_skipped_or_post_resolution_transitions(tmp_path):
    ledger = SupportLedger(tmp_path / "support.sqlite3")
    ledger.open(incident_id="i1", severity="P1", owner_role="support", summary="synthetic")
    with pytest.raises(SupportContinuityError, match="invalid support transition"):
        ledger.transition("i1", "RESOLVED", evidence_ref="x")
    ledger.transition("i1", "ACKNOWLEDGED")
    ledger.transition("i1", "INVESTIGATING")
    ledger.transition("i1", "MITIGATED")
    ledger.record_customer_update("i1", communication_evidence_ref="update")
    ledger.transition("i1", "RESOLVED", evidence_ref="closure")
    with pytest.raises(SupportContinuityError, match="invalid support transition"):
        ledger.transition("i1", "INVESTIGATING")


def test_support_ledger_does_not_store_raw_summary_or_communication_reference(tmp_path):
    path = tmp_path / "support.sqlite3"
    ledger = SupportLedger(path)
    raw_summary = "raw customer wording must not be durable"
    raw_ref = "customer-message-reference-sensitive"
    ledger.open(incident_id="i2", severity="P2", owner_role="support", summary=raw_summary)
    ledger.transition("i2", "ACKNOWLEDGED")
    ledger.record_customer_update("i2", communication_evidence_ref=raw_ref)
    persisted = path.read_bytes()
    assert raw_summary.encode() not in persisted
    assert raw_ref.encode() not in persisted


def test_invalid_severity_fails_closed(tmp_path):
    ledger = SupportLedger(tmp_path / "support.sqlite3")
    with pytest.raises(SupportContinuityError, match="invalid support severity"):
        ledger.open(incident_id="i3", severity="P9", owner_role="support", summary="synthetic")
