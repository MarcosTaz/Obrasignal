"""HTTP-level alert ranking and tenant-isolation regressions (offline SQLite).

The deterministic oracle sorts the ENTIRE event set before applying the page
limit. A SQL implementation that limits recent events before ranking fails.
"""
from datetime import datetime, timedelta, timezone
import random

import pytest

import app
import api


@pytest.fixture
def alert_database(tmp_path, monkeypatch):
    path = str(tmp_path / "alert-ranking.db")
    monkeypatch.setenv("OBRASIGNAL_DB", path)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "tenant-a")
    monkeypatch.setattr(app, "DB", path)
    app.init_db()
    return app.db()


def _add_event(conn, *, account, external_id, decision, score, created_at, delivered=False):
    cur = conn.execute(
        """INSERT INTO tenders(source, external_id, title, country, url,
           deadline, score, first_seen)
           VALUES ('TED', ?, ?, 'PRT', 'https://example.invalid/notice',
                   '2099-01-01', ?, ?)""",
        (external_id, external_id, score, created_at),
    )
    conn.execute(
        """INSERT INTO opportunity_decisions(
           account_id, source, external_id, decision, reason, score,
           features_json, rule_version, decided_at)
           VALUES (?, 'TED', ?, ?, 'test', ?, '{}', 'test', ?)""",
        (account, external_id, decision, score, created_at),
    )
    cur_event = conn.execute(
        """INSERT INTO opportunity_events(
           account_id,event_key,tender_id,source,event_type,score,created_at,delivered_at)
           VALUES (?, ?, ?, 'TED','new_high_match', ?, ?, ?)""",
        (account, f"{account}:{external_id}", cur.lastrowid, score, created_at,
         created_at if delivered else None),
    )
    return cur_event.lastrowid


def _oracle_priority(decision):
    return {"QUALIFIED": 0, "RELEVANT": 0, "REVIEW": 1, "UNKNOWN": 2, "REJECT": 3}[decision]


def test_alerts_rank_full_tenant_set_before_limit_and_preserve_unread_scope(alert_database):
    conn = alert_database
    rng = random.Random(310102026)
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    decisions = ["QUALIFIED", "RELEVANT", "REVIEW", "UNKNOWN", "REJECT"]
    expected = []
    for i in range(80):
        decision = rng.choice(decisions)
        score = rng.randrange(0, 101)
        created = (start + timedelta(seconds=i * 11)).isoformat()
        delivered = i % 3 == 0
        event_id = _add_event(
            conn, account="tenant-a", external_id=f"A-{i:03d}",
            decision=decision, score=score, created_at=created, delivered=delivered,
        )
        expected.append((decision, score, created, event_id, f"A-{i:03d}", delivered))
    for i in range(20):
        _add_event(
            conn, account="tenant-b", external_id=f"B-{i:03d}",
            decision="QUALIFIED", score=100,
            created_at=(start + timedelta(days=4, seconds=i)).isoformat(),
        )
    conn.commit()
    conn.close()

    client = api.APP.test_client()
    # Time is descending for score/priority ties, unlike the ascending tuple
    # above; compute the mathematical ordering explicitly without SQL reuse.
    def expected_order(records):
        return [
            row[4] for row in sorted(
                records, key=lambda row: (
                    _oracle_priority(row[0]),
                    -row[1],
                    -(datetime.fromisoformat(row[2]).timestamp()),
                    -row[3],
                ),
            )
        ]

    for limit in (1, 7, 20, 50):
        response = client.get(f"/api/v1/alerts?limit={limit}")
        assert response.status_code == 200, response.get_json()
        body = response.get_json()
        assert body["account_id"] == "tenant-a"
        assert body["count"] == limit
        assert [item["external_id"] for item in body["items"]] == expected_order(expected)[:limit]

    unread = client.get("/api/v1/alerts?unread=1&limit=50")
    assert unread.status_code == 200
    remaining = [item for item in expected if not item[5]]
    assert [item["external_id"] for item in unread.get_json()["items"]] == expected_order(remaining)[:50]
    assert all(not item["external_id"].startswith("B-") for item in unread.get_json()["items"])


@pytest.mark.parametrize("invalid", ["invalid", "1.2", "-1", "0", "51", "999999999999999999999999999999"])
def test_alerts_invalid_pagination_is_http_400(alert_database, invalid):
    alert_database.close()
    response = api.APP.test_client().get("/api/v1/alerts", query_string={"limit": invalid})
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_query"
