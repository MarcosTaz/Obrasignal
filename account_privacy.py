"""Customer-owned account export and deletion lifecycle for ObraSignal.

This module owns only canonical account-private data persisted by the ObraSignal
server. It deliberately does not claim to delete Supabase identity records,
RevenueCat source records or device-local caches: those are external boundaries
and remain reported as pending/unknown until separately proven.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json

from flask import Blueprint, jsonify, request
from jwt import InvalidTokenError

from auth_context import configured_identity
from account_registry import ensure_account

bp = Blueprint("account_privacy", __name__, url_prefix="/api/v1/account")

EXPORT_SCHEMA_VERSION = "account-export.v1"
DELETE_CONFIRMATION = "DELETE_MY_OBRASIGNAL_DATA"

# Every current server table carrying account_id must be deliberately classified
# here. If a new private table is added later, export/deletion fail closed until
# its owner updates this contract instead of silently omitting customer data.
ACCOUNT_SCOPED_TABLES = frozenset({
    "accounts",
    "company_profiles",
    "opportunity_decisions",
    "opportunity_decision_inputs",
    "opportunity_events",
    "opportunity_workflow",
    "evaluation_events",
    "push_devices",
    "push_preferences",
    "push_digest_deliveries",
})
DEPENDENT_TABLES = (
    "company_profiles",
    "opportunity_decisions",
    "opportunity_decision_inputs",
    "opportunity_events",
    "opportunity_workflow",
    "evaluation_events",
    "push_devices",
    "push_preferences",
    "push_digest_deliveries",
)
DELETION_LOCKED_STATUSES = frozenset({
    "deletion_pending",
    "deletion_failed",
    "deleted_pending_revocation",
    "deleted",
})


class AccountPrivacyContractError(RuntimeError):
    """Storage cannot truthfully support a complete account operation."""


def _db():
    return __import__("app").db()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _tables(conn):
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }


def _columns(conn, table):
    safe = '"' + str(table).replace('"', '""') + '"'
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({safe})").fetchall()}


def account_data_inventory(conn):
    tables = _tables(conn)
    scoped = {name for name in tables if "account_id" in _columns(conn, name)}
    return {
        "required": sorted(ACCOUNT_SCOPED_TABLES),
        "discovered": sorted(scoped),
        "missing": sorted(ACCOUNT_SCOPED_TABLES - scoped),
        "unknown": sorted(scoped - ACCOUNT_SCOPED_TABLES),
    }


def _assert_contract(conn):
    inventory = account_data_inventory(conn)
    if inventory["missing"] or inventory["unknown"]:
        raise AccountPrivacyContractError("account_data_contract_incomplete")
    return inventory


def _decode_json_row(row, field, output_field):
    item = dict(row)
    raw = item.pop(field, None)
    try:
        item[output_field] = json.loads(raw) if raw else {}
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AccountPrivacyContractError("corrupt_account_private_data") from exc
    return item


def _account_row(conn, account_id):
    if "accounts" not in _tables(conn):
        return None
    return conn.execute("SELECT * FROM accounts WHERE account_id=?", (str(account_id),)).fetchone()


def deletion_state(conn, account_id):
    row = _account_row(conn, account_id)
    if row is None:
        return {
            "state": "NOT_FOUND",
            "product_private_db_deleted": None,
            "external_revocation": "UNKNOWN",
        }
    status = str(row["status"] or "active")
    if status == "deleted_pending_revocation":
        return {
            "state": "PENDING",
            "product_private_db_deleted": True,
            "external_revocation": "PENDING",
            "reason": "external_identity_billing_and_device_revocation_unproven",
        }
    if status == "deletion_pending":
        return {
            "state": "PENDING",
            "product_private_db_deleted": False,
            "external_revocation": "NOT_STARTED",
        }
    if status == "deletion_failed":
        return {
            "state": "FAILED",
            "product_private_db_deleted": False,
            "external_revocation": "NOT_STARTED",
        }
    if status == "deleted":
        # Historical raw status alone is not evidence of external completion.
        return {
            "state": "UNKNOWN",
            "product_private_db_deleted": None,
            "external_revocation": "UNKNOWN",
            "reason": "deletion_completion_evidence_unavailable",
        }
    return {
        "state": "NONE",
        "product_private_db_deleted": False,
        "external_revocation": "NOT_STARTED",
    }


def export_account_data(conn, account_id):
    account_id = str(account_id)
    inventory = _assert_contract(conn)
    account = _account_row(conn, account_id)
    if account is None:
        raise LookupError("account_not_found")
    if str(account["status"] or "") in DELETION_LOCKED_STATUSES:
        raise AccountPrivacyContractError("account_deletion_in_progress")

    profile_row = conn.execute(
        "SELECT profile_json, updated_at FROM company_profiles WHERE account_id=?",
        (account_id,),
    ).fetchone()
    profile = None
    if profile_row is not None:
        try:
            profile = {
                "profile": json.loads(profile_row["profile_json"] or "{}"),
                "updated_at": profile_row["updated_at"],
            }
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AccountPrivacyContractError("corrupt_account_private_data") from exc

    decisions = [
        _decode_json_row(row, "features_json", "features")
        for row in conn.execute(
            "SELECT * FROM opportunity_decisions WHERE account_id=? ORDER BY id",
            (account_id,),
        ).fetchall()
    ]
    decision_inputs = [dict(row) for row in conn.execute(
        "SELECT * FROM opportunity_decision_inputs WHERE account_id=? ORDER BY source,external_id",
        (account_id,),
    ).fetchall()]
    events = [dict(row) for row in conn.execute(
        "SELECT * FROM opportunity_events WHERE account_id=? ORDER BY id", (account_id,)
    ).fetchall()]
    workflow = [dict(row) for row in conn.execute(
        "SELECT * FROM opportunity_workflow WHERE account_id=? ORDER BY id", (account_id,)
    ).fetchall()]
    evaluation = [
        _decode_json_row(row, "metadata_json", "metadata")
        for row in conn.execute(
            "SELECT * FROM evaluation_events WHERE account_id=? ORDER BY id",
            (account_id,),
        ).fetchall()
    ]
    push_devices = [dict(row) for row in conn.execute(
        "SELECT * FROM push_devices WHERE account_id=? ORDER BY last_seen_at DESC, token",
        (account_id,),
    ).fetchall()]
    push_preferences = [dict(row) for row in conn.execute(
        "SELECT * FROM push_preferences WHERE account_id=? ORDER BY account_id",
        (account_id,),
    ).fetchall()]
    push_digest_deliveries = [dict(row) for row in conn.execute(
        "SELECT * FROM push_digest_deliveries WHERE account_id=? ORDER BY local_date",
        (account_id,),
    ).fetchall()]

    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "generated_at": _now(),
        "account": dict(account),
        "company_profile": profile,
        "opportunity_decisions": decisions,
        "opportunity_decision_inputs": decision_inputs,
        "opportunity_events": events,
        "opportunity_workflow": workflow,
        "evaluation_events": evaluation,
        "push_devices": push_devices,
        "push_preferences": push_preferences,
        "push_digest_deliveries": push_digest_deliveries,
        "scope": {
            "server_owned_account_tables": inventory["required"],
            "completeness": "CURRENT_CANONICAL_SERVER_ACCOUNT_DATA_ONLY",
            "shared_public_procurement_data_included": False,
            "identity_provider_data_included": False,
            "billing_provider_source_records_included": False,
            "device_local_private_cache_included": False,
        },
    }


def _private_row_counts(conn, account_id):
    return {
        table: int(conn.execute(
            f'SELECT COUNT(*) FROM "{table}" WHERE account_id=?', (str(account_id),)
        ).fetchone()[0])
        for table in DEPENDENT_TABLES
    }


def request_account_deletion(conn, account_id):
    account_id = str(account_id)
    _assert_contract(conn)
    account = _account_row(conn, account_id)
    if account is None:
        raise LookupError("account_not_found")

    existing = deletion_state(conn, account_id)
    if existing["state"] == "PENDING" and existing.get("product_private_db_deleted") is True:
        return existing

    # Persist a pending marker first. If the process stops before the destructive
    # transaction, the customer shell can fail closed on the next request.
    conn.execute("UPDATE accounts SET status='deletion_pending' WHERE account_id=?", (account_id,))
    conn.commit()
    try:
        conn.execute("BEGIN IMMEDIATE")
        for table in DEPENDENT_TABLES:
            conn.execute(f'DELETE FROM "{table}" WHERE account_id=?', (account_id,))
        conn.execute(
            """UPDATE accounts SET
               status='deleted_pending_revocation',
               plan='expired',
               trial_ends_at=NULL,
               entitlement_expires_at=NULL,
               store=NULL,
               product_id=NULL,
               original_transaction_id=NULL,
               subscription_status='none',
               billing_synced_at=NULL,
               evaluation_type=NULL,
               evaluation_status=NULL,
               evaluation_activated_at=NULL,
               evaluation_ends_at=NULL,
               evaluation_extension_days=0,
               evaluation_value_status=NULL,
               evaluation_activation_reason=NULL,
               evaluation_extension_reason=NULL
               WHERE account_id=?""",
            (account_id,),
        )
        if any(_private_row_counts(conn, account_id).values()):
            raise AccountPrivacyContractError("account_deletion_postcondition_failed")
        tombstone = _account_row(conn, account_id)
        if tombstone is None or tombstone["status"] != "deleted_pending_revocation":
            raise AccountPrivacyContractError("account_deletion_postcondition_failed")
        conn.commit()
    except Exception:
        conn.rollback()
        conn.execute("UPDATE accounts SET status='deletion_failed' WHERE account_id=?", (account_id,))
        conn.commit()
        raise
    return deletion_state(conn, account_id)


def _identity_or_response():
    try:
        identity = configured_identity()
    except (RuntimeError, InvalidTokenError):
        return None, (jsonify({"error": "authentication_required"}), 401)

    # Account privacy is a separate Flask blueprint, so it does not inherit the
    # mobile API blueprint's per-request account bootstrap. A newly authenticated
    # Supabase identity can therefore reach this endpoint before any other API
    # call has created its canonical account row. Bootstrap that row here too.
    # Deletion tombstones are retained in `accounts`, and ensure_account never
    # mutates an existing row, so this cannot reactivate a deletion-locked account.
    conn = _db()
    try:
        ensure_account(conn, identity.account_id)
    finally:
        conn.close()
    return identity, None


@bp.get("/export")
def account_export():
    identity, failure = _identity_or_response()
    if failure:
        return failure
    conn = _db()
    try:
        try:
            payload = export_account_data(conn, identity.account_id)
        except LookupError:
            return jsonify({"error": "account_not_found"}), 404
        except AccountPrivacyContractError as exc:
            return jsonify({"error": str(exc)}), 409
        return jsonify(payload)
    finally:
        conn.close()


@bp.route("/deletion", methods=["GET", "POST"])
def account_deletion():
    identity, failure = _identity_or_response()
    if failure:
        return failure
    conn = _db()
    try:
        if request.method == "GET":
            return jsonify(deletion_state(conn, identity.account_id))
        payload = request.get_json(silent=True) or {}
        if payload.get("confirmation") != DELETE_CONFIRMATION:
            return jsonify({"error": "confirmation_required", "confirmation": DELETE_CONFIRMATION}), 400
        try:
            result = request_account_deletion(conn, identity.account_id)
        except LookupError:
            return jsonify({"error": "account_not_found"}), 404
        except AccountPrivacyContractError as exc:
            return jsonify({"error": str(exc)}), 409
        except Exception:
            return jsonify({"error": "account_deletion_failed"}), 500
        return jsonify(result)
    finally:
        conn.close()
