"""Decision-quality invariants for the decision-aware Radar candidate ranking."""

import sqlite3

from decision_log import ensure_decision_table, record_decision
from lifecycle_read_model import _ranked_radar_rows
from opportunity_lifecycle import ensure_lifecycle_table
from radar_decision_feed import enrich_rows


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE tenders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            score INTEGER,
            title TEXT,
            deadline TEXT,
            publication_date TEXT
        )"""
    )
    ensure_lifecycle_table(conn)
    ensure_decision_table(conn)
    return conn


def _insert(conn, external_id, legacy_score, publication_date="2026-08-25"):
    conn.execute(
        "INSERT INTO tenders(source,external_id,score,title,deadline,publication_date) VALUES(?,?,?,?,?,?)",
        ("TEST", external_id, legacy_score, external_id, "2099-01-01T12:00:00+00:00", publication_date),
    )
    conn.commit()


def test_radar_top_k_follows_account_score_not_legacy_global_score():
    conn = _conn()
    _insert(conn, "legacy-winner", 99)
    _insert(conn, "account-winner", 10)
    _insert(conn, "unknown", 100)

    record_decision(conn, "TEST", "legacy-winner", "REJECT", "poor fit for A", score=15, account_id="account-a")
    record_decision(conn, "TEST", "account-winner", "QUALIFIED", "strong fit for A", score=92, account_id="account-a")

    rows = _ranked_radar_rows(conn, "account-a", minscore=0, limit=10)
    items = enrich_rows(conn, rows, account_id="account-a")

    assert [item["external_id"] for item in items] == [
        "account-winner",
        "legacy-winner",
        "unknown",
    ]
    assert [item["decision_summary"]["score"] for item in items] == [92, 15, None]


def test_same_candidates_rank_differently_for_two_accounts_without_cross_tenant_leakage():
    conn = _conn()
    _insert(conn, "alpha", 50)
    _insert(conn, "beta", 50)

    record_decision(conn, "TEST", "alpha", "REJECT", "A dislikes alpha", score=20, account_id="account-a")
    record_decision(conn, "TEST", "beta", "QUALIFIED", "A likes beta", score=90, account_id="account-a")
    record_decision(conn, "TEST", "alpha", "QUALIFIED", "B likes alpha", score=95, account_id="account-b")
    record_decision(conn, "TEST", "beta", "REJECT", "B dislikes beta", score=10, account_id="account-b")

    rows_a = _ranked_radar_rows(conn, "account-a", minscore=0, limit=10)
    rows_b = _ranked_radar_rows(conn, "account-b", minscore=0, limit=10)

    assert [row["external_id"] for row in rows_a] == ["beta", "alpha"]
    assert [row["external_id"] for row in rows_b] == ["alpha", "beta"]


def test_positive_minscore_does_not_coerce_legacy_or_missing_score_into_account_fit():
    conn = _conn()
    _insert(conn, "legacy-high-account-low", 99)
    _insert(conn, "account-high", 5)
    _insert(conn, "no-account-decision", 100)

    record_decision(
        conn,
        "TEST",
        "legacy-high-account-low",
        "REJECT",
        "account evidence is low",
        score=20,
        account_id="account-a",
    )
    record_decision(
        conn,
        "TEST",
        "account-high",
        "QUALIFIED",
        "account evidence is high",
        score=88,
        account_id="account-a",
    )

    rows = _ranked_radar_rows(conn, "account-a", minscore=75, limit=10)

    assert [row["external_id"] for row in rows] == ["account-high"]


def test_radar_uses_latest_account_decision_only():
    conn = _conn()
    _insert(conn, "changed", 50)
    _insert(conn, "steady", 50)

    record_decision(conn, "TEST", "changed", "QUALIFIED", "old", score=99, account_id="account-a")
    record_decision(conn, "TEST", "steady", "QUALIFIED", "current", score=80, account_id="account-a")
    record_decision(conn, "TEST", "changed", "REJECT", "new", score=10, account_id="account-a")

    rows = _ranked_radar_rows(conn, "account-a", minscore=0, limit=10)

    assert [row["external_id"] for row in rows] == ["steady", "changed"]


def test_equal_account_scores_have_stable_technical_tie_break():
    conn = _conn()
    # Insert in the opposite order of the expected stable external-id tie break.
    _insert(conn, "zeta", 5, publication_date="2026-08-25")
    _insert(conn, "alpha", 99, publication_date="2026-08-25")

    record_decision(conn, "TEST", "zeta", "REVIEW", "tie", score=80, account_id="account-a")
    record_decision(conn, "TEST", "alpha", "REVIEW", "tie", score=80, account_id="account-a")

    first = _ranked_radar_rows(conn, "account-a", minscore=0, limit=10)
    second = _ranked_radar_rows(conn, "account-a", minscore=0, limit=10)

    assert [row["external_id"] for row in first] == ["alpha", "zeta"]
    assert [row["external_id"] for row in second] == ["alpha", "zeta"]
