"""Tenant-safe append-only snapshot persistence for Company State v1."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Callable, Mapping

from company_state import CompanyFact, CompanyState, CompanyStateError, CONTRACT_VERSION, MAX_FACTS, TenantBoundaryError, validate_account_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS company_state_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    state_version INTEGER NOT NULL,
    fingerprint TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    as_of TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(account_id, state_version)
)
"""
INDEX = "CREATE INDEX IF NOT EXISTS idx_company_state_account_version ON company_state_snapshots(account_id, state_version DESC)"
MAX_HISTORY_LIMIT = 100


class CompanyStateStorageError(RuntimeError):
    pass


class StaleCompanyStateWrite(CompanyStateStorageError):
    pass


def ensure_company_state_schema(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA)
    conn.execute(INDEX)
    conn.commit()


def _row_state(row: sqlite3.Row | Mapping[str, Any]) -> CompanyState:
    try:
        payload = json.loads(row["snapshot_json"])
        return CompanyState.from_dict(payload, trusted_account_id=str(row["account_id"]))
    except Exception as exc:
        raise CompanyStateStorageError("stored company state is invalid") from exc


def current_company_state(conn: sqlite3.Connection, account_id: str) -> CompanyState | None:
    account = validate_account_id(account_id)
    ensure_company_state_schema(conn)
    row = conn.execute(
        "SELECT * FROM company_state_snapshots WHERE account_id=? ORDER BY state_version DESC LIMIT 1",
        (account,),
    ).fetchone()
    return _row_state(row) if row else None


def company_state_version(conn: sqlite3.Connection, account_id: str, state_version: int) -> CompanyState | None:
    account = validate_account_id(account_id)
    ensure_company_state_schema(conn)
    if isinstance(state_version, bool) or not isinstance(state_version, int) or state_version < 1:
        raise CompanyStateError("state_version must be a positive integer")
    row = conn.execute(
        "SELECT * FROM company_state_snapshots WHERE account_id=? AND state_version=?",
        (account, state_version),
    ).fetchone()
    return _row_state(row) if row else None


def company_state_history(conn: sqlite3.Connection, account_id: str, *, limit: int = 20) -> list[CompanyState]:
    account = validate_account_id(account_id)
    ensure_company_state_schema(conn)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_HISTORY_LIMIT:
        raise CompanyStateError(f"history limit must be 1..{MAX_HISTORY_LIMIT}")
    rows = conn.execute(
        "SELECT * FROM company_state_snapshots WHERE account_id=? ORDER BY state_version DESC LIMIT ?",
        (account, limit),
    ).fetchall()
    return [_row_state(row) for row in rows]


def save_company_state(
    conn: sqlite3.Connection,
    state: CompanyState,
    *,
    expected_version: int | None = None,
    clock: datetime | None = None,
) -> CompanyState:
    """Append a snapshot with optimistic concurrency and consecutive replay idempotency."""
    if not isinstance(state, CompanyState):
        raise CompanyStateError("state must be CompanyState")
    now = (clock or datetime.now(timezone.utc))
    if now.tzinfo is None:
        raise CompanyStateError("clock must be timezone-aware")
    now = now.astimezone(timezone.utc)
    ensure_company_state_schema(conn)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM company_state_snapshots WHERE account_id=? ORDER BY state_version DESC LIMIT 1",
            (state.account_id,),
        ).fetchone()
        current = _row_state(row) if row else None
        current_version = current.state_version if current else 0
        if expected_version is not None and expected_version != current_version:
            raise StaleCompanyStateWrite(f"expected state version {expected_version}, current is {current_version}")
        candidate = state.with_version(current_version + 1)
        if current and current.fingerprint == candidate.fingerprint:
            conn.rollback()
            return current
        payload = candidate.to_dict()
        # Fingerprint is independently recomputed by CompanyState.from_dict on read.
        conn.execute(
            """INSERT INTO company_state_snapshots(
                   account_id, state_version, fingerprint, contract_version, as_of, snapshot_json, created_at
               ) VALUES(?, ?, ?, ?, ?, ?, ?)""",
            (
                candidate.account_id,
                candidate.state_version,
                candidate.fingerprint,
                CONTRACT_VERSION,
                candidate.to_dict()["as_of"],
                json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False),
                now.isoformat(),
            ),
        )
        conn.commit()
        return candidate
    except StaleCompanyStateWrite:
        conn.rollback()
        raise
    except sqlite3.Error as exc:
        conn.rollback()
        raise CompanyStateStorageError("company state persistence failed") from exc


class CompanyStateService:
    """Application boundary that accepts only trusted tenant identity.

    The payload cannot select account_id, fingerprint, version or persistence
    metadata. Missing fields mean "leave current state unchanged". Revocation is
    explicit through revoke_fact_ids; it is not represented by null or omission.
    """

    ALLOWED_PAYLOAD_KEYS = frozenset({"facts", "revoke_fact_ids", "as_of", "company_ref", "expected_version"})
    FORBIDDEN_IDENTITY_KEYS = frozenset({"account_id", "tenant_id", "fingerprint", "state_version", "contract_version", "created_at"})

    def __init__(self, connection_factory: Callable[[], sqlite3.Connection]):
        self._connection_factory = connection_factory

    def get(self, trusted_account_id: str) -> CompanyState | None:
        validate_account_id(trusted_account_id)
        conn = self._connection_factory()
        try:
            return current_company_state(conn, trusted_account_id)
        finally:
            conn.close()

    def get_version(self, trusted_account_id: str, version: int) -> CompanyState | None:
        validate_account_id(trusted_account_id)
        conn = self._connection_factory()
        try:
            return company_state_version(conn, trusted_account_id, version)
        finally:
            conn.close()

    def history(self, trusted_account_id: str, *, limit: int = 20) -> list[CompanyState]:
        validate_account_id(trusted_account_id)
        conn = self._connection_factory()
        try:
            return company_state_history(conn, trusted_account_id, limit=limit)
        finally:
            conn.close()

    def patch(self, trusted_account_id: str, payload: Mapping[str, Any], *, clock: datetime) -> CompanyState:
        account = validate_account_id(trusted_account_id)
        if not isinstance(payload, Mapping):
            raise CompanyStateError("payload must be an object")
        unknown_keys = set(payload) - self.ALLOWED_PAYLOAD_KEYS
        if unknown_keys:
            if unknown_keys & self.FORBIDDEN_IDENTITY_KEYS:
                raise TenantBoundaryError("client-controlled tenant/state identity is forbidden")
            raise CompanyStateError(f"unsupported payload keys: {sorted(unknown_keys)}")
        if clock.tzinfo is None:
            raise CompanyStateError("clock must be timezone-aware")

        conn = self._connection_factory()
        try:
            ensure_company_state_schema(conn)
            current = current_company_state(conn, account)
            current_facts = {fact.fact_id: fact for fact in (current.facts if current else ())}
            if "revoke_fact_ids" in payload and payload["revoke_fact_ids"] is None:
                raise CompanyStateError("revoke_fact_ids null is ambiguous; omit it or provide a list")
            revocations = payload.get("revoke_fact_ids", [])
            if not isinstance(revocations, list) or len(revocations) > 256:
                raise CompanyStateError("revoke_fact_ids must be a bounded list")
            for fact_id in revocations:
                current_facts.pop(str(fact_id), None)

            if "facts" in payload and payload["facts"] is None:
                raise CompanyStateError("facts null is ambiguous; omit it or provide a list")
            raw_facts = payload.get("facts")
            if raw_facts is not None:
                if not isinstance(raw_facts, list):
                    raise CompanyStateError("facts must be a list")
                if len(raw_facts) > MAX_FACTS:
                    raise CompanyStateError("too many company facts")
                for raw in raw_facts:
                    fact = CompanyFact.from_dict(raw)
                    # Upsert only an identical fact id; conflicting semantic facts
                    # are deliberately retained until an explicit supersession.
                    current_facts[fact.fact_id] = fact

            if "as_of" in payload and payload["as_of"] is None:
                raise CompanyStateError("as_of null is ambiguous; omit it or provide an ISO datetime")
            as_of_raw = payload.get("as_of")
            if as_of_raw is None:
                as_of = clock.astimezone(timezone.utc)
            else:
                probe = {"account_id": account, "as_of": as_of_raw, "facts": []}
                as_of = CompanyState.from_dict(probe, trusted_account_id=account).as_of
            company_ref = payload.get("company_ref", current.company_ref if current else None)
            state = CompanyState(account_id=account, company_ref=company_ref, as_of=as_of, facts=tuple(current_facts.values()))
            if "expected_version" in payload and payload["expected_version"] is None:
                raise CompanyStateError("expected_version null is ambiguous; omit it or provide an integer")
            expected = payload.get("expected_version")
            if expected is not None and (isinstance(expected, bool) or not isinstance(expected, int) or expected < 0):
                raise CompanyStateError("expected_version must be a non-negative integer")
            # Even when the transport omits an explicit version token, bind the
            # write to the exact snapshot this service just read. This prevents
            # an interleaving writer from being silently overwritten.
            if expected is None:
                expected = current.state_version if current else 0
            return save_company_state(conn, state, expected_version=expected, clock=clock)
        finally:
            conn.close()
