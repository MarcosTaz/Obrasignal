import sqlite3

import pytest

from factories.capacity_commitment.csv_import import commit_csv_import, preview_csv_facts
from factories.capacity_commitment.evidence import EvidenceKind, EvidenceRepository, EvidenceSource, ReviewState
from factories.capacity_commitment.repository import CapacityRepository


HEADER = "fact_id,fact_type,raw_value,normalized_value,scope_ref,page_ref,clause_ref\n"


def content(*rows):
    return (HEADER + "\n".join(rows) + "\n").encode("utf-8")


def source(preview, evidence_id="csv-1"):
    return EvidenceSource(
        tenant_id="tenant-a",
        evidence_id=evidence_id,
        kind=EvidenceKind.ACTUALS,
        display_name="actuals.csv",
        external_ref="authorized-upload:actuals.csv",
        sha256=preview.sha256,
        captured_at="2026-09-04T14:00:00Z",
    )


def setup_db(tmp_path):
    path = tmp_path / "capacity.db"
    CapacityRepository(str(path))
    return path


def test_csv_preview_validates_rows_and_keeps_them_unreviewed(tmp_path):
    raw = content(
        "actual-a,ACTUAL_UNITS,100,100,shipment-a,row:2,",
        "actual-b,ACTUAL_UNITS,50.25,50.25,shipment-b,row:3,",
    )
    preview = preview_csv_facts(raw, tenant_id="tenant-a", evidence_id="csv-1")
    assert preview.row_count == 2
    assert preview.facts[0].review_state is ReviewState.UNREVIEWED
    assert preview.facts[0].scope_ref == "shipment-a"
    assert preview.facts[1].normalized_value == "50.25"


def test_csv_commit_is_atomic_and_exact_retry_is_idempotent(tmp_path):
    db = setup_db(tmp_path)
    raw = content(
        "actual-a,ACTUAL_UNITS,100,100,shipment-a,row:2,",
        "actual-b,ACTUAL_UNITS,50,50,shipment-b,row:3,",
    )
    preview = preview_csv_facts(raw, tenant_id="tenant-a", evidence_id="csv-1")
    created, inserted = commit_csv_import(db_path=str(db), source=source(preview), preview=preview)
    assert created is True
    assert inserted == 2
    created2, inserted2 = commit_csv_import(db_path=str(db), source=source(preview), preview=preview)
    assert created2 is False
    assert inserted2 == 0
    evidence = EvidenceRepository(str(db))
    assert len(evidence.list_sources(tenant_id="tenant-a")) == 1
    assert len(evidence.list_facts(tenant_id="tenant-a")) == 2


def test_csv_hash_mismatch_rejected_before_persistence(tmp_path):
    db = setup_db(tmp_path)
    raw = content("actual-a,ACTUAL_UNITS,100,100,shipment-a,row:2,")
    preview = preview_csv_facts(raw, tenant_id="tenant-a", evidence_id="csv-1")
    bad = EvidenceSource(
        tenant_id="tenant-a",
        evidence_id="csv-1",
        kind=EvidenceKind.ACTUALS,
        display_name="actuals.csv",
        external_ref="authorized-upload:actuals.csv",
        sha256="0" * 64,
        captured_at="2026-09-04T14:00:00Z",
    )
    with pytest.raises(ValueError, match="sha256"):
        commit_csv_import(db_path=str(db), source=bad, preview=preview)
    assert EvidenceRepository(str(db)).list_sources(tenant_id="tenant-a") == []


def test_csv_rejects_duplicate_fact_id_extra_columns_and_missing_actual_scope():
    duplicate = content(
        "dup,ACTUAL_UNITS,100,100,shipment-a,row:2,",
        "dup,ACTUAL_UNITS,50,50,shipment-b,row:3,",
    )
    with pytest.raises(ValueError, match="duplicate fact_id"):
        preview_csv_facts(duplicate, tenant_id="tenant-a", evidence_id="csv-1")

    extra = (HEADER.strip() + ",extra\nactual-a,ACTUAL_UNITS,100,100,shipment-a,row:2,,x\n").encode()
    with pytest.raises(ValueError, match="header must exactly match"):
        preview_csv_facts(extra, tenant_id="tenant-a", evidence_id="csv-1")

    no_scope = content("actual-a,ACTUAL_UNITS,100,100,,row:2,")
    with pytest.raises(ValueError, match="scope_ref"):
        preview_csv_facts(no_scope, tenant_id="tenant-a", evidence_id="csv-1")


def test_csv_rejects_nonfinite_numeric_value():
    raw = content("cost,DEDICATED_COST,NaN,NaN,,row:2,")
    with pytest.raises(ValueError, match="finite and non-negative"):
        preview_csv_facts(raw, tenant_id="tenant-a", evidence_id="csv-1")


def test_batch_conflict_rolls_back_new_source_and_prior_rows(tmp_path):
    db = setup_db(tmp_path)
    existing_raw = content("conflict,ACTUAL_UNITS,99,99,existing,row:2,")
    existing_preview = preview_csv_facts(existing_raw, tenant_id="tenant-a", evidence_id="existing-source")
    commit_csv_import(db_path=str(db), source=source(existing_preview, "existing-source"), preview=existing_preview)

    new_raw = content(
        "new-first,ACTUAL_UNITS,10,10,new-a,row:2,",
        "conflict,ACTUAL_UNITS,20,20,new-b,row:3,",
    )
    preview = preview_csv_facts(new_raw, tenant_id="tenant-a", evidence_id="csv-2")
    new_source = EvidenceSource(
        tenant_id="tenant-a",
        evidence_id="csv-2",
        kind=EvidenceKind.ACTUALS,
        display_name="new.csv",
        external_ref="authorized-upload:new.csv",
        sha256=preview.sha256,
        captured_at="2026-09-04T14:00:00Z",
    )
    with pytest.raises(FileExistsError, match="fact conflict"):
        commit_csv_import(db_path=str(db), source=new_source, preview=preview)

    evidence = EvidenceRepository(str(db))
    assert [item.evidence_id for item in evidence.list_sources(tenant_id="tenant-a")] == ["existing-source"]
    assert [item.fact_id for item in evidence.list_facts(tenant_id="tenant-a")] == ["conflict"]


def test_reimport_cannot_reset_a_reviewed_fact_to_unreviewed(tmp_path):
    db = setup_db(tmp_path)
    raw = content("actual-a,ACTUAL_UNITS,100,100,shipment-a,row:2,")
    preview = preview_csv_facts(raw, tenant_id="tenant-a", evidence_id="csv-1")
    commit_csv_import(db_path=str(db), source=source(preview), preview=preview)
    evidence = EvidenceRepository(str(db))
    evidence.review_fact(tenant_id="tenant-a", fact_id="actual-a", decision=ReviewState.CONFIRMED)
    with pytest.raises(FileExistsError, match="fact conflict"):
        commit_csv_import(db_path=str(db), source=source(preview), preview=preview)
    assert evidence.load_fact(tenant_id="tenant-a", fact_id="actual-a").review_state is ReviewState.CONFIRMED
