import sqlite3


def test_bounded_sync_commits_in_chunks_without_per_row_lookup(monkeypatch, tmp_path):
    import app
    import bounded_sync

    path = tmp_path / "bounded-sync.db"
    monkeypatch.setattr(app, "DB", str(path))
    app.init_db()

    rows = [
        {
            "source": "TEST",
            "external_id": f"opp-{index}",
            "title": f"Opportunity {index}",
            "description": "construction works",
            "buyer": "Buyer",
            "country": "PRT",
            "cpv": "45260000",
            "value": "100000",
            "deadline": "2099-01-01",
            "publication_date": "2026-09-01",
            "published_at": "2026-09-01T00:00:00+00:00",
            "url": "https://example.invalid/tender",
            "market": "PT",
        }
        for index in range(230)
    ]
    monkeypatch.setattr(app, "fetch_ted", lambda: list(rows))
    monkeypatch.setattr(app, "normalize_ted", lambda item: dict(item))
    monkeypatch.setattr(app, "fetch_base", lambda: [])
    monkeypatch.setattr(app, "commercial_score", lambda *_args, **_kwargs: (88, "HIGH", "hot", "fit"))

    commits = []
    statements = []
    original_db = app.db

    class CountingConnection:
        def __init__(self):
            self.conn = original_db()
            self.conn.set_trace_callback(statements.append)

        def __getattr__(self, name):
            return getattr(self.conn, name)

        def commit(self):
            commits.append(1)
            return self.conn.commit()

        def close(self):
            self.conn.set_trace_callback(None)
            return self.conn.close()

    monkeypatch.setattr(app, "db", lambda: CountingConnection())

    found, new_items = bounded_sync.sync_once(write_chunk=50)
    assert found == 230
    assert new_items == 230
    # run marker + five bounded tender commits + completion commit
    assert len(commits) >= 7
    assert not any("SELECT id FROM tenders WHERE source=" in sql for sql in statements)

    check = sqlite3.connect(path)
    assert check.execute("SELECT COUNT(*) FROM tenders").fetchone()[0] == 230
    assert check.execute("SELECT COUNT(*) FROM sync_runs WHERE finished_at IS NOT NULL").fetchone()[0] == 1
    check.close()

    # A later run upserts the same canonical opportunities rather than duplicating them.
    commits.clear(); statements.clear()
    found_again, new_again = bounded_sync.sync_once(write_chunk=50)
    assert found_again == 230
    assert new_again == 0
    check = sqlite3.connect(path)
    assert check.execute("SELECT COUNT(*) FROM tenders").fetchone()[0] == 230
    assert check.execute("SELECT COUNT(*) FROM sync_runs WHERE finished_at IS NOT NULL").fetchone()[0] == 2
    check.close()
