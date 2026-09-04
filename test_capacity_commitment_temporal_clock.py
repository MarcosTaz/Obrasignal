from datetime import date, datetime, timezone
from decimal import Decimal

from factories.capacity_commitment.state import AssistedCaseState
from factories.capacity_commitment.synthetic_cases import case
import factories.capacity_commitment.temporal as temporal


def _state():
    return AssistedCaseState(
        tenant_id="tenant-a",
        company_id="supplier-a",
        customer_id="oem-a",
        program_id="program-a",
        contract_id="lta-1",
        recovery_case=case("temporal-clock"),
        evidence_refs=("contract:1",),
        forecast_units=Decimal("110000"),
        deadline="2099-12-31",
    )


def test_default_temporal_assessment_uses_explicit_utc_clock(monkeypatch):
    observed = []

    class FakeDateTime:
        @classmethod
        def now(cls, tz=None):
            observed.append(tz)
            return datetime(2026, 8, 29, 23, 30, tzinfo=timezone.utc)

    monkeypatch.setattr(temporal, "datetime", FakeDateTime, raising=False)
    assessment = temporal.assess_temporal_state(_state())

    assert observed == [timezone.utc]
    assert assessment.assessment_date == date(2026, 8, 29)
