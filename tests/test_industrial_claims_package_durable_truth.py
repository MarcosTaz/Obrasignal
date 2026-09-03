from dataclasses import replace
from datetime import date

import pytest

from vertical_apps.industrial_claims.package import build_claim_package
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _case(service: IndustrialClaimsService):
    return service.analyze(
        tenant_id="alpha", actor_id="analyst", customer_ref="oem-1", program_ref="program-1", event_ref="package-durable",
        claim_family="TOOLING", commercial_basis_ref="basis-1", cost_evidence_ref="cost-1", gross_cost="10000",
        currency="EUR", commercial_basis_content="signed tooling agreement",
        event_evidence_content="documented cancellation event", cost_evidence_content="cost ledger supporting 10000 EUR",
        notice_deadline_not_applicable=True,
    )


def _labels():
    return {
        "customer_ref": "oem-1",
        "program_ref": "program-1",
        "event_ref": "package-durable",
        "as_of_date": date(2026, 8, 30),
    }


def test_package_rejects_in_memory_result_after_durable_lifecycle_advances(tmp_path):
    service = IndustrialClaimsService(tmp_path / "lifecycle.sqlite3")
    result = _case(service)
    assert build_claim_package(service, result, **_labels())["finding"]["state"] == "READY_FOR_REVIEW"

    service.review(
        tenant_id="alpha", finding_id=result.finding.finding_id, reviewer="reviewer",
        approved=True, reason="independent review completed",
    )

    with pytest.raises(ValueError, match="lifecycle state is stale relative to durable dossier"):
        build_claim_package(service, result, **_labels())


def test_package_rejects_tampered_in_memory_calculation_even_when_revision_is_current(tmp_path):
    service = IndustrialClaimsService(tmp_path / "calculation.sqlite3")
    result = _case(service)
    tampered = replace(result, calculation=replace(result.calculation, output_value="999999"))

    with pytest.raises(ValueError, match="durable calculation does not match result"):
        build_claim_package(service, tampered, **_labels())

    durable = build_claim_package(service, result, **_labels())
    assert durable["net_potential"] == "10000"
