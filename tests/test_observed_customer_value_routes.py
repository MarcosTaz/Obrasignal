import json
from types import SimpleNamespace

import app
import api
from account_registry import ensure_account
from company_profile import ensure_profile_table
from decision_log import record_decision
from evaluation_policy import ensure_evaluation_schema
from opportunity_match_pipeline import RULE_VERSION


def _open(path):
    import sqlite3
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _seed(monkeypatch, tmp_path, *, relevance_state="RELEVANT", eligible=True):
    path = tmp_path / "observed-value.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    monkeypatch.setattr(app, "DB", str(path))
    app.init_db()

    conn = _open(path)
    ensure_account(conn, "tenant-a")
    ensure_account(conn, "tenant-b")
    ensure_profile_table(conn)
    ensure_evaluation_schema(conn)
    profile = {
        "account_id": "tenant-a",
        "activity": "estrutura metálica",
        "services": ["estrutura metálica"],
        "countries": ["PRT"],
    }
    conn.execute(
        "INSERT OR REPLACE INTO company_profiles(account_id,profile_json,updated_at) VALUES(?,?,?)",
        ("tenant-a", json.dumps(profile, sort_keys=True), "2026-08-26T19:00:00+00:00"),
    )
    conn.execute(
        """INSERT INTO tenders(source, external_id, title, description, buyer, country,
           cpv, value, deadline, publication_date, url, score, first_seen, last_seen, market)
           VALUES ('TED','OBS-1','Estrutura metálica','Montagem de estrutura','Município','PRT',
           '45223100','150000 EUR','2099-10-01','2026-08-26','https://example.test/obs',88,
           '2026-08-26','2026-08-26','PT')"""
    )
    opportunity_id = conn.execute(
        "SELECT id FROM tenders WHERE source='TED' AND external_id='OBS-1'"
    ).fetchone()[0]
    record_decision(
        conn,
        "TED",
        "OBS-1",
        "REVIEW",
        "explicit company relevance",
        score=82,
        features={
            "relevance": {
                "state": relevance_state,
                "evidence": ([{"kind": "service", "value": "estrutura metálica"}] if relevance_state == "RELEVANT" else []),
                "rule_version": "relevance-v1",
            },
            "relevant_shortlist_eligible": eligible,
        },
        rule_version=RULE_VERSION,
        account_id="tenant-a",
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(api, "_identity", lambda: SimpleNamespace(account_id="tenant-a", authenticated=True))
    monkeypatch.setattr(api, "_db", lambda: _open(path))
    return path, opportunity_id


def _events(path, account_id):
    with _open(path) as conn:
        ensure_evaluation_schema(conn)
        return [
            dict(row)
            for row in conn.execute(
                "SELECT event_name, metadata_json FROM evaluation_events WHERE account_id=? ORDER BY id",
                (account_id,),
            ).fetchall()
        ]


def test_opening_current_relevant_opportunity_emits_bounded_observed_view(tmp_path, monkeypatch):
    path, opportunity_id = _seed(monkeypatch, tmp_path)
    response = api.APP.test_client().get(f"/api/v1/opportunities/{opportunity_id}")

    assert response.status_code == 200
    observed = [event for event in _events(path, "tenant-a") if event["event_name"] == "relevant_opportunity_viewed"]
    assert len(observed) == 1
    assert json.loads(observed[0]["metadata_json"]) == {"source": "TED", "external_id": "OBS-1"}
    assert _events(path, "tenant-b") == []


def test_unknown_relevance_detail_does_not_fabricate_observed_value(tmp_path, monkeypatch):
    path, opportunity_id = _seed(monkeypatch, tmp_path, relevance_state="UNKNOWN", eligible=False)
    response = api.APP.test_client().get(f"/api/v1/opportunities/{opportunity_id}")

    assert response.status_code == 200
    assert [event for event in _events(path, "tenant-a") if event["event_name"] == "relevant_opportunity_viewed"] == []


def test_successful_material_workflow_transition_emits_bounded_action(tmp_path, monkeypatch):
    path, opportunity_id = _seed(monkeypatch, tmp_path)
    response = api.APP.test_client().post(
        f"/api/v1/opportunities/{opportunity_id}/workflow",
        json={"status": "REVIEWING", "note": "private note must not enter telemetry"},
    )

    assert response.status_code == 200
    actions = [event for event in _events(path, "tenant-a") if event["event_name"] == "action_taken"]
    assert len(actions) == 1
    metadata = json.loads(actions[0]["metadata_json"])
    assert metadata == {
        "source": "TED",
        "external_id": "OBS-1",
        "from_status": "NEW",
        "to_status": "REVIEWING",
    }
    assert "note" not in metadata
    assert _events(path, "tenant-b") == []


def test_same_status_retry_or_note_only_change_does_not_inflate_actions(tmp_path, monkeypatch):
    path, opportunity_id = _seed(monkeypatch, tmp_path)
    client = api.APP.test_client()
    assert client.post(
        f"/api/v1/opportunities/{opportunity_id}/workflow",
        json={"status": "REVIEWING", "note": "first"},
    ).status_code == 200
    before = len([event for event in _events(path, "tenant-a") if event["event_name"] == "action_taken"])
    assert before == 1

    assert client.post(
        f"/api/v1/opportunities/{opportunity_id}/workflow",
        json={"status": "REVIEWING", "note": "note-only retry"},
    ).status_code == 200
    after = len([event for event in _events(path, "tenant-a") if event["event_name"] == "action_taken"])
    assert after == before


def test_unknown_relevance_workflow_transition_remains_unobserved_value(tmp_path, monkeypatch):
    path, opportunity_id = _seed(monkeypatch, tmp_path, relevance_state="UNKNOWN", eligible=False)
    response = api.APP.test_client().post(
        f"/api/v1/opportunities/{opportunity_id}/workflow",
        json={"status": "REVIEWING"},
    )

    assert response.status_code == 200
    assert [event for event in _events(path, "tenant-a") if event["event_name"] == "action_taken"] == []
