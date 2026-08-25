import pytest

from support_operations import (
    CustomerFailureClass,
    IncidentImpact,
    IncidentSeverity,
    RecoveryState,
    ServiceArea,
    ServiceReadiness,
    SupportEvidencePack,
    classify_incident,
    customer_error_payload,
    recovery_state,
    service_readiness_matrix,
)


def _support_pack(**overrides):
    values = {
        "correlation_id": "req_20260825_abcd",
        "observed_at": "2026-08-25T19:30:00+00:00",
        "service_area": ServiceArea.SOURCES,
        "failure_class": CustomerFailureClass.STALE,
        "service_readiness": ServiceReadiness.DEGRADED,
        "recovery_state": RecoveryState.IN_PROGRESS,
        "build": "66d43f6",
        "version": "support.v1",
        "dependency_state": "STALE",
        "details": {
            "http_status": 503,
            "operation": "radar_refresh",
            "error_code": "SOURCE_STALE",
            "retry_after_seconds": 60,
        },
    }
    values.update(overrides)
    return SupportEvidencePack(**values)


def test_customer_failure_taxonomy_is_exact_and_bounded():
    assert {item.value for item in CustomerFailureClass} == {
        "RETRYABLE",
        "UNAVAILABLE",
        "DEGRADED",
        "STALE",
        "UNKNOWN",
        "AUTH_REQUIRED",
        "PERMISSION_DENIED",
        "NOT_FOUND",
        "CONFLICT",
        "INVALID_INPUT",
    }


def test_service_readiness_contract_is_exact():
    assert {item.value for item in ServiceReadiness} == {
        "HEALTHY",
        "DEGRADED",
        "BLOCKED",
        "UNKNOWN",
    }


def test_service_readiness_matrix_is_complete_and_unknown_without_owner_evidence():
    matrix = service_readiness_matrix()
    assert set(matrix) == {area.value for area in ServiceArea}
    assert set(matrix.values()) == {"UNKNOWN"}


def test_service_readiness_matrix_only_promotes_explicit_owner_evidence():
    matrix = service_readiness_matrix(
        {
            ServiceArea.AUTH: ServiceReadiness.DEGRADED,
            "SOURCES": "BLOCKED",
        }
    )
    assert matrix["AUTH"] == "DEGRADED"
    assert matrix["SOURCES"] == "BLOCKED"
    assert matrix["WEB"] == "UNKNOWN"
    assert matrix["SUPPORT"] == "UNKNOWN"


def test_service_readiness_matrix_rejects_unknown_areas_or_states():
    with pytest.raises(ValueError, match="unsupported service area"):
        service_readiness_matrix({"OTHER": "HEALTHY"})
    with pytest.raises(ValueError, match="unsupported service readiness"):
        service_readiness_matrix({"AUTH": "GREEN"})


@pytest.mark.parametrize(
    ("impact", "expected"),
    [
        (IncidentImpact.TENANT_LEAKAGE, IncidentSeverity.SEV0),
        (IncidentImpact.DATA_LOSS, IncidentSeverity.SEV0),
        (IncidentImpact.SECURITY_COMPROMISE, IncidentSeverity.SEV0),
        (IncidentImpact.BILLING_ACCESS_OUTAGE, IncidentSeverity.SEV1),
        (IncidentImpact.CUSTOMER_JOURNEY_OUTAGE, IncidentSeverity.SEV1),
        (IncidentImpact.SOURCE_DEGRADATION, IncidentSeverity.SEV2),
        (IncidentImpact.SINGLE_CUSTOMER_DEFECT, IncidentSeverity.SEV3),
    ],
)
def test_incident_severity_comes_only_from_explicit_observed_impact(impact, expected):
    assert classify_incident([impact]) is expected


def test_incident_severity_uses_highest_impact_without_downgrade():
    assert classify_incident(
        [IncidentImpact.SOURCE_DEGRADATION, IncidentImpact.TENANT_LEAKAGE]
    ) is IncidentSeverity.SEV0


def test_missing_incident_evidence_is_not_silently_sev3():
    with pytest.raises(ValueError, match="impact evidence"):
        classify_incident([])


def test_recovery_preserves_restored_verified_root_cause_boundaries():
    assert recovery_state(
        started=True,
        service_restored=True,
        recovery_verified=False,
        root_cause_closed=False,
    ) is RecoveryState.SERVICE_RESTORED
    assert recovery_state(
        started=True,
        service_restored=True,
        recovery_verified=True,
        root_cause_closed=False,
    ) is RecoveryState.VERIFIED
    assert recovery_state(
        started=True,
        service_restored=True,
        recovery_verified=True,
        root_cause_closed=True,
    ) is RecoveryState.ROOT_CAUSE_CLOSED


def test_root_cause_cannot_be_closed_before_verified_recovery():
    with pytest.raises(ValueError, match="root cause"):
        recovery_state(
            started=True,
            service_restored=True,
            recovery_verified=False,
            root_cause_closed=True,
        )


def test_recovery_flags_require_real_booleans():
    with pytest.raises(ValueError, match="booleans"):
        recovery_state(
            started=1,
            service_restored=False,
            recovery_verified=False,
            root_cause_closed=False,
        )


def test_support_evidence_pack_contains_only_bounded_operational_metadata():
    pack = _support_pack().as_dict()

    assert pack["failure_class"] == "STALE"
    assert pack["service_readiness"] == "DEGRADED"
    assert set(pack["details"]) == {
        "http_status",
        "operation",
        "error_code",
        "retry_after_seconds",
    }


def test_support_evidence_rejects_any_non_allowlisted_detail_field():
    pack = _support_pack(details={"unexpected_private_field": "not-allowed"})
    with pytest.raises(ValueError, match="unsupported support evidence fields"):
        pack.as_dict()


def test_support_evidence_rejects_free_form_text_in_allowlisted_string_fields():
    pack = _support_pack(details={"operation": "free form customer text"})
    with pytest.raises(ValueError, match="unsupported characters"):
        pack.as_dict()


@pytest.mark.parametrize(
    ("details", "match"),
    [
        ({"http_status": 999}, "100..599"),
        ({"retry_after_seconds": -1}, "0..86400"),
        ({"attempt": True}, "integer"),
        ({"state_version": 2**63}, "0..9223372036854775807"),
    ],
)
def test_support_evidence_rejects_unbounded_or_wrong_type_integers(details, match):
    with pytest.raises(ValueError, match=match):
        _support_pack(details=details).as_dict()


def test_support_evidence_rejects_noncanonical_enum_inputs():
    with pytest.raises(ValueError, match="canonical support enum"):
        _support_pack(service_area="SOURCES").as_dict()


def test_support_evidence_rejects_email_like_dependency_state():
    with pytest.raises(ValueError, match="unsupported characters"):
        _support_pack(dependency_state="person@example.invalid").as_dict()


def test_support_evidence_requires_timezone_aware_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        _support_pack(observed_at="2026-08-25T19:30:00").as_dict()


def test_customer_error_payload_does_not_invent_success_retryability_or_root_cause():
    payload = customer_error_payload(
        CustomerFailureClass.UNKNOWN,
        correlation_id="req_20260825_abcd",
    )
    assert payload == {
        "error_class": "UNKNOWN",
        "correlation_id": "req_20260825_abcd",
    }
    assert "ok" not in payload
    assert "retryable" not in payload
    assert "root_cause" not in payload


def test_known_validation_failure_can_be_classified_without_guessing_conflict_or_unknown():
    assert customer_error_payload(
        CustomerFailureClass.INVALID_INPUT,
        correlation_id="req_20260825_abcd",
    )["error_class"] == "INVALID_INPUT"
