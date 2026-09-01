import json
import sqlite3
from types import SimpleNamespace

import pytest

import account_privacy as privacy
from account_privacy import (
    AccountPrivacyContractError,
    account_data_inventory,
    deletion_state,
    export_account_data,
    request_account_deletion,
)


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE accounts(
          account_id TEXT PRIMARY KEY,
          plan TEXT NOT NULL DEFAULT 'evaluation',
          trial_ends_at TEXT,
          entitlement_expires_at TEXT,
          store TEXT,
          product_id TEXT,
          original_transaction_id TEXT,
          subscription_status TEXT NOT NULL DEFAULT 'none',
          billing_synced_at TEXT,
          status TEXT NOT NULL DEFAULT 'active',
          created_at TEXT NOT NULL,
          evaluation_type TEXT,
          evaluation_status TEXT,
          evaluation_activated_at TEXT,
          evaluation_ends_at TEXT,
          evaluation_extension_days INTEGER NOT NULL DEFAULT 0,
          evaluation_value_status TEXT,
          evaluation_activation_reason TEXT,
          evaluation_extension_reason TEXT
        );
        CREATE TABLE company_profiles(account_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE opportunity_decisions(
          id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL, source TEXT NOT NULL,
          external_id TEXT NOT NULL, decision TEXT NOT NULL, reason TEXT NOT NULL, score INTEGER,
          features_json TEXT NOT NULL, rule_version TEXT NOT NULL, decided_at TEXT NOT NULL
        );
        CREATE TABLE opportunity_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL, event_key TEXT NOT NULL,
          tender_id INTEGER, source TEXT, event_type TEXT NOT NULL, score INTEGER, created_at TEXT NOT NULL,
          delivered_at TEXT
        );
        CREATE TABLE opportunity_workflow(
          id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL, source TEXT NOT NULL,
          external_id TEXT NOT NULL, status TEXT NOT NULL, note TEXT, updated_at TEXT NOT NULL
        );
        CREATE TABLE evaluation_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL, event_name TEXT NOT NULL,
          occurred_at TEXT NOT NULL, metadata_json TEXT
        );
        CREATE TABLE push_devices(
          token TEXT PRIMARY KEY, account_id TEXT NOT NULL, platform TEXT NOT NULL, timezone TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL
        );
        CREATE TABLE push_preferences(
          account_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0, timezone TEXT NOT NULL,
          local_hour INTEGER NOT NULL, local_minute INTEGER NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE push_digest_deliveries(
          account_id TEXT NOT NULL, local_date TEXT NOT NULL, status TEXT NOT NULL,
          event_count INTEGER NOT NULL DEFAULT 0, attempted_at TEXT NOT NULL, sent_at TEXT, error TEXT,
          PRIMARY KEY(account_id, local_date)
        );
        CREATE TABLE tenders(id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT);
        """
    )
    for account in ("acct-a", "acct-b"):
        conn.execute(
            "INSERT INTO accounts(account_id,created_at,status) VALUES(?,?,?)",
            (account, "2026-08-31T00:00:00+00:00", "active"),
        )
        conn.execute(
            "INSERT INTO company_profiles(account_id,profile_json,updated_at) VALUES(?,?,?)",
            (account, json.dumps({"account_id": account, "name": account}), "2026-08-31T00:00:00+00:00"),
        )
        conn.execute(
            """INSERT INTO opportunity_decisions(account_id,source,external_id,decision,reason,score,features_json,rule_version,decided_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (account, "TED", f"{account}-1", "RELEVANT", "fit", 88, json.dumps({"explanation": account}), "v1", "2026-08-31T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO opportunity_events(account_id,event_key,event_type,created_at) VALUES(?,?,?,?)",
            (account, f"{account}:event", "new_high_match", "2026-08-31T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO opportunity_workflow(account_id,source,external_id,status,note,updated_at) VALUES(?,?,?,?,?,?)",
            (account, "TED", f"{account}-1", "REVIEWING", account, "2026-08-31T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO evaluation_events(account_id,event_name,occurred_at,metadata_json) VALUES(?,?,?,?)",
            (account, "profile_ready", "2026-08-31T00:00:00+00:00", json.dumps({"account": account})),
        )
        conn.execute(
            "INSERT INTO push_devices(token,account_id,platform,timezone,enabled,created_at,last_seen_at) VALUES(?,?,?,?,?,?,?)",
            (f"ExpoPushToken[{account}]", account, "android", "Europe/Lisbon", 1, "2026-08-31T00:00:00+00:00", "2026-08-31T01:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO push_preferences(account_id,enabled,timezone,local_hour,local_minute,updated_at) VALUES(?,?,?,?,?,?)",
            (account, 1, "Europe/Lisbon", 8, 0, "2026-08-31T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO push_digest_deliveries(account_id,local_date,status,event_count,attempted_at,sent_at) VALUES(?,?,?,?,?,?)",
            (account, "2026-08-31", "sent", 1, "2026-08-31T08:00:00+00:00", "2026-08-31T08:00:01+00:00"),
        )
    conn.execute("INSERT INTO tenders(id,source,external_id,title) VALUES(1,'TED','shared','public shared tender')")
    conn.commit()
    return conn


class _NoCloseConnection:
    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        return None


def test_inventory_classifies_every_account_scoped_table():
    conn = _db()
    inventory = account_data_inventory(conn)
    assert inventory["missing"] == []
    assert inventory["unknown"] == []
    assert {"push_devices", "push_preferences", "push_digest_deliveries"} <= set(inventory["discovered"])
    assert "tenders" not in inventory["discovered"]


def test_export_is_complete_for_owner_without_cross_tenant_or_shared_tenders():
    conn = _db()
    payload = export_account_data(conn, "acct-a")
    assert payload["schema_version"] == "account-export.v1"
    assert payload["account"]["account_id"] == "acct-a"
    assert payload["company_profile"]["profile"]["name"] == "acct-a"
    assert {row["account_id"] for row in payload["opportunity_decisions"]} == {"acct-a"}
    assert {row["account_id"] for row in payload["opportunity_events"]} == {"acct-a"}
    assert {row["account_id"] for row in payload["opportunity_workflow"]} == {"acct-a"}
    assert {row["account_id"] for row in payload["evaluation_events"]} == {"acct-a"}
    assert {row["account_id"] for row in payload["push_devices"]} == {"acct-a"}
    assert {row["account_id"] for row in payload["push_preferences"]} == {"acct-a"}
    assert {row["account_id"] for row in payload["push_digest_deliveries"]} == {"acct-a"}
    assert payload["scope"]["shared_public_procurement_data_included"] is False
    assert "tenders" not in payload["scope"]["server_owned_account_tables"]


def test_new_unclassified_private_table_makes_export_fail_closed():
    conn = _db()
    conn.execute("CREATE TABLE surprise_private(id INTEGER PRIMARY KEY, account_id TEXT NOT NULL, secret TEXT)")
    with pytest.raises(AccountPrivacyContractError, match="account_data_contract_incomplete"):
        export_account_data(conn, "acct-a")


def test_privacy_boundary_bootstraps_new_authenticated_account(monkeypatch):
    conn = _db()
    conn.execute("DELETE FROM accounts WHERE account_id='acct-a'")
    conn.commit()

    monkeypatch.setattr(privacy, "_db", lambda: _NoCloseConnection(conn))
    monkeypatch.setattr(
        privacy,
        "configured_identity",
        lambda: SimpleNamespace(account_id="acct-a"),
    )

    identity, failure = privacy._identity_or_response()

    assert failure is None
    assert identity.account_id == "acct-a"
    assert deletion_state(conn, "acct-a")["state"] == "NONE"
    row = conn.execute("SELECT status FROM accounts WHERE account_id='acct-a'").fetchone()
    assert row is not None
    assert row["status"] == "active"


def test_deletion_removes_only_target_private_rows_and_leaves_fail_closed_tombstone():
    conn = _db()
    state = request_account_deletion(conn, "acct-a")
    assert state["state"] == "PENDING"
    assert state["product_private_db_deleted"] is True
    assert state["external_revocation"] == "PENDING"

    for table in (
        "company_profiles", "opportunity_decisions", "opportunity_events", "opportunity_workflow",
        "evaluation_events", "push_devices", "push_preferences", "push_digest_deliveries",
    ):
        assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE account_id='acct-a'").fetchone()[0] == 0
        assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE account_id='acct-b'").fetchone()[0] == 1

    tombstone = dict(conn.execute("SELECT * FROM accounts WHERE account_id='acct-a'").fetchone())
    assert tombstone["status"] == "deleted_pending_revocation"
    assert tombstone["plan"] == "expired"
    assert tombstone["subscription_status"] == "none"
    assert conn.execute("SELECT COUNT(*) FROM accounts WHERE account_id='acct-b' AND status='active'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM tenders WHERE id=1").fetchone()[0] == 1


def test_deleted_tombstone_is_idempotently_reported_not_overclaimed_complete():
    conn = _db()
    first = request_account_deletion(conn, "acct-a")
    second = request_account_deletion(conn, "acct-a")
    assert first == second
    assert deletion_state(conn, "acct-a")["state"] == "PENDING"
    assert deletion_state(conn, "acct-a")["external_revocation"] == "PENDING"
