"""Notification Delivery owner contract for account privacy lifecycle.

This module deliberately owns only the push-device/push-delivery lifecycle seam.
It does not perform account deletion, Auth revocation, provider credential changes,
or device-local cache cleanup. Privacy may consume these functions inside its own
transaction once composition ownership is agreed.
"""
from __future__ import annotations

from dataclasses import dataclass

from flask import jsonify, request
from jwt import InvalidTokenError

from app import APP
from auth_context import configured_identity


DELETION_STATES = frozenset({
    "deletion_pending",
    "deletion_failed",
    "deleted_pending_revocation",
    "deleted",
})
TERMINAL_DELETION_STATES = frozenset({"deleted_pending_revocation", "deleted"})


class NotificationPrivacyContractError(RuntimeError):
    """Notification lifecycle state cannot support a truthful private-data action."""


@dataclass(frozen=True)
class NotificationDatasetLifecycleContract:
    owner: str
    tenant_path: str
    export_status: str
    deletion_status: str
    retention_status: str
    cleanup_order: int


DATASET_CONTRACTS = {
    "push_deliveries": NotificationDatasetLifecycleContract(
        owner="Notification Delivery / #263",
        tenant_path=(
            "push_deliveries.event_id -> opportunity_events.id -> account_id; "
            "push_deliveries.push_device_id -> push_devices.id -> account_id"
        ),
        export_status="INCLUDE_SANITIZED",
        deletion_status="DELETE",
        retention_status="RETAIN_WHILE_ACCOUNT_EXISTS_NO_TIME_ASSERTION",
        cleanup_order=10,
    ),
    "push_devices": NotificationDatasetLifecycleContract(
        owner="Notification Delivery / #263",
        tenant_path="push_devices.account_id",
        export_status="INCLUDE_SANITIZED",
        deletion_status="DELETE",
        retention_status="RETAIN_WHILE_ACCOUNT_EXISTS_NO_TIME_ASSERTION",
        cleanup_order=20,
    ),
}

# These are routing/tap credentials or provider identifiers, not customer-facing
# export payload. Their existence is represented without returning the raw value.
PUSH_DEVICE_EXPORT_FIELDS = (
    "id",
    "installation_id",
    "platform",
    "created_at",
    "updated_at",
    "last_error",
    "revoked_at",
)
PUSH_DEVICE_EXPORT_EXCLUDED_FIELDS = ("account_id", "expo_push_token", "binding_id")
PUSH_DELIVERY_EXPORT_FIELDS = (
    "id",
    "event_id",
    "push_device_id",
    "submitted_at",
    "last_error",
    "attempt_count",
    "last_attempt_at",
    "next_attempt_at",
    "receipt_status",
    "receipt_checked_at",
    "receipt_error",
    "failed_at",
)
PUSH_DELIVERY_EXPORT_EXCLUDED_FIELDS = ("ticket_id", "expo_push_token")


def _table_names(conn) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }


def notification_account_status(conn, account_id: str) -> str | None:
    """Read lifecycle state observationally; never create the accounts table."""
    if "accounts" not in _table_names(conn):
        return None
    row = conn.execute(
        "SELECT status FROM accounts WHERE account_id=?",
        (str(account_id),),
    ).fetchone()
    return str(row[0]) if row else None


def notification_account_accepts_new_binding(conn, account_id: str) -> bool:
    status = notification_account_status(conn, account_id)
    return status not in DELETION_STATES


def _require_push_tables(conn) -> None:
    tables = _table_names(conn)
    missing = sorted({"opportunity_events", "push_devices", "push_deliveries"} - tables)
    if missing:
        raise NotificationPrivacyContractError(
            "notification_privacy_tables_missing:" + ",".join(missing)
        )


def _delivery_chain_rows(conn, account_id: str):
    account_id = str(account_id)
    return conn.execute(
        """SELECT pd.id AS delivery_id,
                  pd.event_id,
                  pd.push_device_id,
                  e.account_id AS event_account_id,
                  d.account_id AS device_account_id
           FROM push_deliveries pd
           LEFT JOIN opportunity_events e ON e.id=pd.event_id
           LEFT JOIN push_devices d ON d.id=pd.push_device_id
           WHERE e.account_id=? OR d.account_id=?
           ORDER BY pd.id""",
        (account_id, account_id),
    ).fetchall()


def assert_notification_delivery_tenant_chain(conn, account_id: str) -> None:
    """Fail closed on orphan or cross-account delivery ownership."""
    _require_push_tables(conn)
    account_id = str(account_id)
    for row in _delivery_chain_rows(conn, account_id):
        event_account = row["event_account_id"]
        device_account = row["device_account_id"]
        if event_account is None or device_account is None:
            raise NotificationPrivacyContractError("notification_delivery_orphan_chain")
        if str(event_account) != str(device_account):
            raise NotificationPrivacyContractError("notification_delivery_cross_account_chain")
        if str(event_account) != account_id:
            raise NotificationPrivacyContractError("notification_delivery_tenant_chain_mismatch")


def export_notification_account_data(conn, account_id: str) -> dict:
    """Return privacy-complete notification metadata without routing credentials."""
    account_id = str(account_id)
    _require_push_tables(conn)
    if notification_account_status(conn, account_id) in DELETION_STATES:
        raise NotificationPrivacyContractError("notification_export_blocked_by_deletion_state")
    assert_notification_delivery_tenant_chain(conn, account_id)

    device_rows = conn.execute(
        "SELECT * FROM push_devices WHERE account_id=? ORDER BY id",
        (account_id,),
    ).fetchall()
    devices = []
    for row in device_rows:
        item = {name: row[name] for name in PUSH_DEVICE_EXPORT_FIELDS}
        item["provider_token_present"] = bool(row["expo_push_token"])
        item["tap_binding_present"] = bool(row["binding_id"])
        devices.append(item)

    delivery_rows = conn.execute(
        """SELECT pd.*
           FROM push_deliveries pd
           JOIN opportunity_events e ON e.id=pd.event_id
           JOIN push_devices d ON d.id=pd.push_device_id
           WHERE e.account_id=? AND d.account_id=?
           ORDER BY pd.id""",
        (account_id, account_id),
    ).fetchall()
    deliveries = []
    for row in delivery_rows:
        item = {name: row[name] for name in PUSH_DELIVERY_EXPORT_FIELDS}
        item["provider_ticket_present"] = bool(row["ticket_id"])
        deliveries.append(item)

    return {
        "push_devices": devices,
        "push_deliveries": deliveries,
        "scope": {
            "owner": "Notification Delivery / #263",
            "export_status": "INCLUDE_SANITIZED",
            "excluded_raw_fields": {
                "push_devices": list(PUSH_DEVICE_EXPORT_EXCLUDED_FIELDS),
                "push_deliveries": list(PUSH_DELIVERY_EXPORT_EXCLUDED_FIELDS),
            },
            "provider_acceptance_is_delivery": False,
        },
    }


def _remaining_global_delivery_integrity_error(conn) -> str | None:
    row = conn.execute(
        """SELECT pd.id,
                  e.account_id AS event_account_id,
                  d.account_id AS device_account_id
           FROM push_deliveries pd
           LEFT JOIN opportunity_events e ON e.id=pd.event_id
           LEFT JOIN push_devices d ON d.id=pd.push_device_id
           WHERE e.id IS NULL OR d.id IS NULL OR e.account_id<>d.account_id
           LIMIT 1"""
    ).fetchone()
    if not row:
        return None
    if row["event_account_id"] is None or row["device_account_id"] is None:
        return "notification_delivery_orphan_chain"
    return "notification_delivery_cross_account_chain"


def assert_notification_account_cleanup_postconditions(conn, account_id: str) -> None:
    """Prove no server push ownership or pending delivery remains for one account."""
    _require_push_tables(conn)
    account_id = str(account_id)
    if conn.execute(
        "SELECT 1 FROM push_devices WHERE account_id=? LIMIT 1",
        (account_id,),
    ).fetchone():
        raise NotificationPrivacyContractError("notification_device_private_association_remains")
    if conn.execute(
        """SELECT 1
           FROM push_deliveries pd
           JOIN opportunity_events e ON e.id=pd.event_id
           WHERE e.account_id=?
           LIMIT 1""",
        (account_id,),
    ).fetchone():
        raise NotificationPrivacyContractError("notification_delivery_private_association_remains")
    integrity_error = _remaining_global_delivery_integrity_error(conn)
    if integrity_error:
        raise NotificationPrivacyContractError(integrity_error)


def delete_notification_account_data(conn, account_id: str) -> dict:
    """Delete push private state in owner-safe order without committing caller state.

    Privacy must call this while the account is already ``deletion_pending`` inside
    its destructive transaction. Delivery rows are removed before device rows so
    no delivery is orphaned; Privacy may then delete ``opportunity_events``.
    Revoked/dead-token tombstones are intentionally deleted with the account.
    """
    account_id = str(account_id)
    _require_push_tables(conn)
    status = notification_account_status(conn, account_id)
    if status in TERMINAL_DELETION_STATES:
        assert_notification_account_cleanup_postconditions(conn, account_id)
        return {
            "deleted_push_deliveries": 0,
            "deleted_push_devices": 0,
            "idempotent": True,
        }
    if status != "deletion_pending":
        raise NotificationPrivacyContractError("notification_cleanup_requires_deletion_pending")

    assert_notification_delivery_tenant_chain(conn, account_id)
    event_ids = [
        int(row[0])
        for row in conn.execute(
            "SELECT id FROM opportunity_events WHERE account_id=? ORDER BY id",
            (account_id,),
        ).fetchall()
    ]
    device_ids = [
        int(row[0])
        for row in conn.execute(
            "SELECT id FROM push_devices WHERE account_id=? ORDER BY id",
            (account_id,),
        ).fetchall()
    ]

    delivery_ids = []
    if event_ids or device_ids:
        event_placeholders = ",".join("?" for _ in event_ids) or "NULL"
        device_placeholders = ",".join("?" for _ in device_ids) or "NULL"
        delivery_ids = [
            int(row[0])
            for row in conn.execute(
                f"""SELECT id FROM push_deliveries
                    WHERE event_id IN ({event_placeholders})
                       OR push_device_id IN ({device_placeholders})
                    ORDER BY id""",
                tuple(event_ids) + tuple(device_ids),
            ).fetchall()
        ]
    if delivery_ids:
        placeholders = ",".join("?" for _ in delivery_ids)
        conn.execute(
            f"DELETE FROM push_deliveries WHERE id IN ({placeholders})",
            tuple(delivery_ids),
        )
    if device_ids:
        placeholders = ",".join("?" for _ in device_ids)
        conn.execute(
            f"DELETE FROM push_devices WHERE id IN ({placeholders})",
            tuple(device_ids),
        )

    assert_notification_account_cleanup_postconditions(conn, account_id)
    return {
        "deleted_push_deliveries": len(delivery_ids),
        "deleted_push_devices": len(device_ids),
        "idempotent": False,
        "cleanup_order": ["push_deliveries", "push_devices", "opportunity_events_by_privacy_owner"],
        "retention": "NO_TIME_BASED_RETENTION_ASSERTED",
        "late_provider_receipt": "IGNORE_NO_LOCAL_ROW_NO_REHYDRATION",
        "retry_after_deletion": "DISABLED_BY_ROW_DELETION",
        "dead_token_tombstone": "RETAIN_WHILE_ACCOUNT_EXISTS_DELETE_WITH_ACCOUNT",
        "token_rotation_or_rebind_after_deletion": "BLOCK_AT_PUSH_ROUTE",
    }


def _db():
    factory = APP.config.get("OBRASIGNAL_DB_CONNECT")
    if callable(factory):
        return factory()
    return __import__("app").db()


@APP.before_request
def _notification_privacy_lifecycle_push_guard():
    """Prevent a deletion-state identity from creating a new push association."""
    if request.method == "OPTIONS" or request.path != "/api/v1/push/devices":
        return None
    try:
        identity = configured_identity()
    except (RuntimeError, InvalidTokenError):
        return None  # Canonical Auth remains authoritative for auth failure.
    conn = _db()
    try:
        status = notification_account_status(conn, identity.account_id)
        if status not in DELETION_STATES:
            return None
        code = 410 if status in TERMINAL_DELETION_STATES else 409
        return jsonify({
            "error": "account_notification_lifecycle_block",
            "account_state": status,
            "notification_registration_allowed": False,
        }), code
    finally:
        conn.close()
