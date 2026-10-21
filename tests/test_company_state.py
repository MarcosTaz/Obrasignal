from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from company_state import (
    CompanyFact, CompanyState, CompanyStateError, FactCategory, FreshnessState,
    KnowledgeState, Money, Provenance, ProvenanceBasis, TenantBoundaryError,
)
from company_state_adapters import mobilize_inputs, economics_constraints

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
DECLARED = Provenance(ProvenanceBasis.DECLARED, observed_at=NOW)


def fact(category, code, value, *, knowledge=KnowledgeState.FACT, unit=None, **kwargs):
    return CompanyFact(category=category, code=code, knowledge=knowledge, value=value,
                       provenance=DECLARED, unit=unit, **kwargs)


def state(*facts):
    return CompanyState(account_id="tenant-a", as_of=NOW, facts=facts)


def test_unknown_is_distinct_from_zero():
    unknown = CompanyFact(FactCategory.AVAILABILITY, "crew.available_count", KnowledgeState.UNKNOWN, None, DECLARED, unit="workers")
    zero = fact(FactCategory.AVAILABILITY, "crew.available_count", 0, unit="workers")
    assert unknown.fact_id != zero.fact_id
    assert state(unknown).single_current_value("crew.available_count") is None
    assert state(zero).single_current_value("crew.available_count") == 0


def test_missing_equipment_is_not_negative_claim():
    s = state()
    out = mobilize_inputs(s)
    assert out["own_vehicles_available"]["state"] == "UNKNOWN"
    assert out["own_vehicles_available"]["value"] is None


def test_owned_vehicle_does_not_imply_available_vehicle():
    owned = fact(FactCategory.EQUIPMENT, "vehicle.owned_count", 1, unit="vehicles")
    out = mobilize_inputs(state(owned))
    assert out["own_vehicles_available"]["state"] == "UNKNOWN"


def test_known_zero_vehicle_availability_stays_zero():
    available = fact(FactCategory.AVAILABILITY, "vehicle.available_count", 0, unit="vehicles")
    out = mobilize_inputs(state(available))
    assert out["own_vehicles_available"] == {
        "state": "KNOWN",
        "value": 0,
        "fact_ids": [available.fact_id],
        "reason": None,
        "knowledge_states": ["FACT"],
        "provenance_bases": ["DECLARED"],
    }


def test_no_certification_record_is_not_not_certified():
    assert "qualification.iso-9001" not in state().unknowns()
    assert all(f.category is not FactCategory.QUALIFICATION for f in state().active_facts())


def test_expired_availability_is_not_extended_silently():
    crew = fact(FactCategory.AVAILABILITY, "crew.available_count", 4, unit="workers", effective_until=NOW - timedelta(seconds=1))
    s = state(crew)
    assert crew.freshness(NOW) is FreshnessState.EXPIRED
    assert s.single_current_value("crew.available_count") is None
    assert mobilize_inputs(s)["workers"]["state"] == "UNKNOWN"


def test_future_availability_is_not_current():
    crew = fact(FactCategory.AVAILABILITY, "crew.available_count", 4, unit="workers", effective_from=NOW + timedelta(days=1))
    assert crew.freshness(NOW) is FreshnessState.NOT_YET_EFFECTIVE
    assert mobilize_inputs(state(crew))["workers"]["state"] == "UNKNOWN"


def test_stale_fact_is_visible_but_not_current_truth():
    crew = fact(FactCategory.AVAILABILITY, "crew.available_count", 4, unit="workers", freshness_until=NOW - timedelta(seconds=1))
    s = state(crew)
    assert crew.freshness(NOW) is FreshnessState.STALE
    assert "crew.available_count" in s.unknowns()
    assert s.single_current_value("crew.available_count") is None
    assert mobilize_inputs(s)["workers"]["reason"] == "fact_stale"


def test_stale_observation_does_not_conflict_with_current_observation():
    stale = fact(
        FactCategory.AVAILABILITY,
        "crew.available_count",
        4,
        unit="workers",
        freshness_until=NOW - timedelta(seconds=1),
    )
    current = CompanyFact(
        FactCategory.AVAILABILITY,
        "crew.available_count",
        KnowledgeState.FACT,
        6,
        Provenance(ProvenanceBasis.INTEGRATION, source_ref="office", observed_at=NOW),
        unit="workers",
        freshness_until=NOW + timedelta(days=1),
    )
    s = state(stale, current)
    assert s.conflicts() == ()
    assert s.single_current_value("crew.available_count") == 6
    out = mobilize_inputs(s)["workers"]
    assert out["state"] == "KNOWN"
    assert out["value"] == 6
    assert out["knowledge_states"] == ["FACT"]
    assert out["provenance_bases"] == ["INTEGRATION"]


def test_conflicting_current_counts_are_preserved_not_averaged():
    a = fact(FactCategory.AVAILABILITY, "crew.available_count", 4, unit="workers", scope="operations")
    b = CompanyFact(FactCategory.AVAILABILITY, "crew.available_count", KnowledgeState.FACT, 6,
                    Provenance(ProvenanceBasis.INTEGRATION, source_ref="office"), scope="operations", unit="workers")
    s = state(a, b)
    assert len(s.conflicts()) == 1
    assert s.single_current_value("crew.available_count", category=FactCategory.AVAILABILITY) is None
    assert mobilize_inputs(s)["workers"]["state"] == "CONFLICT"


def test_same_value_two_sources_is_not_conflict():
    a = fact(FactCategory.AVAILABILITY, "crew.available_count", 4, unit="workers")
    b = CompanyFact(FactCategory.AVAILABILITY, "crew.available_count", KnowledgeState.FACT, 4,
                    Provenance(ProvenanceBasis.INTEGRATION, source_ref="office"), unit="workers")
    assert state(a, b).conflicts() == ()


def test_explicit_supersession_preserves_history_and_resolves_current():
    old = fact(FactCategory.AVAILABILITY, "crew.available_count", 4, unit="workers")
    new = CompanyFact(FactCategory.AVAILABILITY, "crew.available_count", KnowledgeState.FACT, 6,
                      Provenance(ProvenanceBasis.VERIFIED, verified_at=NOW), unit="workers",
                      supersedes=(old.fact_id,))
    s = state(old, new)
    assert len(s.facts) == 2
    assert s.single_current_value("crew.available_count") == 6
    assert s.conflicts() == ()


def test_supersession_cannot_cross_semantic_fact():
    old = fact(FactCategory.CAPACITY, "crew.total_count", 10, unit="workers")
    with pytest.raises(CompanyStateError):
        state(old, CompanyFact(FactCategory.AVAILABILITY, "crew.available_count", KnowledgeState.FACT, 4,
                               DECLARED, unit="workers", supersedes=(old.fact_id,)))


def test_available_crew_cannot_exceed_known_total():
    total = fact(FactCategory.CAPACITY, "crew.total_count", 3, unit="workers")
    available = fact(FactCategory.AVAILABILITY, "crew.available_count", 4, unit="workers")
    with pytest.raises(CompanyStateError):
        state(total, available)


def test_stale_total_does_not_constrain_current_available_crew():
    total = fact(
        FactCategory.CAPACITY,
        "crew.total_count",
        3,
        unit="workers",
        freshness_until=NOW - timedelta(seconds=1),
    )
    available = fact(FactCategory.AVAILABILITY, "crew.available_count", 4, unit="workers")
    assert state(total, available).single_current_value("crew.available_count") == 4


def test_estimated_total_does_not_become_hard_capacity_invariant():
    total = fact(FactCategory.CAPACITY, "crew.total_count", 3, knowledge=KnowledgeState.ESTIMATE, unit="workers")
    available = fact(FactCategory.AVAILABILITY, "crew.available_count", 4, unit="workers")
    assert state(total, available).single_current_value("crew.available_count") == 4


def test_unknown_total_does_not_block_known_available():
    total = CompanyFact(FactCategory.CAPACITY, "crew.total_count", KnowledgeState.UNKNOWN, None, DECLARED, unit="workers")
    available = fact(FactCategory.AVAILABILITY, "crew.available_count", 4, unit="workers")
    assert state(total, available).single_current_value("crew.available_count") == 4


def test_negative_counts_invalid():
    with pytest.raises(CompanyStateError):
        fact(FactCategory.CAPACITY, "crew.total_count", -1, unit="workers")


def test_float_values_rejected_including_nan_and_infinity():
    for value in (1.5, float("nan"), float("inf")):
        with pytest.raises(CompanyStateError):
            fact(FactCategory.OPERATIONAL_CONSTRAINT, "policy.test", value)


def test_money_requires_explicit_currency_and_is_decimal():
    money = Money(Decimal("50000.00"), "eur")
    assert money.to_dict() == {"amount": "50000.00", "currency": "EUR"}
    with pytest.raises(CompanyStateError):
        Money(Decimal("1"), "")
    with pytest.raises(CompanyStateError):
        Money(Decimal("NaN"), "EUR")


def test_financial_constraint_adapter_does_not_decide_no_bid():
    limit = fact(FactCategory.FINANCIAL_CONSTRAINT, "finance.maximum_cash_exposure", Money(Decimal("50000"), "EUR"))
    out = economics_constraints(state(limit))
    assert out["maximum_cash_exposure"]["state"] == "KNOWN"
    assert out["maximum_cash_exposure"]["value"] == {"amount": "50000", "currency": "EUR"}
    assert out["maximum_cash_exposure"]["knowledge_states"] == ["FACT"]
    assert out["maximum_cash_exposure"]["provenance_bases"] == ["DECLARED"]
    assert "decision" not in out and "no_bid" not in out


def test_different_currency_is_preserved_not_converted():
    eur = fact(FactCategory.FINANCIAL_CONSTRAINT, "finance.maximum_cash_exposure", Money(Decimal("50000"), "EUR"), scope="primary")
    usd = fact(FactCategory.FINANCIAL_CONSTRAINT, "finance.maximum_cash_exposure", Money(Decimal("50000"), "USD"), scope="other")
    s = state(eur, usd)
    assert eur.value.currency == "EUR" and usd.value.currency == "USD"


def test_verified_provenance_needs_verification_anchor():
    with pytest.raises(CompanyStateError):
        Provenance(ProvenanceBasis.VERIFIED)


def test_declared_is_legitimate_without_becoming_verified():
    p = Provenance(ProvenanceBasis.DECLARED, source_ref="manual")
    assert p.basis is ProvenanceBasis.DECLARED
    assert p.verified_at is None


def test_learned_is_inference_not_fact():
    learned = Provenance(ProvenanceBasis.LEARNED, source_ref="future-dna", observed_at=NOW)
    with pytest.raises(CompanyStateError):
        CompanyFact(FactCategory.CAPACITY, "crew.productivity_hint", KnowledgeState.FACT, 4, learned, unit="units")
    inferred = CompanyFact(FactCategory.CAPACITY, "crew.productivity_hint", KnowledgeState.INFERENCE, 4, learned, unit="units")
    assert inferred.knowledge is KnowledgeState.INFERENCE
    with pytest.raises(CompanyStateError):
        CompanyFact(FactCategory.CAPACITY, "crew.productivity_hint", KnowledgeState.INFERENCE, 4, DECLARED, unit="units")


def test_unavailable_provenance_can_only_be_unknown():
    unavailable = Provenance(ProvenanceBasis.UNAVAILABLE, source_ref="provider")
    with pytest.raises(CompanyStateError):
        CompanyFact(FactCategory.EQUIPMENT, "equipment.crane", KnowledgeState.FACT, True, unavailable)
    unknown = CompanyFact(FactCategory.EQUIPMENT, "equipment.crane", KnowledgeState.UNKNOWN, None, unavailable)
    assert unknown.knowledge is KnowledgeState.UNKNOWN


def test_timezone_naive_temporal_inputs_fail_closed():
    with pytest.raises(CompanyStateError):
        CompanyState(account_id="tenant-a", as_of=datetime(2026, 8, 25), facts=())
    with pytest.raises(CompanyStateError):
        fact(FactCategory.AVAILABILITY, "crew.available_count", 1, unit="workers", effective_until=datetime(2026, 8, 25))


def test_effective_interval_order_is_validated():
    with pytest.raises(CompanyStateError):
        fact(FactCategory.AVAILABILITY, "crew.available_count", 1, unit="workers",
             effective_from=NOW + timedelta(days=1), effective_until=NOW)


def test_deterministic_fingerprint_same_content_order_independent():
    a = fact(FactCategory.CAPACITY, "crew.total_count", 10, unit="workers")
    b = fact(FactCategory.AVAILABILITY, "crew.available_count", 4, unit="workers")
    assert state(a, b).fingerprint == state(b, a).fingerprint


def test_tenant_changes_fingerprint():
    a = fact(FactCategory.CAPACITY, "crew.total_count", 10, unit="workers")
    assert CompanyState("tenant-a", NOW, (a,)).fingerprint != CompanyState("tenant-b", NOW, (a,)).fingerprint


def test_state_version_is_not_part_of_fingerprint():
    a = fact(FactCategory.CAPACITY, "crew.total_count", 10, unit="workers")
    s = state(a)
    assert s.fingerprint == s.with_version(99).fingerprint


def test_round_trip_serialization_and_fingerprint_validation():
    a = fact(FactCategory.FINANCIAL_CONSTRAINT, "finance.working_capital_limit", Money(Decimal("123.45"), "EUR"))
    s = state(a).with_version(3)
    restored = CompanyState.from_dict(s.to_dict(), trusted_account_id="tenant-a")
    assert restored.to_dict() == s.to_dict()
    forged = s.to_dict(); forged["fingerprint"] = "cs1_deadbeef"
    with pytest.raises(CompanyStateError):
        CompanyState.from_dict(forged, trusted_account_id="tenant-a")


def test_cross_tenant_deserialization_denied():
    payload = state().to_dict()
    with pytest.raises(TenantBoundaryError):
        CompanyState.from_dict(payload, trusted_account_id="tenant-b")


def test_control_chars_and_oversized_text_rejected():
    with pytest.raises(CompanyStateError):
        fact(FactCategory.CAPABILITY, "capability.painting", "bad\x00text")
    with pytest.raises(CompanyStateError):
        fact(FactCategory.CAPABILITY, "capability.painting", "x" * 1001)


def test_malformed_fact_codes_and_enums_rejected():
    with pytest.raises(CompanyStateError):
        CompanyFact("CAPACITY", "../../crew", "FACT", 1, DECLARED, unit="workers")
    with pytest.raises(CompanyStateError):
        CompanyFact("NOPE", "crew.total_count", "FACT", 1, DECLARED, unit="workers")


def test_duplicate_semantically_identical_fact_is_deduped():
    a = fact(FactCategory.CAPACITY, "crew.total_count", 10, unit="workers")
    assert len(state(a, a).facts) == 1


def test_quality_summary_is_epistemic_counts_not_fake_score():
    known = fact(FactCategory.CAPACITY, "crew.total_count", 10, unit="workers")
    estimate = fact(FactCategory.CAPACITY, "crew.estimate", 8, knowledge=KnowledgeState.ESTIMATE, unit="workers")
    assumption = fact(FactCategory.OPERATIONAL_CONSTRAINT, "policy.assumption", True, knowledge=KnowledgeState.ASSUMPTION)
    inferred = CompanyFact(
        FactCategory.CAPACITY,
        "crew.inferred_capacity",
        KnowledgeState.INFERENCE,
        7,
        Provenance(ProvenanceBasis.LEARNED, source_ref="future-dna", observed_at=NOW),
        unit="workers",
    )
    unknown = CompanyFact(FactCategory.AVAILABILITY, "crew.available_count", KnowledgeState.UNKNOWN, None, DECLARED, unit="workers")
    summary = state(known, estimate, assumption, inferred, unknown).quality_summary()
    assert summary == {
        "known": 1,
        "estimate": 1,
        "assumption": 1,
        "inference": 1,
        "unknown": 1,
        "stale": 0,
        "conflict": 0,
    }
    assert "score" not in summary and "percent" not in summary


def test_monetary_financial_constraints_require_explicit_money_and_nonnegative():
    with pytest.raises(CompanyStateError):
        fact(FactCategory.FINANCIAL_CONSTRAINT, "finance.maximum_cash_exposure", Decimal("10"))
    with pytest.raises(CompanyStateError):
        fact(FactCategory.FINANCIAL_CONSTRAINT, "finance.maximum_cash_exposure", Money(Decimal("-1"), "EUR"))


def test_unknown_monetary_constraint_needs_no_fake_currency():
    unknown = CompanyFact(FactCategory.FINANCIAL_CONSTRAINT, "finance.maximum_cash_exposure", KnowledgeState.UNKNOWN, None, DECLARED)
    out = economics_constraints(state(unknown))
    assert out["maximum_cash_exposure"]["state"] == "UNKNOWN"
    assert out["maximum_cash_exposure"]["reason"] == "explicit_unknown"
    assert out["maximum_cash_exposure"]["knowledge_states"] == ["UNKNOWN"]


def test_adapter_preserves_estimate_basis():
    estimated = CompanyFact(
        FactCategory.AVAILABILITY,
        "crew.available_count",
        KnowledgeState.ESTIMATE,
        5,
        Provenance(ProvenanceBasis.INTEGRATION, source_ref="planning", observed_at=NOW),
        unit="workers",
    )
    out = mobilize_inputs(state(estimated))["workers"]
    assert out["state"] == "KNOWN"
    assert out["knowledge_states"] == ["ESTIMATE"]
    assert out["provenance_bases"] == ["INTEGRATION"]


def test_state_deserialization_requires_explicit_as_of_and_rejects_boolean_version():
    with pytest.raises(CompanyStateError):
        CompanyState.from_dict({"account_id": "tenant-a", "facts": []})
    with pytest.raises(CompanyStateError):
        CompanyState.from_dict({"account_id": "tenant-a", "as_of": NOW.isoformat(), "state_version": True, "facts": []})


def test_negative_distance_rejected():
    with pytest.raises(CompanyStateError):
        fact(FactCategory.GEOGRAPHY, "geography.practical_radius_km", Decimal("-0.1"), unit="km")


def test_xss_like_text_is_data_and_round_trips_without_execution_contract():
    xss = "<script>alert(1)</script>"
    f = fact(FactCategory.CAPABILITY, "capability.label", xss)
    payload = state(f).to_dict()
    assert payload["facts"][0]["value"] == xss


def test_mapping_keys_must_be_nonempty_and_bounded():
    with pytest.raises(CompanyStateError):
        fact(FactCategory.CAPABILITY, "capability.test", {"": "x"})
    with pytest.raises(CompanyStateError):
        fact(FactCategory.CAPABILITY, "capability.test", {"x" * 97: "x"})
