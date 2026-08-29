"""Repository-safe account/private-data integrity audit.

This module detects account-owned/orphaned state without deciding owner-specific
DELETE/RETAIN/ANONYMIZE policy. It is observational only and fails closed on
unclassified account state.
"""
from __future__ import annotations

from account_privacy_composition import (
    DATASET_CONTRACTS,
    account_privacy_composition_inventory,
)


def _exists(conn, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _count(conn, sql: str, params=()) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


def account_privacy_integrity_report(conn) -> dict:
    """Return explicit orphan/completeness findings for the composed local store."""
    inventory = account_privacy_composition_inventory(conn)
    findings: list[dict] = []

    for table in inventory["unclassified_direct_account_tables"]:
        findings.append({
            "kind": "UNCLASSIFIED_ACCOUNT_DATA",
            "table": table,
            "classification": "UNKNOWN",
            "count": None,
        })

    if _exists(conn, "accounts"):
        for table in inventory["direct_account_tables"]:
            if table == "accounts":
                continue
            orphan_count = _count(
                conn,
                f'SELECT COUNT(*) FROM "{table}" t LEFT JOIN accounts a ON a.account_id=t.account_id '
                'WHERE a.account_id IS NULL',
            )
            if orphan_count:
                findings.append({
                    "kind": "ORPHAN_ACCOUNT_REFERENCE",
                    "table": table,
                    "classification": "CORRUPT_OR_UNKNOWN",
                    "count": orphan_count,
                })

    if _exists(conn, "push_deliveries"):
        if _exists(conn, "opportunity_events"):
            count = _count(
                conn,
                "SELECT COUNT(*) FROM push_deliveries pd "
                "LEFT JOIN opportunity_events e ON e.id=pd.event_id WHERE e.id IS NULL",
            )
            if count:
                findings.append({
                    "kind": "ORPHAN_TRANSITIVE_REFERENCE",
                    "table": "push_deliveries",
                    "edge": "event_id->opportunity_events.id",
                    "classification": "CORRUPT_OR_UNKNOWN",
                    "count": count,
                })
        if _exists(conn, "push_devices"):
            count = _count(
                conn,
                "SELECT COUNT(*) FROM push_deliveries pd "
                "LEFT JOIN push_devices d ON d.id=pd.push_device_id WHERE d.id IS NULL",
            )
            if count:
                findings.append({
                    "kind": "ORPHAN_TRANSITIVE_REFERENCE",
                    "table": "push_deliveries",
                    "edge": "push_device_id->push_devices.id",
                    "classification": "CORRUPT_OR_UNKNOWN",
                    "count": count,
                })

        if _exists(conn, "opportunity_events") and _exists(conn, "push_devices"):
            count = _count(
                conn,
                "SELECT COUNT(*) FROM push_deliveries pd "
                "JOIN opportunity_events e ON e.id=pd.event_id "
                "JOIN push_devices d ON d.id=pd.push_device_id "
                "WHERE e.account_id<>d.account_id",
            )
            if count:
                findings.append({
                    "kind": "CROSS_TENANT_TRANSITIVE_MISMATCH",
                    "table": "push_deliveries",
                    "classification": "CRITICAL",
                    "count": count,
                })

    known_present = set(inventory["known_present"])
    unresolved = []
    for table in sorted(known_present):
        contract = DATASET_CONTRACTS[table]
        if contract.export_status.startswith("UNKNOWN") or contract.deletion_status.startswith("UNKNOWN"):
            unresolved.append(table)

    return {
        "inventory": inventory,
        "findings": findings,
        "unresolved_owner_contracts": unresolved,
        "complete_for_customer_claim": not findings and not unresolved,
    }
