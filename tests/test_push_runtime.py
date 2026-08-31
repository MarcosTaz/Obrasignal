from datetime import datetime, timezone
import sqlite3

import pytest

import push_runtime


def _connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _base_schema(conn):
    conn.execute("CREATE TABLE accounts(account_id TEXT PRIMARY KEY, status TEXT NOT NULL)")
    conn.execute("""CREATE TABLE tenders(
        id INTEGER PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL,
        title TEXT, deadline TEXT
    )""")
    conn.execute("""CREATE TABLE opportunity_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL,
        event_key TEXT NOT NULL UNIQUE, tender_id INTEGER, source TEXT,
        event_type TEXT NOT NULL, score INTEGER DEFAULT 0, created_at TEXT NOT NULL,
        delivered_at TEXT
    )""")
    conn.commit()


@pytest.fixture
def push_db(tmp_path, monkeypatch):
    path = tmp_path / "push.db"
    conn = _connect(path)
    _base_schema(conn)
    push_runtime.ensure_push_schema(conn)
    conn.close()
    monkeypatch.setattr(push_runtime, "_db", lambda: _connect(path))
    return path


def _seed_account(path, account_id="acct-a", status="active"):
    conn = _connect(path)
    conn.execute("INSERT INTO accounts(account_id,status) VALUES(?,?)", (account_id, status))
    conn.commit()
    return conn


def _register(conn, account_id="acct-a", token="ExpoPushToken[AAAAAAAAAAAAAAAAAAAAAA]"):
    push_runtime.set_preference(
        conn, account_id, enabled=True, timezone_name="Europe/Lisbon", local_hour=8, local_minute=0
    )
    push_runtime.register_device(
        conn, account_id, token=token, platform="ios", timezone_name="Europe/Lisbon"
    )
    return token


def test_schedule_accepts_seven_or_eight_and_rejects_other_hours():
    assert push_runtime._valid_schedule(7, 30) == (7, 30)
    assert push_runtime._valid_schedule(8, 0) == (8, 0)
    with pytest.raises(ValueError, match="invalid_schedule"):
        push_runtime._valid_schedule(9, 0)


def test_lisbon_summer_schedule_is_due_at_0800_local():
    due, local_date, target = push_runtime._due(
        {"timezone": "Europe/Lisbon", "local_hour": 8, "local_minute": 0},
        datetime(2026, 8, 31, 7, 5, tzinfo=timezone.utc),
    )
    assert due is True
    assert local_date == "2026-08-31"
    assert target.hour == 8 and target.utcoffset().total_seconds() == 3600


def test_push_token_is_reassigned_atomically_between_tenants(push_db):
    conn = _connect(push_db)
    conn.executemany("INSERT INTO accounts(account_id,status) VALUES(?, 'active')", [("acct-a",), ("acct-b",)])
    token = "ExponentPushToken[BBBBBBBBBBBBBBBBBBBBBB]"
    push_runtime.register_device(conn, "acct-a", token=token, platform="android", timezone_name="Europe/Lisbon")
    push_runtime.register_device(conn, "acct-b", token=token, platform="android", timezone_name="Europe/Lisbon")
    row = conn.execute("SELECT account_id,enabled FROM push_devices WHERE token=?", (token,)).fetchone()
    assert dict(row) == {"account_id": "acct-b", "enabled": 1}
    conn.close()


def test_disabling_preference_disables_all_account_devices(push_db):
    conn = _seed_account(push_db)
    _register(conn)
    push_runtime.set_preference(conn, "acct-a", enabled=False, timezone_name="Europe/Lisbon")
    assert conn.execute("SELECT enabled FROM push_devices WHERE account_id='acct-a'").fetchone()[0] == 0
    assert push_runtime._preference(conn, "acct-a")["enabled"] is False
    conn.close()


def test_signout_can_disable_only_one_device(push_db):
    conn = _seed_account(push_db)
    token_a = _register(conn, token="ExpoPushToken[CCCCCCCCCCCCCCCCCCCCCC]")
    token_b = "ExpoPushToken[DDDDDDDDDDDDDDDDDDDDDD]"
    push_runtime.register_device(conn, "acct-a", token=token_b, platform="android", timezone_name="Europe/Lisbon")
    assert push_runtime.unregister_device(conn, "acct-a", token_a) == 1
    states = {r["token"]: r["enabled"] for r in conn.execute("SELECT token,enabled FROM push_devices")}
    assert states[token_a] == 0 and states[token_b] == 1
    conn.close()


def test_invalid_token_fails_closed(push_db):
    conn = _seed_account(push_db)
    with pytest.raises(ValueError, match="invalid_push_token"):
        push_runtime.register_device(conn, "acct-a", token="not-a-token", platform="ios", timezone_name="Europe/Lisbon")
    conn.close()


def test_daily_digest_sends_when_app_is_not_running_and_is_idempotent(push_db):
    conn = _seed_account(push_db)
    token = _register(conn)
    conn.execute("INSERT INTO tenders(id,source,external_id,title,deadline) VALUES(1,'TED','x1','Escola nova','2099-09-10')")
    conn.execute("""INSERT INTO opportunity_events(account_id,event_key,tender_id,source,event_type,score,created_at)
                    VALUES('acct-a','acct-a:TED:x1',1,'TED','new_high_match',91,'2026-08-30T09:00:00+00:00')""")
    conn.commit(); conn.close()

    calls = []
    def sender(tokens, **payload):
        calls.append((tokens, payload))
        return list(tokens), {}

    now = datetime(2026, 8, 31, 7, 5, tzinfo=timezone.utc)  # 08:05 Europe/Lisbon
    first = push_runtime.deliver_due_digests(now_utc=now, send_func=sender)
    second = push_runtime.deliver_due_digests(now_utc=now, send_func=sender)
    assert first["sent"] == 1 and second["sent"] == 0
    assert len(calls) == 1 and calls[0][0] == [token]
    assert calls[0][1]["data"]["count"] == 1
    conn = _connect(push_db)
    row = conn.execute("SELECT status,event_count FROM push_digest_deliveries WHERE account_id='acct-a'").fetchone()
    assert dict(row) == {"status": "sent", "event_count": 1}
    conn.close()


def test_daily_digest_still_notifies_when_there_are_zero_new_matches(push_db):
    conn = _seed_account(push_db)
    _register(conn); conn.close()
    calls = []
    def sender(tokens, **payload):
        calls.append(payload)
        return list(tokens), {}
    out = push_runtime.deliver_due_digests(
        now_utc=datetime(2026, 8, 31, 7, 1, tzinfo=timezone.utc), send_func=sender
    )
    assert out["sent"] == 1 and len(calls) == 1
    assert calls[0]["data"]["count"] == 0
    assert "Sem novas oportunidades" in calls[0]["body"]


def test_failed_delivery_is_retryable_within_morning_window(push_db):
    conn = _seed_account(push_db)
    _register(conn); conn.close()
    attempts = {"count": 0}
    def flaky(tokens, **payload):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("provider_down")
        return list(tokens), {}
    now = datetime(2026, 8, 31, 7, 10, tzinfo=timezone.utc)
    assert push_runtime.deliver_due_digests(now_utc=now, send_func=flaky)["failed"] == 1
    assert push_runtime.deliver_due_digests(now_utc=now, send_func=flaky)["sent"] == 1
    assert attempts["count"] == 2


def test_inactive_account_never_receives_digest(push_db):
    conn = _seed_account(push_db, status="deleting")
    _register(conn); conn.close()
    calls = []
    out = push_runtime.deliver_due_digests(
        now_utc=datetime(2026, 8, 31, 7, 5, tzinfo=timezone.utc),
        send_func=lambda *a, **k: calls.append((a, k)) or (list(a[0]), {}),
    )
    assert out["accounts_due"] == 0 and calls == []
