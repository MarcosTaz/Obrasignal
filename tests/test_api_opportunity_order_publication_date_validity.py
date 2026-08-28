from types import SimpleNamespace

from flask import request

import api
import app
from decision_log import record_decision
from opportunity_match_pipeline import RULE_VERSION


ACCOUNT = "api-order-publication-validity-account"
OLD_ID = "API-ORDER-MALFORMED-PUBLICATION"
NEW_ID = "API-ORDER-GENUINE-DISCOVERY"


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
            "2026-12-31T23:59:59+00:00",
            publication_date,
            first_seen,
            first_seen,
            "PT",
        ),
    )


def test_malformed_publication_date_cannot_outrank_valid_discovery_chronology(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DB", str(tmp_path / "api-order-publication-validity.db"))
    app.init_db()

    conn = app.db()
    try:
        # Older opportunity carries a malformed publisher date. That string has no
        # chronological authority and must not beat a genuinely newer discovery.
        _insert_tender(
            conn,
            OLD_ID,
            "Older opportunity with malformed publication date",
            "2026-08-20T09:00:00+00:00",
            "zzzz-not-a-date",
        )
        _insert_tender(
            conn,
            NEW_ID,
            "Genuinely newer opportunity",
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
        "MALFORMED_PUBLICATION_DATE_ORDER_AUTHORITY: an unparsable publication_date "
        "must not become ordering authority merely because it is non-null; valid "
        "discovery chronology must win when publisher chronology is UNKNOWN"
    )
