from __future__ import annotations

from vertical_apps.industrial_claims.production_trust_runtime import (
    configured_production_trust_gate,
    reset_production_trust_runtime_for_tests,
)


REQUIRED = (
    "CERTACTUM_WORM_BUCKET",
    "AWS_REGION",
    "CERTACTUM_TSA_ENDPOINT",
    "CERTACTUM_TSA_PROVIDER_NAME",
    "CERTACTUM_TSA_CERT_PEM",
    "CERTACTUM_TSA_ROOT_CERTS_PEM",
    "CERTACTUM_EIDAS_TERRITORY",
    "CERTACTUM_EU_LOTL_SIGNER_CERTS_PEM",
)


def test_missing_external_configuration_keeps_runtime_gate_closed(monkeypatch):
    for name in REQUIRED:
        monkeypatch.delenv(name, raising=False)
    reset_production_trust_runtime_for_tests()
    assert configured_production_trust_gate() is None


def test_partial_external_configuration_never_builds_a_gate(monkeypatch):
    for name in REQUIRED:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CERTACTUM_WORM_BUCKET", "certactum-worm")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    reset_production_trust_runtime_for_tests()
    assert configured_production_trust_gate() is None
