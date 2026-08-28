from types import SimpleNamespace

from flask import request

import api
import app
from decision_log import record_decision
from opportunity_match_pipeline import RULE_VERSION
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync


def _record(updated_at, title):
    return {
        "source": "TED",
        "external_id": "API-NEW24-STALE-1",
        "signal_type": "TENDER",
        "title": title,
        "description": "synthetic",
        "buyer": "Synthetic Buyer",
        "country": "PRT",
        "taxonomy": "CPV",
        "category_code": "45200000",
        "deadline": "2026-12-31T23:59:59+00:00",
        "source_status": "active",
        "source_updated_at": updated_at,
        "is_actionable": True,
        "lifecycle_status": "active",
        "lifecycle_reason": "publisher reports active",
    }


def test_rejected_stale_cannot_inflate_api_new24(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DB", str(tmp_path / "api-new24.db"))
    app.init_db()
    discard_staged_source_syncs()

    conn = app.db()
    try:
        # Establish old canonical publisher/discovery truth and the matching legacy row.
        conn.execute(
            """INSERT INTO tenders(
                   source,external_id,title,description,buyer,country,cpv,deadline,
                   first_seen,last_seen,market
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "TED",
                "API-NEW24-STALE-1",
                "Canonical old opportunity",
                "synthetic",
                "Synthetic Buyer",
                "PRT",
                "45200000",
                "2026-12-31T23:59:59+00:00",
                "2026-08-20T09:00:00+00:00",
                "2026-08-20T09:00:00+00:00",
                "EU",
            ),
        )
        conn.commit()
        stage_source_sync(
            "TED",
            [_record("2026-08-20T09:00:00+00:00", "Canonical old opportunity")],
            "cursor-old",
        )
        commit_staged_source_syncs(conn)

        # Simulate the legacy transaction having just recreated false sync-time freshness
        # before publisher-time authority rejects the stale source observation.
        conn.execute(
            """UPDATE tenders
                  SET title=?, first_seen=?, last_seen=?
                WHERE source='TED' AND external_id='API-NEW24-STALE-1'""",
            (
                "Stale arrival must not look new",
                "2099-01-01T00:00:00+00:00",
                "2099-01-01T00:00:00+00:00",
            ),
        )
        conn.commit()
        stage_source_sync(
            "TED",
            [_record("2026-08-19T09:00:00+00:00", "Stale arrival must not look new")],
            "cursor-stale-fetch",
        )
        commit_staged_source_syncs(conn)

        row = conn.execute(
            "SELECT title,first_seen FROM tenders WHERE source='TED' AND external_id='API-NEW24-STALE-1'"
        ).fetchone()
        assert row["title"] == "Canonical old opportunity"
        assert row["first_seen"].startswith("2026-08-20T09:00:00")

        record_decision(
            conn,
            "TED",
            "API-NEW24-STALE-1",
            "RELEVANT",
            "synthetic current decision",
            score=80,
            features={},
            rule_version=RULE_VERSION,
            account_id="api-new24-account",
        )
    finally:
        conn.close()

    monkeypatch.setattr(api, "_db", app.db)
    monkeypatch.setattr(
        api,
        "_source_contract",
        lambda _conn, source=None: {
            "summary": {"state": "synthetic"},
            "contract_version": "test",
        },
    )

    with app.APP.test_request_context("/api/v1/stats"):
        request.obrasignal_identity = SimpleNamespace(
            account_id="api-new24-account", authenticated=True
        )
        response = api.stats()
        payload = response.get_json()

    assert payload["total"] == 1
    assert payload["high"] == 1
    assert payload["new24"] == 0, (
        "REJECTED_STALE_API_NEW24_FABRICATION: a stale source arrival rejected by "
        "publisher-time authority must not become a customer-facing new24 count"
    )
