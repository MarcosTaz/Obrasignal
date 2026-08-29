import app
from company_profile import save_profile
from decision_log import record_decision
from notification_events import record_new_opportunities, register_push_device, submit_pending_pushes
from opportunity_match_pipeline import RULE_VERSION
from signal_store import persist_signal_records


ACCOUNT = "pending-push-revision-account"
SOURCE = "TED"
EXTERNAL_ID = "pending-push-revision-1"


def _signal(title, deadline, updated):
    return {
        "source": SOURCE,
        "signal_type": "TENDER",
        "external_id": EXTERNAL_ID,
        "title": title,
        "description": "Synthetic pending-push currentness probe",
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


class _FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"data": [{"status": "ok", "id": "ticket-stale-pending-probe"}]}


def test_pending_push_is_not_submitted_after_canonical_opportunity_revision(monkeypatch, tmp_path):
    db_path = tmp_path / "pending-push-currentness.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    monkeypatch.setattr(app, "DB", str(db_path))
    app.init_db()
    save_profile(
        {
            "name": "Pending push revision company",
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
                "Synthetic pending-push currentness probe", "Synthetic buyer",
                "PRT", "45200000", "100000 EUR", "2099-10-01",
                "2026-08-01", "https://example.invalid/pending-push-revision", 90,
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

        events = record_new_opportunities(conn, account_id=ACCOUNT, min_score=75)
        assert len(events) == 1
        assert events[0]["tender_id"] == tender_id

        register_push_device(
            conn,
            ACCOUNT,
            "installation-pending-push-probe",
            "ExpoPushToken[pending-push-probe]",
            "android",
        )

        persist_signal_records(
            conn,
            [_signal("Materially revised scope", "2099-09-01", "2026-08-10T00:00:00+00:00")],
        )

        provider_calls = []

        def fake_post(*args, **kwargs):
            provider_calls.append((args, kwargs))
            return _FakeResponse()

        submitted = submit_pending_pushes(conn, ACCOUNT, post=fake_post)

        assert submitted == 0
        assert provider_calls == []
        assert conn.execute(
            "SELECT COUNT(*) FROM push_deliveries WHERE event_id=?",
            (conn.execute(
                "SELECT id FROM opportunity_events WHERE account_id=? AND tender_id=?",
                (ACCOUNT, tender_id),
            ).fetchone()[0],),
        ).fetchone()[0] == 0
    finally:
        conn.close()
