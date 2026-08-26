"""Decision-quality invariants for current-authority Radar ranking."""

import sqlite3

from decision_log import ensure_decision_table, record_decision
from lifecycle_read_model import _ranked_radar_rows
from opportunity_lifecycle import ensure_lifecycle_table
from opportunity_match_pipeline import RULE_VERSION
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


def _record(conn, external_id, decision, reason, score, account_id):
    record_decision(
        conn,
        "TEST",
        external_id,
        decision,
        reason,
        score=score,
        account_id=account_id,
        rule_version=RULE_VERSION,
    )


def test_radar_top_k_follows_current_account_score_not_legacy_global_score():
    conn = _conn()
    _insert(conn, "legacy-winner", 99)
    _insert(conn, "account-winner", 10)
    _insert(conn, "unknown", 100)

    _record(conn, "legacy-winner", "REJECT", "poor fit for A", 15, "account-a")
    _record(conn, "account-winner", "QUALIFIED", "strong fit for A", 92, "account-a")

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

    _record(conn, "alpha", "REJECT", "A dislikes alpha", 20, "account-a")
    _record(conn, "beta", "QUALIFIED", "A likes beta", 90, "account-a")
    _record(conn, "alpha", "QUALIFIED", "B likes alpha", 95, "account-b")
    _record(conn, "beta", "REJECT", "B dislikes beta", 10, "account-b")

    rows_a = _ranked_radar_rows(conn, "account-a", minscore=0, limit=10)
    rows_b = _ranked_radar_rows(conn, "account-b", minscore=0, limit=10)

    assert [row["external_id"] for row in rows_a] == ["beta", "alpha"]
    assert [row["external_id"] for row in rows_b] == ["alpha", "beta"]


def test_positive_minscore_cannot_borrow_legacy_or_missing_account_score():
    conn = _conn()
    _insert(conn, "legacy-high-account-low", 99)
    _insert(conn, "account-high", 5)
    _insert(conn, "no-account-decision", 100)

    _record(conn, "legacy-high-account-low", "REJECT", "account evidence is low", 20, "account-a")
    _record(conn, "account-high", "QUALIFIED", "account evidence is high", 88, "account-a")

    rows = _ranked_radar_rows(conn, "account-a", minscore=75, limit=10)

    assert [row["external_id"] for row in rows] == ["account-high"]


def test_latest_current_account_decision_controls_ranking():
    conn = _conn()
    _insert(conn, "changed", 50)
    _insert(conn, "steady", 50)

    _record(conn, "changed", "QUALIFIED", "old", 99, "account-a")
    _record(conn, "steady", "QUALIFIED", "current", 80, "account-a")
    _record(conn, "changed", "REJECT", "new", 10, "account-a")

    rows = _ranked_radar_rows(conn, "account-a", minscore=0, limit=10)

    assert [row["external_id"] for row in rows] == ["steady", "changed"]


def test_equal_current_account_scores_have_stable_technical_tie_break():
    conn = _conn()
    _insert(conn, "zeta", 5, publication_date="2026-08-25")
    _insert(conn, "alpha", 99, publication_date="2026-08-25")

    _record(conn, "zeta", "REVIEW", "tie", 80, "account-a")
    _record(conn, "alpha", "REVIEW", "tie", 80, "account-a")

    first = _ranked_radar_rows(conn, "account-a", minscore=0, limit=10)
    second = _ranked_radar_rows(conn, "account-a", minscore=0, limit=10)

    assert [row["external_id"] for row in first] == ["alpha", "zeta"]
    assert [row["external_id"] for row in second] == ["alpha", "zeta"]


def test_superseded_rule_latest_decision_cannot_enter_current_positive_top_k():
    conn = _conn()
    _insert(conn, "stale-rule", 99)
    _record(conn, "stale-rule", "QUALIFIED", "current historical row", 85, "account-a")
    record_decision(
        conn,
        "TEST",
        "stale-rule",
        "QUALIFIED",
        "superseded semantics",
        score=99,
        account_id="account-a",
        rule_version="superseded-rule",
    )

    assert _ranked_radar_rows(conn, "account-a", minscore=75, limit=10) == []
    unknown = _ranked_radar_rows(conn, "account-a", minscore=0, limit=10)
    assert [row["external_id"] for row in unknown] == ["stale-rule"]
    assert enrich_rows(conn, unknown, account_id="account-a")[0]["decision_summary"]["score"] is None


def test_stale_profile_latest_decision_cannot_enter_current_positive_top_k():
    conn = _conn()
    _insert(conn, "stale-profile", 100)
    _record(conn, "stale-profile", "QUALIFIED", "old profile", 97, "account-a")
    conn.execute(
        "UPDATE opportunity_decisions SET profile_fingerprint='sha256:stale-profile' WHERE account_id='account-a' AND external_id='stale-profile'"
    )
    conn.commit()

    assert _ranked_radar_rows(conn, "account-a", minscore=75, limit=10) == []
    unknown = _ranked_radar_rows(conn, "account-a", minscore=0, limit=10)
    assert [row["external_id"] for row in unknown] == ["stale-profile"]


def test_stale_latest_does_not_resurrect_older_current_decision():
    conn = _conn()
    _insert(conn, "no-resurrection", 100)
    _record(conn, "no-resurrection", "QUALIFIED", "older current", 91, "account-a")
    record_decision(
        conn,
        "TEST",
        "no-resurrection",
        "QUALIFIED",
        "latest but stale",
        score=99,
        account_id="account-a",
        rule_version="superseded-rule",
    )

    assert _ranked_radar_rows(conn, "account-a", minscore=75, limit=10) == []
