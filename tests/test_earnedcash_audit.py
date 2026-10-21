from dataclasses import replace

from earnedcash.audit import append_event, verify_history


def test_empty_history_is_valid_for_tenant():
    assert verify_history((), tenant_id="t1") is True


def test_appended_history_verifies():
    history = append_event(
        (), tenant_id="t1", event_type="RECONCILED", entity_id="p1",
        payload={"due_unpaid":"100"}
    )
    history = append_event(
        history, tenant_id="t1", event_type="QUEUE_CREATED", entity_id="p1",
        payload={"case_ids":["invoice:i1"]}
    )
    assert verify_history(history, tenant_id="t1") is True
    assert history[1].previous_hash == history[0].event_hash


def test_payload_tamper_is_detected():
    history = append_event(
        (), tenant_id="t1", event_type="RECONCILED", entity_id="p1",
        payload={"due_unpaid":"100"}
    )
    tampered = (replace(history[0], payload={"due_unpaid":"100000"}),)
    assert verify_history(tampered, tenant_id="t1") is False


def test_cross_tenant_history_is_rejected():
    history = append_event(
        (), tenant_id="t1", event_type="RECONCILED", entity_id="p1", payload={}
    )
    assert verify_history(history, tenant_id="t2") is False


def test_broken_previous_hash_is_detected():
    history = append_event(
        (), tenant_id="t1", event_type="RECONCILED", entity_id="p1", payload={}
    )
    history = append_event(
        history, tenant_id="t1", event_type="QUEUE_CREATED", entity_id="p1", payload={}
    )
    tampered = (history[0], replace(history[1], previous_hash="bad"))
    assert verify_history(tampered, tenant_id="t1") is False
