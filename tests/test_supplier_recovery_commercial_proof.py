import pytest

from vertical_apps.industrial_claims.commercial_proof import CommercialProofError, CommercialProofStore


def _append(store, *, event_id, kind, klass="REAL"):
    return store.append(
        event_id=event_id,
        account_id="account-1",
        event_type=kind,
        evidence_class=klass,
        evidence_ref=f"evidence-{event_id}",
        actor_id="operator-1",
    )


def test_test_payment_never_becomes_real_customer_or_market_proof(tmp_path):
    store = CommercialProofStore(tmp_path / "commercial-proof.sqlite3")
    _append(store, event_id="test-payment", kind="CUSTOMER_PAYMENT", klass="TEST")
    state = store.state(account_id="account-1")
    assert state.stage == "T0_INTERNAL_ONLY"
    assert state.real_customer_payment_proven is False
    assert state.test_event_types == ("CUSTOMER_PAYMENT",)
    assert state.as_dict()["test_or_synthetic_evidence_counts_as_commercial_proof"] is False


def test_real_commercial_stage_requires_upstream_chain_and_cannot_be_skipped(tmp_path):
    store = CommercialProofStore(tmp_path / "commercial-chain.sqlite3")
    _append(store, event_id="payment-before-buyer", kind="CUSTOMER_PAYMENT")
    _append(store, event_id="outcome-before-buyer", kind="VERIFIED_CASE_OUTCOME")
    assert store.state(account_id="account-1").stage == "T0_INTERNAL_ONLY"
    _append(store, event_id="buyer", kind="QUALIFIED_BUYER")
    assert store.state(account_id="account-1").stage == "T1_QUALIFIED_BUYER"
    _append(store, event_id="case", kind="BOUNDED_CASE_CONFIRMED")
    assert store.state(account_id="account-1").stage == "T2_BOUNDED_REAL_CASE"
    _append(store, event_id="commitment", kind="PAID_AUDIT_COMMITMENT")
    assert store.state(account_id="account-1").stage == "T4_VERIFIED_OUTCOME"
    _append(store, event_id="repeat", kind="REPEAT_OR_MONITORING_INTENT")
    state = store.state(account_id="account-1")
    assert state.stage == "T5_PAYMENT_AND_REPEAT_SIGNAL"
    assert state.real_customer_payment_proven is True
    assert state.verified_outcome_proven is True
    assert state.repeat_intent_proven is True


def test_t3_can_exist_without_payment_or_verified_outcome(tmp_path):
    store = CommercialProofStore(tmp_path / "paid-commitment.sqlite3")
    _append(store, event_id="buyer", kind="QUALIFIED_BUYER")
    _append(store, event_id="case", kind="BOUNDED_CASE_CONFIRMED")
    _append(store, event_id="commitment", kind="PAID_AUDIT_COMMITMENT")
    state = store.state(account_id="account-1")
    assert state.stage == "T3_COSTLY_COMMERCIAL_COMMITMENT"
    assert state.real_customer_payment_proven is False
    assert state.verified_outcome_proven is False


def test_exact_event_replay_is_idempotent_and_rebinding_collides(tmp_path):
    store = CommercialProofStore(tmp_path / "commercial-replay.sqlite3")
    first = _append(store, event_id="buyer", kind="QUALIFIED_BUYER")
    replay = _append(store, event_id="buyer", kind="QUALIFIED_BUYER")
    assert replay == first
    assert len(store.events(account_id="account-1")) == 1
    with pytest.raises(CommercialProofError, match="event id collision"):
        store.append(
            event_id="buyer", account_id="account-1", event_type="QUALIFIED_BUYER",
            evidence_class="REAL", evidence_ref="different-evidence", actor_id="operator-1",
        )


def test_unknown_event_or_evidence_class_fails_closed(tmp_path):
    store = CommercialProofStore(tmp_path / "commercial-invalid.sqlite3")
    with pytest.raises(CommercialProofError, match="unsupported"):
        _append(store, event_id="unknown", kind="EMAIL_OPEN")
    with pytest.raises(CommercialProofError, match="REAL or TEST"):
        _append(store, event_id="bad-class", kind="QUALIFIED_BUYER", klass="SYNTHETIC")
