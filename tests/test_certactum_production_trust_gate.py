from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from vertical_apps.industrial_claims.production_trust_gate import (
    ControlReceipt,
    ProductionTrustGate,
    ProductionTrustGateError,
)


NOW = datetime(2026, 9, 3, 16, 0, tzinfo=timezone.utc)


def receipt(control: str, *, verified: bool = True, minutes: int = 10, provider: str | None = None):
    return ControlReceipt(
        control=control,
        verified=verified,
        provider=provider or f"{control}-provider",
        reference=f"{control}:receipt" if verified else None,
        checked_at=NOW,
        valid_until=NOW + timedelta(minutes=minutes),
    )


def gate(*, worm=None, timestamp=None):
    return ProductionTrustGate(
        worm_probe=worm or (lambda: receipt("worm")),
        timestamp_probe=timestamp or (lambda: receipt("timestamp")),
        cache_ttl=timedelta(minutes=5),
        clock=lambda: NOW,
    )


def test_all_three_controls_open_real_intake():
    decision = gate().require_ready(verified_claims={"aal": "aal2"})
    assert decision.ready is True
    assert decision.blockers == ()
    assert decision.as_dict()["real_confidential_intake_allowed"] is True
    assert decision.as_dict()["fail_closed"] is True


def test_aal1_blocks_even_when_external_controls_are_verified():
    with pytest.raises(ProductionTrustGateError, match="mfa_aal2_required"):
        gate().require_ready(verified_claims={"aal": "aal1"})


@pytest.mark.parametrize("failed_control", ["worm", "timestamp"])
def test_each_external_control_fails_closed_independently(failed_control):
    kwargs = {failed_control: lambda: receipt(failed_control, verified=False)}
    with pytest.raises(ProductionTrustGateError, match=f"{failed_control}_unverified"):
        gate(**kwargs).require_ready(verified_claims={"aal": "aal2"})


def test_provider_exception_fails_closed_without_exposing_exception_text():
    def broken():
        raise RuntimeError("SUPER-SECRET-CREDENTIAL")

    decision = gate(worm=broken).evaluate(verified_claims={"aal": "aal2"})
    assert decision.ready is False
    assert "worm_unverified" in decision.blockers
    serialized = str(decision.as_dict())
    assert "SUPER-SECRET-CREDENTIAL" not in serialized


def test_expired_receipt_blocks():
    def expired():
        return ControlReceipt(
            control="worm",
            verified=True,
            provider="worm-provider",
            reference="worm:old",
            checked_at=NOW - timedelta(minutes=20),
            valid_until=NOW - timedelta(minutes=1),
        )

    with pytest.raises(ProductionTrustGateError, match="worm_unverified"):
        gate(worm=expired).require_ready(verified_claims={"aal": "aal2"})


def test_probe_cannot_substitute_one_control_for_another():
    wrong = gate(worm=lambda: receipt("timestamp"))
    decision = wrong.evaluate(verified_claims={"aal": "aal2"})
    assert decision.ready is False
    assert "control_identity_invalid" in decision.blockers
    assert "worm_unverified" in decision.blockers
    assert "timestamp_unverified" in decision.blockers


def test_verified_receipt_requires_provider_reference():
    with pytest.raises(ValueError, match="provider reference"):
        ControlReceipt(
            control="worm",
            verified=True,
            provider="worm-provider",
            reference=None,
            checked_at=NOW,
            valid_until=NOW + timedelta(minutes=5),
        )


def test_fresh_verified_controls_are_cached_but_invalidate_forces_recheck():
    calls = {"worm": 0, "timestamp": 0}

    def worm():
        calls["worm"] += 1
        return receipt("worm")

    def timestamp():
        calls["timestamp"] += 1
        return receipt("timestamp")

    trust = gate(worm=worm, timestamp=timestamp)
    trust.require_ready(verified_claims={"aal": "aal2"})
    trust.require_ready(verified_claims={"aal": "aal2"})
    assert calls == {"worm": 1, "timestamp": 1}

    trust.invalidate()
    trust.require_ready(verified_claims={"aal": "aal2"})
    assert calls == {"worm": 2, "timestamp": 2}
