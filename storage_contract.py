"""Executable persistence invariants for the ObraSignal SQLite datastore.

This verifier is not a second migration engine. Existing domain owners remain
responsible for their schemas; this registry makes ownership and safety gates
explicit and fail-closed.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import sqlite3
from typing import Iterable


class StorageContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class TableContract:
    owner: str
    required_columns: frozenset[str]
    tenant_column: str | None = None
    unique_keys: tuple[tuple[str, ...], ...] = ()
    required_indexes: tuple[str, ...] = ()


STARTUP_CONTRACTS: dict[str, TableContract] = {
    "tenders": TableContract("Opportunity legacy projection / app", frozenset({"id","source","external_id","title","score","first_seen","last_seen","published_at","match_reason","priority_label","priority_class","market"}), unique_keys=(("source","external_id"),)),
    "sync_runs": TableContract("sync runtime / app", frozenset({"id","started_at","finished_at","found","new_items"})),
    "accounts": TableContract("account_registry + evaluation_policy", frozenset({"account_id","status","plan","created_at","subscription_status","evaluation_status","evaluation_extension_days"}), tenant_column="account_id"),
    "company_profiles": TableContract("company_profile", frozenset({"account_id","profile_json","updated_at"}), tenant_column="account_id"),
    "opportunity_decisions": TableContract("decision_log", frozenset({"id","account_id","source","external_id","decision","features_json","rule_version","decided_at"}), tenant_column="account_id"),
    "opportunity_events": TableContract("notification_events", frozenset({"id","account_id","event_key","event_type","created_at","delivered_at"}), tenant_column="account_id", unique_keys=(("event_key",),)),
    "opportunity_workflow": TableContract("opportunity_workflow", frozenset({"id","account_id","source","external_id","status","note","updated_at"}), tenant_column="account_id", unique_keys=(("account_id","source","external_id"),)),
    "pipeline_latency": TableContract("latency_metrics", frozenset({"id","source","stage","started_at","finished_at","duration_ms","items"})),
    "source_health": TableContract("source_health", frozenset({"source","last_attempt","last_success","last_error","last_duration_ms","last_found","last_new_items","status"})),
    "source_cursor": TableContract("source_health", frozenset({"source","watermark","updated_at"})),
    "evaluation_events": TableContract("evaluation_policy", frozenset({"id","account_id","event_name","occurred_at","metadata_json"}), tenant_column="account_id", unique_keys=(("account_id","event_name","occurred_at"),)),
    "billing_webhook_events": TableContract("app billing webhook dedupe", frozenset({"event_id","received_at"})),
}

RUNTIME_CONTRACTS: dict[str, TableContract] = {
    "signal_records": TableContract("signal_store", frozenset({"source","signal_type","external_id","signal_schema_version","normalized_json","first_observed","last_observed"}), unique_keys=(("source","signal_type","external_id"),), required_indexes=("idx_signal_records_type_target","idx_signal_records_source_updated","idx_signal_records_country_type")),
    "source_record_metadata": TableContract("source_metadata", frozenset({"source","external_id","metadata_json","last_observed"}), unique_keys=(("source","external_id"),)),
    "opportunity_lifecycle": TableContract("opportunity_lifecycle", frozenset({"source","external_id","is_actionable","last_observed"}), unique_keys=(("source","external_id"),), required_indexes=("idx_opportunity_lifecycle_actionable",)),
}

# Reviewed but not canonical-on-main persistence owners. These contracts exist so
# Integration Lab can compose candidate branches without treating known owner
# tables as unregistered storage. They are deliberately excluded from the
# canonical verify_database()/contract_fingerprint() path unless explicitly
# requested, so registration cannot silently promote a prebuild capability.
PREBUILD_CONTRACTS: dict[str, TableContract] = {
    "company_state_snapshots": TableContract(
        "Company State / company_state_store",
        frozenset({
            "id", "account_id", "state_version", "fingerprint",
            "contract_version", "as_of", "snapshot_json", "created_at",
        }),
        tenant_column="account_id",
        unique_keys=(("account_id", "state_version"),),
        required_indexes=("idx_company_state_account_version",),
    ),
    "push_devices": TableContract(
        "Notification Delivery / notification_events",
        frozenset({
            "id", "account_id", "installation_id", "expo_push_token", "platform",
            "binding_id", "created_at", "updated_at", "last_error", "revoked_at",
        }),
        tenant_column="account_id",
        unique_keys=(("installation_id",), ("expo_push_token",)),
        required_indexes=("idx_push_devices_account",),
    ),
    "push_deliveries": TableContract(
        "Notification Delivery / notification_events",
        frozenset({
            "id", "event_id", "push_device_id", "ticket_id", "submitted_at",
            "last_error", "attempt_count", "last_attempt_at", "next_attempt_at",
            "expo_push_token", "receipt_status", "receipt_checked_at",
            "receipt_error", "failed_at",
        }),
        unique_keys=(("event_id", "push_device_id"),),
        required_indexes=("idx_push_deliveries_event_device",),
    ),
}

# Explicitly owned persistence that is test infrastructure only. These tables are
# classified for the root ownership guard but are never included in canonical or
# PREBUILD fingerprints/verification, so registration cannot promote fixture data
# into product persistence truth.
TEST_ONLY_CONTRACTS: dict[str, TableContract] = {
    "e2e_opportunity_fixtures": TableContract(
        "E2E fixture / e2e_fixture_api [TEST_ONLY]",
        frozenset({"fixture_id", "account_id", "run_id", "source", "external_id", "created_at"}),
        tenant_column="account_id",
        unique_keys=(("fixture_id",), ("account_id", "run_id"), ("account_id", "source", "external_id")),
        required_indexes=("idx_e2e_fixture_account_run",),
    ),
}

KNOWN_TABLE_OWNERS = {**STARTUP_CONTRACTS, **RUNTIME_CONTRACTS, **PREBUILD_CONTRACTS, **TEST_ONLY_CONTRACTS}

JSON_COLUMNS: tuple[tuple[str, str], ...] = (
    ("company_profiles","profile_json"),
    ("opportunity_decisions","features_json"),
    ("evaluation_events","metadata_json"),
    ("signal_records","normalized_json"),
    ("source_record_metadata","metadata_json"),
    ("company_state_snapshots","snapshot_json"),
)

REGISTERED_ADDITIVE_MIGRATIONS: dict[str, tuple[str, ...]] = {
    "tenders": ("published_at","match_reason","priority_label","priority_class","market"),
    "accounts": ("trial_ends_at","entitlement_expires_at","store","product_id","original_transaction_id","subscription_status","billing_synced_at","evaluation_type","evaluation_status","evaluation_activated_at","evaluation_ends_at","evaluation_extension_days","evaluation_value_status","evaluation_activation_reason","evaluation_extension_reason"),
    "opportunity_decisions": ("account_id",),
    "opportunity_events": ("account_id",),
    "push_devices": ("revoked_at",),
    "push_deliveries": (
        "attempt_count", "last_attempt_at", "next_attempt_at", "expo_push_token",
        "receipt_status", "receipt_checked_at", "receipt_error", "failed_at",
    ),
}

_CREATE_TABLE_RE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"'`\[]?([A-Za-z_][A-Za-z0-9_]*)\b(?=\s*\()", re.IGNORECASE)
_ALTER_TABLE_RE = re.compile(r"ALTER\s+TABLE\s+[\"'`\[]?([A-Za-z_][A-Za-z0-9_]*)[\"'`\]]?\s+(?=ADD\b|RENAME\b|DROP\b)", re.IGNORECASE)


def declared_persistent_tables(source_text: str) -> set[str]:
    return {m.group(1) for m in _CREATE_TABLE_RE.finditer(source_text)}


def altered_persistent_tables(source_text: str) -> set[str]:
    return {m.group(1) for m in _ALTER_TABLE_RE.finditer(source_text)}


def _contract_payload(contracts: dict[str, TableContract]) -> list[dict]:
    return [
        {
            "table": table,
            "owner": contract.owner,
            "tenant_column": contract.tenant_column,
            "required_columns": sorted(contract.required_columns),
            "unique_keys": [list(key) for key in contract.unique_keys],
            "required_indexes": list(contract.required_indexes),
        }
        for table, contract in sorted(contracts.items())
    ]


def contract_fingerprint(*, include_runtime: bool = True, include_prebuild: bool = False) -> str:
    """Return a deterministic fingerprint of expected structure/ownership.

    This is observability only, not a migration version or authoritative ledger.
    A changed fingerprint means the reviewed storage contract changed; database
    compatibility is still decided by the executable verifier below. Prebuild
    contracts are opt-in so registering a candidate owner cannot imply canonical
    persistence or mutate the current-main contract fingerprint.
    """
    contracts = dict(STARTUP_CONTRACTS)
    if include_runtime:
        contracts.update(RUNTIME_CONTRACTS)
    if include_prebuild:
        contracts.update(PREBUILD_CONTRACTS)
    payload = json.dumps(_contract_payload(contracts), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def table_columns(conn: sqlite3.Connection, table: str) -> tuple[str, ...]:
    return tuple(str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall())


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _unique_signatures(conn: sqlite3.Connection, table: str) -> set[tuple[str, ...]]:
    signatures: set[tuple[str, ...]] = set()
    pk_rows = sorted(((int(row[5]), str(row[1])) for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall() if int(row[5]) > 0), key=lambda x: x[0])
    if pk_rows:
        signatures.add(tuple(name for _, name in pk_rows))
    for row in conn.execute(f'PRAGMA index_list("{table}")').fetchall():
        if not bool(row[2]):
            continue
        name = str(row[1]).replace("'", "''")
        cols = tuple(str(item[2]) for item in conn.execute(f"PRAGMA index_info('{name}')").fetchall())
        if cols:
            signatures.add(cols)
    return signatures


def redundant_indexes(conn: sqlite3.Connection, table: str) -> tuple[tuple[str, ...], ...]:
    by_signature: dict[tuple[bool, tuple[str, ...]], list[str]] = {}
    for row in conn.execute(f'PRAGMA index_list("{table}")').fetchall():
        name = str(row[1])
        if name.startswith("sqlite_autoindex_"):
            continue
        escaped = name.replace("'", "''")
        cols = tuple(str(item[2]) for item in conn.execute(f"PRAGMA index_info('{escaped}')").fetchall())
        by_signature.setdefault((bool(row[2]), cols), []).append(name)
    return tuple(sorted(cols for (_, cols), names in by_signature.items() if cols and len(names) > 1))


def verify_schema(conn: sqlite3.Connection, contracts: dict[str, TableContract]) -> None:
    errors: list[str] = []
    for table, contract in contracts.items():
        if not _table_exists(conn, table):
            errors.append(f"{table}:missing_table")
            continue
        columns = set(table_columns(conn, table))
        missing = sorted(contract.required_columns - columns)
        if missing:
            errors.append(f"{table}:missing_columns={','.join(missing)}")
        uniques = _unique_signatures(conn, table)
        for key in contract.unique_keys:
            if key not in uniques:
                errors.append(f"{table}:missing_unique={','.join(key)}")
        existing_indexes = {str(row[1]) for row in conn.execute(f'PRAGMA index_list("{table}")').fetchall()}
        for index in contract.required_indexes:
            if index not in existing_indexes:
                errors.append(f"{table}:missing_index={index}")
    if errors:
        raise StorageContractError("schema contract failed: " + "; ".join(errors))


def verify_json_integrity(conn: sqlite3.Connection, columns: Iterable[tuple[str, str]] = JSON_COLUMNS) -> None:
    errors: list[str] = []
    for table, column in columns:
        if not _table_exists(conn, table) or column not in table_columns(conn, table):
            continue
        invalid = int(conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" IS NOT NULL AND json_valid("{column}")=0').fetchone()[0])
        if invalid:
            errors.append(f"{table}.{column}:invalid_json_rows={invalid}")
    if errors:
        raise StorageContractError("json integrity failed: " + "; ".join(errors))


def verify_foreign_keys(conn: sqlite3.Connection) -> None:
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        tables = sorted({str(row[0]) for row in violations})
        raise StorageContractError("foreign key integrity failed: tables=" + ",".join(tables) + f" violations={len(violations)}")


def verify_push_delivery_integrity(conn: sqlite3.Connection) -> None:
    """Fail closed on cross-owner corruption without creating another event truth."""
    if not (_table_exists(conn, "push_devices") and _table_exists(conn, "push_deliveries")):
        return
    errors: list[str] = []
    if _table_exists(conn, "opportunity_events"):
        orphan_events = int(conn.execute(
            """SELECT COUNT(*) FROM push_deliveries pd
               LEFT JOIN opportunity_events e ON e.id=pd.event_id
               WHERE e.id IS NULL"""
        ).fetchone()[0])
        tenant_mismatch = int(conn.execute(
            """SELECT COUNT(*) FROM push_deliveries pd
               JOIN opportunity_events e ON e.id=pd.event_id
               JOIN push_devices d ON d.id=pd.push_device_id
               WHERE e.account_id<>d.account_id"""
        ).fetchone()[0])
        if orphan_events:
            errors.append(f"push_deliveries:orphan_event_rows={orphan_events}")
        if tenant_mismatch:
            errors.append(f"push_deliveries:tenant_chain_mismatch_rows={tenant_mismatch}")
    orphan_devices = int(conn.execute(
        """SELECT COUNT(*) FROM push_deliveries pd
           LEFT JOIN push_devices d ON d.id=pd.push_device_id
           WHERE d.id IS NULL"""
    ).fetchone()[0])
    if orphan_devices:
        errors.append(f"push_deliveries:orphan_device_rows={orphan_devices}")

    negative_attempts = int(conn.execute(
        "SELECT COUNT(*) FROM push_deliveries WHERE attempt_count<0"
    ).fetchone()[0])
    attempted_without_time = int(conn.execute(
        "SELECT COUNT(*) FROM push_deliveries WHERE attempt_count>0 AND last_attempt_at IS NULL"
    ).fetchone()[0])
    submission_without_ticket = int(conn.execute(
        "SELECT COUNT(*) FROM push_deliveries WHERE submitted_at IS NOT NULL AND (ticket_id IS NULL OR length(trim(ticket_id))=0)"
    ).fetchone()[0])
    ticket_without_submission = int(conn.execute(
        "SELECT COUNT(*) FROM push_deliveries WHERE ticket_id IS NOT NULL AND submitted_at IS NULL"
    ).fetchone()[0])
    retry_after_submission = int(conn.execute(
        "SELECT COUNT(*) FROM push_deliveries WHERE next_attempt_at IS NOT NULL AND submitted_at IS NOT NULL"
    ).fetchone()[0])
    accepted_without_submission = int(conn.execute(
        """SELECT COUNT(*) FROM push_deliveries
           WHERE receipt_status='provider_accepted'
             AND (submitted_at IS NULL OR ticket_id IS NULL)"""
    ).fetchone()[0])
    revoked_token_not_tombstoned = int(conn.execute(
        """SELECT COUNT(*) FROM push_devices
           WHERE revoked_at IS NOT NULL AND expo_push_token NOT LIKE 'revoked:%'"""
    ).fetchone()[0])
    active_tombstone = int(conn.execute(
        """SELECT COUNT(*) FROM push_devices
           WHERE revoked_at IS NULL AND expo_push_token LIKE 'revoked:%'"""
    ).fetchone()[0])
    for label, count in (
        ("negative_attempt_count_rows", negative_attempts),
        ("attempt_without_timestamp_rows", attempted_without_time),
        ("submitted_without_ticket_rows", submission_without_ticket),
        ("ticket_without_submission_rows", ticket_without_submission),
        ("retry_after_submission_rows", retry_after_submission),
        ("accepted_without_submission_rows", accepted_without_submission),
        ("revoked_token_not_tombstoned_rows", revoked_token_not_tombstoned),
        ("active_tombstone_rows", active_tombstone),
    ):
        if count:
            errors.append(f"push_delivery_integrity:{label}={count}")
    if errors:
        raise StorageContractError("push delivery integrity failed: " + "; ".join(errors))


def verify_database(
    conn: sqlite3.Connection,
    *,
    include_runtime: bool = False,
    include_prebuild: bool = False,
) -> None:
    contracts = dict(STARTUP_CONTRACTS)
    if include_runtime:
        contracts.update(RUNTIME_CONTRACTS)
    if include_prebuild:
        contracts.update(PREBUILD_CONTRACTS)
    verify_schema(conn, contracts)
    verify_json_integrity(conn)
    verify_foreign_keys(conn)
    if include_prebuild:
        verify_push_delivery_integrity(conn)


def tenant_owned_tables(*, include_prebuild: bool = False) -> dict[str, str]:
    contracts = {**STARTUP_CONTRACTS, **RUNTIME_CONTRACTS}
    if include_prebuild:
        contracts.update(PREBUILD_CONTRACTS)
    return {table: contract.tenant_column for table, contract in contracts.items() if contract.tenant_column is not None}
