import json
import sqlite3

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
