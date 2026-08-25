import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from opportunity_outcome import (
    OutcomeIdempotencyConflict,
    OutcomeNotFound,
    OutcomeValidationError,
    correct_outcome,
    current_outcome,
    ensure_outcome_table,
    official_award_candidate,
    outcome_history,
    record_outcome,
)


def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        '''CREATE TABLE tenders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            title TEXT,
            value TEXT,
            UNIQUE(source, external_id)
        )'''
    )
    conn.execute(
        "INSERT INTO tenders(source, external_id, title, value) VALUES('TED','OPP-1','Bridge','999999')"
    )
    conn.execute(
        "INSERT INTO tenders(source, external_id, title, value) VALUES('TED','OPP-2','School','1200000')"
    )
    conn.commit()
    return conn


def record(conn, outcome_type, **kwargs):
    return record_outcome(
        conn,
        account_id=kwargs.pop("account_id", "company-a"),
        source="TED",
        external_id=kwargs.pop("external_id", "OPP-1"),
        outcome_type=outcome_type,
        **kwargs,
    )


@pytest.mark.parametrize(
    "outcome_type",
    ["BID_SUBMITTED", "NO_SUBMISSION", "WITHDRAWN", "CANCELLED", "UNKNOWN"],
)
def test_core_outcome_types_are_recordable_without_collapsing_semantics(outcome_type):
    conn = db()
    item, created = record(conn, outcome_type)
    assert created is True
    assert item["outcome_type"] == outcome_type
    assert item["source_type"] == "USER_CONFIRMED"


def test_won_official_requires_provenance_and_keeps_actual_award_value_separate():
    conn = db()
    before = dict(conn.execute("SELECT * FROM tenders WHERE external_id='OPP-1'").fetchone())
    item, created = record(
        conn,
        "WON",
        source_type="OFFICIAL_SOURCE",
        source_ref="https://official.example/award/77",
        source_publication="Official awards bulletin",
        source_native_id="AWARD-77",
        award_value="875000.50",
        currency="EUR",
        evidence_refs=["award:AWARD-77"],
    )
    after = dict(conn.execute("SELECT * FROM tenders WHERE external_id='OPP-1'").fetchone())
    assert created is True
    assert item["source_type"] == "OFFICIAL_SOURCE"
    assert item["award_value"] == "875000.5"
    assert item["currency"] == "EUR"
    assert before == after
    assert before["value"] == "999999"


def test_won_user_confirmed_is_not_mislabeled_official():
    conn = db()
    item, _ = record(conn, "WON", award_value="100", currency="GBP")
    assert item["source_type"] == "USER_CONFIRMED"
    assert item["award_value"] == "100"


def test_lost_official_and_user_confirmed_remain_distinct():
    conn = db()
    official, _ = record(
        conn,
        "LOST",
        source_type="OFFICIAL_SOURCE",
        source_native_id="RESULT-1",
        evidence_refs=["official-result:1"],
    )
    user, _ = record(conn, "LOST", external_id="OPP-2", reason_code="PRICE")
    assert official["source_type"] == "OFFICIAL_SOURCE"
    assert user["source_type"] == "USER_CONFIRMED"
    assert user["reason_code"] == "PRICE"


def test_outcome_can_exist_without_decision():
    conn = db()
    item, _ = record(conn, "BID_SUBMITTED")
    assert item["decision_id"] is None


def test_decision_reference_is_optional_but_cross_tenant_or_wrong_opportunity_is_rejected():
    conn = db()
    conn.execute(
        '''CREATE TABLE opportunity_pursuit_decisions(
            decision_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            opportunity_id INTEGER NOT NULL
        )'''
    )
    conn.execute(
        "INSERT INTO opportunity_pursuit_decisions VALUES('D-1','company-a',1)"
    )
    conn.commit()
    item, _ = record(conn, "BID_SUBMITTED", decision_id="D-1")
    assert item["decision_id"] == "D-1"
    with pytest.raises(OutcomeValidationError):
        record(conn, "BID_SUBMITTED", external_id="OPP-2", decision_id="D-1")
    with pytest.raises(OutcomeValidationError):
        record(conn, "BID_SUBMITTED", account_id="company-b", decision_id="D-1")


def test_decision_reference_fails_closed_when_parallel_journal_not_integrated():
    conn = db()
    with pytest.raises(OutcomeValidationError, match="not available"):
        record(conn, "BID_SUBMITTED", decision_id="parallel-branch-id")


def test_current_outcome_and_history_preserve_correction():
    conn = db()
    first, _ = record(conn, "UNKNOWN", idempotency_key="first")
    corrected, created = correct_outcome(
        conn,
        account_id="company-a",
        outcome_id=first["outcome_id"],
        outcome_type="LOST",
        reason_code="PRICE",
        idempotency_key="correction-1",
    )
    assert created is True
    assert corrected["supersedes_outcome_id"] == first["outcome_id"]
    assert current_outcome(conn, "company-a", "TED", "OPP-1")["outcome_type"] == "LOST"
    history = outcome_history(conn, "company-a", "TED", "OPP-1")
    assert [row["outcome_type"] for row in history] == ["UNKNOWN", "LOST"]
    assert [row["status"] for row in history] == ["SUPERSEDED", "CURRENT"]


def test_correction_cannot_cross_tenant_or_change_lot_scope():
    conn = db()
    first, _ = record(conn, "UNKNOWN", lot_id="LOT-1")
    with pytest.raises(OutcomeNotFound):
        correct_outcome(conn, account_id="company-b", outcome_id=first["outcome_id"], outcome_type="WON")
    with pytest.raises(OutcomeValidationError):
        record_outcome(
            conn,
            account_id="company-a",
            source="TED",
            external_id="OPP-1",
            lot_id="LOT-2",
            outcome_type="WON",
            supersedes_outcome_id=first["outcome_id"],
        )


def test_tenant_isolation_read_and_history():
    conn = db()
    record(conn, "WON", account_id="company-a", award_value="50", currency="EUR")
    record(conn, "LOST", account_id="company-b")
    assert current_outcome(conn, "company-a", "TED", "OPP-1")["outcome_type"] == "WON"
    assert current_outcome(conn, "company-b", "TED", "OPP-1")["outcome_type"] == "LOST"
    assert len(outcome_history(conn, "company-a", "TED", "OPP-1")) == 1


def test_idempotent_retry_does_not_duplicate_and_conflicting_retry_is_rejected():
    conn = db()
    first, created1 = record(conn, "NO_SUBMISSION", idempotency_key="retry-1")
    second, created2 = record(conn, "NO_SUBMISSION", idempotency_key="retry-1")
    assert created1 is True and created2 is False
    assert first["outcome_id"] == second["outcome_id"]
    with pytest.raises(OutcomeIdempotencyConflict):
        record(conn, "WON", idempotency_key="retry-1", award_value="1", currency="EUR")


def test_duplicate_official_event_is_suppressed_without_client_idempotency_key():
    conn = db()
    kwargs = dict(
        source_type="OFFICIAL_SOURCE",
        source_native_id="AW-9",
        source_ref="official:AW-9",
        award_value="10",
        currency="EUR",
    )
    first, created1 = record(conn, "WON", **kwargs)
    second, created2 = record(conn, "WON", **kwargs)
    assert created1 is True and created2 is False
    assert first["outcome_id"] == second["outcome_id"]


def test_missing_opportunity_and_invalid_outcome_fail_closed():
    conn = db()
    with pytest.raises(OutcomeNotFound):
        record(conn, "UNKNOWN", external_id="MISSING")
    with pytest.raises(OutcomeValidationError):
        record(conn, "GOOD_DECISION")


def test_future_occurred_at_is_rejected_but_historical_discovery_is_valid():
    conn = db()
    past = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    item, _ = record(conn, "LOST", occurred_at=past)
    assert item["occurred_at"].startswith(past[:10])
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    with pytest.raises(OutcomeValidationError, match="future"):
        record(conn, "LOST", external_id="OPP-2", occurred_at=future)


def test_money_validation_rejects_negative_nan_missing_currency_and_wrong_context():
    conn = db()
    for value in ("-1", "NaN", "Infinity"):
        with pytest.raises(OutcomeValidationError):
            record(conn, "WON", award_value=value, currency="EUR")
    with pytest.raises(OutcomeValidationError):
        record(conn, "WON", award_value="100")
    with pytest.raises(OutcomeValidationError):
        record(conn, "LOST", award_value="100", currency="EUR")


def test_lot_granularity_supports_win_and_loss_without_artificial_partial_win():
    conn = db()
    won, _ = record(conn, "WON", lot_id="LOT-A", award_value="100", currency="EUR")
    lost, _ = record(conn, "LOST", lot_id="LOT-B")
    assert current_outcome(conn, "company-a", "TED", "OPP-1", "LOT-A")["outcome_type"] == "WON"
    assert current_outcome(conn, "company-a", "TED", "OPP-1", "LOT-B")["outcome_type"] == "LOST"
    assert won["lot_id"] == "LOT-A" and lost["lot_id"] == "LOT-B"


def test_multi_currency_values_are_preserved_not_aggregated_or_converted():
    conn = db()
    eur, _ = record(conn, "WON", lot_id="EUR-LOT", award_value="100", currency="EUR")
    gbp, _ = record(conn, "WON", lot_id="GBP-LOT", award_value="90", currency="GBP")
    assert (eur["award_value"], eur["currency"]) == ("100", "EUR")
    assert (gbp["award_value"], gbp["currency"]) == ("90", "GBP")


def test_exact_official_identifier_match_can_create_win_candidate():
    candidate = official_award_candidate(
        account_identifiers=["GB-COH:12345678"],
        winner_identifiers=["GB-COH:12345678"],
        source_native_id="award-1",
        source_ref="official:award-1",
        award_value="42",
        currency="GBP",
    )
    assert candidate["outcome_type"] == "WON"
    assert candidate["source_type"] == "OFFICIAL_SOURCE"


def test_false_win_similar_company_name_has_no_identifier_match_path():
    # Names are deliberately not accepted by the adapter. Different canonical
    # identifiers stay different even if a caller believes names look similar.
    candidate = official_award_candidate(
        account_identifiers=["GB-COH:111"],  # ABC Construction Services Ltd
        winner_identifiers=["GB-COH:222"],  # ABC Construction Ltd
        source_native_id="award-2",
        source_ref="official:award-2",
    )
    assert candidate is None


def test_same_local_identifier_in_different_jurisdiction_is_not_a_match():
    candidate = official_award_candidate(
        account_identifiers=["PT-NIF:123456789"],
        winner_identifiers=["ES-NIF:123456789"],
        source_native_id="award-3",
        source_ref="official:award-3",
    )
    assert candidate is None


def test_false_loss_absence_or_another_winner_does_not_create_lost():
    no_award = official_award_candidate(
        account_identifiers=["PT-NIF:1"],
        winner_identifiers=[],
    )
    another_winner = official_award_candidate(
        account_identifiers=["PT-NIF:1"],
        winner_identifiers=["PT-NIF:2"],
        source_native_id="award-4",
        source_ref="official:award-4",
    )
    assert no_award is None
    assert another_winner is None


def test_pursue_without_further_evidence_does_not_create_outcome():
    conn = db()
    conn.execute(
        '''CREATE TABLE opportunity_pursuit_decisions(
            decision_id TEXT PRIMARY KEY, account_id TEXT, opportunity_id INTEGER, decision_type TEXT
        )'''
    )
    conn.execute("INSERT INTO opportunity_pursuit_decisions VALUES('D-PURSUE','company-a',1,'PURSUE')")
    conn.commit()
    assert current_outcome(conn, "company-a", "TED", "OPP-1") is None


def test_cancelled_procedure_candidate_is_cancelled_not_lost():
    candidate = official_award_candidate(
        account_identifiers=["PT-NIF:1"],
        procedure_cancelled=True,
        source_ref="official:cancellation-1",
        source_native_id="cancellation-1",
    )
    assert candidate["outcome_type"] == "CANCELLED"
    assert candidate["reason_code"] == "CANCELLED_PROCEDURE"
    assert candidate["source_type"] == "SYSTEM_DERIVED"


def test_official_or_derived_fact_without_provenance_is_rejected():
    conn = db()
    with pytest.raises(OutcomeValidationError, match="provenance"):
        record(conn, "WON", source_type="OFFICIAL_SOURCE", award_value="1", currency="EUR")
    with pytest.raises(OutcomeValidationError, match="provenance"):
        record(conn, "CANCELLED", source_type="SYSTEM_DERIVED")


def test_sql_injection_like_identity_and_xss_note_are_data_not_code():
    conn = db()
    hostile_id = "x'); DROP TABLE tenders; --"
    conn.execute("INSERT INTO tenders(source, external_id, title) VALUES(?,?,?)", ("TED", hostile_id, "safe"))
    conn.commit()
    item, _ = record_outcome(
        conn,
        account_id="company-a",
        source="TED",
        external_id=hostile_id,
        outcome_type="UNKNOWN",
        note="<script>alert('x')</script>",
    )
    assert item["note"] == "<script>alert('x')</script>"
    assert conn.execute("SELECT COUNT(*) FROM tenders").fetchone()[0] == 3


def test_oversized_and_control_character_notes_are_rejected():
    conn = db()
    with pytest.raises(OutcomeValidationError):
        record(conn, "UNKNOWN", note="x" * 1001)
    with pytest.raises(OutcomeValidationError):
        record(conn, "UNKNOWN", note="bad\x00note")


def test_migration_is_idempotent_and_does_not_change_tenders_schema():
    conn = db()
    before = [row[1] for row in conn.execute("PRAGMA table_info(tenders)").fetchall()]
    ensure_outcome_table(conn)
    ensure_outcome_table(conn)
    after = [row[1] for row in conn.execute("PRAGMA table_info(tenders)").fetchall()]
    assert before == after
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='opportunity_outcomes'"
    ).fetchone()
