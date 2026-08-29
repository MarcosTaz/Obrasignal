from copy import deepcopy
from datetime import datetime, timezone

import pytest

from opportunity_data_quality import (
    DataQualityPolicy,
    FIELD_REGISTRY,
    POLICY_VERSION,
    evaluate_opportunity_data_quality,
)


NOW = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)


def _full(**overrides):
    record = {
        "source": "TED",
        "signal_type": "TENDER",
        "external_id": "123-2026",
        "title": "Construction of a school",
        "buyer": "City Council",
        "country": "PRT",
        "deadline": "2026-09-30T17:00:00Z",
        "value": "500000 EUR",
        "currency": "EUR",
        "description": "Construction works",
        "cpv": "45214200",
        "publication_date": "2026-08-20",
        "url": "https://example.test/tender/123",
        "source_updated_at": "2026-08-24T12:00:00Z",
    }
    record.update(overrides)
    return record


def _evaluate(record, context=None, policy=None):
    return evaluate_opportunity_data_quality(
        record,
        context or {},
        policy or DataQualityPolicy(),
        evaluated_at=NOW,
    )


def test_field_registry_has_unique_central_keys():
    keys = [field.key for field in FIELD_REGISTRY]
    assert len(keys) == len(set(keys))
    assert {"source", "opportunity_identity", "deadline", "published_value", "provenance"} <= set(keys)


def test_fully_populated_opportunity_is_complete_without_commercial_claims():
    result = _evaluate(_full())
    payload = result.to_dict()

    assert result.completeness_ratio == 1.0
    assert not result.missing_fields
    assert not result.unknown_fields
    assert not result.invalid_fields
    assert not result.critical_missing_fields
    assert "confidence" not in repr(payload).lower()
    assert "commercial" not in repr(payload).lower()
    assert "score" not in payload


def test_partially_populated_and_almost_empty_records_are_transparent():
    partial = _evaluate(_full(buyer="", description=None, value=None))
    empty = _evaluate({"signal_type": "TENDER"})

    assert {"buyer", "description", "published_value"} <= set(partial.missing_fields)
    assert partial.completeness_ratio < 1.0
    assert {"source", "opportunity_identity", "title", "provenance"} <= set(empty.critical_missing_fields)
    assert empty.available_fields == ()
    assert empty.completeness_ratio == 0.0


def test_blank_value_is_missing_not_available():
    result = _evaluate(_full(deadline="   "))
    assert "deadline" in result.missing_fields
    assert "deadline" not in result.available_fields


def test_not_applicable_fields_do_not_reduce_ratio():
    record = _full(signal_type="PROCUREMENT_PLAN")
    record.pop("deadline")
    record.pop("currency")
    result = _evaluate(record)

    assert "deadline" in result.not_applicable_fields
    assert "currency" in result.not_applicable_fields
    assert result.completeness_ratio == 1.0


def test_unknown_is_distinct_and_counts_in_denominator():
    base = _evaluate(_full(buyer=None))
    unknown = _evaluate(_full(buyer=None), {"unknown_fields": ["buyer"]})

    assert "buyer" in unknown.unknown_fields
    assert "buyer" not in unknown.missing_fields
    assert "buyer" not in unknown.available_fields
    assert unknown.completeness_ratio == base.completeness_ratio


def test_invalid_values_are_not_missing():
    result = _evaluate(_full(deadline="31/31/2026", currency="EURO", value="-1"))

    assert {"deadline", "currency", "published_value"} <= set(result.invalid_fields)
    assert not ({"deadline", "currency", "published_value"} & set(result.missing_fields))


def test_critical_missing_is_small_explicit_subset():
    result = _evaluate(_full(source=None, external_id=None, url=None, title=None))
    assert set(result.critical_missing_fields) == {
        "source",
        "opportunity_identity",
        "title",
        "provenance",
    }


def test_completeness_ratio_is_plain_available_over_applicable_expected():
    record = _full()
    record["buyer"] = None
    result = _evaluate(record)
    payload = result.to_dict()

    assert payload["summary"]["applicable_expected"] == 13
    assert payload["summary"]["present"] == 12
    assert result.completeness_ratio == round(12 / 13, 4)


def test_source_limitation_is_not_connector_failure_or_missing():
    record = _full(value=None)
    result = _evaluate(
        record,
        {
            "not_provided_fields": ["published_value"],
            "source_coverage_notes": ["Publisher does not provide an estimated value for this notice family."],
        },
    )

    assert "published_value" in result.not_provided_by_source_fields
    assert "published_value" not in result.missing_fields
    assert result.completeness_ratio == 1.0
    assert "failure" not in " ".join(result.source_coverage_notes).lower()


def test_missing_provenance_is_a_data_quality_issue():
    result = _evaluate(_full(url=None, source_reference=None))
    assert "provenance" in result.missing_fields
    assert "provenance" in result.critical_missing_fields


def test_different_signal_types_have_different_deadline_applicability():
    tender = _evaluate(_full(deadline=None, signal_type="TENDER"))
    plan = _evaluate(_full(deadline=None, signal_type="PROCUREMENT_PLAN"))
    forecast = _evaluate(_full(deadline=None, signal_type="FORECAST"))

    assert "deadline" in tender.missing_fields
    assert "deadline" in forecast.missing_fields
    assert "deadline" in plan.not_applicable_fields


def test_expected_field_overrides_signal_type_applicability():
    result = _evaluate(
        _full(deadline=None, signal_type="PROCUREMENT_PLAN"),
        {"expected_fields": ["deadline"]},
    )
    assert "deadline" in result.missing_fields


def test_evaluator_does_not_mutate_opportunity_or_context():
    record = _full()
    context = {"unknown_fields": ["buyer"], "source_coverage_notes": ["note"]}
    record_before = deepcopy(record)
    context_before = deepcopy(context)

    _evaluate(record, context)

    assert record == record_before
    assert context == context_before


def test_fixed_inputs_policy_and_clock_are_deterministic():
    record = _full()
    context = {"source_coverage_notes": ["stable"]}
    policy = DataQualityPolicy(version="test-policy")

    first = evaluate_opportunity_data_quality(record, context, policy, evaluated_at=NOW)
    second = evaluate_opportunity_data_quality(record, context, policy, evaluated_at=NOW)

    assert first == second
    assert first.policy_version == "test-policy"


def test_freshness_requires_policy_and_timestamp():
    record = _full(source_updated_at="2026-08-01T00:00:00Z")
    no_policy = _evaluate(record)
    stale = _evaluate(record, policy=DataQualityPolicy(stale_after_days=7))

    assert "updated_at" in no_policy.available_fields
    assert "updated_at" in stale.stale_fields
    # Stale means present-but-old; it does not pretend the field is absent.
    assert stale.completeness_ratio == no_policy.completeness_ratio == 1.0


def test_malformed_date_invalid_currency_and_unsafe_text_fail_closed():
    result = _evaluate(
        _full(
            deadline="javascript:alert(1)",
            currency="<script>",
            title="bad\x00title",
        )
    )
    assert {"deadline", "currency", "title"} <= set(result.invalid_fields)


def test_oversized_source_notes_are_bounded_and_nul_stripped():
    result = _evaluate(
        _full(),
        {"source_coverage_notes": [("x" * 2000) + "\x00"] * 30},
    )
    assert len(result.source_coverage_notes) == 20
    assert all(len(note) <= 1000 and "\x00" not in note for note in result.source_coverage_notes)


def test_adding_valid_expected_field_cannot_reduce_completeness():
    base_record = _full(buyer=None)
    before = _evaluate(base_record)
    after = _evaluate({**base_record, "buyer": "Municipality"})
    assert after.completeness_ratio >= before.completeness_ratio


def test_removing_valid_expected_field_cannot_increase_completeness():
    before = _evaluate(_full())
    record = _full()
    record["buyer"] = None
    after = _evaluate(record)
    assert after.completeness_ratio <= before.completeness_ratio


def test_non_applicable_field_value_does_not_change_denominator_when_absent():
    without_currency = _full(signal_type="PROCUREMENT_PLAN")
    without_currency.pop("currency")
    without_currency.pop("deadline")
    result = _evaluate(without_currency)
    assert "currency" in result.not_applicable_fields
    assert "deadline" in result.not_applicable_fields


def test_policy_validation_and_contract_version():
    assert DataQualityPolicy().version == POLICY_VERSION
    with pytest.raises(ValueError):
        DataQualityPolicy(version="")
    with pytest.raises(ValueError):
        DataQualityPolicy(stale_after_days=-1)


def test_non_mapping_input_rejected():
    with pytest.raises(TypeError):
        evaluate_opportunity_data_quality([], evaluated_at=NOW)
    with pytest.raises(TypeError):
        evaluate_opportunity_data_quality(_full(), [], evaluated_at=NOW)
