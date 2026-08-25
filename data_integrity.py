"""Read-only cross-store integrity checks for canonical ObraSignal state.

This module observes existing storage only. It never creates schema, repairs rows,
or decides domain policy. Domain owners remain authoritative for business semantics.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Iterable


@dataclass(frozen=True)
class IntegrityFinding:
    invariant: str
    severity: str
    tenant_ref: str
    stores: tuple[str, ...]
    expected: str
    observed: str
    owner: str
    repairable: bool
    unknown: bool
    exact_sha: str

    def as_dict(self) -> dict:
        value = asdict(self)
        value["stores"] = list(self.stores)
        return value


def safe_tenant_ref(account_id: object) -> str:
    """Return a stable diagnostic identifier without exposing account identity."""
    digest = hashlib.sha256(str(account_id).encode("utf-8")).hexdigest()[:12]
    return f"acct:{digest}"


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _finding(
    *,
    invariant: str,
    severity: str,
    account_id: object,
    stores: Iterable[str],
    expected: str,
    observed: str,
    owner: str,
    repairable: bool,
    unknown: bool,
    exact_sha: str,
) -> IntegrityFinding:
    return IntegrityFinding(
        invariant=invariant,
        severity=severity,
        tenant_ref=safe_tenant_ref(account_id),
        stores=tuple(stores),
        expected=expected,
        observed=observed,
        owner=owner,
        repairable=repairable,
        unknown=unknown,
        exact_sha=str(exact_sha or "UNKNOWN"),
    )


def scan_canonical_integrity(conn, *, exact_sha: str = "UNKNOWN") -> list[IntegrityFinding]:
    """Scan canonical-main account/profile/evaluation relations without mutation.

    Missing tables are not created and are not reported as corruption: this scanner
    can be run against partial disposable fixtures. Findings describe only relations
    that are present and therefore observable.
    """
    findings: list[IntegrityFinding] = []
    has_accounts = _table_exists(conn, "accounts")
    has_profiles = _table_exists(conn, "company_profiles")
    has_events = _table_exists(conn, "evaluation_events")

    if has_accounts and has_profiles:
        rows = conn.execute(
            """SELECT p.account_id
               FROM company_profiles p
               LEFT JOIN accounts a ON a.account_id=p.account_id
               WHERE a.account_id IS NULL
               ORDER BY p.account_id"""
        ).fetchall()
        for row in rows:
            findings.append(_finding(
                invariant="PROFILE_ACCOUNT_ORPHAN",
                severity="HIGH",
                account_id=row[0],
                stores=("company_profiles", "accounts"),
                expected="every tenant-private profile resolves to one canonical local account",
                observed="profile row has no local account owner",
                owner="Company Profile + Account Registry",
                repairable=False,
                unknown=True,
                exact_sha=exact_sha,
            ))

    if has_accounts and has_events:
        rows = conn.execute(
            """SELECT e.account_id
               FROM evaluation_events e
               LEFT JOIN accounts a ON a.account_id=e.account_id
               WHERE a.account_id IS NULL
               GROUP BY e.account_id
               ORDER BY e.account_id"""
        ).fetchall()
        for row in rows:
            findings.append(_finding(
                invariant="EVALUATION_EVENT_ACCOUNT_ORPHAN",
                severity="HIGH",
                account_id=row[0],
                stores=("evaluation_events", "accounts"),
                expected="every tenant evaluation event resolves to one canonical local account",
                observed="evaluation ledger references a missing local account",
                owner="Evaluation + Account Registry",
                repairable=False,
                unknown=True,
                exact_sha=exact_sha,
            ))

    if has_profiles and has_events:
        rows = conn.execute(
            """SELECT p.account_id
               FROM company_profiles p
               WHERE NOT EXISTS (
                   SELECT 1 FROM evaluation_events e
                   WHERE e.account_id=p.account_id AND e.event_name='profile_ready'
               )
               ORDER BY p.account_id"""
        ).fetchall()
        for row in rows:
            findings.append(_finding(
                invariant="PROFILE_READY_EVENT_MISSING",
                severity="MEDIUM",
                account_id=row[0],
                stores=("company_profiles", "evaluation_events"),
                expected="persisted canonical profile has corresponding profile_ready lifecycle evidence",
                observed="profile exists but profile_ready event is absent",
                owner="Evaluation owner repair; Integrity owns detection/reconciliation contract",
                repairable=True,
                unknown=False,
                exact_sha=exact_sha,
            ))

        rows = conn.execute(
            """SELECT e.account_id
               FROM evaluation_events e
               WHERE e.event_name='profile_ready'
                 AND NOT EXISTS (
                     SELECT 1 FROM company_profiles p WHERE p.account_id=e.account_id
                 )
               GROUP BY e.account_id
               ORDER BY e.account_id"""
        ).fetchall()
        for row in rows:
            findings.append(_finding(
                invariant="PROFILE_READY_WITHOUT_PROFILE",
                severity="HIGH",
                account_id=row[0],
                stores=("evaluation_events", "company_profiles"),
                expected="profile_ready lifecycle evidence is backed by a canonical persisted profile",
                observed="profile_ready event exists but canonical profile is absent",
                owner="Company Profile + Evaluation",
                repairable=False,
                unknown=True,
                exact_sha=exact_sha,
            ))

    return sorted(
        findings,
        key=lambda item: (item.severity, item.invariant, item.tenant_ref, item.stores),
    )


def report_json(findings: Iterable[IntegrityFinding]) -> str:
    """Machine-readable privacy-safe report with deterministic key ordering."""
    return json.dumps(
        [finding.as_dict() for finding in findings],
        sort_keys=True,
        separators=(",", ":"),
    )
