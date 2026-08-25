from datetime import datetime, timedelta, timezone
import sqlite3
import tempfile

import pytest

from company_state import CompanyFact, CompanyStateError, FactCategory, KnowledgeState, Provenance, ProvenanceBasis
from company_state_store import CompanyStateService, StaleCompanyStateWrite

NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)


def make_conn(path):
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def provider_crew(value, *, source="office", observed_at=NOW, basis=ProvenanceBasis.INTEGRATION):
    knowledge = KnowledgeState.INFERENCE if basis is ProvenanceBasis.LEARNED else KnowledgeState.FACT
    return CompanyFact(
        FactCategory.AVAILABILITY,
        "crew.available_count",
        knowledge,
        value,
        Provenance(basis, source_ref=source, observed_at=observed_at),
        unit="workers",
    )


def test_trusted_provider_same_source_supersedes_its_own_previous_observation():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        first = service.ingest_trusted_facts("a", [provider_crew(4)], clock=NOW)
        second_fact = provider_crew(5, observed_at=NOW + timedelta(minutes=1))
        second = service.ingest_trusted_facts("a", [second_fact], clock=NOW + timedelta(minutes=1))
        current = [f for f in second.current_facts() if f.code == "crew.available_count"]
        assert len(current) == 1 and current[0].value == 5
        assert current[0].supersedes == (first.facts[0].fact_id,)
        assert service.get_version("a", 1).single_current_value("crew.available_count") == 4


def test_trusted_provider_cross_source_disagreement_remains_conflict():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        service.ingest_trusted_facts("a", [provider_crew(4, source="office-a")], clock=NOW)
        mixed = service.ingest_trusted_facts(
            "a", [provider_crew(6, source="office-b", observed_at=NOW + timedelta(minutes=1))],
            clock=NOW + timedelta(minutes=1),
        )
        assert mixed.single_current_value("crew.available_count") is None
        assert len(mixed.conflicts()) == 1


def test_trusted_provider_rejects_manual_provenance_and_future_observation():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        declared = CompanyFact(
            FactCategory.AVAILABILITY, "crew.available_count", KnowledgeState.FACT, 4,
            Provenance(ProvenanceBasis.DECLARED, source_ref="manual", observed_at=NOW), unit="workers",
        )
        with pytest.raises(CompanyStateError):
            service.ingest_trusted_facts("a", [declared], clock=NOW)
        with pytest.raises(CompanyStateError, match="future"):
            service.ingest_trusted_facts(
                "a", [provider_crew(4, observed_at=NOW + timedelta(minutes=1))], clock=NOW,
            )


def test_learned_provenance_cannot_masquerade_as_fact():
    with pytest.raises(CompanyStateError, match="INFERENCE"):
        CompanyFact(
            FactCategory.CAPABILITY, "capability.painting", KnowledgeState.FACT, True,
            Provenance(ProvenanceBasis.LEARNED, source_ref="dna", observed_at=NOW),
        )
    inferred = CompanyFact(
        FactCategory.CAPABILITY, "capability.painting", KnowledgeState.INFERENCE, True,
        Provenance(ProvenanceBasis.LEARNED, source_ref="dna", observed_at=NOW),
    )
    assert inferred.knowledge is KnowledgeState.INFERENCE


def test_trusted_provider_optimistic_concurrency_is_enforced():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        service.ingest_trusted_facts("a", [provider_crew(4)], clock=NOW)
        with pytest.raises(StaleCompanyStateWrite):
            service.ingest_trusted_facts(
                "a", [provider_crew(5, observed_at=NOW + timedelta(minutes=1))],
                clock=NOW + timedelta(minutes=1), expected_version=0,
            )
