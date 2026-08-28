"""Revalidate source→canonical normalization provenance for current BASE rows."""
import sqlite3

import app


def _synthetic_base_record():
    return {
        "source": "BASE",
        "external_id": "BASE-LINEAGE-0001",
        "title": "Synthetic BASE lineage tender",
        "description": "Synthetic BASE source evidence",
        "buyer": "Synthetic Buyer",
        "country": "PRT",
        "cpv": "45223200",
        "value": "100000 EUR",
        "deadline": "2099-12-31",
        "publication_date": "2026-08-20",
        "published_at": "2026-08-20T00:00:00+00:00",
        "url": "https://example.test/base-lineage",
        "market": "PT",
        "place": "",
    }


def test_base_canonical_opportunity_retains_normalization_semantics(monkeypatch, tmp_path):
    """Durable state alone must identify BASE source identity and normalizer semantics."""
    monkeypatch.setattr(app, "DB", str(tmp_path / "base-lineage.db"))
    app.init_db()

    monkeypatch.setattr(app, "fetch_ted", lambda: [])
    monkeypatch.setattr(app, "fetch_base", lambda: [_synthetic_base_record()])

    app.sync_once()

    conn = sqlite3.connect(app.DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM tenders WHERE source=? AND external_id=?",
        ("BASE", "BASE-LINEAGE-0001"),
    ).fetchone()
    columns = {item[1] for item in conn.execute("PRAGMA table_info(tenders)")}
    conn.close()

    assert row is not None
    assert row["source"] == "BASE"
    assert row["external_id"] == "BASE-LINEAGE-0001"
    assert "normalization_version" in columns
    assert row["normalization_version"] == "base-canonical-normalizer-v1", (
        "BASE_SOURCE_CANONICAL_LINEAGE_BROKEN: current BASE canonical state cannot "
        "identify the normalization semantics that produced the customer projection"
    )
