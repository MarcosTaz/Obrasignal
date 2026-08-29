from types import SimpleNamespace

from flask import request

import api
import app
from decision_log import record_decision
from opportunity_match_pipeline import RULE_VERSION
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync


ACCOUNT = "api-order-stale-account"
OLD_ID = "API-ORDER-STALE-OLD"
NEW_ID = "API-ORDER-GENUINE-NEW"


def _record(updated_at, title):
    return {
        "source": "TED",
        "external_id": OLD_ID,
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


def _insert_tender(conn, external_id, title, first_seen):
    conn.execute(
        """INSERT INTO tenders(
               source,external_id,title,description,buyer,country,cpv,deadline,
               first_seen,last_seen,market
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "TED",
            external_id,
            title,
            "synthetic",
            "Synthetic Buyer",
            "PRT",
            "45200000",
            "2026-12-31T23:59:59+00:00",
            first_seen,
            first_seen,
            "PT",
        ),
    )


def test_rejected_stale_cannot_outrank_genuinely_newer_opportunity(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DB", str(tmp_path / "api-order-stale.db"))
    app.init_db()
    discard_staged_source_syncs()

    conn = app.db()
    try:
        _insert_tender(conn, OLD_ID, "Canonical old opportunity", "2026-08-20T09:00:00+00:00")
        _insert_tender(conn, NEW_ID, "Genuinely newer opportunity", "2026-08-25T09:00:00+00:00")
        conn.commit()

        stage_source_sync(
            "TED",
            [_record("2026-08-20T09:00:00+00:00", "Canonical old opportunity")],
            "cursor-old",
        )
        commit_staged_source_syncs(conn)
        conn.execute(
            """UPDATE signal_records SET first_observed=?
               WHERE source='TED' AND signal_type='TENDER' AND external_id=?""",
            ("2026-08-20T09:00:00+00:00", OLD_ID),
        )
        conn.execute(
            "UPDATE tenders SET first_seen=?,last_seen=? WHERE source='TED' AND external_id=?",
            ("2026-08-20T09:00:00+00:00", "2026-08-20T09:00:00+00:00", OLD_ID),
        )
        conn.commit()

        # Simulate a later legacy write fabricating freshness before the source-side
        # temporal gate rejects the publisher-stale observation.
        conn.execute(
            "UPDATE tenders SET title=?,first_seen=?,last_seen=? WHERE source='TED' AND external_id=?",
            (
                "Stale arrival must not outrank",
                "2099-01-01T00:00:00+00:00",
                "2099-01-01T00:00:00+00:00",
                OLD_ID,
            ),
        )
        conn.commit()
        stage_source_sync(
            "TED",
            [_record("2026-08-19T09:00:00+00:00", "Stale arrival must not outrank")],
            "cursor-stale-fetch",
        )
        commit_staged_source_syncs(conn)

        reconciled = conn.execute(
            "SELECT title,first_seen FROM tenders WHERE source='TED' AND external_id=?",
            (OLD_ID,),
        ).fetchone()
        assert reconciled["title"] == "Canonical old opportunity"
        assert reconciled["first_seen"].startswith("2026-08-20T09:00:00")

        for external_id in (OLD_ID, NEW_ID):
            record_decision(
                conn,
                "TED",
                external_id,
                "RELEVANT",
                "synthetic current decision",
                score=80,
                features={},
                rule_version=RULE_VERSION,
                account_id=ACCOUNT,
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

    with app.APP.test_request_context("/api/v1/opportunities?market=PT&limit=10"):
        request.obrasignal_identity = SimpleNamespace(account_id=ACCOUNT, authenticated=True)
        response = api.opportunities()
        payload = response.get_json()

    ids = [item["external_id"] for item in payload["items"]]
    assert ids[:2] == [NEW_ID, OLD_ID], (
        "REJECTED_STALE_OPPORTUNITY_ORDER_FABRICATION: equal-score ordering must use "
        "canonical discovery chronology after stale rejection, not fabricated sync freshness"
    )
