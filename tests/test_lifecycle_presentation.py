from datetime import datetime, timezone

import app
import api
import lifecycle_read_model
import preload
from decision_log import record_decision
from notification_events import record_new_opportunities
from opportunity_lifecycle import persist_lifecycle_observations
from opportunity_match_pipeline import RULE_VERSION
from opportunity_web import render_opportunity_detail


class Identity:
    account_id = "company-lifecycle"
    authenticated = True


def _seed(monkeypatch, tmp_path):
    db_path = tmp_path / "lifecycle-presentation.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", Identity.account_id)
    monkeypatch.setattr(app, "DB", str(db_path))
    app.init_db()
    conn = app.db()
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        ("UK_PROCUREMENT", "ocds-live:lot:1", "Live construction lot", "Current works opportunity", "Buyer A", "GBR", "45200000", "100000 GBP", "2099-10-01T12:00:00+00:00", "2026-08-24", "https://example.test/live", 90, now, now, "GLOBAL"),
        ("UK_PROCUREMENT", "ocds-closed:lot:1", "Cancelled construction lot", "Was once commercially relevant", "Buyer B", "GBR", "45200000", "200000 GBP", "2099-10-01T12:00:00+00:00", "2026-08-24", "https://example.test/closed", 95, now, now, "GLOBAL"),
    ]
    conn.executemany(
        """INSERT INTO tenders(
               source,external_id,title,description,buyer,country,cpv,value,
               deadline,publication_date,url,score,first_seen,last_seen,market
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()
    record_decision(conn, "UK_PROCUREMENT", "ocds-live:lot:1", "QUALIFIED", "live fit", score=90, rule_version=RULE_VERSION, account_id=Identity.account_id)
    record_decision(conn, "UK_PROCUREMENT", "ocds-closed:lot:1", "QUALIFIED", "historical fit", score=95, rule_version=RULE_VERSION, account_id=Identity.account_id)
    persist_lifecycle_observations(
        conn,
        [{"source": "UK_PROCUREMENT", "external_id": "ocds-closed:lot:1", "is_actionable": False, "lifecycle_status": "cancelled", "lifecycle_reason": "publisher reports tender cancelled", "source_updated_at": "2026-08-24T12:00:00+01:00"}],
    )
    live_id = conn.execute("SELECT id FROM tenders WHERE external_id='ocds-live:lot:1'").fetchone()[0]
    closed_id = conn.execute("SELECT id FROM tenders WHERE external_id='ocds-closed:lot:1'").fetchone()[0]
    conn.close()
    return live_id, closed_id


def test_mobile_feed_and_stats_exclude_source_tombstone(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    monkeypatch.setattr(api, "configured_identity", lambda: Identity())
    monkeypatch.setattr(api, "_identity", lambda: Identity())
    client = api.APP.test_client()
    feed = client.get("/api/v1/opportunities?market=ALL").get_json()
    assert [item["external_id"] for item in feed["items"]] == ["ocds-live:lot:1"]
    assert feed["items"][0]["is_actionable"] is True
    stats = client.get("/api/v1/stats").get_json()
    assert stats["total"] == 1
    assert stats["high"] == 1
    assert stats["open"] == 1
    assert stats["new24"] == 1


def test_detail_preserves_closed_history_and_exposes_lifecycle(monkeypatch, tmp_path):
    _, closed_id = _seed(monkeypatch, tmp_path)
    monkeypatch.setattr(api, "configured_identity", lambda: Identity())
    monkeypatch.setattr(api, "_identity", lambda: Identity())
    response = api.APP.test_client().get(f"/api/v1/opportunities/{closed_id}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["external_id"] == "ocds-closed:lot:1"
    assert body["is_actionable"] is False
    assert body["is_open"] is False
    assert body["lifecycle_status"] == "cancelled"
    assert "publisher reports tender cancelled" in body["lifecycle_reason"]
    assert body["account_decision"] == "QUALIFIED"


def test_legacy_read_model_excludes_tombstone_from_list_stats_and_radar(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    monkeypatch.setattr(lifecycle_read_model, "configured_identity", lambda: Identity())
    lifecycle_read_model.install(preload)
    rows = app.query_tenders("ALL", "", "", "", limit=20)
    assert [row["external_id"] for row in rows] == ["ocds-live:lot:1"]
    assert app.stats_for("ALL")["total"] == 1
    response = app.APP.test_client().get("/api/v1/radar?minscore=0&limit=20")
    assert response.status_code == 200
    body = response.get_json()
    assert [item["external_id"] for item in body["items"]] == ["ocds-live:lot:1"]


def test_post_sync_decisioning_skips_tombstoned_row(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    conn = app.db()
    calls = []
    try:
        last_seen = conn.execute("SELECT last_seen FROM tenders WHERE external_id='ocds-live:lot:1'").fetchone()[0]
        conn.execute("DELETE FROM sync_runs")
        conn.execute("INSERT INTO sync_runs(started_at,finished_at,found,new_items) VALUES(?,?,?,?)", (last_seen, last_seen, 2, 2))
        conn.commit()
        monkeypatch.setattr(lifecycle_read_model, "persist_and_classify", lambda target, row, emit, account_id=None: calls.append((row["external_id"], account_id)))
        count = lifecycle_read_model.record_account_decisions(conn, list_active_accounts=lambda target: [Identity.account_id])
    finally:
        conn.close()
    assert count == 1
    assert calls == [("ocds-live:lot:1", Identity.account_id)]


def test_tombstone_cannot_generate_new_high_match_alert(monkeypatch, tmp_path):
    _seed(monkeypatch, tmp_path)
    conn = app.db()
    try:
        events = record_new_opportunities(conn, account_id=Identity.account_id, min_score=75)
    finally:
        conn.close()
    assert [event["event_key"].split(":", 1)[1] for event in events] == ["uk_procurement:ocds-live:lot:1"]


def test_historical_web_detail_labels_old_decision_as_historical():
    html = render_opportunity_detail(
        {"source": "UK_PROCUREMENT", "external_id": "ocds-closed:lot:1", "title": "Cancelled works", "is_actionable": False, "lifecycle_status": "cancelled", "lifecycle_reason": "publisher reports tender cancelled", "lifecycle_last_observed": "2026-08-24T12:00:00+01:00"},
        {"status": "QUALIFIED", "reason": "historical fit", "score": 95},
    )
    assert "ESTADO OFICIAL ATUAL" in html
    assert "já não está ativa" in html
    assert "CANCELLED" in html
    assert "Decisão histórica" in html
    assert "QUALIFIED" in html
