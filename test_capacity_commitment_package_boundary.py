from datetime import date

import pytest

from factories.capacity_commitment.engine import evaluate_recoverability
from factories.capacity_commitment.recovery_package import build_recovery_package
from factories.capacity_commitment.synthetic_cases import case


def test_positive_package_requires_persistable_evidence_reference():
    recovery_case = case("package-boundary-no-evidence")
    result = evaluate_recoverability(recovery_case)

    with pytest.raises(ValueError, match="evidence_supported requires"):
        build_recovery_package(
            recovery_case,
            result,
            evidence_refs=(),
            deadline="2099-12-31",
            assessment_date="2026-08-29",
        )


def test_verified_notice_window_requires_canonical_deadline_even_for_direct_package_call():
    recovery_case = case("package-boundary-no-deadline")
    result = evaluate_recoverability(recovery_case)

    with pytest.raises(ValueError, match="notice_window_verified requires"):
        build_recovery_package(
            recovery_case,
            result,
            evidence_refs=("contract:1",),
            assessment_date="2026-08-29",
        )


def test_package_rejects_fabricated_deadline_expiry_context():
    recovery_case = case("package-boundary-false-expiry")
    result = evaluate_recoverability(recovery_case)

    with pytest.raises(ValueError, match="deadline expiry context"):
        build_recovery_package(
            recovery_case,
            result,
            evidence_refs=("contract:1",),
            deadline="2099-12-31",
            assessment_date="2026-08-29",
            deadline_expired_by_date=True,
        )


def test_package_rejects_noncanonical_assessment_date():
    recovery_case = case("package-boundary-bad-date")
    result = evaluate_recoverability(recovery_case)

    with pytest.raises(ValueError, match="assessment_date"):
        build_recovery_package(
            recovery_case,
            result,
            evidence_refs=("contract:1",),
            deadline="2099-12-31",
            assessment_date="29/08/2026",
        )
