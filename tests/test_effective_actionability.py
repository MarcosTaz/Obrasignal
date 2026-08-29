from datetime import datetime, timedelta, timezone

import api
import app
import lifecycle_read_model
import preload
from decision_log import record_decision
from notification_events import record_new_opportunities
from opportunity_lifecycle import persist_lifecycle_observations
from opportunity_match_pipeline import RULE_VERSION


class Identity:
    account_id = "sentinel-actionability"
    authenticated = True


def _relevant_features():
    return {
        "relevance": {
            "state": "RELEVANT",
            "evidence": [{"kind": "service", "value": "construction"}],
            "rule_version": "relevance-v1",
        },
        "relevant_shortlist_eligible": True,
    }


def _seed(monkeypatch, tmp_path):
    db_path = tmp_path / "effective-actionability.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", Identity.account_id)
    monkeypatch.setattr(app, "DB", str(db_path))
    app.init_db()
    conn = app.db()
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        ("TEST_SOURCE", "expired-no-lifecycle", "Expired without lifecycle", "Historical tender", "Buyer A", "PRT", "45200000", "100000 EUR", "2000-01-01T12:00:00+00:00", "2026-08-24", "https://example.test/expired", 95, now, now, "PT"),
        ("TEST_SOURCE", "future-no-lifecycle", "Future without lifecycle", "Current tender", "Buyer B", "PRT", "45200000", "100000 EUR", "2099-01-01T12:00:00+00:00", "2026-08-24", "https://example.test/future", 90, now, now, "PT"),
        ("TEST_SOURCE", "expired-explicit-open", "Expired deadline with explicit lifecycle open", "Publisher says still actionable", "Buyer C", "PRT", "45200000", "100000 EUR", "2000-01-01T12:00:00+00:00", "2026-08-24", "https://example.test/reopened", 85, now, now, "PT"),
        ("TEST_SOURCE", "future-explicit-closed", "Future deadline with explicit lifecycle closed", "Publisher cancelled it", "Buyer D", "PRT", "45200000", "100000 EUR", "2099-01-01T12:00:00+00:00", "2026-08-24", "https://example.test/cancelled", 80, now, now, "PT"),
    ]
    conn.executemany(
        """INSERT INTO tenders(
               source,external_id,title,description,buyer,country,cpv,value,
               deadline,publication_date,url,score,first_seen,last_seen,market
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()
    for external_id, score in (
        ("expired-no-lifecycle", 95),
        ("future-no-lifecycle", 90),
        ("expired-explicit-open", 85),
        ("future-explicit-closed", 80),
    ):
        record_decision(
            conn,
            "TEST_SOURCE",
            external_id,
            "QUALIFIED",
            "fixture",
            score=score,
            features=_relevant_features(),
            account_id=Identity.account_id,
            rule_version=RULE_VERSION,
        )
    persist_lifecycle_observations(
        conn,
        [
            {"source": "TEST_SOURCE", "external_id": "expired-explicit-open", "is_actionable": True, "lifecycle_status": "open", "lifecycle_reason": "publisher explicitly reports actionable"},
            {"source": "TEST_SOURCE", "external_id": "future-explicit-closed", "is_actionable": False, "lifecycle_status": "cancelled", "lifecycle_reason": "publisher explicitly cancelled"},
        ],
    )
    ids = {row["external_id"]: row["id"] for row in conn.execute("SELECT id, external_id FROM tenders").fetchall()}
    conn.close()
    return ids


def _api_client(monkeypatch):
    monkeypatch.setattr(api, "configured_identity", lambda: Identity())
    monkeypatch.setattr(api, "_identity", lambda: Identity())
    return api.APP.test_client()


def test_default_feed_fails_closed_for_expired_deadline_without_lifecycle(monkeypatch, tmp_path):
    ids = _seed(monkeypatch, tmp_path)
    client = _api_client(monkeypatch)
    feed = client.get("/api/v1/opportunities?market=PT&limit=20").get_json()
    assert [item["external_id"] for item in feed["items"]] == ["future-no-lifecycle", "expired-explicit-open"]
    detail = client.get(f"/api/v1/opportunities/{ids['expired-no-lifecycle']}").get_json()
    assert detail["deadline_status"]["state"] == "closed"
    assert detail["is_actionable"] is False
    assert detail["is_open"] is False


def test_date_only_deadline_today_does_not_invent_midnight_closure(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    today = datetime.now(timezone.utc).date().isoformat()
    conn = app.db()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            """INSERT INTO tenders(
                   source,external_id,title,description,buyer,country,cpv,value,
                   deadline,publication_date,url,score,first_seen,last_seen,market
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("TEST_SOURCE", "date-only-today", "Date-only deadline today", "Publisher did not provide a closing time", "Buyer E", "PRT", "45200000", "100000 EUR", today, today, "https://example.test/date-only-today", 92, now, now, "PT"),
        )
        opportunity_id = cur.lastrowid
        record_decision(
            conn,
            "TEST_SOURCE",
            "date-only-today",
            "QUALIFIED",
            "fixture",
            score=92,
            account_id=Identity.account_id,
            rule_version=RULE_VERSION,
        )
    finally:
        conn.close()

    client = _api_client(monkeypatch)
    feed = client.get("/api/v1/opportunities?market=PT&limit=20").get_json()["items"]
    item = next(row for row in feed if row["external_id"] == "date-only-today")
    assert item["is_actionable"] is True
    assert item["deadline_status"]["state"] == "unknown"
    assert item["is_open"] is False
    detail = client.get(f"/api/v1/opportunities/{opportunity_id}").get_json()
    assert detail["deadline_status"]["state"] == "unknown"
    assert detail["is_actionable"] is True
    assert detail["is_open"] is False


def test_date_only_commercial_score_uses_calendar_precision_not_midnight():
    today = datetime.now(timezone.utc).date()
    base_score = lifecycle_read_model.commercial_score("obra", "", "45200000", None)[0]
    today_score, _, _, today_reason = lifecycle_read_model.commercial_score("obra", "", "45200000", today.isoformat())
    eight_days_score = lifecycle_read_model.commercial_score("obra", "", "45200000", (today + timedelta(days=8)).isoformat())[0]
    yesterday_score = lifecycle_read_model.commercial_score("obra", "", "45200000", (today - timedelta(days=1)).isoformat())[0]
    assert today_score == min(100, base_score + 10)
    assert eight_days_score == min(100, base_score + 5)
    assert yesterday_score == max(0, base_score - 30)
    assert "prazo hoje" in today_reason
    assert "hora não indicada" in today_reason


def test_install_replaces_only_legacy_score_entrypoint_with_precision_adapter():
    lifecycle_read_model.install(preload)
    assert app.commercial_score is lifecycle_read_model.commercial_score


def test_explicit_source_lifecycle_has_precedence_over_deadline_inference(monkeypatch, tmp_path):
    ids = _seed(monkeypatch, tmp_path)
    client = _api_client(monkeypatch)
    reopened = client.get(f"/api/v1/opportunities/{ids['expired-explicit-open']}").get_json()
    assert reopened["deadline_status"]["state"] == "closed"
    assert reopened["is_actionable"] is True
    assert reopened["lifecycle_status"] == "open"
    cancelled = client.get(f"/api/v1/opportunities/{ids['future-explicit-closed']}").get_json()
    assert cancelled["deadline_status"]["state"] == "open"
    assert cancelled["is_actionable"] is False
    assert cancelled["lifecycle_status"] == "cancelled"


def test_stats_and_legacy_read_model_share_effective_actionability(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    client = _api_client(monkeypatch)
    stats = client.get("/api/v1/stats").get_json()
    assert stats["total"] == 2
    assert stats["high"] == 2
    assert stats["open"] == 1
    monkeypatch.setattr(lifecycle_read_model, "configured_identity", lambda: Identity())
    lifecycle_read_model.install(preload)
    assert [row["external_id"] for row in app.query_tenders("PT", "", "", "", limit=20)] == ["future-no-lifecycle", "expired-explicit-open"]
    assert app.stats_for("PT")["total"] == 2


def test_event_generation_uses_same_effective_actionability(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    conn = app.db()
    try:
        events = record_new_opportunities(conn, account_id=Identity.account_id, min_score=0)
    finally:
        conn.close()
    keys = [event["event_key"].split(":", 1)[1] for event in events]
    assert keys == ["test_source:future-no-lifecycle", "test_source:expired-explicit-open"]
