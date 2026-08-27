from __future__ import annotations

from .registry import connect

DEFAULT_SNAPSHOT_RETENTION = 2000
MIN_SNAPSHOT_RETENTION = 10
MAX_SNAPSHOT_RETENTION = 100000
TRIGGER_NAME = "fcc_trim_company_snapshots"


def _limit(value: int | None = None) -> int:
    candidate = DEFAULT_SNAPSHOT_RETENTION if value is None else int(value)
    return max(MIN_SNAPSHOT_RETENTION, min(candidate, MAX_SNAPSHOT_RETENTION))


def install_snapshot_retention(limit: int | None = None) -> int:
    """Install deterministic per-company snapshot retention and prune existing excess.

    Snapshot history is operational evidence, not an unbounded event store. The
    retention trigger limits future growth while preserving the newest snapshots.
    """
    keep = _limit(limit)
    with connect() as conn:
        conn.execute(f"DROP TRIGGER IF EXISTS {TRIGGER_NAME}")
        conn.execute(
            f"""
            CREATE TRIGGER {TRIGGER_NAME}
            AFTER INSERT ON company_snapshots
            BEGIN
                DELETE FROM company_snapshots
                WHERE company_id = NEW.company_id
                  AND id NOT IN (
                    SELECT id FROM company_snapshots
                    WHERE company_id = NEW.company_id
                    ORDER BY id DESC
                    LIMIT {keep}
                  );
            END
            """
        )
        company_ids = [row[0] for row in conn.execute("SELECT DISTINCT company_id FROM company_snapshots").fetchall()]
        for company_id in company_ids:
            conn.execute(
                """
                DELETE FROM company_snapshots
                WHERE company_id=?
                  AND id NOT IN (
                    SELECT id FROM company_snapshots
                    WHERE company_id=?
                    ORDER BY id DESC
                    LIMIT ?
                  )
                """,
                (company_id, company_id, keep),
            )
        conn.commit()
    return keep
