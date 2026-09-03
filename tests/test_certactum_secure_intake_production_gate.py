from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from vertical_apps.industrial_claims.production_trust_gate import (
    ControlReceipt,
    ProductionTrustGate,
    ProductionTrustGateError,
)
from vertical_apps.industrial_claims.secure_intake_web import _require_production_trust


NOW = datetime(2026, 9, 3, 16, 0, tzinfo=timezone.utc)


def _receipt(control: str) -> ControlReceipt:
    return ControlReceipt(
        control=control,
        verified=True,
        provider=f"{control}-provider",
        reference=f"{control}:verified",
        checked_at=NOW,
        valid_until=NOW + timedelta(minutes=10),
    )


def _gate() -> ProductionTrustGate:
    return ProductionTrustGate(
        worm_probe=lambda: _receipt("worm"),
        timestamp_probe=lambda: _receipt("timestamp"),
        clock=lambda: NOW,
    )


def test_development_mode_remains_synthetic_and_does_not_require_external_gate(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    _require_production_trust(production_trust_gate=None, verified_claims=None)


def test_provider_mode_without_external_gate_fails_closed(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.delenv("CERTACTUM_WORM_BUCKET", raising=False)
    with pytest.raises(ProductionTrustGateError, match="production trust gate is not configured"):
        _require_production_trust(production_trust_gate=None, verified_claims=lambda: {"aal": "aal2"})


def test_provider_mode_requires_aal2_even_with_verified_external_controls(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    with pytest.raises(ProductionTrustGateError, match="mfa_aal2_required"):
        _require_production_trust(production_trust_gate=_gate(), verified_claims=lambda: {"aal": "aal1"})


def test_provider_mode_opens_only_with_aal2_and_verified_external_controls(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    _require_production_trust(production_trust_gate=_gate(), verified_claims=lambda: {"aal": "aal2"})


def test_provider_mode_rejects_non_mapping_claims(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    with pytest.raises(ProductionTrustGateError, match="verified JWT claims are unavailable"):
        _require_production_trust(production_trust_gate=_gate(), verified_claims=lambda: None)
