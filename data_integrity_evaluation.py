"""Read-only Evaluation temporal integrity checks.

Evaluation owns lifecycle semantics. This module only detects persisted temporal
states that cannot safely support those semantics; it never rewrites access state.
"""
from __future__ import annotations

from datetime import datetime

from data_integrity import IntegrityFinding, safe_tenant_ref


def _table_exists(conn, table):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _columns(conn, table):
    if not _table_exists(conn, table):
        return set()
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _parse(value):
    if not value:
        return None, "MISSING"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None, "INVALID"
    if parsed.tzinfo is None:
        return None, "NAIVE"
    return parsed, None


def _finding(*, invariant, severity, account_id, stores, expected, observed, owner,
             repairable, unknown, exact_sha):
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


def scan_evaluation_time_integrity(conn, *, exact_sha="UNKNOWN"):
    """Detect impossible/corrupt Evaluation time state without mutation."""
    findings = []
    account_columns = _columns(conn, "accounts")
    required = {
        "account_id",
        "evaluation_status",
        "evaluation_activated_at",
        "evaluation_ends_at",
    }
    if required <= account_columns:
        rows = conn.execute(
            """SELECT account_id,evaluation_status,evaluation_activated_at,evaluation_ends_at
               FROM accounts
               WHERE evaluation_status IS NOT NULL
               ORDER BY account_id"""
        ).fetchall()
        for row in rows:
            account_id, status, activated_at, ends_at = row[0], row[1], row[2], row[3]
            if status != "EVALUATION_ACTIVE":
                continue
            activated, activated_error = _parse(activated_at)
            ends, ends_error = _parse(ends_at)
            if activated_error or ends_error:
                parts = []
                if activated_error:
                    parts.append(f"evaluation_activated_at:{activated_error}")
                if ends_error:
                    parts.append(f"evaluation_ends_at:{ends_error}")
                findings.append(_finding(
                    invariant="EVALUATION_ACTIVE_WINDOW_CORRUPT",
                    severity="HIGH",
                    account_id=account_id,
                    stores=("accounts",),
                    expected="active evaluation has parseable timezone-aware activation and end boundaries",
                    observed=";".join(parts),
                    owner="Evaluation",
                    repairable=False,
                    unknown=True,
                    exact_sha=exact_sha,
                ))
            elif ends <= activated:
                findings.append(_finding(
                    invariant="EVALUATION_ACTIVE_WINDOW_REGRESSION",
                    severity="HIGH",
                    account_id=account_id,
                    stores=("accounts",),
                    expected="active evaluation end boundary occurs strictly after activation",
                    observed="evaluation_ends_at is not later than evaluation_activated_at",
                    owner="Evaluation",
                    repairable=False,
                    unknown=True,
                    exact_sha=exact_sha,
                ))

    event_columns = _columns(conn, "evaluation_events")
    if {"account_id", "occurred_at"} <= event_columns:
        rows = conn.execute(
            "SELECT account_id,occurred_at FROM evaluation_events ORDER BY account_id,id"
        ).fetchall()
        emitted = set()
        for row in rows:
            account_id, occurred_at = row[0], row[1]
            _occurred, error = _parse(occurred_at)
            if error and account_id not in emitted:
                emitted.add(account_id)
                findings.append(_finding(
                    invariant="EVALUATION_EVENT_TIMESTAMP_CORRUPT",
                    severity="HIGH",
                    account_id=account_id,
                    stores=("evaluation_events",),
                    expected="Evaluation event evidence has a parseable timezone-aware occurrence timestamp",
                    observed=f"occurred_at:{error}",
                    owner="Evaluation",
                    repairable=False,
                    unknown=True,
                    exact_sha=exact_sha,
                ))

    return sorted(
        findings,
        key=lambda item: (item.severity, item.invariant, item.tenant_ref, item.stores),
    )
