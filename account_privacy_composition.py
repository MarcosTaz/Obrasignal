"""Cross-owner account/private-data composition audit.

This module deliberately does not implement Notification Delivery, Company State,
Auth, Billing or persistence ownership. It consumes their observed storage contracts
so export/deletion readiness cannot silently ignore account-owned state that is
transitively tenant-bound or not yet canonical on main.
"""
from __future__ import annotations

from dataclasses import dataclass


class AccountPrivacyCompositionError(RuntimeError):
    """A composed account operation cannot truthfully claim completeness."""


@dataclass(frozen=True)
class DatasetContract:
    owner: str
    tenant_path: str
    canonicality: str
    export_status: str
    deletion_status: str
    retention_status: str
    recovery_status: str
    expected_store: str = "primary"


# Current canonical account-owned rows already handled by #342/account_privacy.
# Candidate/prebuild entries are observations of owner contracts only. UNKNOWN is
# intentional until those owners provide export/deletion/retention semantics.
DATASET_CONTRACTS: dict[str, DatasetContract] = {
    "accounts": DatasetContract(
        "account_registry + evaluation_policy",
        "accounts.account_id",
        "CANONICAL",
        "INCLUDE",
        "SCRUB_AND_TOMBSTONE",
        "PARTIAL",
        "PARTIAL",
    ),
    "company_profiles": DatasetContract(
        "company_profile",
        "company_profiles.account_id",
        "CANONICAL",
        "INCLUDE",
        "DELETE",
        "UNKNOWN_LEGACY_FILE",
        "PARTIAL",
    ),
    "opportunity_decisions": DatasetContract(
        "decision_log",
        "opportunity_decisions.account_id",
        "CANONICAL",
        "INCLUDE",
        "DELETE",
        "DELETE_WITH_ACCOUNT",
        "PARTIAL",
    ),
    "opportunity_events": DatasetContract(
        "notification_events",
        "opportunity_events.account_id",
        "CANONICAL",
        "INCLUDE",
        "DELETE",
        "DELETE_WITH_ACCOUNT",
        "PARTIAL",
    ),
    "opportunity_workflow": DatasetContract(
        "opportunity_workflow",
        "opportunity_workflow.account_id",
        "CANONICAL",
        "INCLUDE",
        "DELETE",
        "DELETE_WITH_ACCOUNT",
        "PARTIAL",
    ),
    "evaluation_events": DatasetContract(
        "evaluation_policy",
        "evaluation_events.account_id",
        "CANONICAL",
        "INCLUDE",
        "DELETE",
        "DELETE_WITH_ACCOUNT",
        "PARTIAL",
    ),
    "company_state_snapshots": DatasetContract(
        "Company State / company_state_store",
        "company_state_snapshots.account_id",
        "PREBUILD",
        "UNKNOWN_OWNER_CONTRACT",
        "UNKNOWN_OWNER_CONTRACT",
        "UNKNOWN",
        "PARTIAL_PREBUILD",
    ),
    "push_devices": DatasetContract(
        "Notification Delivery / #263",
        "push_devices.account_id",
        "PREBUILD",
        "UNKNOWN_OWNER_CONTRACT",
        "UNKNOWN_OWNER_CONTRACT",
        "UNKNOWN",
        "PARTIAL_PREBUILD",
    ),
    "push_deliveries": DatasetContract(
        "Notification Delivery / #263",
        "push_deliveries.event_id -> opportunity_events.id -> account_id; "
        "push_deliveries.push_device_id -> push_devices.id -> account_id",
        "PREBUILD",
        "UNKNOWN_OWNER_CONTRACT",
        "UNKNOWN_OWNER_CONTRACT",
        "UNKNOWN",
        "PARTIAL_PREBUILD",
    ),
    "e2e_opportunity_fixtures": DatasetContract(
        "E2E fixture / #335",
        "e2e_opportunity_fixtures.account_id",
        "TEST_ONLY",
        "TEST_ONLY_EXCLUDE",
        "TEST_ONLY_CLEANUP",
        "TEST_ONLY",
        "TEST_ONLY",
        expected_store="separate_test_db",
    ),
}


def _table_names(conn) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }


def _columns(conn, table: str) -> set[str]:
    escaped = str(table).replace('"', '""')
    return {
        str(row[1])
        for row in conn.execute(f'PRAGMA table_info("{escaped}")').fetchall()
    }


def account_privacy_composition_inventory(conn, *, store_kind: str = "primary") -> dict:
    """Discover direct and known-transitive account state without promoting it.

    Direct ``account_id`` discovery catches ordinary tenant tables. The explicit
    transitive registry closes the known Notification Delivery gap where
    ``push_deliveries`` has no account_id but is private through event/device chains.
    ``store_kind`` prevents a test-only fixture store from being mistaken for primary
    customer persistence, or vice versa.
    """
    if store_kind not in {"primary", "separate_test_db"}:
        raise ValueError("unsupported_account_privacy_store_kind")

    tables = _table_names(conn)
    direct = sorted(name for name in tables if "account_id" in _columns(conn, name))
    known_present = sorted(name for name in tables if name in DATASET_CONTRACTS)
    unclassified_direct = sorted(name for name in direct if name not in DATASET_CONTRACTS)

    datasets = []
    for name in known_present:
        contract = DATASET_CONTRACTS[name]
        store_violation = contract.expected_store != store_kind
        datasets.append(
            {
                "table": name,
                "owner": contract.owner,
                "tenant_path": contract.tenant_path,
                "canonicality": contract.canonicality,
                "export_status": contract.export_status,
                "deletion_status": contract.deletion_status,
                "retention_status": contract.retention_status,
                "recovery_status": contract.recovery_status,
                "expected_store": contract.expected_store,
                "observed_store": store_kind,
                "store_violation": store_violation,
            }
        )

    transitive_present = sorted(
        name
        for name in known_present
        if "->" in DATASET_CONTRACTS[name].tenant_path
    )
    return {
        "store_kind": store_kind,
        "direct_account_tables": direct,
        "known_present": known_present,
        "known_transitive_private_tables": transitive_present,
        "unclassified_direct_account_tables": unclassified_direct,
        "datasets": datasets,
    }


def operation_blockers(conn, operation: str, *, store_kind: str = "primary") -> list[dict]:
    operation = str(operation or "").strip().lower()
    if operation not in {"export", "deletion"}:
        raise ValueError("unsupported_account_privacy_operation")

    inventory = account_privacy_composition_inventory(conn, store_kind=store_kind)
    blockers: list[dict] = []
    for table in inventory["unclassified_direct_account_tables"]:
        blockers.append(
            {
                "table": table,
                "reason": "UNCLASSIFIED_DIRECT_ACCOUNT_DATA",
                "owner": "UNKNOWN",
            }
        )

    status_key = f"{operation}_status"
    for dataset in inventory["datasets"]:
        if dataset["store_violation"]:
            blockers.append(
                {
                    "table": dataset["table"],
                    "reason": "STORE_BOUNDARY_VIOLATION",
                    "owner": dataset["owner"],
                }
            )
            continue
        status = dataset[status_key]
        if status.startswith("UNKNOWN"):
            blockers.append(
                {
                    "table": dataset["table"],
                    "reason": status,
                    "owner": dataset["owner"],
                    "tenant_path": dataset["tenant_path"],
                }
            )
    return blockers


def assert_composed_operation_complete(
    conn, operation: str, *, store_kind: str = "primary"
) -> None:
    """Fail closed when a composed tree has unresolved private-data semantics."""
    blockers = operation_blockers(conn, operation, store_kind=store_kind)
    if blockers:
        names = ",".join(sorted(item["table"] for item in blockers))
        raise AccountPrivacyCompositionError(
            f"account_{operation}_composition_incomplete:{names}"
        )
