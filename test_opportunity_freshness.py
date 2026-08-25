from datetime import datetime, timedelta, timezone

import pytest

from opportunity_freshness import evaluate_freshness, policy_for


NOW = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)


def _iso(delta):
    return (NOW - delta).isoformat()


def _health(*, success_age=timedelta(minutes=5), failures=0):
    return {
        "last_success": _iso(success_age),
        "last_attempt": _iso(timedelta(minutes=1)),
        "last_failed": _iso(timedelta(minutes=1)) if failures else None,
        "consecutive_failures": failures,
    }


def _record(**overrides):
    data = {
        "external_id": "opp-1",
        "source": "TED",
        "signal_type": "TENDER",
        "published_at": _iso(timedelta(hours=2)),
        "source_updated_at": _iso(timedelta(hours=1)),
        "last_observed": _iso(timedelta(minutes=20)),
        "deadline": (NOW + timedelta(days=7)).isoformat(),
    }
    data.update(overrides)
    return data


def test_fresh_daily_source():
    result = evaluate_freshness(_record(), _health(), now=NOW)
    assert result.freshness_status == "FRESH"
    assert result.source_health_status == "HEALTHY"
    assert "RECENTLY_OBSERVED" in result.reason_codes


def test_aging_and_stale_records():
    policy = policy_for("TED", "TENDER")
    aging = evaluate_freshness(_record(last_observed=_iso(timedelta(minutes=45))), _health(), now=NOW)
    stale = evaluate_freshness(_record(last_observed=_iso(timedelta(minutes=90))), _health(), now=NOW)
    assert policy.aging_after_minutes == 30
    assert policy.stale_after_minutes == 60
    assert aging.freshness_status == "AGING"
    assert stale.freshness_status == "STALE"


def test_threshold_boundaries_are_inclusive():
    aging = evaluate_freshness(_record(last_observed=_iso(timedelta(minutes=30))), _health(), now=NOW)
    stale = evaluate_freshness(_record(last_observed=_iso(timedelta(minutes=60))), _health(), now=NOW)
    assert aging.freshness_status == "AGING"
    assert stale.freshness_status == "STALE"


def test_unknown_when_observation_timestamp_missing():
    result = evaluate_freshness(_record(last_observed=None), _health(), now=NOW)
    assert result.freshness_status == "UNKNOWN"
    assert "INSUFFICIENT_TIMESTAMPS" in result.reason_codes


def test_source_health_transient_and_persistent_failures_are_distinct():
    transient = evaluate_freshness(_record(), _health(failures=1), now=NOW)
    persistent_recent_success = evaluate_freshness(_record(), _health(failures=4), now=NOW)
    unavailable = evaluate_freshness(
        _record(),
        _health(success_age=timedelta(hours=2), failures=4),
        now=NOW,
    )
    assert transient.source_health_status == "DEGRADED"
    assert persistent_recent_success.source_health_status == "DEGRADED"
    assert unavailable.source_health_status == "UNAVAILABLE"


def test_historical_award_is_not_falsely_stale():
    result = evaluate_freshness(
        _record(
            signal_type="AWARD",
            published_at=_iso(timedelta(days=730)),
            source_updated_at=_iso(timedelta(days=730)),
            last_observed=_iso(timedelta(days=730)),
            deadline=None,
        ),
        _health(),
        now=NOW,
    )
    assert result.freshness_status == "UNKNOWN"
    assert "ARCHIVAL_RECORD" in result.reason_codes
    assert "NO_RECENT_OBSERVATION" not in result.reason_codes


def test_closed_tender_is_not_reclassified_as_stale():
    result = evaluate_freshness(
        _record(status="CLOSED", last_observed=_iso(timedelta(days=20))),
        _health(),
        now=NOW,
    )
    assert result.freshness_status == "UNKNOWN"
    assert "EXPLICITLY_CLOSED" in result.reason_codes


def test_retrieved_today_does_not_make_old_observation_fresh():
    result = evaluate_freshness(
        _record(
            last_observed=_iso(timedelta(days=5)),
            source_updated_at=_iso(timedelta(days=5)),
            retrieved_at=NOW.isoformat(),
        ),
        _health(),
        now=NOW,
    )
    assert result.freshness_status == "STALE"


def test_near_deadline_tightens_same_observation_age():
    old = _iso(timedelta(minutes=40))
    far = evaluate_freshness(
        _record(last_observed=old, deadline=(NOW + timedelta(days=10)).isoformat()),
        _health(),
        now=NOW,
    )
    near = evaluate_freshness(
        _record(last_observed=old, deadline=(NOW + timedelta(hours=12)).isoformat()),
        _health(),
        now=NOW,
    )
    assert far.freshness_status == "AGING"
    assert near.freshness_status == "STALE"
    assert "DEADLINE_NEAR_WITH_OLD_OBSERVATION" in near.reason_codes


def test_long_horizon_planning_signal_uses_source_and_signal_policy():
    result = evaluate_freshness(
        _record(
            signal_type="PROCUREMENT_PLAN",
            last_observed=_iso(timedelta(hours=2)),
            deadline=(NOW + timedelta(days=180)).isoformat(),
        ),
        _health(),
        now=NOW,
    )
    assert result.freshness_status == "AGING"
    assert policy_for("TED", "PROCUREMENT_PLAN").stale_after_minutes == 240


def test_unknown_source_uses_explicit_conservative_fallback_and_unknown_health():
    result = evaluate_freshness(
        _record(source="CUSTOM", last_observed=_iso(timedelta(hours=2))),
        None,
        now=NOW,
    )
    assert result.freshness_status == "FRESH"
    assert result.source_health_status == "UNKNOWN"
    assert result.policy_source == "fallback_conservative"
    assert result.confidence == "LOW"


def test_future_and_naive_timestamps_fail_closed_to_unknown():
    future = evaluate_freshness(
        _record(last_observed=(NOW + timedelta(minutes=1)).isoformat()),
        _health(),
        now=NOW,
    )
    naive = evaluate_freshness(
        _record(last_observed="2026-08-24T23:00:00"),
        _health(),
        now=NOW,
    )
    assert future.freshness_status == "UNKNOWN"
    assert naive.freshness_status == "UNKNOWN"
    assert "INVALID_TIMESTAMP" in future.reason_codes
    assert "INVALID_TIMESTAMP" in naive.reason_codes


def test_timezone_boundaries_are_normalized_to_utc():
    result = evaluate_freshness(
        _record(last_observed="2026-08-25T01:40:00+02:00"),
        _health(),
        now=NOW,
    )
    assert result.observation_age_minutes == 20.0
    assert result.freshness_status == "FRESH"


def test_same_inputs_are_deterministic_and_input_is_not_mutated():
    record = _record()
    health = _health()
    before_record = dict(record)
    before_health = dict(health)
    first = evaluate_freshness(record, health, now=NOW)
    second = evaluate_freshness(record, health, now=NOW)
    assert first == second
    assert record == before_record
    assert health == before_health


def test_increasing_observation_age_cannot_improve_status():
    statuses = []
    for minutes in (5, 35, 70):
        result = evaluate_freshness(
            _record(last_observed=_iso(timedelta(minutes=minutes))),
            _health(),
            now=NOW,
        )
        statuses.append(result.freshness_status)
    assert statuses == ["FRESH", "AGING", "STALE"]


def test_malformed_timestamps_do_not_escape_as_fresh():
    result = evaluate_freshness(_record(last_observed="not-a-time"), _health(), now=NOW)
    assert result.freshness_status == "UNKNOWN"
    assert "INVALID_TIMESTAMP" in result.reason_codes


def test_oversized_or_control_character_source_ids_are_rejected():
    with pytest.raises(ValueError, match="invalid source"):
        evaluate_freshness(_record(source="X" * 129), _health(), now=NOW)
    with pytest.raises(ValueError, match="invalid source"):
        evaluate_freshness(_record(source="TED\n<script>"), _health(), now=NOW)


def test_oversized_opportunity_id_is_rejected():
    with pytest.raises(ValueError, match="invalid opportunity_id"):
        evaluate_freshness(_record(external_id="x" * 513), _health(), now=NOW)


def test_sql_metacharacters_in_bounded_source_id_are_data_not_execution():
    result = evaluate_freshness(_record(source="TED'; DROP TABLE signal_records;--"), None, now=NOW)
    assert result.source_id == "TED'; DROP TABLE signal_records;--"
    assert result.policy_source == "fallback_conservative"


def test_invalid_failure_count_fails_health_closed_without_changing_record_freshness():
    result = evaluate_freshness(_record(), {"consecutive_failures": "many"}, now=NOW)
    assert result.freshness_status == "FRESH"
    assert result.source_health_status == "UNKNOWN"
    assert "INVALID_SOURCE_HEALTH" in result.reason_codes
