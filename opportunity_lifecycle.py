"""Durable commercial lifecycle state for source-native opportunity updates.

The legacy ``tenders`` table remains the canonical content/history row. Sources
that publish later cancellation/completion updates can mark the corresponding
(source, external_id) commercially non-actionable without deleting history,
decisions or workflow state.
"""
from datetime import datetime, timezone


_LIFECYCLE_TABLE = "opportunity_lifecycle"
_LIFECYCLE_INDEX = "idx_opportunity_lifecycle_actionable"


def _lifecycle_schema_ready(conn):
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (_LIFECYCLE_TABLE,)
    ).fetchone()
    if not table:
        return False
    index = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (_LIFECYCLE_INDEX,)
    ).fetchone()
    return bool(index)


def ensure_lifecycle_table(conn):
    # Production startup creates this schema before workers/traffic. Keeping the
    # steady-state path read-only avoids needless SQLite schema-writer locks on
    # Radar, alert and push reads.
    if _lifecycle_schema_ready(conn):
        return
    conn.execute('''CREATE TABLE IF NOT EXISTS opportunity_lifecycle (
        source TEXT NOT NULL,
        external_id TEXT NOT NULL,
        is_actionable INTEGER NOT NULL,
        lifecycle_status TEXT,
        lifecycle_reason TEXT,
        source_updated_at TEXT,
        last_observed TEXT NOT NULL,
        PRIMARY KEY(source, external_id)
    )''')
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_opportunity_lifecycle_actionable "
        "ON opportunity_lifecycle(is_actionable, source)"
    )


def persist_lifecycle_observations(conn, records, *, observed_at=None, commit=True):
    """Persist only records that explicitly carry ``is_actionable``.

    Absence of a lifecycle field means the source has not opted into lifecycle
    semantics and therefore preserves compatibility with the existing radar.
    """
    ensure_lifecycle_table(conn)
    observed = observed_at or datetime.now(timezone.utc).isoformat()
    written = 0
    for record in records or []:
        if not isinstance(record, dict) or "is_actionable" not in record:
            continue
        source = str(record.get("source") or "").strip()
        external_id = str(record.get("external_id") or "").strip()
        if not source or not external_id:
            continue
        actionable = 1 if bool(record.get("is_actionable")) else 0
        conn.execute(
            '''INSERT INTO opportunity_lifecycle(
                source,external_id,is_actionable,lifecycle_status,lifecycle_reason,
                source_updated_at,last_observed
            ) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(source,external_id) DO UPDATE SET
                is_actionable=excluded.is_actionable,
                lifecycle_status=excluded.lifecycle_status,
                lifecycle_reason=excluded.lifecycle_reason,
                source_updated_at=excluded.source_updated_at,
                last_observed=excluded.last_observed''',
            (
                source,
                external_id,
                actionable,
                record.get("lifecycle_status"),
                record.get("lifecycle_reason"),
                record.get("source_updated_at") or record.get("published_at"),
                observed,
            ),
        )
        written += 1
    if commit:
        conn.commit()
    return written


def lifecycle_for(conn, source, external_id):
    ensure_lifecycle_table(conn)
    row = conn.execute(
        "SELECT * FROM opportunity_lifecycle WHERE source=? AND external_id=?",
        (source, external_id),
    ).fetchone()
    return dict(row) if row else None


def is_actionable(conn, source, external_id, *, default=True):
    state = lifecycle_for(conn, source, external_id)
    if state is None:
        return bool(default)
    return bool(state.get("is_actionable"))


def actionable_join(alias="t", lifecycle_alias="lc"):
    """Return the canonical LEFT JOIN for source-native lifecycle evidence."""
    return (
        f" LEFT JOIN opportunity_lifecycle {lifecycle_alias} "
        f"ON {lifecycle_alias}.source={alias}.source AND {lifecycle_alias}.external_id={alias}.external_id "
    )


def actionable_predicate(lifecycle_alias="lc", opportunity_alias="t"):
    """Return the canonical effective commercial-actionability predicate.

    Source-native lifecycle evidence has precedence. An explicit actionable
    lifecycle observation may keep an opportunity commercially actionable even
    after the originally published submission deadline (for example, where the
    publisher has extended/reopened the opportunity but the legacy tender row
    has not yet received a replacement deadline). An explicit non-actionable
    observation always closes it.

    When no lifecycle observation exists, a known expired deadline is sufficient
    evidence that the opportunity must not be presented as current actionable
    work. Missing, blank, or unparsable deadlines remain UNKNOWN rather than
    being silently coerced to closed.

    Date-only values retain day precision: the deadline date itself remains
    actionable for that calendar day instead of being silently coerced to
    midnight and closed early.
    """
    lifecycle = f"{lifecycle_alias}.is_actionable"
    deadline = f"{opportunity_alias}.deadline"
    trimmed = f"TRIM({deadline})"
    is_date_only = f"LENGTH({trimmed})=10"
    date_unknown = f"({is_date_only} AND date({deadline}) IS NULL)"
    datetime_unknown = f"(NOT ({is_date_only}) AND datetime({deadline}) IS NULL)"
    date_open = f"({is_date_only} AND date({deadline})>=date('now'))"
    datetime_open = f"(NOT ({is_date_only}) AND datetime({deadline})>=datetime('now'))"
    return (
        f"({lifecycle}=1 OR ("
        f"{lifecycle} IS NULL AND ("
        f"{deadline} IS NULL OR {trimmed}='' OR "
        f"{date_unknown} OR {datetime_unknown} OR {date_open} OR {datetime_open}"
        f")))"
    )
