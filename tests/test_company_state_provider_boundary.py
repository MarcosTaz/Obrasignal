from datetime import datetime, timedelta, timezone
import sqlite3
import tempfile

import pytest

from company_state import (
    CompanyFact,
    CompanyStateError,
    FactCategory,
    KnowledgeState,
    Provenance,
    ProvenanceBasis,
    TenantBoundaryError,
)
from company_state_store import (
    CompanyStateService,
    CompanyStateStorageError,
    StaleCompanyStateWrite,
    ensure_company_state_schema,
)

NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)


def make_conn(path=":memory:"):
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def provider_crew(value, *, source="office", observed_at=NOW, basis=ProvenanceBasis.INTEGRATION, **kwargs):
    return CompanyFact(
        FactCategory.AVAILABILITY,
        "crew.available_count",
        KnowledgeState.FACT,
        value,
        Provenance(basis, source_ref=source, observed_at=observed_at, **kwargs),
        unit="workers",
    )


def test_partial_existing_snapshot_schema_fails_closed():
    conn = make_conn()
    conn.execute("CREATE TABLE company_state_snapshots(id INTEGER PRIMARY KEY)")
    conn.commit()
    with pytest.raises(CompanyStateStorageError, match="schema is incompatible"):
        ensure_company_state_schema(conn)


def test_trusted_provider_requires_explicit_provider_provenance():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        declared = CompanyFact(
            FactCategory.AVAILABILITY,
            "crew.available_count",
            KnowledgeState.FACT,
            4,
            Provenance(ProvenanceBasis.DECLARED, source_ref="manual", observed_at=NOW),
            unit="workers",
        )
        with pytest.raises(CompanyStateError, match="provider provenance"):
            service.ingest_trusted_facts("a", [declared], clock=NOW)


def test_trusted_provider_requires_source_and_observation_time():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        missing_source = CompanyFact(
            FactCategory.AVAILABILITY,
            "crew.available_count",
            KnowledgeState.FACT,
            4,
            Provenance(ProvenanceBasis.INTEGRATION, observed_at=NOW),
            unit="workers",
        )
        missing_observed = CompanyFact(
            FactCategory.AVAILABILITY,
            "crew.available_count",
            KnowledgeState.FACT,
            4,
            Provenance(ProvenanceBasis.INTEGRATION, source_ref="office"),
            unit="workers",
        )
        with pytest.raises(CompanyStateError, match="source_ref"):
            service.ingest_trusted_facts("a", [missing_source], clock=NOW)
        with pytest.raises(CompanyStateError, match="observed_at"):
            service.ingest_trusted_facts("a", [missing_observed], clock=NOW)


def test_trusted_provider_rejects_future_audit_timestamps():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        future_observation = provider_crew(4, observed_at=NOW + timedelta(seconds=1))
        with pytest.raises(CompanyStateError, match="observed_at cannot be in the future"):
            service.ingest_trusted_facts("a", [future_observation], clock=NOW)

        future_verified = CompanyFact(
            FactCategory.QUALIFICATION,
            "qualification.iso-9001",
            KnowledgeState.FACT,
            {"status": "VALID"},
            Provenance(
                ProvenanceBasis.VERIFIED,
                source_ref="cert-check",
                observed_at=NOW,
                verified_at=NOW + timedelta(seconds=1),
            ),
        )
        with pytest.raises(CompanyStateError, match="verified_at cannot be in the future"):
            service.ingest_trusted_facts("a", [future_verified], clock=NOW)


def test_trusted_provider_cannot_select_supersession_targets():
    old = provider_crew(4)
    selected = CompanyFact(
        FactCategory.AVAILABILITY,
        "crew.available_count",
        KnowledgeState.FACT,
        6,
        Provenance(ProvenanceBasis.INTEGRATION, source_ref="office", observed_at=NOW),
        unit="workers",
        supersedes=(old.fact_id,),
    )
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        with pytest.raises(CompanyStateError, match="cannot select supersession"):
            service.ingest_trusted_facts("a", [selected], clock=NOW)


def test_same_provider_supersedes_only_its_previous_same_semantic_fact():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        first = provider_crew(4, observed_at=NOW)
        s1 = service.ingest_trusted_facts("a", [first], clock=NOW)
        second = provider_crew(6, observed_at=NOW + timedelta(minutes=1))
        s2 = service.ingest_trusted_facts("a", [second], clock=NOW + timedelta(minutes=1))

        assert s1.state_version == 1
        assert s2.state_version == 2
        assert s2.single_current_value("crew.available_count") == 6
        assert s2.conflicts() == ()
        latest = [f for f in s2.current_facts() if f.code == "crew.available_count"]
        assert len(latest) == 1
        assert latest[0].supersedes == (first.fact_id,)
        assert service.get_version("a", 1).single_current_value("crew.available_count") == 4


def test_different_trusted_sources_remain_conflict_without_precedence_contract():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        office = provider_crew(5, source="office", observed_at=NOW)
        registry = provider_crew(8, source="registry", observed_at=NOW, basis=ProvenanceBasis.PUBLIC_REGISTRY)
        service.ingest_trusted_facts("a", [office], clock=NOW)
        state = service.ingest_trusted_facts("a", [registry], clock=NOW)
        assert len(state.conflicts()) == 1
        assert state.single_current_value("crew.available_count") is None


def test_manual_and_trusted_provider_disagreement_remains_conflict():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        manual = {
            "category": "AVAILABILITY",
            "code": "crew.available_count",
            "knowledge": "FACT",
            "value": 8,
            "unit": "workers",
        }
        service.patch("a", {"facts": [manual]}, clock=NOW)
        state = service.ingest_trusted_facts("a", [provider_crew(5)], clock=NOW)
        assert len(state.conflicts()) == 1


def test_trusted_provider_retry_same_fact_and_clock_is_idempotent():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        observation = provider_crew(4)
        first = service.ingest_trusted_facts("a", [observation], clock=NOW)
        second = service.ingest_trusted_facts("a", [observation], clock=NOW)
        assert first.state_version == second.state_version == 1
        assert first.fingerprint == second.fingerprint


def test_trusted_provider_expected_version_prevents_stale_write():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        service.ingest_trusted_facts("a", [provider_crew(4)], clock=NOW)
        with pytest.raises(StaleCompanyStateWrite):
            service.ingest_trusted_facts(
                "a",
                [provider_crew(5, observed_at=NOW + timedelta(minutes=1))],
                clock=NOW + timedelta(minutes=1),
                expected_version=0,
            )


def test_trusted_provider_batch_rejects_duplicate_source_semantics():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        with pytest.raises(CompanyStateError, match="duplicate source semantic keys"):
            service.ingest_trusted_facts("a", [provider_crew(4), provider_crew(5)], clock=NOW)


def test_learned_provider_input_remains_inference():
    inferred = CompanyFact(
        FactCategory.CAPACITY,
        "crew.inferred_capacity",
        KnowledgeState.INFERENCE,
        7,
        Provenance(ProvenanceBasis.LEARNED, source_ref="future-dna", observed_at=NOW),
        unit="workers",
    )
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        state = service.ingest_trusted_facts("a", [inferred], clock=NOW)
        saved = [f for f in state.current_facts() if f.code == "crew.inferred_capacity"][0]
        assert saved.knowledge is KnowledgeState.INFERENCE
        assert saved.provenance.basis is ProvenanceBasis.LEARNED


def test_invalid_trusted_tenant_fails_before_provider_write():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        with pytest.raises(TenantBoundaryError):
            service.ingest_trusted_facts("../../tenant", [provider_crew(4)], clock=NOW)
