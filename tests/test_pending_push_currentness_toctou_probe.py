import app
import notification_events
from company_profile import save_profile
from decision_log import record_decision
from notification_events import record_new_opportunities, register_push_device, submit_pending_pushes
from opportunity_match_pipeline import RULE_VERSION
from signal_store import persist_signal_records


ACCOUNT = "pending-push-toctou-account"
SOURCE = "TED"
EXTERNAL_ID = "pending-push-toctou-1"


def _signal(title, deadline, updated):
    return {
        "source": SOURCE,
        "signal_type": "TENDER",
        "external_id": EXTERNAL_ID,
        "title": title,
        "description": "Synthetic pending-push TOCTOU probe",
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
        return {"data": [{"status": "ok", "id": "ticket-toctou-probe"}]}


def test_pending_push_rechecks_authority_atomically_before_provider_boundary(monkeypatch, tmp_path):
    db_path = tmp_path / "pending-push-toctou.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    monkeypatch.setattr(app, "DB", str(db_path))
    app.init_db()
    save_profile(
        {
            "name": "Pending push TOCTOU company",
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
                "Synthetic pending-push TOCTOU probe", "Synthetic buyer",
                "PRT", "45200000", "100000 EUR", "2099-10-01",
                "2026-08-01", "https://example.invalid/pending-push-toctou", 90,
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
            "installation-pending-toctou",
            "ExpoPushToken[pending-toctou]",
            "android",
        )

        original_currentness = notification_events.latest_opportunity_current_decision
        revision_injected = False

        def currentness_then_revision(*args, **kwargs):
            nonlocal revision_injected
            decision = original_currentness(*args, **kwargs)
            if decision is not None and not revision_injected:
                revision_injected = True
                persist_signal_records(
                    conn,
                    [_signal("Materially revised scope", "2099-09-01", "2026-08-10T00:00:00+00:00")],
                )
            return decision

        monkeypatch.setattr(
            notification_events,
            "latest_opportunity_current_decision",
            currentness_then_revision,
        )

        provider_calls = []

        def fake_post(*args, **kwargs):
            provider_calls.append((args, kwargs))
            return _FakeResponse()

        submitted = submit_pending_pushes(conn, ACCOUNT, post=fake_post)

        assert revision_injected is True
        assert original_currentness(
            conn,
            SOURCE,
            EXTERNAL_ID,
            account_id=ACCOUNT,
        ) is None
        assert submitted == 0
        assert provider_calls == []
        event_id = conn.execute(
            "SELECT id FROM opportunity_events WHERE account_id=? AND tender_id=?",
            (ACCOUNT, tender_id),
        ).fetchone()[0]
        assert conn.execute(
            "SELECT COUNT(*) FROM push_deliveries WHERE event_id=?",
            (event_id,),
        ).fetchone()[0] == 0
    finally:
        conn.close()
