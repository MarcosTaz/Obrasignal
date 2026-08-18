"""End-to-end-ish test for ingestion -> profile scoring -> event creation.

The test isolates the external source fetch and exercises the real sync wrapper
and notification event implementation against a temporary SQLite database.
"""
import sqlite3
from datetime import datetime, timezone

import preload


def _profile():
    return {
        "activity": "estruturas metálicas, pavilhões e serralharia industrial",
        "countries": ["PT", "ES", "FR"],
        "keywords": ["estruturas metálicas", "pavilhões", "serralharia industrial"],
        "exclude_keywords": ["arquitetura", "fiscalização"],
        "cpv_prefixes": ["4522"],
        "min_value": 100000,
        "max_value": 2000000,
    }


def test_pipeline_scores_and_deduplicates(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE tenders(
        id INTEGER PRIMARY KEY,
        source TEXT, external_id TEXT, title TEXT, description TEXT,
        buyer TEXT, country TEXT, cpv TEXT, value TEXT, deadline TEXT,
        first_seen TEXT, score INTEGER, priority_label TEXT,
        priority_class TEXT, match_reason TEXT
    )""")
    conn.execute(
        """INSERT INTO tenders(
            id, source, external_id, title, description, buyer, country,
            cpv, value, first_seen, score
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (1, "TED", "2026/S-123456", "Construção de pavilhão industrial em estruturas metálicas",
         "Fabrico e montagem de estrutura metálica", "Município", "ES",
         "45223200", "850000", datetime.now(timezone.utc).isoformat(), 70),
    )
    monkeypatch.setattr(preload, "load_profile", _profile, raising=False)
    monkeypatch.setattr("profile_scoring.load_profile", _profile)

    preload._apply_profile_scores(conn)
    row = conn.execute("SELECT score, profile_score, global_score FROM tenders WHERE id=1").fetchone()
    assert row[0] >= 90
    assert row[1] == row[0]
    assert row[2] == 70

    from notification_events import record_new_opportunities
    first = record_new_opportunities(conn, min_score=75)
    second = record_new_opportunities(conn, min_score=75)
    assert len(first) == 1
    assert len(second) == 0
    assert conn.execute("SELECT COUNT(*) FROM opportunity_events").fetchone()[0] == 1
    conn.close()
