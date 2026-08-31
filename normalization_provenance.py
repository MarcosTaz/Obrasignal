"""Durable semantic identity for source -> canonical normalization.

These identifiers describe the semantics of the current source normalizers, not
SQLite/storage envelope versions. Historical canonical rows are deliberately not
backfilled: absence means the transformation used for that historical row is
UNKNOWN. Rows inserted or rewritten through the current canonical projection are
stamped by source-specific SQLite triggers installed at schema initialization.
"""

NORMALIZATION_SEMANTIC_VERSIONS = {
    "TED": "ted-canonical-normalizer-v1",
    "BASE": "base-canonical-normalizer-v1",
}


def normalization_semantic_version(source):
    return NORMALIZATION_SEMANTIC_VERSIONS.get(str(source or "").strip().upper())


def ensure_normalization_provenance(conn):
    """Add bounded provenance without inventing semantics for historical rows."""
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tenders'"
    ).fetchone()
    if not table:
        return

    columns = {row[1] for row in conn.execute("PRAGMA table_info(tenders)").fetchall()}
    if "normalization_version" not in columns:
        conn.execute("ALTER TABLE tenders ADD COLUMN normalization_version TEXT")

    conn.execute("DROP TRIGGER IF EXISTS tenders_normalization_provenance_insert")
    conn.execute("DROP TRIGGER IF EXISTS tenders_normalization_provenance_update")

    ted = NORMALIZATION_SEMANTIC_VERSIONS["TED"].replace("'", "''")
    base = NORMALIZATION_SEMANTIC_VERSIONS["BASE"].replace("'", "''")
    expression = (
        "CASE NEW.source "
        f"WHEN 'TED' THEN '{ted}' "
        f"WHEN 'BASE' THEN '{base}' "
        "ELSE NULL END"
    )

    conn.execute(
        f"""CREATE TRIGGER tenders_normalization_provenance_insert
        AFTER INSERT ON tenders
        WHEN NEW.normalization_version IS NULL
        BEGIN
          UPDATE tenders
             SET normalization_version={expression}
           WHERE id=NEW.id;
        END"""
    )
    conn.execute(
        f"""CREATE TRIGGER tenders_normalization_provenance_update
        AFTER UPDATE OF title,description,buyer,country,cpv,value,deadline,
                        publication_date,url,published_at,market
        ON tenders
        WHEN NEW.normalization_version IS NULL
             OR NEW.normalization_version != {expression}
        BEGIN
          UPDATE tenders
             SET normalization_version={expression}
           WHERE id=NEW.id;
        END"""
    )
