"""Tenant-safe append-only snapshot persistence for Company State v1."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import sqlite3
from typing import Any, Callable, Iterable, Mapping

from company_state import (
    CompanyFact,
    CompanyState,
    CompanyStateError,
    CONTRACT_VERSION,
    MAX_FACTS,
    ProvenanceBasis,
    TenantBoundaryError,
    validate_account_id,
)

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
_FACT_ID_RE = re.compile(r"^cf_[0-9a-f]{24}$")
_REQUIRED_COLUMNS = {
    "id", "account_id", "state_version", "fingerprint", "contract_version",
    "as_of", "snapshot_json", "created_at",
}
_TRUSTED_PROVIDER_BASES = frozenset({
    ProvenanceBasis.VERIFIED,
    ProvenanceBasis.PUBLIC_REGISTRY,
    ProvenanceBasis.INTEGRATION,
    ProvenanceBasis.LEARNED,
    ProvenanceBasis.UNAVAILABLE,
})


class CompanyStateStorageError(RuntimeError):
    pass


class StaleCompanyStateWrite(CompanyStateStorageError):
    pass


def _has_account_version_unique_constraint(conn: sqlite3.Connection) -> bool:
    for row in conn.execute("PRAGMA index_list(company_state_snapshots)").fetchall():
        if not bool(row[2]):
            continue
        index_name = str(row[1]).replace("'", "''")
        columns = tuple(str(item[2]) for item in conn.execute(f"PRAGMA index_info('{index_name}')").fetchall())
        if columns == ("account_id", "state_version"):
            return True
    return False


def ensure_company_state_schema(conn: sqlite3.Connection) -> None:
    """Add and validate the snapshot schema without mutating unrelated tables."""
    try:
        conn.execute(SCHEMA)
        columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(company_state_snapshots)").fetchall()}
        if not _REQUIRED_COLUMNS.issubset(columns) or not _has_account_version_unique_constraint(conn):
            conn.rollback()
            raise CompanyStateStorageError("company state snapshot schema is incompatible")
        conn.execute(INDEX)
        conn.commit()
    except CompanyStateStorageError:
        conn.rollback()
        raise
    except sqlite3.Error as exc:
        conn.rollback()
        raise CompanyStateStorageError("company state schema initialization failed") from exc


def _clock_utc(value: datetime, name: str = "clock") -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise CompanyStateError(f"{name} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _validate_expected_version(value: int | None) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
        raise CompanyStateError("expected_version must be a non-negative integer")


def _row_state(row: sqlite3.Row | Mapping[str, Any]) -> CompanyState:
    """Deserialize a row and prove duplicated query metadata still agrees."""
    try:
        payload = json.loads(row["snapshot_json"])
        state = CompanyState.from_dict(payload, trusted_account_id=str(row["account_id"]))
        if state.state_version != int(row["state_version"]):
            raise CompanyStateStorageError("stored company state version metadata mismatch")
        if state.fingerprint != str(row["fingerprint"]):
            raise CompanyStateStorageError("stored company state fingerprint metadata mismatch")
        if state.contract_version != str(row["contract_version"]):
            raise CompanyStateStorageError("stored company state contract metadata mismatch")
        if state.to_dict()["as_of"] != str(row["as_of"]):
            raise CompanyStateStorageError("stored company state as_of metadata mismatch")
        return state
    except CompanyStateStorageError:
        raise
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
    """Append a snapshot with optimistic concurrency and replay idempotency."""
    if not isinstance(state, CompanyState):
        raise CompanyStateError("state must be CompanyState")
    _validate_expected_version(expected_version)
    now = _clock_utc(clock, "clock") if clock is not None else datetime.now(timezone.utc)
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
        conn.execute(
            """INSERT INTO company_state_snapshots(
                   account_id, state_version, fingerprint, contract_version, as_of, snapshot_json, created_at
               ) VALUES(?, ?, ?, ?, ?, ?, ?)""",
            (
                candidate.account_id,
                candidate.state_version,
                candidate.fingerprint,
                CONTRACT_VERSION,
                payload["as_of"],
                json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False),
                now.isoformat(),
            ),
        )
        conn.commit()
        return candidate
    except StaleCompanyStateWrite:
        conn.rollback()
        raise
    except CompanyStateStorageError:
        conn.rollback()
        raise
    except sqlite3.Error as exc:
        conn.rollback()
        raise CompanyStateStorageError("company state persistence failed") from exc


def _is_manual_fact(fact: CompanyFact) -> bool:
    return fact.provenance.basis is ProvenanceBasis.DECLARED and fact.provenance.source_ref == "manual"


def _manual_fact(
    raw: Mapping[str, Any],
    *,
    observed_at: datetime,
    supersedes: tuple[str, ...] = (),
) -> CompanyFact:
    """Convert voluntary user input into server-owned DECLARED provenance.

    The client may state fact content, but it cannot choose a privileged evidence
    basis, audit anchors or supersession targets. Supersession between successive
    manual declarations is assigned by the server after comparing semantic keys.
    """
    if not isinstance(raw, Mapping):
        raise CompanyStateError("each fact must be an object")
    provenance = raw.get("provenance")
    if provenance is not None:
        if not isinstance(provenance, Mapping):
            raise CompanyStateError("fact provenance must be an object")
        basis = str(provenance.get("basis") or "DECLARED").strip().upper()
        if basis != "DECLARED":
            raise CompanyStateError("manual facts cannot promote provenance beyond DECLARED")
        if provenance.get("evidence_ref") or provenance.get("verified_at"):
            raise CompanyStateError("manual facts cannot provide verification anchors")
        source_ref = str(provenance.get("source_ref") or "").strip()
        if source_ref and source_ref != "manual":
            raise CompanyStateError("manual fact source_ref is server-owned")
        if provenance.get("observed_at") not in (None, ""):
            raise CompanyStateError("manual fact observed_at is server-owned")
    if raw.get("supersedes") not in (None, (), []):
        raise CompanyStateError("manual facts cannot select supersession targets")

    normalized = dict(raw)
    normalized["provenance"] = {
        "basis": "DECLARED",
        "source_ref": "manual",
        "observed_at": observed_at.isoformat(),
    }
    normalized["supersedes"] = list(supersedes)
    return CompanyFact.from_dict(normalized)


def _manual_revoke(current_facts: dict[str, CompanyFact], fact_id: str) -> None:
    """Remove a voluntary fact and its older manual chain from the current view.

    Historical snapshots remain immutable. Removing the newest declaration must
    not accidentally resurrect a previous superseded declaration as current.
    """
    target = current_facts.get(fact_id)
    if target is None:
        return
    if not _is_manual_fact(target):
        raise CompanyStateError("only voluntary manual facts can be revoked through this boundary")
    stack = [fact_id]
    while stack:
        current_id = stack.pop()
        current = current_facts.get(current_id)
        if current is None or not _is_manual_fact(current):
            continue
        stack.extend(current.supersedes)
        current_facts.pop(current_id, None)


def _provider_fact(fact: CompanyFact, *, operation_clock: datetime, supersedes: tuple[str, ...]) -> CompanyFact:
    """Validate a trusted-provider fact and assign server-owned supersession."""
    if not isinstance(fact, CompanyFact):
        raise CompanyStateError("trusted provider facts must be CompanyFact values")
    provenance = fact.provenance
    if provenance.basis not in _TRUSTED_PROVIDER_BASES:
        raise CompanyStateError("trusted provider facts require a provider provenance basis")
    if not provenance.source_ref:
        raise CompanyStateError("trusted provider facts require source_ref")
    if provenance.observed_at is None:
        raise CompanyStateError("trusted provider facts require observed_at")
    if provenance.observed_at > operation_clock:
        raise CompanyStateError("trusted provider observed_at cannot be in the future")
    if provenance.verified_at is not None and provenance.verified_at > operation_clock:
        raise CompanyStateError("trusted provider verified_at cannot be in the future")
    if fact.supersedes:
        raise CompanyStateError("trusted providers cannot select supersession targets")
    return CompanyFact(
        category=fact.category,
        code=fact.code,
        knowledge=fact.knowledge,
        value=fact.value,
        provenance=fact.provenance,
        scope=fact.scope,
        unit=fact.unit,
        effective_from=fact.effective_from,
        effective_until=fact.effective_until,
        freshness_until=fact.freshness_until,
        supersedes=supersedes,
    )


class CompanyStateService:
    """Application boundary that accepts only trusted tenant identity.

    ``patch`` is the voluntary/user boundary: facts are always server-labelled
    DECLARED/manual and cannot mutate trusted provider evidence. ``ingest_trusted_facts``
    is the narrow future OFFICE/registry/integration boundary for already-validated
    server-side facts. Neither boundary accepts client tenant authority.
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
        observed_at = _clock_utc(clock)

        conn = self._connection_factory()
        try:
            ensure_company_state_schema(conn)
            current = current_company_state(conn, account)
            current_facts = {fact.fact_id: fact for fact in (current.facts if current else ())}

            if "revoke_fact_ids" in payload and payload["revoke_fact_ids"] is None:
                raise CompanyStateError("revoke_fact_ids null is ambiguous; omit it or provide a list")
            revocations = payload.get("revoke_fact_ids", [])
            if not isinstance(revocations, list) or len(revocations) > MAX_FACTS:
                raise CompanyStateError("revoke_fact_ids must be a bounded list")
            for fact_id in revocations:
                if not isinstance(fact_id, str) or not _FACT_ID_RE.fullmatch(fact_id):
                    raise CompanyStateError("revoke_fact_ids contains an invalid fact id")
                _manual_revoke(current_facts, fact_id)

            if "facts" in payload and payload["facts"] is None:
                raise CompanyStateError("facts null is ambiguous; omit it or provide a list")
            raw_facts = payload.get("facts")
            if raw_facts is not None:
                if not isinstance(raw_facts, list):
                    raise CompanyStateError("facts must be a list")
                if len(raw_facts) > MAX_FACTS:
                    raise CompanyStateError("too many company facts")
                seen_patch_semantic: set[tuple[str, str, str | None]] = set()
                for raw in raw_facts:
                    probe = _manual_fact(raw, observed_at=observed_at)
                    if probe.semantic_key in seen_patch_semantic:
                        raise CompanyStateError("facts contains duplicate semantic keys")
                    seen_patch_semantic.add(probe.semantic_key)
                    already_superseded = {
                        prior_id
                        for existing in current_facts.values()
                        for prior_id in existing.supersedes
                    }
                    prior_manual = tuple(sorted(
                        existing.fact_id
                        for existing in current_facts.values()
                        if existing.fact_id != probe.fact_id
                        and existing.fact_id not in already_superseded
                        and existing.semantic_key == probe.semantic_key
                        and _is_manual_fact(existing)
                    ))
                    fact = _manual_fact(raw, observed_at=observed_at, supersedes=prior_manual)
                    current_facts[fact.fact_id] = fact

            if "as_of" in payload and payload["as_of"] is None:
                raise CompanyStateError("as_of null is ambiguous; omit it or provide an ISO datetime")
            as_of_raw = payload.get("as_of")
            if as_of_raw is None:
                as_of = observed_at
            else:
                probe = {"account_id": account, "as_of": as_of_raw, "facts": []}
                as_of = CompanyState.from_dict(probe, trusted_account_id=account).as_of
            company_ref = payload.get("company_ref", current.company_ref if current else None)
            state = CompanyState(account_id=account, company_ref=company_ref, as_of=as_of, facts=tuple(current_facts.values()))

            if "expected_version" in payload and payload["expected_version"] is None:
                raise CompanyStateError("expected_version null is ambiguous; omit it or provide an integer")
            expected = payload.get("expected_version")
            _validate_expected_version(expected)
            if expected is None:
                expected = current.state_version if current else 0
            return save_company_state(conn, state, expected_version=expected, clock=observed_at)
        finally:
            conn.close()

    def ingest_trusted_facts(
        self,
        trusted_account_id: str,
        facts: Iterable[CompanyFact],
        *,
        clock: datetime,
        expected_version: int | None = None,
        as_of: datetime | None = None,
    ) -> CompanyState:
        """Ingest trusted OFFICE/registry/integration facts without a provider framework.

        Tenant identity is supplied by a trusted server caller. Provider facts must
        carry explicit source and observation provenance. A provider can supersede
        only its own previous current observation for the same semantic fact;
        cross-source/manual disagreement remains an explicit conflict.
        """
        account = validate_account_id(trusted_account_id)
        operation_clock = _clock_utc(clock)
        _validate_expected_version(expected_version)
        try:
            supplied = tuple(facts)
        except TypeError as exc:
            raise CompanyStateError("trusted provider facts must be iterable") from exc
        if not supplied:
            raise CompanyStateError("trusted provider facts cannot be empty")
        if len(supplied) > MAX_FACTS:
            raise CompanyStateError("too many trusted provider facts")
        target_as_of = _clock_utc(as_of, "as_of") if as_of is not None else operation_clock

        conn = self._connection_factory()
        try:
            ensure_company_state_schema(conn)
            current = current_company_state(conn, account)
            current_facts = {fact.fact_id: fact for fact in (current.facts if current else ())}
            already_superseded = {
                prior_id
                for existing in current_facts.values()
                for prior_id in existing.supersedes
            }
            seen_source_semantics: set[tuple[tuple[str, str, str | None], ProvenanceBasis, str]] = set()
            for raw_fact in supplied:
                if not isinstance(raw_fact, CompanyFact):
                    raise CompanyStateError("trusted provider facts must be CompanyFact values")
                source_key = (raw_fact.semantic_key, raw_fact.provenance.basis, raw_fact.provenance.source_ref or "")
                if source_key in seen_source_semantics:
                    raise CompanyStateError("trusted provider batch contains duplicate source semantic keys")
                seen_source_semantics.add(source_key)
                prior_same_source = tuple(sorted(
                    existing.fact_id
                    for existing in current_facts.values()
                    if existing.fact_id != raw_fact.fact_id
                    and existing.fact_id not in already_superseded
                    and existing.semantic_key == raw_fact.semantic_key
                    and existing.provenance.basis is raw_fact.provenance.basis
                    and existing.provenance.source_ref == raw_fact.provenance.source_ref
                ))
                fact = _provider_fact(raw_fact, operation_clock=operation_clock, supersedes=prior_same_source)
                current_facts[fact.fact_id] = fact
                already_superseded.update(prior_same_source)

            expected = expected_version
            if expected is None:
                expected = current.state_version if current else 0
            state = CompanyState(
                account_id=account,
                company_ref=current.company_ref if current else None,
                as_of=target_as_of,
                facts=tuple(current_facts.values()),
            )
            return save_company_state(conn, state, expected_version=expected, clock=operation_clock)
        finally:
            conn.close()
