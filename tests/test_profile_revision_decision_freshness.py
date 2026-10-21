"""Failing-before proof for company-profile revision freshness.

A bounded synchronous profile bootstrap may legitimately reclassify only the newest
opportunities. Anything left outside that bound must not keep authority to create
current customer-facing high-match work under an older company profile.
"""
from datetime import datetime, timedelta, timezone

import account_onboarding
import app
from company_profile import save_profile
from decision_log import latest_decision, record_decision
from opportunity_match_pipeline import RULE_VERSION


def _profile(activity: str, cpv: str, service: str) -> dict:
    return {
        "name": f"Demo {activity}",
        "activity": activity,
        "coverage_mode": "portugal",
        "countries": ["PRT"],
        "cpv_prefixes": [cpv],
        "services": [service],
        "capability_tags": [service],
        "min_value": 1_000,
        "max_value": 1_000_000,
    }


def test_profile_change_cannot_turn_unreclassified_stale_decision_into_current_high_match_event(
    monkeypatch, tmp_path
):
    db_path = tmp_path / "profile-revision-freshness.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    monkeypatch.setattr(app, "DB", str(db_path))
    app.init_db()

    account_id = "account-profile-freshness"
    save_profile(
        _profile("estruturas metálicas", "4522", "estruturas metálicas"),
        account_id=account_id,
    )

    # Seed 251 open opportunities. The oldest row is deliberately outside the
    # production MAX_BOOTSTRAP_ROWS=250 profile-refresh window.
    conn = app.db()
    try:
        base = datetime(2099, 1, 1, tzinfo=timezone.utc)
        for index in range(account_onboarding.MAX_BOOTSTRAP_ROWS + 1):
            published = (base + timedelta(minutes=index)).isoformat()
            external_id = f"opp-{index:03d}"
            conn.execute(
                """INSERT INTO tenders(
                       source, external_id, title, description, buyer, country, cpv,
                       value, deadline, publication_date, url, score, first_seen, last_seen
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "TEST",
                    external_id,
                    f"Opportunity {index}",
                    "Synthetic deterministic freshness fixture",
                    "Buyer",
                    "PRT",
                    "45220000",
                    "100000",
                    "2099-12-31T23:59:59+00:00",
                    published,
                    f"https://example.invalid/{external_id}",
                    0,
                    published,
                    published,
                ),
            )
            record_decision(
                conn,
                "TEST",
                external_id,
                "QUALIFIED",
                "high under profile A",
                score=95,
                features={"fixture": "profile-a"},
                rule_version=RULE_VERSION,
                decided_at="2026-01-01T00:00:00+00:00",
                account_id=account_id,
            )
        conn.commit()
    finally:
        conn.close()

    # Profile B is now authoritative and materially different from profile A.
    save_profile(
        _profile("instalações elétricas", "4531", "instalações elétricas"),
        account_id=account_id,
    )

    conn = app.db()
    try:
        profile_updated_at = conn.execute(
            "SELECT updated_at FROM company_profiles WHERE account_id=?",
            (account_id,),
        ).fetchone()["updated_at"]
    finally:
        conn.close()

    # Isolate the freshness defect from scoring-policy details: every opportunity
    # that the bounded bootstrap actually touches receives an explicitly current,
    # low decision under the same current RULE_VERSION. The omitted 251st row is
    # therefore the only stale-profile high decision left.
    def reclassify_under_profile_b(conn, item, is_new, account_id="default"):
        record_decision(
            conn,
            item["source"],
            item["external_id"],
            "REJECT",
            "profile B no longer matches",
            score=0,
            features={"fixture": "profile-b"},
            rule_version=RULE_VERSION,
            account_id=account_id,
        )
        return "REJECT", "profile B no longer matches"

    monkeypatch.setattr(account_onboarding, "persist_and_classify", reclassify_under_profile_b)

    evaluated = account_onboarding.bootstrap_account(account_id)
    assert evaluated == account_onboarding.MAX_BOOTSTRAP_ROWS

    conn = app.db()
    try:
        newest = latest_decision(conn, "TEST", "opp-250", account_id=account_id)
        oldest = latest_decision(conn, "TEST", "opp-000", account_id=account_id)
        stale_event = conn.execute(
            "SELECT event_type, score FROM opportunity_events WHERE event_key=?",
            (f"{account_id}:TEST:opp-000",),
        ).fetchone()
    finally:
        conn.close()

    # Positive controls: the bounded window moved to profile-B truth, while the
    # omitted row still carries the current algorithm version but old profile time.
    assert newest["score"] == 0
    assert newest["features"]["fixture"] == "profile-b"
    assert oldest["score"] == 95
    assert oldest["rule_version"] == RULE_VERSION
    assert oldest["decided_at"] < profile_updated_at

    # Safety invariant: an unreclassified decision produced under the previous
    # company profile must degrade to stale/unknown. It must never authorize a
    # current high-match event merely because it is still the latest stored row.
    assert stale_event is None, dict(stale_event) if stale_event is not None else None
