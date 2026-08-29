from types import SimpleNamespace

from flask import request

import api
import app
from decision_log import record_decision
from opportunity_match_pipeline import RULE_VERSION


ACCOUNT = "api-future-publication-account"
OLD_ID = "API-IMPOSSIBLE-FUTURE-PUBLICATION"
NEW_ID = "API-GENUINE-RECENT-DISCOVERY"


def _insert_tender(conn, external_id, title, first_seen, publication_date):
    conn.execute(
        """INSERT INTO tenders(
               source,external_id,title,description,buyer,country,cpv,deadline,
               publication_date,first_seen,last_seen,market
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "TED",
            external_id,
            title,
            "synthetic",
            "Synthetic Buyer",
            "PRT",
            "45200000",
            "2099-12-31T23:59:59+00:00",
            publication_date,
            first_seen,
            first_seen,
            "PT",
        ),
    )


def test_impossible_future_publication_date_cannot_control_current_ordering(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DB", str(tmp_path / "api-future-publication.db"))
    app.init_db()

    conn = app.db()
    try:
        _insert_tender(
            conn,
            OLD_ID,
            "Old opportunity carrying impossible future publisher time",
            "2026-08-20T09:00:00+00:00",
            "2099-01-01T00:00:00+00:00",
        )
        _insert_tender(
            conn,
            NEW_ID,
            "Genuinely newer discovery",
            "2026-08-25T09:00:00+00:00",
            None,
        )
        conn.commit()

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
        "IMPOSSIBLE_FUTURE_PUBLICATION_ORDER_AUTHORITY: a publisher date decades "
        "after durable discovery is parseable but cannot be granted chronological "
        "authority over a genuinely newer observed opportunity"
    )
