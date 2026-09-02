"""Incremental account decision refresh for the production sync pipeline.

The source poll observes many unchanged opportunities every minute. Re-running
account scoring and committing one decision per observation creates duplicate
decisions and SQLite contention with customer requests. This module records a
stable fingerprint of the source inputs plus company profile and re-evaluates
only when that combined input changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

from account_registry import list_active_accounts
from auth_context import configured_identity
from company_profile import load_profile
from funnel_integration import persist_and_classify


SCHEMA = """CREATE TABLE IF NOT EXISTS opportunity_decision_inputs (
    account_id TEXT NOT NULL,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    PRIMARY KEY(account_id, source, external_id)
)"""

# Bump whenever account-level ranking semantics change even if source/profile
# inputs stay identical. Without this, a production matcher fix can deploy while
# every existing customer's old decision remains frozen indefinitely.
MATCHER_INPUT_VERSION = "profile-semantic-v3"

# A profile edit can invalidate a large observed corpus. Spread that work over
# successive 60-second source polls instead of monopolising SQLite in one pass.
MAX_REFRESH_PER_ACCOUNT = 100

_MATERIAL_FIELDS = (
    "title",
    "description",
    "buyer",
    "country",
    "cpv",
    "value",
    "deadline",
    "publication_date",
    "published_at",
    "market",
)


def ensure_decision_input_table(conn):
    """Startup-only schema preparation; never call this from request hot paths."""
    conn.execute(SCHEMA)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_decision_inputs_account "
        "ON opportunity_decision_inputs(account_id)"
    )


def _fingerprint(row: dict, profile: dict) -> str:
    source_input = {field: row.get(field) for field in _MATERIAL_FIELDS}
    # Ignore storage/account metadata that cannot affect the commercial model.
    profile_input = {
        key: value
        for key, value in dict(profile or {}).items()
        if key not in {"account_id", "updated_at"}
    }
    payload = json.dumps(
        {
            "opportunity": source_input,
            "profile": profile_input,
            "matcher_version": MATCHER_INPUT_VERSION,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _profile_updated_at(conn, account_id: str):
    row = conn.execute(
        "SELECT updated_at FROM company_profiles WHERE account_id=?",
        (account_id,),
    ).fetchone()
    return row[0] if row else None


def _existing_fingerprints(conn, account_id: str) -> dict[tuple[str, str], str]:
    rows = conn.execute(
        "SELECT source,external_id,fingerprint FROM opportunity_decision_inputs WHERE account_id=?",
        (account_id,),
    ).fetchall()
    return {(str(row[0]), str(row[1])): str(row[2]) for row in rows}


def _latest_decision_times(conn, account_id: str) -> dict[tuple[str, str], str]:
    """Load current decision timestamps once per tenant, not once per tender."""
    rows = conn.execute(
        """SELECT d.source,d.external_id,d.decided_at
           FROM opportunity_decisions d
           JOIN (
               SELECT source,external_id,MAX(id) AS max_id
               FROM opportunity_decisions
               WHERE account_id=?
               GROUP BY source,external_id
           ) latest ON latest.max_id=d.id
           WHERE d.account_id=?""",
        (account_id, account_id),
    ).fetchall()
    return {(str(row[0]), str(row[1])): str(row[2]) for row in rows}


def _mark(conn, account_id: str, source: str, external_id: str, fingerprint: str):
    conn.execute(
        """INSERT INTO opportunity_decision_inputs(
               account_id,source,external_id,fingerprint,evaluated_at
           ) VALUES(?,?,?,?,?)
           ON CONFLICT(account_id,source,external_id) DO UPDATE SET
               fingerprint=excluded.fingerprint,
               evaluated_at=excluded.evaluated_at""",
        (
            account_id,
            source,
            external_id,
            fingerprint,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def record_account_decisions(
    conn,
    *,
    commit_chunk: int = 50,
    max_refresh_per_account: int = MAX_REFRESH_PER_ACCOUNT,
) -> int:
    """Refresh only materially stale decisions for the latest source observation.

    Existing deployments have decisions but no fingerprint rows. They are
    seeded without a costly re-score when the latest decision is at least as
    recent as the current profile. If the profile is newer, stale opportunities
    are re-scored in bounded batches across successive source polls.

    All existing fingerprints and latest decision timestamps are prefetched once
    per tenant. This keeps work approximately O(accounts + observed tenders)
    database reads instead of O(accounts * observed tenders) point queries.
    """
    run = conn.execute(
        "SELECT finished_at FROM sync_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not run or not run["finished_at"]:
        return 0

    rows = conn.execute(
        "SELECT * FROM tenders WHERE last_seen=?",
        (run["finished_at"],),
    ).fetchall()
    accounts = list_active_accounts(conn) or [configured_identity().account_id]
    recorded = 0
    pending_writes = 0
    refresh_limit = max(1, int(max_refresh_per_account))
    commit_limit = max(1, int(commit_chunk))

    for raw_account_id in accounts:
        account_id = str(raw_account_id or "").strip()
        if not account_id:
            continue
        profile = load_profile(account_id)
        profile_updated = _profile_updated_at(conn, account_id)
        fingerprints = _existing_fingerprints(conn, account_id)
        latest_decisions = _latest_decision_times(conn, account_id)
        rescored_for_account = 0

        for raw_row in rows:
            row = dict(raw_row)
            source = str(row.get("source") or "")
            external_id = str(row.get("external_id") or "")
            if not source or not external_id:
                continue
            key = (source, external_id)
            fingerprint = _fingerprint(row, profile)
            existing = fingerprints.get(key)
            if existing == fingerprint:
                continue

            # Migration path: do not re-score the whole observed corpus merely
            # because the fingerprint table is new. A decision made after the
            # current profile was saved is already compatible with that profile.
            # Once a matcher version is encoded, old fingerprints are different
            # and therefore correctly re-evaluated instead of being re-seeded.
            if existing is None:
                latest_decided = latest_decisions.get(key)
                if latest_decided and (not profile_updated or latest_decided >= profile_updated):
                    _mark(conn, account_id, source, external_id, fingerprint)
                    fingerprints[key] = fingerprint
                    pending_writes += 1
                    if pending_writes >= commit_limit:
                        conn.commit()
                        pending_writes = 0
                    continue

            # Leave excess stale rows unmarked. The next poll sees them again
            # and continues convergence without one long write transaction.
            if rescored_for_account >= refresh_limit:
                continue

            persist_and_classify(
                conn,
                row,
                True,
                account_id=account_id,
                profile=profile,
                commit=False,
                ensure=False,
            )
            _mark(conn, account_id, source, external_id, fingerprint)
            fingerprints[key] = fingerprint
            recorded += 1
            rescored_for_account += 1
            pending_writes += 2
            if pending_writes >= commit_limit:
                conn.commit()
                pending_writes = 0

    if pending_writes:
        conn.commit()
    return recorded
