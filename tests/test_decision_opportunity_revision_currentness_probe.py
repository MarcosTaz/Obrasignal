import json
import sqlite3

from decision_log import latest_current_decision, record_decision
from signal_store import persist_signal_records


def _profile(conn, account_id="acct-a"):
    conn.execute(
        """CREATE TABLE company_profiles(
               account_id TEXT PRIMARY KEY,
               profile_json TEXT NOT NULL,
               updated_at TEXT NOT NULL
           )"""
    )
    conn.execute(
        "INSERT INTO company_profiles(account_id,profile_json,updated_at) VALUES(?,?,?)",
        (account_id, json.dumps({"name": "Synthetic A", "activity": "construction"}), "2026-08-29T00:00:00+00:00"),
    )
    conn.commit()


def _signal(*, title, deadline, source_updated_at):
    return {
        "source": "TED",
        "signal_type": "TENDER",
        "external_id": "REVISION-CURRENTNESS-1",
        "title": title,
        "description": "Synthetic canonical decision-currentness probe",
        "buyer": "Synthetic Buyer",
        "country": "PRT",
        "cpv": "45000000",
        "value": "1000000",
        "currency": "EUR",
        "deadline": deadline,
        "publication_date": "2026-08-01",
        "source_updated_at": source_updated_at,
        "url": "https://example.invalid/revision-currentness",
    }


def test_material_authoritative_opportunity_revision_invalidates_t1_account_decision():
    """T1 decision cannot remain current authority after canonical T2 content changes."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _profile(conn)

    t1 = _signal(
        title="School refurbishment — original scope",
        deadline="2026-09-30T12:00:00+00:00",
        source_updated_at="2026-08-01T10:00:00+00:00",
    )
    persist_signal_records(conn, [t1], observed_at="2026-08-01T10:01:00+00:00")
    record_decision(
        conn,
        "TED",
        "REVISION-CURRENTNESS-1",
        "QUALIFIED",
        "T1 scope fits company profile",
        score=90,
        features={"relevant_shortlist_eligible": True},
        rule_version="probe-rule-v1",
        account_id="acct-a",
        decided_at="2026-08-01T10:02:00+00:00",
    )

    current_t1 = latest_current_decision(
        conn,
        "TED",
        "REVISION-CURRENTNESS-1",
        account_id="acct-a",
        expected_rule_version="probe-rule-v1",
    )
    assert current_t1 is not None
    assert current_t1["score"] == 90

    # Publisher materially revises the authoritative opportunity after the decision:
    # changed scope/title and a materially earlier deadline under a newer source revision.
    t2 = _signal(
        title="School refurbishment — revised electrical-heavy scope",
        deadline="2026-08-20T12:00:00+00:00",
        source_updated_at="2026-08-10T09:00:00+00:00",
    )
    persist_signal_records(conn, [t2], observed_at="2026-08-10T09:01:00+00:00")

    canonical = conn.execute(
        """SELECT title, deadline, source_updated_at
           FROM signal_records
           WHERE source='TED' AND signal_type='TENDER' AND external_id='REVISION-CURRENTNESS-1'"""
    ).fetchone()
    assert canonical["title"] == t2["title"]
    assert canonical["deadline"] == t2["deadline"]
    assert canonical["source_updated_at"] == t2["source_updated_at"]

    # Required truth: the T1 decision was made about T1 content. Once T2 becomes
    # canonical, rule/profile equality alone cannot authorize the stale score/reason.
    assert latest_current_decision(
        conn,
        "TED",
        "REVISION-CURRENTNESS-1",
        account_id="acct-a",
        expected_rule_version="probe-rule-v1",
    ) is None
