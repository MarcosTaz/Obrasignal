import pytest

from analytics_commercial import commercial_funnel, evidence_point


def _stage(result, name):
    return next(stage for stage in result["stages"] if stage["stage"] == name)


def test_missing_commercial_stages_are_unknown_not_zero_or_rejection():
    result = commercial_funnel({
        "outreach": evidence_point(
            quality="OBSERVABLE",
            count=10,
            source_owner="GTM",
            observed_at="2026-08-25T18:00:00+00:00",
        )
    })
    reply = _stage(result, "reply")
    interest = _stage(result, "interest")

    assert reply["quality"] == "UNKNOWN"
    assert reply["count"] is None
    assert reply["progression_rate"] is None
    assert reply["dropoff_rate"] is None
    assert reply["rate_blocker"] == "missing_or_partial_owner_evidence"
    assert interest["quality"] == "UNKNOWN"
    assert "never interpreted as rejection" in result["interpretation"]


def test_adjacent_observable_owner_counts_can_compute_progression():
    result = commercial_funnel({
        "outreach": evidence_point(
            quality="OBSERVABLE", count=10, source_owner="GTM"
        ),
        "reply": evidence_point(
            quality="OBSERVABLE", count=2, source_owner="GTM"
        ),
    })
    reply = _stage(result, "reply")
    interest = _stage(result, "interest")

    assert reply["progression_rate"] == 0.2
    assert reply["dropoff_rate"] == 0.8
    assert interest["progression_rate"] is None
    assert interest["dropoff_rate"] is None


def test_partial_or_unknown_evidence_cannot_publish_numeric_count():
    for quality in ("PARTIAL", "UNKNOWN"):
        with pytest.raises(ValueError, match="cannot_publish_count"):
            evidence_point(
                quality=quality,
                count=0,
                source_owner="GTM",
            )


def test_zero_previous_stage_denominator_does_not_create_a_rate():
    result = commercial_funnel({
        "outreach": evidence_point(
            quality="OBSERVABLE", count=0, source_owner="GTM"
        ),
        "reply": evidence_point(
            quality="OBSERVABLE", count=0, source_owner="GTM"
        ),
    })
    reply = _stage(result, "reply")
    assert reply["progression_rate"] is None
    assert reply["dropoff_rate"] is None
    assert reply["rate_blocker"] == "zero_previous_stage_denominator"


def test_non_monotonic_cross_owner_counts_are_exposed_as_inconsistent():
    result = commercial_funnel({
        "outreach": evidence_point(
            quality="OBSERVABLE", count=3, source_owner="GTM"
        ),
        "reply": evidence_point(
            quality="OBSERVABLE", count=4, source_owner="GTM"
        ),
    })
    reply = _stage(result, "reply")
    assert reply["progression_rate"] is None
    assert reply["dropoff_rate"] is None
    assert reply["rate_blocker"] == "non_monotonic_cross_owner_evidence"


def test_unknown_commercial_stage_names_fail_closed():
    with pytest.raises(ValueError, match="unknown_commercial_stages"):
        commercial_funnel({"made_up_stage": {"quality": "UNKNOWN"}})
