from datetime import datetime, timedelta, timezone
import sqlite3

import funnel_integration
from account_registry import ensure_account, get_account
from evaluation_policy import evaluation_summary, record_evaluation_event


def _db(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _summary(conn, account_id):
    return evaluation_summary(conn, get_account(conn, account_id))


def test_real_funnel_path_invokes_customer_evaluation_bridge(monkeypatch):
    evaluation = {
        "decision": "QUALIFIED",
        "reason": "relevant",
        "profile_score": 82,
        "lot_score": 80,
        "lot_id": "lot-1",
        "match": True,
        "geography": {"score": 100, "reason": "in coverage"},
        "commercial": {},
        "economic_fit": {},
        "capability": {},
        "capability_evidence": {},
        "cpv_evidence": {},
        "hard_capability_blockers": [],
        "explanation": {},
    }
    calls = []
    monkeypatch.setattr(funnel_integration, "load_profile", lambda _account_id: {})
    monkeypatch.setattr(funnel_integration, "evaluate_row", lambda _item, profile=None: evaluation)
    monkeypatch.setattr(funnel_integration, "record_decision", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        funnel_integration,
        "_record_customer_evaluation_events",
        lambda conn, item, result, account_id: calls.append((item, result, account_id)),
    )

    result = funnel_integration.persist_and_classify(
        object(),
        {"source": "TED", "external_id": "notice-1"},
        False,
        account_id="tenant-a",
    )

    assert result == ("QUALIFIED", "relevant")
    assert len(calls) == 1
    assert calls[0][0]["source"] == "TED"
    assert calls[0][0]["external_id"] == "notice-1"
    assert calls[0][2] == "tenant-a"


def test_usable_market_data_and_relevant_shortlist_activate_same_tenant_only():
    conn = _db()
    ensure_account(conn, "tenant-a")
    ensure_account(conn, "tenant-b")
    base = datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc)
    record_evaluation_event(conn, "tenant-a", "profile_ready", occurred_at=base)

    emitted = funnel_integration._record_customer_evaluation_events(
        conn,
        {"source": "TED", "external_id": "notice-1"},
        {"decision": "QUALIFIED"},
        "tenant-a",
    )

    assert emitted is True
    tenant_a = _summary(conn, "tenant-a")
    tenant_b = _summary(conn, "tenant-b")
    assert tenant_a["activation_requirements"] == {
        "profile_ready": True,
        "market_data_available": True,
        "first_relevant_shortlist_generated": True,
    }
    assert tenant_a["status"] == "EVALUATION_ACTIVE"
    assert datetime.fromisoformat(tenant_a["ends_at"]) - datetime.fromisoformat(tenant_a["activated_at"]) == timedelta(days=21)
    assert tenant_b["activation_requirements"] == {
        "profile_ready": False,
        "market_data_available": False,
        "first_relevant_shortlist_generated": False,
    }
    assert tenant_b["activated_at"] is None


def test_empty_or_unknown_market_identity_cannot_satisfy_activation_requirements():
    conn = _db()
    ensure_account(conn, "tenant-a")
    record_evaluation_event(conn, "tenant-a", "profile_ready")

    for item in (
        {"source": "", "external_id": "notice-1"},
        {"source": "UNKNOWN", "external_id": "notice-1"},
        {"source": "UNAVAILABLE", "external_id": "notice-1"},
        {"source": "TED", "external_id": ""},
    ):
        assert funnel_integration._record_customer_evaluation_events(
            conn, item, {"decision": "QUALIFIED"}, "tenant-a"
        ) is False

    summary = _summary(conn, "tenant-a")
    assert summary["activation_requirements"]["profile_ready"] is True
    assert summary["activation_requirements"]["market_data_available"] is False
    assert summary["activation_requirements"]["first_relevant_shortlist_generated"] is False
    assert summary["activated_at"] is None
    assert summary["ends_at"] is None


def test_retry_after_restart_never_resets_or_extends_evaluation_clock(tmp_path):
    path = str(tmp_path / "evaluation-restart.db")
    conn = _db(path)
    ensure_account(conn, "tenant-a")
    record_evaluation_event(conn, "tenant-a", "profile_ready")
    funnel_integration._record_customer_evaluation_events(
        conn,
        {"source": "TED", "external_id": "notice-1"},
        {"decision": "REVIEW"},
        "tenant-a",
    )
    first = _summary(conn, "tenant-a")
    activated_at = first["activated_at"]
    ends_at = first["ends_at"]
    conn.close()

    restarted = _db(path)
    funnel_integration._record_customer_evaluation_events(
        restarted,
        {"source": "TED", "external_id": "notice-1"},
        {"decision": "QUALIFIED"},
        "tenant-a",
    )
    funnel_integration._record_customer_evaluation_events(
        restarted,
        {"source": "TED", "external_id": "notice-2"},
        {"decision": "REVIEW"},
        "tenant-a",
    )
    after_retry = _summary(restarted, "tenant-a")

    assert after_retry["activated_at"] == activated_at
    assert after_retry["ends_at"] == ends_at
    restarted.close()
