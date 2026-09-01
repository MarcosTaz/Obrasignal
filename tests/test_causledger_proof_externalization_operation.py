from __future__ import annotations

import hashlib
from datetime import date

import pytest

from vertical_apps.industrial_claims.durable_proof import build_durable_claim_proof_pack
from vertical_apps.industrial_claims.proof import ExternalAttestation, sha256_hex
from vertical_apps.industrial_claims.proof_externalization import ProofExternalizationError
from vertical_apps.industrial_claims.proof_externalization_audit import ProofExternalizationAuditStore
from vertical_apps.industrial_claims.proof_externalization_operation import externalize_proof_with_audit
from vertical_apps.industrial_claims.proof_providers import ProofProviderBundle, ProofRequest, UnavailableProofProvider
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _case(database):
    service = IndustrialClaimsService(database)
    finding = service.analyze(
        tenant_id="tenant-a", actor_id="analyst-a", customer_ref="oem-a", program_ref="program-a",
        event_ref="ECO-017", claim_family="NRE", commercial_basis_ref="po-1", cost_evidence_ref="ledger-1",
        gross_cost="10000", currency="EUR", commercial_basis_content="basis",
        event_evidence_content="change", cost_evidence_content="cost", notice_due=date(2026, 9, 30),
    ).finding.finding_id
    return service, finding


class Provider:
    def __init__(self, kind, calls, *, wrong_digest=False):
        self.kind = kind
        self.name = f"provider-{kind.lower()}"
        self.calls = calls
        self.wrong_digest = wrong_digest

    def attest(self, request: ProofRequest):
        self.calls.append(self.kind)
        digest = "f" * 64 if self.wrong_digest else request.digest
        return ExternalAttestation(
            kind=self.kind, provider=self.name, state="VERIFIED" if not self.wrong_digest else "UNAVAILABLE",
            digest_algorithm="SHA-256", digest=digest,
            provider_ref=None if self.wrong_digest else f"receipt:{self.kind}",
            issued_at=None if self.wrong_digest else "2026-09-01T00:00:00+00:00",
            validation_ref=None if self.wrong_digest else f"validation:{self.kind}",
            details={"subject_ref": request.subject_ref, "purpose": request.purpose},
        )


def _bundle(calls, *, wrong_first=False):
    return ProofProviderBundle(
        qualified_timestamp=Provider("QUALIFIED_TIMESTAMP", calls, wrong_digest=wrong_first),
        qualified_seal=Provider("QUALIFIED_SEAL", calls),
        qualified_signature=Provider("QUALIFIED_SIGNATURE", calls),
        worm_lock=UnavailableProofProvider(kind="WORM_LOCK"),
        public_anchor=Provider("PUBLIC_ANCHOR", calls),
        evidence_escrow=UnavailableProofProvider(kind="EVIDENCE_ESCROW"),
    )


def _target(service, finding):
    pack = build_durable_claim_proof_pack(
        service, tenant_id="tenant-a", finding_id=finding, generated_at="2026-09-01T00:00:00+00:00"
    )
    return pack["proof_manifest"]["attestation_target"]["sha256"]


def test_successful_externalization_is_bracketed_by_started_and_completed_events(tmp_path):
    database = tmp_path / "success.sqlite3"
    service, finding = _case(database)
    audit = ProofExternalizationAuditStore(database)
    calls = []
    result = externalize_proof_with_audit(
        service, audit_store=audit, tenant_id="tenant-a", finding_id=finding, actor_id="operator-a",
        providers=_bundle(calls), expected_target_sha256=_target(service, finding),
        generated_at="2026-09-01T00:00:00+00:00",
    )
    operation = result["externalization_operation"]
    assert operation["proof_manifest_sha256"] == sha256_hex(result["proof_manifest"])
    assert operation["external_attestations_sha256"] == sha256_hex(result["proof_manifest"]["external_attestations"])
    status = audit.status(tenant_id="tenant-a", finding_id=finding)
    events = status["operations"][operation["operation_id"]]
    assert [event["state"] for event in events] == ["STARTED", "COMPLETED"]
    assert calls == ["QUALIFIED_TIMESTAMP", "QUALIFIED_SEAL", "QUALIFIED_SIGNATURE", "PUBLIC_ANCHOR"]


def test_misbound_provider_receipt_leaves_failed_terminal_event(tmp_path):
    database = tmp_path / "failed.sqlite3"
    service, finding = _case(database)
    audit = ProofExternalizationAuditStore(database)
    calls = []
    with pytest.raises(ProofExternalizationError, match="another digest"):
        externalize_proof_with_audit(
            service, audit_store=audit, tenant_id="tenant-a", finding_id=finding, actor_id="operator-a",
            providers=_bundle(calls, wrong_first=True), expected_target_sha256=_target(service, finding),
            generated_at="2026-09-01T00:00:00+00:00",
        )
    status = audit.status(tenant_id="tenant-a", finding_id=finding)
    assert status["event_count"] == 2
    events = next(iter(status["operations"].values()))
    assert [event["state"] for event in events] == ["STARTED", "FAILED"]
    assert events[-1]["payload"]["error_type"] == "ProofExternalizationError"
    assert calls == ["QUALIFIED_TIMESTAMP"]


def test_stale_reviewed_target_calls_no_provider_and_creates_no_operation_event(tmp_path):
    database = tmp_path / "stale.sqlite3"
    service, finding = _case(database)
    audit = ProofExternalizationAuditStore(database)
    calls = []
    with pytest.raises(ProofExternalizationError, match="stale"):
        externalize_proof_with_audit(
            service, audit_store=audit, tenant_id="tenant-a", finding_id=finding, actor_id="operator-a",
            providers=_bundle(calls), expected_target_sha256="f" * 64,
            generated_at="2026-09-01T00:00:00+00:00",
        )
    assert calls == []
    assert audit.status(tenant_id="tenant-a", finding_id=finding)["event_count"] == 0
