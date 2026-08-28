from types import SimpleNamespace

from flask import request

import api
import app
from decision_log import record_decision
from normalization_provenance import ensure_normalization_provenance
from opportunity_match_pipeline import RULE_VERSION


ACCOUNT = "api-historical-publication-account"
OLD_ID = "API-HISTORICAL-MALFORMED-PUBLICATION"
NEW_ID = "API-HISTORICAL-GENUINE-DISCOVERY"


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


def test_historical_malformed_publication_date_cannot_control_current_ordering(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DB", str(tmp_path / "api-historical-publication.db"))
    app.init_db()

    conn = app.db()
    try:
        # Emulate rows written before the publication-date validity guards existed.
        conn.execute("DROP TRIGGER IF EXISTS tenders_publication_date_validity_insert")
        conn.execute("DROP TRIGGER IF EXISTS tenders_publication_date_validity_update")
        _insert_tender(
            conn,
            OLD_ID,
            "Historical malformed publication date",
            "2026-08-20T09:00:00+00:00",
            "zzzz-historical-not-a-date",
        )
        _insert_tender(
            conn,
            NEW_ID,
            "Genuinely newer opportunity",
            "2026-08-25T09:00:00+00:00",
            None,
        )
        conn.commit()

        # Current schema initialization reinstalls guards but deliberately performs
        # no silent historical backfill. Read-time ordering therefore must itself
        # refuse to elevate malformed publisher chronology.
        ensure_normalization_provenance(conn)
        historical = conn.execute(
            "SELECT publication_date FROM tenders WHERE source='TED' AND external_id=?",
            (OLD_ID,),
        ).fetchone()
        assert historical["publication_date"] == "zzzz-historical-not-a-date"

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
        "HISTORICAL_MALFORMED_PUBLICATION_ORDER_AUTHORITY: preserved raw historical "
        "evidence must not retain chronological authority when it is unparsable"
    )
