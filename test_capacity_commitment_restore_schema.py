import sqlite3
from decimal import Decimal

import pytest

from factories.capacity_commitment.engine import ENGINE_VERSION
from factories.capacity_commitment.repository import CapacityRepository
from factories.capacity_commitment.state import AssistedCaseState, dump_state
from factories.capacity_commitment.synthetic_cases import case


def _state(case_id: str) -> AssistedCaseState:
    return AssistedCaseState(
        tenant_id="tenant-a",
        company_id="supplier-a",
        customer_id="oem-a",
        program_id="program-a",
        contract_id="lta-1",
        recovery_case=case(case_id),
        evidence_refs=("contract:1",),
        forecast_units=Decimal("110000"),
        deadline="2099-12-31",
    )


def _create_canonical_table(conn):
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


def test_restore_rejects_required_columns_without_canonical_primary_key(tmp_path):
    live_path = tmp_path / "live.db"
    weak_path = tmp_path / "weak-schema.db"
    repo = CapacityRepository(str(live_path))
    original = _state("original")
    repo.save(original)

    candidate = _state("candidate")
    with sqlite3.connect(weak_path) as conn:
        conn.execute(
            """
            CREATE TABLE capacity_commitment_cases (
                tenant_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                snapshot TEXT NOT NULL,
                engine_version TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO capacity_commitment_cases
                (tenant_id, case_id, snapshot, engine_version, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                candidate.tenant_id,
                candidate.recovery_case.case_id,
                dump_state(candidate),
                ENGINE_VERSION,
                "2026-08-29T00:00:00+00:00",
            ),
        )

    with pytest.raises(ValueError, match="primary key"):
        repo.restore_from(str(weak_path))

    assert repo.load(tenant_id="tenant-a", case_id="original") == original


def test_restore_rejects_unknown_columns_instead_of_silently_importing_newer_schema(tmp_path):
    live_path = tmp_path / "live.db"
    future_path = tmp_path / "future-schema.db"
    repo = CapacityRepository(str(live_path))
    original = _state("original")
    repo.save(original)

    candidate = _state("candidate")
    with sqlite3.connect(future_path) as conn:
        conn.execute(
            """
            CREATE TABLE capacity_commitment_cases (
                tenant_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                snapshot TEXT NOT NULL,
                engine_version TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                future_semantic_state TEXT,
                PRIMARY KEY (tenant_id, case_id)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO capacity_commitment_cases
                (tenant_id, case_id, snapshot, engine_version, updated_at, future_semantic_state)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.tenant_id,
                candidate.recovery_case.case_id,
                dump_state(candidate),
                ENGINE_VERSION,
                "2026-08-29T00:00:00+00:00",
                "must-not-be-silently-dropped",
            ),
        )

    with pytest.raises(ValueError, match="schema"):
        repo.restore_from(str(future_path))

    assert repo.load(tenant_id="tenant-a", case_id="original") == original


def test_repository_rejects_live_trigger_that_can_change_create_only_semantics(tmp_path):
    db_path = tmp_path / "triggered.db"
    with sqlite3.connect(db_path) as conn:
        _create_canonical_table(conn)
        conn.execute(
            """
            CREATE TRIGGER capacity_ignore_insert
            BEFORE INSERT ON capacity_commitment_cases
            BEGIN
                SELECT RAISE(IGNORE);
            END
            """
        )

    with pytest.raises(RuntimeError, match="trigger"):
        CapacityRepository(str(db_path))


def test_repository_rejects_live_custom_index_that_changes_identity_constraints(tmp_path):
    db_path = tmp_path / "indexed.db"
    with sqlite3.connect(db_path) as conn:
        _create_canonical_table(conn)
        conn.execute(
            "CREATE UNIQUE INDEX one_case_per_tenant ON capacity_commitment_cases (tenant_id)"
        )

    with pytest.raises(RuntimeError, match="index"):
        CapacityRepository(str(db_path))


def test_restore_rejects_source_trigger_even_though_rows_are_copied_not_schema(tmp_path):
    live_path = tmp_path / "live.db"
    source_path = tmp_path / "triggered-source.db"
    repo = CapacityRepository(str(live_path))
    original = _state("original")
    repo.save(original)

    candidate = _state("candidate")
    with sqlite3.connect(source_path) as conn:
        _create_canonical_table(conn)
        conn.execute(
            """
            INSERT INTO capacity_commitment_cases
                (tenant_id, case_id, snapshot, engine_version, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                candidate.tenant_id,
                candidate.recovery_case.case_id,
                dump_state(candidate),
                ENGINE_VERSION,
                "2026-08-29T00:00:00+00:00",
            ),
        )
        conn.execute(
            """
            CREATE TRIGGER capacity_ignore_insert
            BEFORE INSERT ON capacity_commitment_cases
            BEGIN
                SELECT RAISE(IGNORE);
            END
            """
        )

    with pytest.raises(ValueError, match="trigger"):
        repo.restore_from(str(source_path))

    assert repo.load(tenant_id="tenant-a", case_id="original") == original
