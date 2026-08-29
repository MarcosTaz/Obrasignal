import sqlite3

from opportunity_outcome import current_outcome, outcome_history, record_outcome


def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        '''CREATE TABLE tenders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            UNIQUE(source, external_id)
        )'''
    )
    conn.execute("INSERT INTO tenders(source, external_id) VALUES('TED','OPP-1')")
    conn.commit()
    return conn


def test_idempotency_is_stable_when_occurred_at_is_server_defaulted():
    conn = db()
    first, first_created = record_outcome(
        conn,
        account_id="account-a",
        source="TED",
        external_id="OPP-1",
        outcome_type="NO_SUBMISSION",
        idempotency_key="stable-default-time",
    )
    second, second_created = record_outcome(
        conn,
        account_id="account-a",
        source="TED",
        external_id="OPP-1",
        outcome_type="NO_SUBMISSION",
        idempotency_key="stable-default-time",
    )
    assert first_created is True
    assert second_created is False
    assert first["outcome_id"] == second["outcome_id"]
    assert first["occurred_at"] == second["occurred_at"]


def test_history_has_exactly_one_current_for_independent_observations():
    conn = db()
    record_outcome(
        conn,
        account_id="account-a",
        source="TED",
        external_id="OPP-1",
        outcome_type="BID_SUBMITTED",
    )
    latest, _ = record_outcome(
        conn,
        account_id="account-a",
        source="TED",
        external_id="OPP-1",
        outcome_type="WON",
        award_value="100",
        currency="EUR",
    )
    history = outcome_history(conn, "account-a", "TED", "OPP-1")
    assert [row["status"] for row in history] == ["HISTORICAL", "CURRENT"]
    assert current_outcome(conn, "account-a", "TED", "OPP-1")["outcome_id"] == latest["outcome_id"]
