import sqlite3

import pytest

from factories.capacity_commitment.evidence import (
    EvidenceKind,
    EvidenceRepository,
    EvidenceSource,
    ExtractedFact,
    FactType,
    ReviewState,
    sha256_bytes,
)
from factories.capacity_commitment.repository import CapacityRepository


def add_evidence(db_path, *, evidence_id="contract-1", fact_id="committed", value="100000"):
    evidence = EvidenceRepository(str(db_path))
    evidence.save_source(
        EvidenceSource(
            tenant_id="tenant-a",
            evidence_id=evidence_id,
            kind=EvidenceKind.CONTRACT,
            display_name=f"{evidence_id}.pdf",
            external_ref=f"customer-room:{evidence_id}",
            sha256=sha256_bytes(evidence_id.encode()),
            captured_at="2026-08-29T20:00:00Z",
        )
    )
    evidence.save_fact(
        ExtractedFact(
            tenant_id="tenant-a",
            fact_id=fact_id,
            evidence_id=evidence_id,
            fact_type=FactType.COMMITTED_UNITS,
            raw_value=value,
            normalized_value=value,
            page_ref="p.4",
            clause_ref="4.2",
        )
    )
    evidence.review_fact(
        tenant_id="tenant-a", fact_id=fact_id, decision=ReviewState.CONFIRMED
    )
    return evidence


def test_capacity_backup_restore_rewinds_evidence_with_case_snapshot(tmp_path):
    live_path = tmp_path / "live.db"
    backup_path = tmp_path / "backup.db"
    capacity = CapacityRepository(str(live_path))
    add_evidence(live_path, evidence_id="contract-v1", fact_id="fact-v1", value="100000")
    capacity.backup_to(str(backup_path))

    evidence_live = add_evidence(
        live_path, evidence_id="contract-v2", fact_id="fact-v2", value="90000"
    )
    assert {item.evidence_id for item in evidence_live.list_sources(tenant_id="tenant-a")} == {
        "contract-v1",
        "contract-v2",
    }

    capacity.restore_from(str(backup_path))
    restored = EvidenceRepository(str(live_path))
    assert [item.evidence_id for item in restored.list_sources(tenant_id="tenant-a")] == [
        "contract-v1"
    ]
    facts = restored.list_facts(tenant_id="tenant-a")
    assert [item.fact_id for item in facts] == ["fact-v1"]
    assert facts[0].review_state is ReviewState.CONFIRMED


def test_restore_rejects_cross_tenant_evidence_fact_before_mutating_live(tmp_path):
    live_path = tmp_path / "live.db"
    bad_path = tmp_path / "bad.db"
    live = CapacityRepository(str(live_path))
    add_evidence(live_path, evidence_id="live-source", fact_id="live-fact")

    CapacityRepository(str(bad_path))
    add_evidence(bad_path, evidence_id="bad-source", fact_id="bad-fact")
    with sqlite3.connect(bad_path) as conn:
        conn.execute(
            "UPDATE capacity_commitment_evidence_facts SET tenant_id='tenant-b' WHERE fact_id='bad-fact'"
        )

    with pytest.raises(ValueError, match="missing or cross-tenant source"):
        live.restore_from(str(bad_path))

    restored = EvidenceRepository(str(live_path))
    assert [item.evidence_id for item in restored.list_sources(tenant_id="tenant-a")] == [
        "live-source"
    ]


def test_restore_rejects_noncanonical_evidence_fact_before_mutating_live(tmp_path):
    live_path = tmp_path / "live.db"
    bad_path = tmp_path / "bad.db"
    live = CapacityRepository(str(live_path))
    add_evidence(live_path, evidence_id="live-source", fact_id="live-fact")

    CapacityRepository(str(bad_path))
    add_evidence(bad_path, evidence_id="bad-source", fact_id="bad-fact")
    with sqlite3.connect(bad_path) as conn:
        conn.execute(
            "UPDATE capacity_commitment_evidence_facts SET normalized_value='1E+5' WHERE fact_id='bad-fact'"
        )

    with pytest.raises(ValueError, match="not canonically normalized"):
        live.restore_from(str(bad_path))

    restored = EvidenceRepository(str(live_path))
    assert [item.evidence_id for item in restored.list_sources(tenant_id="tenant-a")] == [
        "live-source"
    ]


def test_restore_of_legacy_case_only_backup_clears_newer_evidence(tmp_path):
    live_path = tmp_path / "live.db"
    legacy_path = tmp_path / "legacy.db"
    capacity = CapacityRepository(str(live_path))
    add_evidence(live_path, evidence_id="newer", fact_id="newer-fact")

    # Valid historical backup shape from before revision/evidence tables existed.
    with sqlite3.connect(legacy_path) as conn:
        conn.execute(
            """
            CREATE TABLE capacity_commitment_cases (
                tenant_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                snapshot TEXT NOT NULL,
                engine_version TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, case_id)
            )
            """
        )

    capacity.restore_from(str(legacy_path))
    evidence = EvidenceRepository(str(live_path))
    assert evidence.list_sources(tenant_id="tenant-a") == []
    assert evidence.list_facts(tenant_id="tenant-a") == []


def test_restore_rejects_half_present_evidence_schema(tmp_path):
    live_path = tmp_path / "live.db"
    bad_path = tmp_path / "bad.db"
    live = CapacityRepository(str(live_path))

    # Start valid then deliberately remove one half of the evidence schema.
    CapacityRepository(str(bad_path))
    with sqlite3.connect(bad_path) as conn:
        conn.execute("DROP TABLE capacity_commitment_evidence_facts")

    with pytest.raises(ValueError, match="incomplete evidence schema"):
        live.restore_from(str(bad_path))
