import json
import sqlite3
from pathlib import Path

from signal_store import persist_signal_records


ROOT = Path(__file__).resolve().parents[1]


def _registry():
    return json.loads((ROOT / "source_lineage_registry.json").read_text(encoding="utf-8"))


def test_source_history_registry_does_not_claim_full_history():
    registry = _registry()
    history = {row["surface"]: row for row in registry["history_models"]}

    assert history["signal_records"]["history_classification"] == "CURRENT_ONLY_LINEAGE"
    assert history["source_record_metadata"]["history_classification"] == "CURRENT_ONLY_LINEAGE"
    assert history["tenders"]["history_classification"] == "CURRENT_ONLY_LINEAGE"
    assert history["signal_records"]["prior_normalized_versions_retained"] is False
    assert history["tenders"]["prior_normalized_versions_retained"] is False
    assert all(row["normalization_semantics_versioned"] is False for row in history.values())


def test_lossy_transformations_remain_explicit_and_fail_closed():
    registry = _registry()
    lossy_without = [
        row for row in registry["transformations"]
        if row["lossiness"] == "LOSSY_WITHOUT_PROVENANCE"
    ]

    assert lossy_without, "known lossy transformations must not disappear from provenance debt"
    assert all(row["versioned"] is False for row in lossy_without)
    assert all(row["reconstructable"] == "NO" for row in lossy_without)
    assert "LOSSY_WITHOUT_PROVENANCE" in registry["open_gaps"]


def test_multi_source_authority_stays_unknown_without_evidence():
    registry = _registry()
    multi = registry["multi_source"]

    assert multi["cross_source_collapse_proven"] is False
    assert multi["authority_status"] == "UNKNOWN"
    assert multi["field_level_provenance_required"] == "UNKNOWN"


def test_same_normalized_content_with_distinct_external_ids_keeps_both_origins():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    common = {
        "source": "TED",
        "signal_type": "TENDER",
        "title": "Identical normalized content",
        "description": "same",
        "country": "PRT",
    }

    persist_signal_records(
        conn,
        [
            {**common, "external_id": "origin-a"},
            {**common, "external_id": "origin-b"},
        ],
    )

    rows = conn.execute(
        "SELECT source,external_id,title FROM signal_records ORDER BY external_id"
    ).fetchall()
    assert [(r["source"], r["external_id"]) for r in rows] == [
        ("TED", "origin-a"),
        ("TED", "origin-b"),
    ]
    conn.close()


def test_same_external_id_from_distinct_sources_keeps_both_origins():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    common = {
        "signal_type": "TENDER",
        "external_id": "shared-external-id",
        "title": "Identical normalized content",
    }

    persist_signal_records(
        conn,
        [
            {**common, "source": "SOURCE-A"},
            {**common, "source": "SOURCE-B"},
        ],
    )

    rows = conn.execute(
        "SELECT source,external_id FROM signal_records ORDER BY source"
    ).fetchall()
    assert [(r["source"], r["external_id"]) for r in rows] == [
        ("SOURCE-A", "shared-external-id"),
        ("SOURCE-B", "shared-external-id"),
    ]
    conn.close()
