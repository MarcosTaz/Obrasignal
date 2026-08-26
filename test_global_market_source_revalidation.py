from global_market_source_revalidation import (
    SourceContractFingerprint,
    changed_dimensions,
    compare_source_contract,
    source_revalidation_required,
)


def fp(**overrides):
    base = dict(
        endpoint="https://official.example/api",
        api_version="v1",
        schema="schema-a",
        pagination="cursor",
        authentication="none",
        identity="notice-id",
        update_identity="version-id",
        lifecycle="open/closed/cancelled",
        time_semantics="UTC",
        taxonomy="native",
        rate_limit="100/min",
    )
    base.update(overrides)
    return SourceContractFingerprint(**base)


def test_exact_contract_is_unchanged_only_with_current_evidence():
    baseline = fp()
    assert compare_source_contract(baseline, baseline) == "UNCHANGED"
    assert compare_source_contract(baseline, None) == "CURRENT_EVIDENCE_MISSING"
    assert compare_source_contract(None, baseline) == "CURRENT_EVIDENCE_MISSING"


def test_each_material_contract_dimension_can_force_revalidation():
    baseline = fp()
    for field in SourceContractFingerprint.__dataclass_fields__:
        current = fp(**{field: getattr(baseline, field) + "-changed"})
        assert compare_source_contract(baseline, current) == "MATERIAL_DRIFT"
        assert changed_dimensions(baseline, current) == (field,)
        assert source_revalidation_required(
            previous=baseline,
            current=current,
            reachable=True,
            response_semantics_valid=True,
        ) is True


def test_http_200_equivalent_reachability_is_not_enough():
    baseline = fp()
    assert source_revalidation_required(
        previous=baseline,
        current=fp(schema="schema-b"),
        reachable=True,
        response_semantics_valid=True,
    ) is True
    assert source_revalidation_required(
        previous=baseline,
        current=baseline,
        reachable=True,
        response_semantics_valid=False,
    ) is True


def test_only_exact_current_contract_plus_valid_semantics_stays_green():
    baseline = fp()
    assert source_revalidation_required(
        previous=baseline,
        current=baseline,
        reachable=True,
        response_semantics_valid=True,
    ) is False
