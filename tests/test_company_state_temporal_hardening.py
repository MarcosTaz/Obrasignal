from datetime import datetime, timedelta, timezone

import pytest

from company_state import (
    CompanyFact,
    CompanyState,
    CompanyStateError,
    FactCategory,
    KnowledgeState,
    Money,
    Provenance,
    ProvenanceBasis,
)

NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)
DECLARED = Provenance(ProvenanceBasis.DECLARED, source_ref="manual", observed_at=NOW)


def test_future_superseding_fact_does_not_hide_current_truth_before_effective_from():
    current = CompanyFact(
        FactCategory.AVAILABILITY,
        "crew.available_count",
        KnowledgeState.FACT,
        4,
        DECLARED,
        unit="workers",
    )
    future = CompanyFact(
        FactCategory.AVAILABILITY,
        "crew.available_count",
        KnowledgeState.FACT,
        6,
        Provenance(ProvenanceBasis.INTEGRATION, source_ref="office", observed_at=NOW),
        unit="workers",
        effective_from=NOW + timedelta(days=1),
        supersedes=(current.fact_id,),
    )
    state = CompanyState("tenant-a", NOW, (current, future))

    assert state.single_current_value("crew.available_count", as_of=NOW) == 4
    assert state.single_current_value("crew.available_count", as_of=NOW + timedelta(days=1)) == 6


def test_effective_replacement_does_not_resurrect_superseded_history_after_it_expires():
    current = CompanyFact(
        FactCategory.AVAILABILITY,
        "crew.available_count",
        KnowledgeState.FACT,
        4,
        DECLARED,
        unit="workers",
    )
    replacement = CompanyFact(
        FactCategory.AVAILABILITY,
        "crew.available_count",
        KnowledgeState.FACT,
        6,
        Provenance(ProvenanceBasis.INTEGRATION, source_ref="office", observed_at=NOW),
        unit="workers",
        effective_from=NOW + timedelta(hours=1),
        effective_until=NOW + timedelta(hours=2),
        supersedes=(current.fact_id,),
    )
    state = CompanyState("tenant-a", NOW, (current, replacement))

    assert state.single_current_value("crew.available_count", as_of=NOW + timedelta(minutes=30)) == 4
    assert state.single_current_value("crew.available_count", as_of=NOW + timedelta(hours=1)) == 6
    assert state.single_current_value("crew.available_count", as_of=NOW + timedelta(hours=3)) is None


def test_malformed_serialized_money_fails_with_contract_error():
    with pytest.raises(CompanyStateError, match="money amount must be a finite decimal"):
        Money.from_dict({"amount": "not-a-number", "currency": "EUR"})


def test_non_nul_c0_control_character_is_rejected_in_fact_text():
    with pytest.raises(CompanyStateError, match="fact text is invalid"):
        CompanyFact(
            FactCategory.CAPABILITY,
            "capability.label",
            KnowledgeState.FACT,
            "painting\x1fmetalwork",
            DECLARED,
        )
