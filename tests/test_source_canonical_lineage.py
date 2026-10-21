"""Failing-before proof for source -> canonical opportunity lineage.

Data Lineage owns the reconstructability invariant only. Source owners retain
normalization semantics and Persistence owns the durable schema/repair shape.
"""
import sqlite3

import app


def _synthetic_ted_record():
    return {
        "publication-number": "LINEAGE-0001-2026",
        "notice-title": {"eng": "Synthetic lineage tender"},
        "description-proc": {"eng": "Synthetic source evidence"},
        "buyer-name": {"eng": "Synthetic Buyer"},
        "buyer-country": "PRT",
        "classification-cpv": [{"code": "45223200", "label": "Structural works"}],
        "publication-date": "2026-08-20",
        "place-of-performance-country-proc": "PRT",
        "place-of-performance-city-proc": "Leiria",
    }


def test_ted_canonical_opportunity_retains_normalization_semantics(monkeypatch, tmp_path):
    """Durable state alone must identify source identity and normalizer semantics."""
    monkeypatch.setattr(app, "DB", str(tmp_path / "lineage.db"))
    app.init_db()

    raw = _synthetic_ted_record()
    monkeypatch.setattr(app, "fetch_ted", lambda: [raw])
    monkeypatch.setattr(app, "fetch_base", lambda: [])

    # The sync return contract is not part of this lineage invariant. Drive the
    # real persistence path and reconstruct exclusively from durable state below.
    app.sync_once()

    conn = sqlite3.connect(app.DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM tenders WHERE source=? AND external_id=?",
        ("TED", "LINEAGE-0001-2026"),
    ).fetchone()
    columns = {item[1] for item in conn.execute("PRAGMA table_info(tenders)")}
    conn.close()

    assert row is not None
    assert row["source"] == "TED"
    assert row["external_id"] == "LINEAGE-0001-2026"

    # Failing-before on canonical main: storage schema versions elsewhere do not
    # identify the transformation semantics that produced this customer-facing
    # canonical opportunity. A repair may choose another bounded durable shape,
    # but durable audit state must expose equivalent semantics.
    assert "normalization_version" in columns, (
        "SOURCE_CANONICAL_LINEAGE_BROKEN: canonical tender identifies TED and the "
        "source record, but durable state cannot identify which normalization "
        "semantics/version produced the current canonical opportunity"
    )
    assert row["normalization_version"], "normalization lineage must fail closed when absent"
