import sqlite3
from datetime import datetime, timedelta, timezone

import pytest


ACCOUNT_ID = "synthetic-returning-electrical"
SOURCE = "TED"
EXTERNAL_ID = "RETURN-1"


def _conn(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _seed_customer_state(monkeypatch, db_path):
    from account_registry import get_account
    from company_profile import save_profile
    from evaluation_policy import record_evaluation_event
    from opportunity_workflow import set_workflow

    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    created = datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)

    saved = save_profile(
        {
            "activity": "instalações elétricas",
            "countries": ["PRT"],
            "cpv_prefixes": ["4531"],
            "keywords": ["instalação elétrica", "quadros elétricos"],
            "economic_min_score": 60,
        },
        ACCOUNT_ID,
    )
    assert saved["account_id"] == ACCOUNT_ID

    conn = _conn(db_path)
    try:
        conn.execute(
            "UPDATE accounts SET created_at=? WHERE account_id=?",
            (created.isoformat(), ACCOUNT_ID),
        )
        conn.commit()
        assert get_account(conn, ACCOUNT_ID) is not None

        record_evaluation_event(
            conn,
            ACCOUNT_ID,
            "market_data_available",
            occurred_at=created + timedelta(minutes=1),
        )
        record_evaluation_event(
            conn,
            ACCOUNT_ID,
            "first_shortlist_generated",
            occurred_at=created + timedelta(minutes=2),
        )
        record_evaluation_event(
            conn,
            ACCOUNT_ID,
            "relevant_opportunity_viewed",
            occurred_at=created + timedelta(minutes=3),
        )
        record_evaluation_event(
            conn,
            ACCOUNT_ID,
            "action_taken",
            occurred_at=created + timedelta(minutes=4),
        )
        workflow = set_workflow(
            conn,
            ACCOUNT_ID,
            SOURCE,
            EXTERNAL_ID,
            "PREPARING",
            "proposal preparation in progress",
        )
        assert workflow["status"] == "PREPARING"
        assert workflow["verified_outcome"] is False
        event_count = conn.execute(
            "SELECT COUNT(*) FROM evaluation_events WHERE account_id=?",
            (ACCOUNT_ID,),
        ).fetchone()[0]
    finally:
        conn.close()
    return created, event_count


@pytest.mark.parametrize(
    "pause",
    [timedelta(minutes=15), timedelta(days=1), timedelta(days=7)],
    ids=["minutes", "day", "week"],
)
def test_returning_customer_resumes_durable_state_without_manufacturing_repeat_value(monkeypatch, tmp_path, pause):
    from account_registry import get_account
    from company_profile import load_profile
    from evaluation_policy import evaluation_metrics, evaluation_summary
    from opportunity_workflow import get_workflow

    db_path = tmp_path / "return-resume.db"
    created, event_count_before_leave = _seed_customer_state(monkeypatch, db_path)

    # LEAVE: every seed connection is closed. RETURN uses fresh SQLite and
    # profile connections, so no in-memory object is allowed to carry truth.
    returned = _conn(db_path)
    try:
        account = get_account(returned, ACCOUNT_ID)
        profile = load_profile(ACCOUNT_ID)
        workflow = get_workflow(returned, ACCOUNT_ID, SOURCE, EXTERNAL_ID)
        metrics = evaluation_metrics(returned, account, now=created + pause)
        summary = evaluation_summary(returned, account, now=created + pause)
        event_count_after_return = returned.execute(
            "SELECT COUNT(*) FROM evaluation_events WHERE account_id=?",
            (ACCOUNT_ID,),
        ).fetchone()[0]

        assert profile["account_id"] == ACCOUNT_ID
        assert profile["activity"] == "instalações elétricas"
        assert workflow["status"] == "PREPARING"
        assert workflow["note"] == "proposal preparation in progress"
        assert workflow["outcome_verification"] == "NOT_AN_OUTCOME"
        assert workflow["verified_outcome"] is False

        assert summary["status"] == "EVALUATION_ACTIVE"
        assert summary["activation_requirements"] == {
            "profile_ready": True,
            "market_data_available": True,
            "first_relevant_shortlist_generated": True,
        }
        assert metrics["TRIAL_ACTIVATION_RATE"] == 1
        assert metrics["VALUE_EXPOSURE_RATE"] == 1
        assert metrics["TIME_TO_FIRST_VALUE_EXPOSURE_SECONDS"] == 120

        # RETURN/READ is not FIRST_VERIFIED_VALUE and unchanged viewing is not
        # REPEAT_VALUE. No new event is inserted merely because the customer came back.
        assert metrics["FIRST_VERIFIED_VALUE_RECORDED"] is False
        assert metrics["TIME_TO_FIRST_VALUE_SECONDS"] is None
        assert metrics["TIME_TO_FIRST_VERIFIED_VALUE_SECONDS"] is None
        assert metrics["REPEAT_VALUE_RECORDED"] is False
        assert metrics["TIME_TO_FIRST_REPEAT_VALUE_SECONDS"] is None
        assert metrics["repeat_value_semantics"] == "REQUIRES_CANONICAL_VERIFIED_VALUE_AND_NEW_VALUE_EVENT"
        assert metrics["measured_value_event_count"] == 0
        assert metrics["estimated_value_event_count"] == 0
        assert event_count_after_return == event_count_before_leave
    finally:
        returned.close()


def test_repeated_unchanged_reads_never_become_repeat_value(monkeypatch, tmp_path):
    from account_registry import get_account
    from evaluation_policy import evaluation_metrics

    db_path = tmp_path / "repeat-value-negative.db"
    created, event_count_before = _seed_customer_state(monkeypatch, db_path)

    conn = _conn(db_path)
    try:
        account = get_account(conn, ACCOUNT_ID)
        first_return = evaluation_metrics(conn, account, now=created + timedelta(days=1))
        second_return = evaluation_metrics(conn, account, now=created + timedelta(days=7))
        event_count_after = conn.execute(
            "SELECT COUNT(*) FROM evaluation_events WHERE account_id=?",
            (ACCOUNT_ID,),
        ).fetchone()[0]

        for metrics in (first_return, second_return):
            assert metrics["FIRST_VERIFIED_VALUE_RECORDED"] is False
            assert metrics["REPEAT_VALUE_RECORDED"] is False
            assert metrics["TIME_TO_FIRST_REPEAT_VALUE_SECONDS"] is None
            assert metrics["repeat_value_semantics"] == "REQUIRES_CANONICAL_VERIFIED_VALUE_AND_NEW_VALUE_EVENT"
        assert event_count_after == event_count_before
    finally:
        conn.close()


def test_return_read_is_tenant_scoped_and_does_not_leak_previous_work(monkeypatch, tmp_path):
    from opportunity_workflow import get_workflow

    db_path = tmp_path / "return-tenant.db"
    _seed_customer_state(monkeypatch, db_path)

    conn = _conn(db_path)
    try:
        owner = get_workflow(conn, ACCOUNT_ID, SOURCE, EXTERNAL_ID)
        other = get_workflow(conn, "synthetic-other-company", SOURCE, EXTERNAL_ID)
        assert owner["status"] == "PREPARING"
        assert owner["note"] == "proposal preparation in progress"
        assert other["status"] == "NEW"
        assert other["note"] is None
        assert other["verified_outcome"] is False
    finally:
        conn.close()
