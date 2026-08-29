from datetime import datetime, timedelta, timezone

import account_onboarding
import app
from company_profile import save_profile
from decision_log import latest_current_decision, latest_decision, record_decision
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


def _setup(monkeypatch, tmp_path, filename="authority.db"):
    db_path = tmp_path / filename
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    monkeypatch.setattr(app, "DB", str(db_path))
    app.init_db()
    return db_path


def test_profile_content_change_invalidates_latest_decision_authority(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    account_id = "account-a"
    profile_a = _profile("estruturas metálicas", "4522", "estruturas metálicas")
    profile_b = _profile("instalações elétricas", "4531", "instalações elétricas")

    save_profile(profile_a, account_id=account_id)
    conn = app.db()
    try:
        record_decision(
            conn, "TEST", "opp-1", "QUALIFIED", "profile A", score=95,
            rule_version=RULE_VERSION, account_id=account_id,
        )
        assert latest_current_decision(
            conn, "TEST", "opp-1", account_id=account_id,
            expected_rule_version=RULE_VERSION,
        )["score"] == 95
    finally:
        conn.close()

    save_profile(profile_b, account_id=account_id)
    conn = app.db()
    try:
        historical = latest_decision(conn, "TEST", "opp-1", account_id=account_id)
        current = latest_current_decision(
            conn, "TEST", "opp-1", account_id=account_id,
            expected_rule_version=RULE_VERSION,
        )
        assert historical["score"] == 95
        assert current is None

        record_decision(
            conn, "TEST", "opp-1", "REJECT", "profile B", score=0,
            rule_version=RULE_VERSION, account_id=account_id,
        )
        current = latest_current_decision(
            conn, "TEST", "opp-1", account_id=account_id,
            expected_rule_version=RULE_VERSION,
        )
        assert current["decision"] == "REJECT"
        assert current["score"] == 0
    finally:
        conn.close()


def test_identical_profile_resave_does_not_create_false_staleness(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, "same-profile.db")
    account_id = "account-same"
    profile = _profile("estruturas metálicas", "4522", "estruturas metálicas")

    save_profile(profile, account_id=account_id)
    conn = app.db()
    try:
        record_decision(
            conn, "TEST", "opp-same", "QUALIFIED", "same content", score=88,
            rule_version=RULE_VERSION, account_id=account_id,
        )
    finally:
        conn.close()

    save_profile(profile, account_id=account_id)
    conn = app.db()
    try:
        current = latest_current_decision(
            conn, "TEST", "opp-same", account_id=account_id,
            expected_rule_version=RULE_VERSION,
        )
        assert current["score"] == 88
    finally:
        conn.close()


def test_superseded_rule_and_legacy_unbound_rows_fail_closed(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, "legacy.db")
    account_id = "account-legacy"
    save_profile(_profile("construção", "45", "construção"), account_id=account_id)

    conn = app.db()
    try:
        record_decision(
            conn, "TEST", "old-rule", "QUALIFIED", "old algorithm", score=99,
            rule_version="superseded-rule", account_id=account_id,
        )
        assert latest_current_decision(
            conn, "TEST", "old-rule", account_id=account_id,
            expected_rule_version=RULE_VERSION,
        ) is None

        conn.execute(
            """INSERT INTO opportunity_decisions(
                   account_id, source, external_id, decision, reason, score,
                   features_json, rule_version, profile_fingerprint, decided_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                account_id, "TEST", "legacy-unbound", "QUALIFIED",
                "historical row without profile binding", 98, "{}",
                RULE_VERSION, None, "2026-01-01T00:00:00+00:00",
            ),
        )
        conn.commit()
        assert latest_current_decision(
            conn, "TEST", "legacy-unbound", account_id=account_id,
            expected_rule_version=RULE_VERSION,
        ) is None
    finally:
        conn.close()


def test_bounded_profile_refresh_cannot_authorize_omitted_old_profile_event(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, "bounded.db")
    account_id = "account-bounded"
    save_profile(
        _profile("estruturas metálicas", "4522", "estruturas metálicas"),
        account_id=account_id,
    )

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
                    "TEST", external_id, f"Opportunity {index}",
                    "Synthetic current-authority fixture", "Buyer", "PRT",
                    "45220000", "100000", "2099-12-31T23:59:59+00:00",
                    published, f"https://example.invalid/{external_id}", 0,
                    published, published,
                ),
            )
            record_decision(
                conn, "TEST", external_id, "QUALIFIED", "high under profile A",
                score=95, features={"fixture": "profile-a"},
                rule_version=RULE_VERSION, account_id=account_id,
            )
        conn.commit()
    finally:
        conn.close()

    save_profile(
        _profile("instalações elétricas", "4531", "instalações elétricas"),
        account_id=account_id,
    )

    def reclassify_under_profile_b(conn, item, is_new, account_id="default"):
        record_decision(
            conn, item["source"], item["external_id"], "REJECT",
            "profile B no longer matches", score=0,
            features={"fixture": "profile-b"}, rule_version=RULE_VERSION,
            account_id=account_id,
        )
        return "REJECT", "profile B no longer matches"

    monkeypatch.setattr(account_onboarding, "persist_and_classify", reclassify_under_profile_b)

    assert account_onboarding.bootstrap_account(account_id) == account_onboarding.MAX_BOOTSTRAP_ROWS

    conn = app.db()
    try:
        old = latest_decision(conn, "TEST", "opp-000", account_id=account_id)
        event = conn.execute(
            "SELECT event_type, score FROM opportunity_events WHERE event_key=?",
            (f"{account_id}:TEST:opp-000",),
        ).fetchone()
        assert old["score"] == 95
        assert latest_current_decision(
            conn, "TEST", "opp-000", account_id=account_id,
            expected_rule_version=RULE_VERSION,
        ) is None
        assert event is None
    finally:
        conn.close()
