from concurrent.futures import ThreadPoolExecutor

import app
from company_profile import save_profile
from decision_log import record_decision
from notification_events import record_new_opportunities
from opportunity_match_pipeline import RULE_VERSION
from opportunity_workflow import get_saved_opportunity, save_opportunity, update_saved_opportunity
from signal_store import persist_signal_records


ACCOUNT = "g11-idempotency-account"
SOURCE = "TED"
EXTERNAL_ID = "g11-idempotency-1"


def _signal():
    return {
        "source": SOURCE,
        "signal_type": "TENDER",
        "external_id": EXTERNAL_ID,
        "title": "G11 synthetic idempotency opportunity",
        "description": "Synthetic composed retry proof",
        "buyer": "Synthetic buyer",
        "country": "PRT",
        "cpv": "45200000",
        "value": "100000 EUR",
        "value_numeric": 100000,
        "currency": "EUR",
        "deadline": "2099-12-31",
        "procedure_type": "OPEN",
        "locations": [{"country": "PRT"}],
        "source_updated_at": "2026-08-29T19:00:00+00:00",
    }


def test_g11_duplicate_event_and_watchlist_retries_converge_to_one_canonical_state(monkeypatch, tmp_path):
    path = tmp_path / "g11-idempotency.sqlite"
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    monkeypatch.setattr(app, "DB", str(path))
    app.init_db()
    save_profile(
        {
            "name": "G11 Synthetic Contractor",
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
        persist_signal_records(conn, [_signal()])
        tender_id = conn.execute(
            """INSERT INTO tenders(
                source,external_id,title,description,buyer,country,cpv,value,deadline,
                publication_date,url,score,first_seen,last_seen
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
            (
                SOURCE, EXTERNAL_ID, "G11 synthetic idempotency opportunity",
                "Synthetic composed retry proof", "Synthetic buyer", "PRT", "45200000",
                "100000 EUR", "2099-12-31", "2026-08-29",
                "https://example.invalid/g11", 91,
            ),
        ).lastrowid
        conn.commit()
        record_decision(
            conn,
            SOURCE,
            EXTERNAL_ID,
            "QUALIFIED",
            "current synthetic decision",
            score=91,
            features={"profile_score": 91},
            rule_version=RULE_VERSION,
            account_id=ACCOUNT,
        )

        first = record_new_opportunities(conn, account_id=ACCOUNT, min_score=75)
        second = record_new_opportunities(conn, account_id=ACCOUNT, min_score=75)
        third = record_new_opportunities(conn, account_id=ACCOUNT, min_score=75)
        assert len(first) == 1
        assert second == []
        assert third == []
        assert conn.execute(
            "SELECT COUNT(*) FROM opportunity_events WHERE account_id=? AND tender_id=? AND event_type='new_high_match'",
            (ACCOUNT, tender_id),
        ).fetchone()[0] == 1
    finally:
        conn.close()

    workers = 10

    def retry_save(_index):
        local = app.db()
        try:
            item = save_opportunity(local, ACCOUNT, tender_id)
            return item["saved_at"]
        finally:
            local.close()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        saved_ats = list(pool.map(retry_save, range(workers)))

    assert len(set(saved_ats)) == 1

    conn = app.db()
    try:
        rows = conn.execute(
            """SELECT account_id,source,external_id,status,note,priority,saved_at
               FROM opportunity_workflow WHERE account_id=? AND source=? AND external_id=?""",
            (ACCOUNT, SOURCE, EXTERNAL_ID),
        ).fetchall()
        assert len(rows) == 1
        original_saved_at = rows[0]["saved_at"]
        assert original_saved_at

        updated = update_saved_opportunity(
            conn,
            ACCOUNT,
            tender_id,
            status="REVIEWING",
            priority="HIGH",
            note="one canonical pursuit state",
            note_provided=True,
        )
        assert updated["status"] == "REVIEWING"
        assert updated["priority"] == "HIGH"
        assert updated["note"] == "one canonical pursuit state"

        for _ in range(5):
            retried = save_opportunity(conn, ACCOUNT, tender_id)
            assert retried["saved_at"] == original_saved_at
            assert retried["status"] == "REVIEWING"
            assert retried["priority"] == "HIGH"
            assert retried["note"] == "one canonical pursuit state"

        final = get_saved_opportunity(conn, ACCOUNT, tender_id)
        assert final["saved_at"] == original_saved_at
        assert final["status"] == "REVIEWING"
        assert final["priority"] == "HIGH"
        assert final["note"] == "one canonical pursuit state"
        assert conn.execute(
            "SELECT COUNT(*) FROM opportunity_workflow WHERE account_id=? AND source=? AND external_id=?",
            (ACCOUNT, SOURCE, EXTERNAL_ID),
        ).fetchone()[0] == 1
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()
