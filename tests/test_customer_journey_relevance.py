import json
import sqlite3

from decision_log import current_profile_fingerprint, decision_is_current, ensure_decision_table, latest_current_decision, record_decision
from decision_relevance import UNKNOWN, derive_relevance, relevant_shortlist_eligible_from_features
from opportunity_match_pipeline import RULE_VERSION


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE company_profiles(account_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL, updated_at TEXT NOT NULL)")
    ensure_decision_table(conn)
    return conn


def _save_profile(conn, payload):
    conn.execute("INSERT OR REPLACE INTO company_profiles(account_id,profile_json,updated_at) VALUES('tenant-a',?,?)", (json.dumps(payload, sort_keys=True), "2026-08-29T00:00:00+00:00"))
    conn.commit()


def test_profile_change_invalidates_old_decision():
    conn = _db()
    _save_profile(conn, {"activity": "eletricidade"})
    before = current_profile_fingerprint(conn, "tenant-a")
    record_decision(conn, "TED", "A-1", "REVIEW", "current", rule_version=RULE_VERSION, account_id="tenant-a")
    decision = latest_current_decision(conn, "TED", "A-1", account_id="tenant-a", expected_rule_version=RULE_VERSION)
    assert decision and decision["profile_fingerprint"] == before
    assert decision_is_current(conn, decision, account_id="tenant-a", expected_rule_version=RULE_VERSION)

    _save_profile(conn, {"activity": "avac"})
    assert current_profile_fingerprint(conn, "tenant-a") != before
    assert latest_current_decision(conn, "TED", "A-1", account_id="tenant-a", expected_rule_version=RULE_VERSION) is None


def test_review_label_without_relevance_evidence_stays_unknown():
    relevance = derive_relevance(
        {"matched_services": [], "matched_capabilities": []},
        {"strength": "WEAK", "matched_prefixes": ["45"]},
        [],
    )
    assert relevance["state"] == UNKNOWN
    assert relevant_shortlist_eligible_from_features({"decision": "REVIEW", "relevance": relevance, "relevant_shortlist_eligible": True}) is False
