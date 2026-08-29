import app
from company_profile import save_profile
from decision_log import record_decision
from notification_events import (
    reconcile_push_receipts,
    record_new_opportunities,
    register_push_device,
    submit_pending_pushes,
)
from opportunity_match_pipeline import RULE_VERSION
from signal_store import persist_signal_records


ACCOUNT = "pending-rate-retry-account"
SOURCE = "TED"
EXTERNAL_ID = "pending-rate-retry-1"


def _signal(title, deadline, updated):
    return {
        "source": SOURCE,
        "signal_type": "TENDER",
        "external_id": EXTERNAL_ID,
        "title": title,
        "description": "Synthetic rate retry currentness probe",
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


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_rate_limited_retry_is_suppressed_after_canonical_revision(monkeypatch, tmp_path):
    db_path = tmp_path / "pending-rate-retry.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    monkeypatch.setattr(app, "DB", str(db_path))
    app.init_db()
    save_profile(
        {
            "name": "Pending rate retry company",
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
        persist_signal_records(
            conn,
            [_signal("Original scope", "2099-10-01", "2026-08-01T00:00:00+00:00")],
        )
        cur = conn.execute(
            """INSERT INTO tenders(
                source,external_id,title,description,buyer,country,cpv,value,deadline,
                publication_date,url,score,first_seen,last_seen
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
            (
                SOURCE, EXTERNAL_ID, "Original scope",
                "Synthetic rate retry currentness probe", "Synthetic buyer",
                "PRT", "45200000", "100000 EUR", "2099-10-01",
                "2026-08-01", "https://example.invalid/pending-rate-retry", 90,
            ),
        )
        tender_id = cur.lastrowid
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
        assert len(record_new_opportunities(conn, account_id=ACCOUNT, min_score=75)) == 1
        register_push_device(
            conn,
            ACCOUNT,
            "installation-rate-retry",
            "ExpoPushToken[rate-retry]",
            "android",
        )

        initial_calls = []

        def initial_post(*args, **kwargs):
            initial_calls.append((args, kwargs))
            return _Response({"data": [{"status": "ok", "id": "ticket-rate-retry"}]})

        assert submit_pending_pushes(conn, ACCOUNT, post=initial_post) == 1
        assert len(initial_calls) == 1

        assert reconcile_push_receipts(
            conn,
            ACCOUNT,
            min_age_seconds=0,
            post=lambda *_args, **_kwargs: _Response({
                "data": {
                    "ticket-rate-retry": {
                        "status": "error",
                        "message": "rate exceeded",
                        "details": {"error": "MessageRateExceeded"},
                    }
                }
            }),
        ) == 1
        delivery = conn.execute(
            "SELECT id,attempt_count,ticket_id,submitted_at,last_error,next_attempt_at,failed_at FROM push_deliveries"
        ).fetchone()
        assert delivery["attempt_count"] == 1
        assert delivery["ticket_id"] is None
        assert delivery["submitted_at"] is None
        assert delivery["last_error"] == "MessageRateExceeded"
        assert delivery["next_attempt_at"]
        assert delivery["failed_at"] is None

        persist_signal_records(
            conn,
            [_signal("Materially revised scope", "2099-09-01", "2026-08-10T00:00:00+00:00")],
        )
        conn.execute(
            "UPDATE push_deliveries SET next_attempt_at=datetime('now','-1 second') WHERE id=?",
            (delivery["id"],),
        )
        conn.commit()

        retry_calls = []

        def retry_post(*args, **kwargs):
            retry_calls.append((args, kwargs))
            return _Response({"data": [{"status": "ok", "id": "ticket-stale-retry"}]})

        assert submit_pending_pushes(conn, ACCOUNT, post=retry_post) == 0
        assert retry_calls == []
        final = conn.execute(
            "SELECT attempt_count,ticket_id,submitted_at,last_error,failed_at FROM push_deliveries WHERE id=?",
            (delivery["id"],),
        ).fetchone()
        assert final["attempt_count"] == 1
        assert final["ticket_id"] is None
        assert final["submitted_at"] is None
        assert final["last_error"] == "MessageRateExceeded"
        assert final["failed_at"] is None
        assert conn.execute(
            "SELECT COUNT(*) FROM push_deliveries WHERE event_id=(SELECT id FROM opportunity_events WHERE account_id=? AND tender_id=?)",
            (ACCOUNT, tender_id),
        ).fetchone()[0] == 1
    finally:
        conn.close()
