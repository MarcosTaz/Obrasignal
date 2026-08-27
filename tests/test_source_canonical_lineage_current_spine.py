"""Current-spine failing-before proof for source -> canonical normalization lineage."""
import sqlite3

import app


def _synthetic_ted_record():
    return {
        "publication-number": "LINEAGE-CURRENT-0001-2026",
        "notice-title": {"eng": "Synthetic current-spine lineage tender"},
        "description-proc": {"eng": "Synthetic source evidence"},
        "buyer-name": {"eng": "Synthetic Buyer"},
        "buyer-country": "PRT",
        "classification-cpv": [{"code": "45223200", "label": "Structural works"}],
        "publication-date": "2026-08-20",
        "place-of-performance-country-proc": "PRT",
        "place-of-performance-city-proc": "Leiria",
    }


def test_current_ted_canonical_opportunity_retains_normalization_semantics(monkeypatch, tmp_path):
    """Durable audit state must identify source record and transformation semantics."""
    monkeypatch.setattr(app, "DB", str(tmp_path / "lineage-current.db"))
    app.init_db()

    raw = _synthetic_ted_record()
    monkeypatch.setattr(app, "fetch_ted", lambda: [raw])
    monkeypatch.setattr(app, "fetch_base", lambda: [])

    app.sync_once()

    conn = sqlite3.connect(app.DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM tenders WHERE source=? AND external_id=?",
        ("TED", "LINEAGE-CURRENT-0001-2026"),
    ).fetchone()
    columns = {item[1] for item in conn.execute("PRAGMA table_info(tenders)")}
    conn.close()

    assert row is not None
    assert row["source"] == "TED"
    assert row["external_id"] == "LINEAGE-CURRENT-0001-2026"

    assert "normalization_version" in columns, (
        "SOURCE_CANONICAL_LINEAGE_BROKEN: canonical opportunity preserves source and "
        "logical record identity but durable state cannot identify which normalization "
        "semantics/version produced the customer-facing projection"
    )
    assert row["normalization_version"], "normalization lineage must fail closed when absent"
