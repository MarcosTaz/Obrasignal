from datetime import datetime, timezone
import json
import sqlite3

from decision_log import record_decision
from notification_events import record_new_opportunities
from opportunity_lifecycle import persist_lifecycle_observations
from opportunity_match_pipeline import RULE_VERSION
from signal_store import persist_signal_records


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE tenders(
        id INTEGER PRIMARY KEY,
        source TEXT NOT NULL,
        external_id TEXT NOT NULL,
        title TEXT,
        buyer TEXT,
        deadline TEXT,
        country TEXT,
        url TEXT,
        score INTEGER,
        first_seen TEXT
    )""")
    return conn


def _tender(conn, external_id="A-1", score=99):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO tenders VALUES(1,'TEST',?,?,NULL,'2099-01-01','PRT',NULL,?,?)",
        (external_id, "Obra relevante", score, now),
    )
    persist_signal_records(conn, [{
        "source": "TEST",
        "signal_type": "TENDER",
        "external_id": external_id,
        "title": "Obra relevante",
        "country": "PRT",
        "deadline": "2099-01-01",
    }])


def _relevant_features():
    return {
        "relevance": {
            "state": "RELEVANT",
            "evidence": [{"kind": "service", "value": "obra"}],
            "rule_version": "relevance-v1",
        },
        "relevant_shortlist_eligible": True,
    }


def test_global_tender_score_alone_cannot_create_customer_high_match():
    conn = _db()
    _tender(conn, score=100)
    assert record_new_opportunities(conn, account_id="tenant-a", min_score=75) == []


def test_current_explicitly_relevant_account_decision_creates_one_event_with_account_score():
    conn = _db()
    _tender(conn, score=100)
    record_decision(
        conn, "TEST", "A-1", "REVIEW", "tenant relevant", score=81,
        features=_relevant_features(), rule_version=RULE_VERSION, account_id="tenant-a",
    )
    events = record_new_opportunities(conn, account_id="tenant-a", min_score=75)
    assert len(events) == 1
    assert events[0]["score"] == 81
    assert record_new_opportunities(conn, account_id="tenant-a", min_score=75) == []
    assert record_new_opportunities(conn, account_id="tenant-b", min_score=75) == []


def test_stale_rule_or_unknown_relevance_cannot_create_high_match():
    for rule_version, features in (
        ("obsolete-rule", _relevant_features()),
        (RULE_VERSION, {"relevance": {"state": "UNKNOWN", "evidence": [], "rule_version": "relevance-v1"}, "relevant_shortlist_eligible": False}),
    ):
        conn = _db()
        _tender(conn)
        record_decision(
            conn, "TEST", "A-1", "QUALIFIED", "not authoritative", score=95,
            features=features, rule_version=rule_version, account_id="tenant-a",
        )
        assert record_new_opportunities(conn, account_id="tenant-a", min_score=75) == []


def test_material_canonical_opportunity_change_invalidates_queued_creation_authority():
    conn = _db()
    _tender(conn)
    record_decision(
        conn, "TEST", "A-1", "QUALIFIED", "T1 relevant", score=95,
        features=_relevant_features(), rule_version=RULE_VERSION, account_id="tenant-a",
    )
    persist_signal_records(conn, [{
        "source": "TEST",
        "signal_type": "TENDER",
        "external_id": "A-1",
        "title": "Escopo materialmente alterado",
        "country": "PRT",
        "deadline": "2099-01-01",
    }])
    assert record_new_opportunities(conn, account_id="tenant-a", min_score=75) == []


def test_explicitly_closed_lifecycle_blocks_current_relevant_event():
    conn = _db()
    _tender(conn)
    record_decision(
        conn, "TEST", "A-1", "QUALIFIED", "relevant but closed", score=95,
        features=_relevant_features(), rule_version=RULE_VERSION, account_id="tenant-a",
    )
    persist_lifecycle_observations(conn, [{
        "source": "TEST",
        "external_id": "A-1",
        "is_actionable": False,
        "lifecycle_status": "cancelled",
    }])
    assert record_new_opportunities(conn, account_id="tenant-a", min_score=75) == []
