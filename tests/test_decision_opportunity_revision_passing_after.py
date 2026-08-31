import json
import sqlite3

import account_onboarding
import app
from company_profile import save_profile
from decision_dashboard import get_presented_decision
from decision_log import latest_current_decision, record_decision
from opportunity_match_pipeline import RULE_VERSION
from radar_decision_feed import enrich_rows
from signal_store import persist_signal_records


ACCOUNT = "revision-account"
SOURCE = "TED"
EXTERNAL_ID = "revision-1"


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE company_profiles(
            account_id TEXT PRIMARY KEY,
            profile_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        "INSERT INTO company_profiles(account_id,profile_json,updated_at) VALUES (?,?,?)",
        (ACCOUNT, json.dumps({"services": ["construction"]}), "2026-08-29T00:00:00+00:00"),
    )
    return conn


def _signal(title="Original scope", deadline="2026-10-01", updated="2026-08-01T00:00:00+00:00"):
    return {
        "source": SOURCE,
        "signal_type": "TENDER",
        "external_id": EXTERNAL_ID,
        "title": title,
        "description": "Synthetic scope",
        "buyer": "Synthetic buyer",
        "country": "PRT",
        "cpv": "45200000",
        "value": "100000 EUR",
        "value_numeric": 100000,
        "currency": "EUR",
        "deadline": deadline,
        "procedure_type": "OPEN",
        "locations": [{"country": "PRT"}],
        "source_updated_at": updated,
    }


def _record(conn):
    record_decision(
        conn,
        SOURCE,
        EXTERNAL_ID,
        "QUALIFIED",
        "current at T1",
        score=90,
        features={"profile_score": 90},
        rule_version=RULE_VERSION,
        account_id=ACCOUNT,
    )


def test_timestamp_only_refresh_keeps_content_bound_decision_current():
    conn = _conn()
    persist_signal_records(conn, [_signal(updated="2026-08-01T00:00:00+00:00")])
    _record(conn)
    assert latest_current_decision(
        conn, SOURCE, EXTERNAL_ID, account_id=ACCOUNT, expected_rule_version=RULE_VERSION
    ) is not None

    persist_signal_records(conn, [_signal(updated="2026-08-29T00:00:00+00:00")])
    assert latest_current_decision(
        conn, SOURCE, EXTERNAL_ID, account_id=ACCOUNT, expected_rule_version=RULE_VERSION
    ) is not None
    conn.close()


def test_material_revision_invalidates_detail_and_radar_presentation():
    conn = _conn()
    persist_signal_records(conn, [_signal()])
    _record(conn)

    current = get_presented_decision(conn, SOURCE, EXTERNAL_ID, account_id=ACCOUNT)
    assert current["status"] == "QUALIFIED"

    persist_signal_records(
        conn,
        [_signal(title="Revised electrical-heavy scope", deadline="2026-08-20", updated="2026-08-10T00:00:00+00:00")],
    )

    assert latest_current_decision(
        conn, SOURCE, EXTERNAL_ID, account_id=ACCOUNT, expected_rule_version=RULE_VERSION
    ) is None
    detail = get_presented_decision(conn, SOURCE, EXTERNAL_ID, account_id=ACCOUNT)
    assert detail["status"] == "SEM DECISÃO"
    radar = enrich_rows(
        conn,
        [{"source": SOURCE, "external_id": EXTERNAL_ID, "title": "Revised electrical-heavy scope"}],
        account_id=ACCOUNT,
    )
    assert radar[0]["decision_summary"]["status"] == "SEM DECISÃO"
    conn.close()


def test_malformed_canonical_snapshot_fails_currentness_closed():
    conn = _conn()
    persist_signal_records(conn, [_signal()])
    _record(conn)
    conn.execute(
        "UPDATE signal_records SET normalized_json='not-json' WHERE source=? AND signal_type='TENDER' AND external_id=?",
        (SOURCE, EXTERNAL_ID),
    )
    conn.commit()
    assert latest_current_decision(
        conn, SOURCE, EXTERNAL_ID, account_id=ACCOUNT, expected_rule_version=RULE_VERSION
    ) is None
    conn.close()


def test_stale_opportunity_revision_cannot_emit_bootstrap_event(monkeypatch, tmp_path):
    db_path = tmp_path / "revision-bootstrap.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    monkeypatch.setattr(app, "DB", str(db_path))
    app.init_db()
    save_profile(
        {
            "name": "Revision company",
            "activity": "construction",
            "coverage_mode": "portugal",
            "countries": ["PRT"],
            "cpv_prefixes": ["452"],
            "services": ["construction"],
            "capability_tags": ["construction"],
            "min_value": 1000,
            "max_value": 1000000,
        },
        account_id=ACCOUNT,
    )
    conn = app.db()
    try:
        persist_signal_records(conn, [_signal(deadline="2099-10-01")])
        conn.execute(
            """INSERT INTO tenders(
                source,external_id,title,description,buyer,country,cpv,value,deadline,
                publication_date,url,score,first_seen,last_seen
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
            (
                SOURCE, EXTERNAL_ID, "Original scope", "Synthetic scope",
                "Synthetic buyer", "PRT", "45200000", "100000 EUR", "2099-10-01",
                "2026-08-01", "https://example.invalid/revision", 90,
            ),
        )
        _record(conn)
        persist_signal_records(
            conn,
            [_signal(title="Materially revised scope", deadline="2099-09-01", updated="2026-08-10T00:00:00+00:00")],
        )
        assert account_onboarding._emit_bootstrap_events(conn, ACCOUNT) == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM opportunity_events WHERE account_id=? AND source=?",
            (ACCOUNT, SOURCE),
        ).fetchone()[0] == 0
    finally:
        conn.close()
