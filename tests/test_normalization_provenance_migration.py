import sqlite3

import app


def _legacy_tenders_table(conn):
    conn.execute(
        """CREATE TABLE tenders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        external_id TEXT NOT NULL,
        title TEXT,
        description TEXT,
        buyer TEXT,
        country TEXT,
        cpv TEXT,
        value TEXT,
        deadline TEXT,
        publication_date TEXT,
        url TEXT,
        score INTEGER DEFAULT 0,
        first_seen TEXT,
        last_seen TEXT,
        UNIQUE(source,external_id)
        )"""
    )


def _ted_record(external_id):
    return {
        "publication-number": external_id,
        "notice-title": {"eng": "Re-normalized lineage tender"},
        "description-proc": {"eng": "Current normalizer semantics"},
        "buyer-name": {"eng": "Buyer"},
        "buyer-country": "PRT",
        "classification-cpv": [{"code": "45223200"}],
        "publication-date": "2026-08-20",
    }


def test_additive_provenance_does_not_fabricate_historical_normalizer(monkeypatch, tmp_path):
    db_path = tmp_path / "legacy-lineage.db"
    conn = sqlite3.connect(db_path)
    _legacy_tenders_table(conn)
    conn.execute(
        "INSERT INTO tenders(source,external_id,title) VALUES('TED','LEGACY-ROW','old projection')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(app, "DB", str(db_path))
    app.init_db()

    conn = sqlite3.connect(db_path)
    legacy = conn.execute(
        "SELECT normalization_version FROM tenders WHERE external_id='LEGACY-ROW'"
    ).fetchone()
    conn.close()
    assert legacy == (None,), "untouched historical rows must remain UNKNOWN"

    monkeypatch.setattr(app, "fetch_ted", lambda: [_ted_record("LEGACY-ROW")])
    monkeypatch.setattr(app, "fetch_base", lambda: [])
    app.sync_once()

    conn = sqlite3.connect(db_path)
    current = conn.execute(
        "SELECT normalization_version FROM tenders WHERE external_id='LEGACY-ROW'"
    ).fetchone()
    conn.close()
    assert current == ("ted-canonical-normalizer-v1",)
