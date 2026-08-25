"""Read-only cross-store integrity checks for canonical ObraSignal state.

This module observes existing storage only. It never creates schema, repairs rows,
or decides domain policy. Domain owners remain authoritative for business semantics.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
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


def _parse_timestamp(value):
    if value is None:
        return None, None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None, "INVALID"
    if parsed.tzinfo is None:
        return None, "NAIVE"
    return parsed, None


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


def _scan_account_orphan(
    conn,
    *,
    table: str,
    invariant: str,
    owner: str,
    exact_sha: str,
) -> list[IntegrityFinding]:
    if not (_table_exists(conn, "accounts") and _table_exists(conn, table)):
        return []
    rows = conn.execute(
        f"""SELECT child.account_id
            FROM {table} child
            LEFT JOIN accounts a ON a.account_id=child.account_id
            WHERE a.account_id IS NULL
            GROUP BY child.account_id
            ORDER BY child.account_id"""
    ).fetchall()
    return [
        _finding(
            invariant=invariant,
            severity="HIGH",
            account_id=row[0],
            stores=(table, "accounts"),
            expected=f"every tenant-private {table} row resolves to one canonical local account",
            observed=f"{table} references a missing local account",
            owner=owner,
            repairable=False,
            unknown=True,
            exact_sha=exact_sha,
        )
        for row in rows
    ]


def _scan_opportunity_identity_orphans(
    conn,
    *,
    table: str,
    invariant: str,
    owner: str,
    exact_sha: str,
) -> list[IntegrityFinding]:
    if not (_table_exists(conn, "tenders") and _table_exists(conn, table)):
        return []
    rows = conn.execute(
        f"""SELECT child.account_id
            FROM {table} child
            LEFT JOIN tenders t
              ON t.source=child.source AND t.external_id=child.external_id
            WHERE t.id IS NULL
            GROUP BY child.account_id
            ORDER BY child.account_id"""
    ).fetchall()
    return [
        _finding(
            invariant=invariant,
            severity="HIGH",
            account_id=row[0],
            stores=(table, "tenders"),
            expected=f"every {table} opportunity identity resolves to canonical source + external_id",
            observed=f"{table} references an opportunity identity absent from tenders",
            owner=owner,
            repairable=False,
            unknown=True,
            exact_sha=exact_sha,
        )
        for row in rows
    ]


def _scan_source_time_integrity(conn, *, exact_sha: str) -> list[IntegrityFinding]:
    findings = []
    if _table_exists(conn, "source_health"):
        rows = conn.execute(
            """SELECT source,last_attempt,last_success,last_duration_ms
               FROM source_health ORDER BY source"""
        ).fetchall()
        for row in rows:
            source, last_attempt, last_success, duration_ms = row[0], row[1], row[2], row[3]
            attempt_dt, attempt_error = _parse_timestamp(last_attempt)
            success_dt, success_error = _parse_timestamp(last_success)
            if attempt_error or success_error:
                bad = []
                if attempt_error:
                    bad.append(f"last_attempt:{attempt_error}")
                if success_error:
                    bad.append(f"last_success:{success_error}")
                findings.append(_finding(
                    invariant="SOURCE_HEALTH_TIMESTAMP_CORRUPT",
                    severity="HIGH",
                    account_id=f"source:{source}",
                    stores=("source_health",),
                    expected="source health temporal evidence is timezone-aware and parseable before it can support freshness/health truth",
                    observed=";".join(bad),
                    owner="Source Health",
                    repairable=True,
                    unknown=False,
                    exact_sha=exact_sha,
                ))
            elif attempt_dt is not None and success_dt is not None and success_dt > attempt_dt:
                findings.append(_finding(
                    invariant="SOURCE_HEALTH_TIME_REGRESSION",
                    severity="HIGH",
                    account_id=f"source:{source}",
                    stores=("source_health",),
                    expected="last_success cannot occur after the row's last_attempt",
                    observed="last_success is later than last_attempt",
                    owner="Source Health",
                    repairable=False,
                    unknown=True,
                    exact_sha=exact_sha,
                ))
            if duration_ms is not None:
                try:
                    negative_duration = int(duration_ms) < 0
                except (TypeError, ValueError):
                    negative_duration = True
                if negative_duration:
                    findings.append(_finding(
                        invariant="SOURCE_HEALTH_DURATION_INVALID",
                        severity="MEDIUM",
                        account_id=f"source:{source}",
                        stores=("source_health",),
                        expected="last_duration_ms is a non-negative integer when present",
                        observed="duration is negative or non-integer",
                        owner="Source Health",
                        repairable=False,
                        unknown=True,
                        exact_sha=exact_sha,
                    ))

    if _table_exists(conn, "source_cursor"):
        rows = conn.execute(
            "SELECT source,updated_at FROM source_cursor ORDER BY source"
        ).fetchall()
        for row in rows:
            source, updated_at = row[0], row[1]
            _updated_dt, updated_error = _parse_timestamp(updated_at)
            if updated_at is not None and updated_error:
                findings.append(_finding(
                    invariant="SOURCE_CURSOR_TIMESTAMP_CORRUPT",
                    severity="MEDIUM",
                    account_id=f"source:{source}",
                    stores=("source_cursor",),
                    expected="cursor updated_at is timezone-aware and parseable when present",
                    observed=f"updated_at:{updated_error}",
                    owner="Source Health / Persistence",
                    repairable=False,
                    unknown=True,
                    exact_sha=exact_sha,
                ))
    return findings


def scan_canonical_integrity(conn, *, exact_sha: str = "UNKNOWN") -> list[IntegrityFinding]:
    """Scan canonical-main relationships without mutating or normalizing state.

    Missing tables are not created and are not reported as corruption: this scanner
    can be run against partial disposable fixtures. Findings describe only relations
    that are present and therefore observable.
    """
    findings: list[IntegrityFinding] = []
    has_profiles = _table_exists(conn, "company_profiles")
    has_events = _table_exists(conn, "evaluation_events")

    findings.extend(_scan_account_orphan(
        conn,
        table="company_profiles",
        invariant="PROFILE_ACCOUNT_ORPHAN",
        owner="Company Profile + Account Registry",
        exact_sha=exact_sha,
    ))
    findings.extend(_scan_account_orphan(
        conn,
        table="evaluation_events",
        invariant="EVALUATION_EVENT_ACCOUNT_ORPHAN",
        owner="Evaluation + Account Registry",
        exact_sha=exact_sha,
    ))
    findings.extend(_scan_account_orphan(
        conn,
        table="opportunity_decisions",
        invariant="DECISION_ACCOUNT_ORPHAN",
        owner="Decision Log + Account Registry",
        exact_sha=exact_sha,
    ))
    findings.extend(_scan_account_orphan(
        conn,
        table="opportunity_workflow",
        invariant="WORKFLOW_ACCOUNT_ORPHAN",
        owner="Opportunity Workflow + Account Registry",
        exact_sha=exact_sha,
    ))
    findings.extend(_scan_account_orphan(
        conn,
        table="opportunity_events",
        invariant="OPPORTUNITY_EVENT_ACCOUNT_ORPHAN",
        owner="Notification Events + Account Registry",
        exact_sha=exact_sha,
    ))

    findings.extend(_scan_opportunity_identity_orphans(
        conn,
        table="opportunity_decisions",
        invariant="DECISION_OPPORTUNITY_ORPHAN",
        owner="Decision Log + Opportunity owner",
        exact_sha=exact_sha,
    ))
    findings.extend(_scan_opportunity_identity_orphans(
        conn,
        table="opportunity_workflow",
        invariant="WORKFLOW_OPPORTUNITY_ORPHAN",
        owner="Opportunity Workflow + Opportunity owner",
        exact_sha=exact_sha,
    ))
    findings.extend(_scan_source_time_integrity(conn, exact_sha=exact_sha))

    if _table_exists(conn, "opportunity_events"):
        rows = conn.execute(
            """SELECT account_id
               FROM opportunity_events
               WHERE substr(event_key, 1, length(account_id) + 1) <> account_id || ':'
               GROUP BY account_id
               ORDER BY account_id"""
        ).fetchall()
        for row in rows:
            findings.append(_finding(
                invariant="OPPORTUNITY_EVENT_TENANT_KEY_MISMATCH",
                severity="HIGH",
                account_id=row[0],
                stores=("opportunity_events",),
                expected="event_key tenant namespace agrees with event account_id",
                observed="event_key is outside the account_id tenant namespace",
                owner="Notification Events",
                repairable=False,
                unknown=False,
                exact_sha=exact_sha,
            ))

    if _table_exists(conn, "opportunity_events") and _table_exists(conn, "tenders"):
        rows = conn.execute(
            """SELECT e.account_id
               FROM opportunity_events e
               LEFT JOIN tenders t ON t.id=e.tender_id
               WHERE e.tender_id IS NOT NULL AND t.id IS NULL
               GROUP BY e.account_id
               ORDER BY e.account_id"""
        ).fetchall()
        for row in rows:
            findings.append(_finding(
                invariant="OPPORTUNITY_EVENT_TENDER_ORPHAN",
                severity="HIGH",
                account_id=row[0],
                stores=("opportunity_events", "tenders"),
                expected="non-null opportunity event tender_id resolves to canonical tender",
                observed="opportunity event tender_id references no canonical tender",
                owner="Notification Events + Opportunity owner",
                repairable=False,
                unknown=True,
                exact_sha=exact_sha,
            ))

        rows = conn.execute(
            """SELECT e.account_id
               FROM opportunity_events e
               JOIN tenders t ON t.id=e.tender_id
               WHERE e.source IS NOT NULL AND e.source<>t.source
               GROUP BY e.account_id
               ORDER BY e.account_id"""
        ).fetchall()
        for row in rows:
            findings.append(_finding(
                invariant="OPPORTUNITY_EVENT_SOURCE_MISMATCH",
                severity="HIGH",
                account_id=row[0],
                stores=("opportunity_events", "tenders"),
                expected="event source agrees with canonical tender source for its tender_id",
                observed="event source and canonical tender source disagree",
                owner="Notification Events + Opportunity owner",
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
