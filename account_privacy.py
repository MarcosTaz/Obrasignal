"""Tenant-safe customer account export and deletion lifecycle.

This module owns ObraSignal product-data privacy orchestration only. Authentication,
billing-provider state, device-local cache and external session/device revocation stay
with their canonical owners and are represented here as explicit boundaries.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json

from flask import Blueprint, jsonify, request
from jwt import InvalidTokenError

from app import APP
from auth_context import configured_identity

bp = Blueprint("account_privacy", __name__, url_prefix="/api/v1/account")

EXPORT_SCHEMA_VERSION = "account-export.v1"
DELETE_CONFIRMATION = "DELETE_MY_OBRASIGNAL_DATA"

# Current canonical server-side account-owned persistence on main@66d43f6.
# This is intentionally explicit: a new account-scoped table must be reviewed by
# this lifecycle owner before export/deletion may claim completeness.
ACCOUNT_SCOPED_TABLES = frozenset({
    "accounts",
    "company_profiles",
    "opportunity_decisions",
    "opportunity_events",
    "opportunity_workflow",
    "evaluation_events",
})
DEPENDENT_PRIVATE_TABLES = (
    "company_profiles",
    "opportunity_decisions",
    "opportunity_events",
    "opportunity_workflow",
    "evaluation_events",
)
KNOWN_ACCOUNT_COLUMNS = frozenset({
    "account_id",
    "status",
    "plan",
    "created_at",
    "trial_ends_at",
    "entitlement_expires_at",
    "store",
    "product_id",
    "original_transaction_id",
    "subscription_status",
    "billing_synced_at",
    "evaluation_type",
    "evaluation_status",
    "evaluation_activated_at",
    "evaluation_ends_at",
    "evaluation_extension_days",
    "evaluation_value_status",
    "evaluation_activation_reason",
    "evaluation_extension_reason",
})
DELETION_STATES = frozenset({
    "deletion_pending",
    "deletion_failed",
    "deleted_pending_revocation",
    "deleted",
})


class AccountDataContractError(RuntimeError):
    """Current storage cannot support a truthful complete account operation."""


class AccountDeletionError(RuntimeError):
    """Deletion cleanup failed and was not reported as completed."""


def _db():
    return __import__("app").db()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _table_names(conn) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }


def _columns(conn, table: str) -> set[str]:
    return {
        str(row[1])
        for row in conn.execute(f"PRAGMA table_info({_quote_identifier(table)})").fetchall()
    }


def account_data_inventory(conn) -> dict:
    """Return the executable account-owned persistence contract.

    Any new table carrying ``account_id`` is considered tenant-private until the
    account/privacy owner explicitly classifies it. That makes future feature
    integration fail closed instead of silently omitting data from export/deletion.
    """
    tables = _table_names(conn)
    scoped = {name for name in tables if "account_id" in _columns(conn, name)}
    missing = sorted(ACCOUNT_SCOPED_TABLES - scoped)
    unknown = sorted(scoped - ACCOUNT_SCOPED_TABLES)
    account_columns = _columns(conn, "accounts") if "accounts" in tables else set()
    unknown_account_columns = sorted(account_columns - KNOWN_ACCOUNT_COLUMNS)
    return {
        "required": sorted(ACCOUNT_SCOPED_TABLES),
        "discovered": sorted(scoped),
        "missing": missing,
        "unknown": unknown,
        "unknown_account_columns": unknown_account_columns,
    }


def _assert_export_contract(conn) -> dict:
    inventory = account_data_inventory(conn)
    if inventory["missing"] or inventory["unknown"]:
        raise AccountDataContractError("account_data_contract_incomplete")
    return inventory


def _assert_deletion_contract(conn) -> dict:
    inventory = _assert_export_contract(conn)
    if inventory["unknown_account_columns"]:
        # Export SELECT * naturally includes additive account columns, but deletion
        # may not guess whether a newly added column must be scrubbed or retained.
        raise AccountDataContractError("account_deletion_contract_incomplete")
    return inventory


def _parse_json(value, *, field: str, default):
    if value in (None, ""):
        return default
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AccountDataContractError("corrupt_account_private_data") from exc
    if field in {"profile_json", "features_json", "metadata_json"} and not isinstance(parsed, dict):
        raise AccountDataContractError("corrupt_account_private_data")
    return parsed


def _rows(conn, sql: str, params=()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _ensure_legacy_profile_imported(conn, account_id: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM company_profiles WHERE account_id=?", (str(account_id),)
    ).fetchone()
    if row:
        return
    # Consume the Company Profile owner's public read contract. Historical
    # profile files are imported by that owner into canonical durable storage.
    from company_profile import load_profile

    load_profile(str(account_id))


def export_account_data(conn, account_id: str) -> dict:
    """Export current canonical server-owned private state for exactly one tenant."""
    account_id = str(account_id)
    inventory = _assert_export_contract(conn)
    account = conn.execute("SELECT * FROM accounts WHERE account_id=?", (account_id,)).fetchone()
    if account is None:
        raise LookupError("account_not_found")

    # Make the profile owner's historical import path observable to this export
    # without reading or deleting its private filesystem implementation directly.
    _ensure_legacy_profile_imported(conn, account_id)

    profile_row = conn.execute(
        "SELECT profile_json, updated_at FROM company_profiles WHERE account_id=?", (account_id,)
    ).fetchone()
    profile = None
    if profile_row is not None:
        profile = {
            "profile": _parse_json(profile_row["profile_json"], field="profile_json", default={}),
            "updated_at": profile_row["updated_at"],
        }

    decisions = _rows(
        conn,
        "SELECT * FROM opportunity_decisions WHERE account_id=? ORDER BY id",
        (account_id,),
    )
    for item in decisions:
        item["features"] = _parse_json(item.pop("features_json"), field="features_json", default={})

    events = _rows(
        conn,
        "SELECT * FROM opportunity_events WHERE account_id=? ORDER BY id",
        (account_id,),
    )
    workflow = _rows(
        conn,
        "SELECT * FROM opportunity_workflow WHERE account_id=? ORDER BY id",
        (account_id,),
    )
    evaluation = _rows(
        conn,
        "SELECT * FROM evaluation_events WHERE account_id=? ORDER BY id",
        (account_id,),
    )
    for item in evaluation:
        item["metadata"] = _parse_json(item.pop("metadata_json"), field="metadata_json", default={})

    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "generated_at": _now(),
        "account": dict(account),
        "company_profile": profile,
        "opportunity_decisions": decisions,
        "opportunity_events": events,
        "opportunity_workflow": workflow,
        "evaluation_events": evaluation,
        "scope": {
            "server_owned_account_tables": inventory["required"],
            "completeness": "CURRENT_CANONICAL_SERVER_ACCOUNT_DATA_ONLY",
            "shared_public_procurement_data_included": False,
            "identity_provider_data_included": False,
            "billing_provider_source_records_included": False,
            "device_local_private_cache_included": False,
        },
    }


def _account_status(conn, account_id: str) -> str | None:
    row = conn.execute("SELECT status FROM accounts WHERE account_id=?", (str(account_id),)).fetchone()
    return str(row[0]) if row else None


def deletion_state(conn, account_id: str) -> dict:
    status = _account_status(conn, account_id)
    if status is None:
        return {"state": "NOT_FOUND", "product_private_db_deleted": None, "external_revocation": "UNKNOWN"}
    if status == "deleted":
        return {"state": "COMPLETED", "product_private_db_deleted": True, "external_revocation": "PROVEN_EXTERNAL"}
    if status == "deleted_pending_revocation":
        return {"state": "PENDING", "product_private_db_deleted": True, "external_revocation": "PENDING"}
    if status == "deletion_pending":
        return {"state": "PENDING", "product_private_db_deleted": False, "external_revocation": "NOT_STARTED"}
    if status == "deletion_failed":
        return {"state": "FAILED", "product_private_db_deleted": False, "external_revocation": "NOT_STARTED"}
    return {"state": "NONE", "product_private_db_deleted": False, "external_revocation": "NOT_STARTED"}


def _dependent_counts(conn, account_id: str) -> dict[str, int]:
    counts = {}
    for table in DEPENDENT_PRIVATE_TABLES:
        counts[table] = int(
            conn.execute(
                f"SELECT COUNT(*) FROM {_quote_identifier(table)} WHERE account_id=?",
                (str(account_id),),
            ).fetchone()[0]
        )
    return counts


def _postconditions_hold(conn, account_id: str) -> bool:
    if any(_dependent_counts(conn, account_id).values()):
        return False
    row = conn.execute("SELECT * FROM accounts WHERE account_id=?", (str(account_id),)).fetchone()
    if row is None:
        # Current Auth/Billing contracts can recreate a missing row. Keep a minimal
        # anti-resurrection tombstone until external revocation is actually proven.
        return False
    account = dict(row)
    if account.get("status") != "deleted_pending_revocation":
        return False
    if account.get("plan") != "expired" or account.get("subscription_status") != "none":
        return False
    must_be_empty = (
        "trial_ends_at",
        "entitlement_expires_at",
        "store",
        "product_id",
        "original_transaction_id",
        "billing_synced_at",
        "evaluation_type",
        "evaluation_status",
        "evaluation_activated_at",
        "evaluation_ends_at",
        "evaluation_value_status",
        "evaluation_activation_reason",
        "evaluation_extension_reason",
    )
    return all(account.get(name) is None for name in must_be_empty) and int(account.get("evaluation_extension_days") or 0) == 0


def request_account_deletion(conn, account_id: str) -> dict:
    """Delete canonical private DB dependants, but never overclaim external revocation.

    Completion deliberately stops at ``PENDING`` because Supabase identity/session
    revocation, device-local cache cleanup and any legacy profile-file destruction
    belong to other owners and are not proven by this server transaction.
    """
    account_id = str(account_id)
    row = conn.execute("SELECT 1 FROM accounts WHERE account_id=?", (account_id,)).fetchone()
    if row is None:
        raise LookupError("account_not_found")

    existing = deletion_state(conn, account_id)
    if existing["state"] == "COMPLETED" or _account_status(conn, account_id) == "deleted_pending_revocation":
        return existing
    if _account_status(conn, account_id) == "deletion_pending":
        return existing

    try:
        _assert_deletion_contract(conn)
    except AccountDataContractError:
        conn.execute("UPDATE accounts SET status='deletion_failed' WHERE account_id=?", (account_id,))
        conn.commit()
        raise

    # Make an interrupted cleanup visibly pending before the destructive transaction.
    conn.execute("UPDATE accounts SET status='deletion_pending' WHERE account_id=?", (account_id,))
    conn.commit()

    try:
        conn.execute("BEGIN IMMEDIATE")
        for table in DEPENDENT_PRIVATE_TABLES:
            conn.execute(
                f"DELETE FROM {_quote_identifier(table)} WHERE account_id=?",
                (account_id,),
            )
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
        if not _postconditions_hold(conn, account_id):
            raise AccountDeletionError("account_deletion_postcondition_failed")
        conn.commit()
    except Exception as exc:
        conn.rollback()
        conn.execute("UPDATE accounts SET status='deletion_failed' WHERE account_id=?", (account_id,))
        conn.commit()
        if isinstance(exc, AccountDeletionError):
            raise
        raise AccountDeletionError("account_deletion_failed") from exc

    state = deletion_state(conn, account_id)
    state.update({
        "server_cleanup": {
            "deleted_private_tables": list(DEPENDENT_PRIVATE_TABLES),
            "shared_public_procurement_deleted": False,
            "minimal_account_tombstone_retained": True,
        },
        "pending_boundaries": [
            "AUTH_PROVIDER_IDENTITY_AND_SESSION_REVOCATION",
            "DEVICE_LOCAL_PRIVATE_CACHE_PURGE_VIA_291",
            "LEGACY_PROFILE_FILE_RETENTION_REVIEW",
            "BILLING_PROVIDER_ACCOUNT_RECONCILIATION",
        ],
    })
    return state


def _authenticated_identity():
    try:
        return configured_identity(), None
    except (RuntimeError, InvalidTokenError):
        return None, (jsonify({"error": "authentication_required"}), 401)


@bp.get("/export")
def account_export():
    identity, failure = _authenticated_identity()
    if failure:
        return failure
    conn = _db()
    try:
        status = _account_status(conn, identity.account_id)
        if status in {"deletion_pending", "deleted_pending_revocation", "deleted"}:
            return jsonify({"error": "account_deletion_in_progress_or_completed", "deletion": deletion_state(conn, identity.account_id)}), 410
        try:
            payload = export_account_data(conn, identity.account_id)
        except LookupError:
            return jsonify({"error": "account_not_found"}), 404
        except AccountDataContractError:
            return jsonify({"error": "account_export_unavailable", "reason": "account_data_contract_unproven"}), 409
        return jsonify(payload)
    finally:
        conn.close()


@bp.route("/deletion", methods=["GET", "POST"])
def account_deletion():
    identity, failure = _authenticated_identity()
    if failure:
        return failure
    conn = _db()
    try:
        if request.method == "GET":
            state = deletion_state(conn, identity.account_id)
            return jsonify({"account_id": identity.account_id, **state})

        payload = request.get_json(silent=True) or {}
        if payload.get("confirmation") != DELETE_CONFIRMATION:
            return jsonify({
                "error": "explicit_deletion_confirmation_required",
                "required_confirmation": DELETE_CONFIRMATION,
            }), 400
        try:
            state = request_account_deletion(conn, identity.account_id)
        except LookupError:
            return jsonify({"error": "account_not_found"}), 404
        except AccountDataContractError:
            return jsonify({"error": "account_deletion_failed", "state": "FAILED", "reason": "account_data_contract_unproven"}), 409
        except AccountDeletionError:
            return jsonify({"error": "account_deletion_failed", "state": "FAILED", "reason": "postcondition_unproven"}), 500
        code = 200 if state["state"] == "COMPLETED" else 202
        return jsonify({"account_id": identity.account_id, **state}), code
    finally:
        conn.close()


@APP.before_request
def _privacy_lifecycle_guard():
    """Prevent a deletion-state identity from reading/writing ordinary private APIs."""
    if request.method == "OPTIONS" or not request.path.startswith("/api/v1/"):
        return None
    if request.path.startswith("/api/v1/account/"):
        return None
    if request.path in {"/api/v1/health", "/api/v1/billing/webhook"}:
        return None
    try:
        identity = configured_identity()
    except (RuntimeError, InvalidTokenError):
        return None  # Canonical Auth boundary returns the authentication error.
    conn = _db()
    try:
        status = _account_status(conn, identity.account_id)
        if status not in DELETION_STATES:
            return None
        state = deletion_state(conn, identity.account_id)
        code = 410 if status in {"deleted_pending_revocation", "deleted"} else 409
        return jsonify({"error": "account_privacy_lifecycle_block", "account_state": status, "deletion": state}), code
    finally:
        conn.close()
