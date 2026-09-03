from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from threading import Lock

from vertical_apps.industrial_claims.eidas_trusted_list_verifier import SignedEidasTrustedListVerifier
from vertical_apps.industrial_claims.production_trust_gate import ControlReceipt, ProductionTrustGate
from vertical_apps.industrial_claims.proof_providers import ProofRequest
from vertical_apps.industrial_claims.rfc3161_timestamp_provider import Rfc3161QualifiedTimestampProvider
from vertical_apps.industrial_claims.s3_worm_backend import S3ObjectLockBackend


_RUNTIME_LOCK = Lock()
_RUNTIME_GATE: ProductionTrustGate | None = None
_RUNTIME_CONFIG: tuple[str, ...] | None = None


def _env(name: str) -> str:
    return str(os.getenv(name) or "").strip()


def _config() -> tuple[str, ...]:
    return tuple(
        _env(name)
        for name in (
            "CERTACTUM_WORM_BUCKET",
            "AWS_REGION",
            "CERTACTUM_WORM_S3_ENDPOINT",
            "CERTACTUM_AWS_EXPECTED_BUCKET_OWNER",
            "CERTACTUM_TSA_ENDPOINT",
            "CERTACTUM_TSA_PROVIDER_NAME",
            "CERTACTUM_TSA_CERT_PEM",
            "CERTACTUM_TSA_ROOT_CERTS_PEM",
            "CERTACTUM_TSA_INTERMEDIATE_CERTS_PEM",
            "CERTACTUM_EIDAS_TERRITORY",
            "CERTACTUM_EU_LOTL_SIGNER_CERTS_PEM",
        )
    )


def _configured(values: tuple[str, ...]) -> bool:
    # Optional: S3-compatible endpoint, expected owner and TSA intermediates.
    # An empty endpoint preserves native AWS S3 behavior.
    required_indexes = (0, 1, 4, 5, 6, 7, 9, 10)
    return all(bool(values[index]) for index in required_indexes)


def _build_gate(values: tuple[str, ...]) -> ProductionTrustGate:
    (
        bucket,
        region,
        s3_endpoint,
        expected_owner,
        tsa_endpoint,
        tsa_name,
        tsa_cert_pem,
        tsa_roots_pem,
        tsa_intermediates_pem,
        territory,
        lotl_signers_pem,
    ) = values

    # Import lazily so development/synthetic execution does not need AWS credentials.
    import boto3

    s3_client_args: dict[str, str] = {"region_name": region}
    if s3_endpoint:
        s3_client_args["endpoint_url"] = s3_endpoint
    s3 = boto3.client("s3", **s3_client_args)
    worm_backend = S3ObjectLockBackend(
        client=s3,
        bucket=bucket,
        expected_bucket_owner=expected_owner or None,
    )
    qualification_verifier = SignedEidasTrustedListVerifier(
        territory=territory,
        lotl_signing_certificates_pem=(lotl_signers_pem.encode("utf-8"),),
    )
    timestamp_provider = Rfc3161QualifiedTimestampProvider(
        endpoint=tsa_endpoint,
        provider_name=tsa_name,
        tsa_certificate_pem=tsa_cert_pem.encode("utf-8"),
        root_certificates_pem=(tsa_roots_pem.encode("utf-8"),),
        intermediate_certificates_pem=(tsa_intermediates_pem.encode("utf-8"),) if tsa_intermediates_pem else (),
        qualification_verifier=qualification_verifier,
    )

    def worm_probe() -> ControlReceipt:
        checked = datetime.now(timezone.utc)
        worm_backend.verify_bucket_controls()
        reference_material = f"{bucket}\n{region}\n{s3_endpoint}\n{expected_owner}".encode("utf-8")
        return ControlReceipt(
            control="worm",
            verified=True,
            provider=worm_backend.name,
            reference="s3-object-lock-config:" + hashlib.sha256(reference_material).hexdigest(),
            checked_at=checked,
            valid_until=checked + timedelta(minutes=5),
        )

    def timestamp_probe() -> ControlReceipt:
        checked = datetime.now(timezone.utc)
        payload = b"Certactum production trust control probe v1"
        digest = hashlib.sha256(payload).hexdigest()
        attestation = timestamp_provider.attest(
            ProofRequest(
                tenant_id="certactum-system",
                subject_ref="production-trust-control",
                digest_algorithm="SHA-256",
                digest=digest,
                purpose="PRODUCTION_TRUST_CONTROL_PROBE",
                metadata={"contains_customer_data": False},
                payload=payload,
            )
        )
        details = dict(attestation.details or {})
        verified = (
            str(attestation.state or "").upper() == "VERIFIED"
            and details.get("qualified_trusted_list_gate_satisfied") is True
            and details.get("rfc3161_signature_and_chain_verified") is True
            and details.get("exact_payload_verified") is True
            and bool(attestation.provider_ref)
            and bool(attestation.validation_ref)
        )
        return ControlReceipt(
            control="timestamp",
            verified=verified,
            provider=timestamp_provider.name,
            reference=attestation.validation_ref if verified else None,
            checked_at=checked,
            valid_until=checked + timedelta(minutes=5),
        )

    return ProductionTrustGate(
        worm_probe=worm_probe,
        timestamp_probe=timestamp_probe,
        cache_ttl=timedelta(minutes=5),
    )


def configured_production_trust_gate() -> ProductionTrustGate | None:
    """Return a cached live gate only when every required external input exists.

    AWS credentials deliberately use boto3's standard production credential chain
    (workload role or protected environment variables); secrets are never accepted
    from request data and are never returned by this module. A protected custom
    endpoint may be supplied for S3-compatible Object Lock providers such as B2.
    """
    global _RUNTIME_GATE, _RUNTIME_CONFIG
    values = _config()
    if not _configured(values):
        return None
    if _RUNTIME_GATE is not None and _RUNTIME_CONFIG == values:
        return _RUNTIME_GATE
    with _RUNTIME_LOCK:
        if _RUNTIME_GATE is None or _RUNTIME_CONFIG != values:
            _RUNTIME_GATE = _build_gate(values)
            _RUNTIME_CONFIG = values
        return _RUNTIME_GATE


def reset_production_trust_runtime_for_tests() -> None:
    global _RUNTIME_GATE, _RUNTIME_CONFIG
    with _RUNTIME_LOCK:
        _RUNTIME_GATE = None
        _RUNTIME_CONFIG = None
