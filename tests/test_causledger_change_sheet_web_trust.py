from __future__ import annotations

import hashlib
from datetime import date

from flask import Flask

from vertical_apps.industrial_claims.change_capture import ChangeCaptureStore
from vertical_apps.industrial_claims.change_capture_web import create_change_capture_blueprint
from vertical_apps.industrial_claims.change_sheet_trust import ChangeSheetTrustService
from vertical_apps.industrial_claims.proof import ExternalAttestation
from vertical_apps.industrial_claims.proof_providers import ProofProviderBundle, ProofRequest
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _case(database) -> str:
    result = IndustrialClaimsService(database).analyze(
        tenant_id="tenant-a",
        actor_id="analyst-a",
        customer_ref="oem-a",
        program_ref="program-a",
        event_ref="ECO-017",
        claim_family="NRE",
        commercial_basis_ref="po-1",
        cost_evidence_ref="ledger-1",
        gross_cost="10000",
        currency="EUR",
        commercial_basis_content="commercial basis",
        event_evidence_content="customer requested engineering change",
        cost_evidence_content="engineering cost record",
        notice_due=date(2026, 9, 30),
    )
    return result.finding.finding_id


class VerifiedTimestampProvider:
    kind = "QUALIFIED_TIMESTAMP"
    name = "qtsp-a"

    def attest(self, request: ProofRequest) -> ExternalAttestation:
        assert request.payload is not None
        assert hashlib.sha256(request.payload).hexdigest() == request.digest
        return ExternalAttestation(
            kind=self.kind,
            provider=self.name,
            state="VERIFIED",
            digest_algorithm=request.digest_algorithm,
            digest=request.digest,
            provider_ref=f"receipt:{request.digest[:12]}",
            issued_at="2026-09-01T00:00:00+00:00",
            validation_ref=f"validation:{request.digest[:12]}",
            details={"subject_ref": request.subject_ref, "purpose": request.purpose},
        )


class WrongDigestProvider(VerifiedTimestampProvider):
    name = "wrong-digest"

    def attest(self, request: ProofRequest) -> ExternalAttestation:
        item = super().attest(request)
        return ExternalAttestation(
            kind=item.kind,
            provider=item.provider,
            state=item.state,
            digest_algorithm=item.digest_algorithm,
            digest="e" * 64,
            provider_ref=item.provider_ref,
            issued_at=item.issued_at,
            validation_ref=item.validation_ref,
            details=item.details,
        )


class ConcurrentEditProvider(VerifiedTimestampProvider):
    name = "concurrent-edit-qtsp"

    def __init__(self, capture: ChangeCaptureStore, finding_id: str):
        self.capture = capture
        self.finding_id = finding_id
        self.attested_payload = None
        self.attested_digest = None

    def attest(self, request: ProofRequest) -> ExternalAttestation:
        self.attested_payload = request.payload
        self.attested_digest = request.digest
        self.capture.add_fact(
            tenant_id="tenant-a",
            finding_id=self.finding_id,
            actor_id="client-b",
            fact_type="OTHER_FACT",
            fact_text="Concurrent factual edit while the external timestamp request is in flight.",
            source_ref="concurrent-source",
        )
        return super().attest(request)


def _client(database, provider, *, capture=None):
    capture = capture or ChangeCaptureStore(database)
    trust = ChangeSheetTrustService(
        database,
        capture_store=capture,
        qualified_timestamp_provider=provider,
    )
    app = Flask(__name__)
    app.register_blueprint(
        create_change_capture_blueprint(
            store=capture,
            capture_identity=lambda: ("tenant-a", "client-a"),
            trust_service=trust,
        )
    )
    return app.test_client(), capture, trust


def test_download_with_unconfigured_provider_exports_sheet_but_never_claims_timestamp(tmp_path):
    database = tmp_path / "unconfigured-web.sqlite3"
    finding = _case(database)
    client, capture, _trust = _client(database, ProofProviderBundle.fail_closed().qualified_timestamp)

    response = client.get(f"/findings/{finding}/change-sheet")
    assert response.status_code == 200
    assert response.headers["X-VINDORUM-Timestamp-State"] == "UNAVAILABLE"
    assert response.headers["X-VINDORUM-Timestamp-Provider"] == "UNCONFIGURED"
    assert response.headers["X-VINDORUM-Transfer-Completion-Proven"] == "false"
    digest = response.headers["X-VINDORUM-Sheet-SHA256"]
    assert hashlib.sha256(response.data).hexdigest() == digest
    assert f"Snapshot SHA-256: {digest}" not in response.get_data(as_text=True)
    assert capture.status(tenant_id="tenant-a", finding_id=finding)["download_count"] == 1


def test_verified_provider_binds_http_export_to_exact_sheet_digest(tmp_path):
    database = tmp_path / "verified-web.sqlite3"
    finding = _case(database)
    client, _capture, _trust = _client(database, VerifiedTimestampProvider())

    response = client.get(f"/findings/{finding}/change-sheet")
    assert response.status_code == 200
    assert response.headers["X-VINDORUM-Timestamp-State"] == "VERIFIED"
    assert response.headers["X-VINDORUM-Timestamp-Provider"] == "qtsp-a"
    assert response.headers["X-VINDORUM-Timestamp-Attestation"].startswith("sheettsa_")
    assert response.headers["X-VINDORUM-Export-Receipt"].startswith("download_")
    assert hashlib.sha256(response.data).hexdigest() == response.headers["X-VINDORUM-Sheet-SHA256"]


def test_misbound_timestamp_fails_before_export_receipt_is_recorded(tmp_path):
    database = tmp_path / "misbound-web.sqlite3"
    finding = _case(database)
    client, capture, _trust = _client(database, WrongDigestProvider())

    response = client.get(f"/findings/{finding}/change-sheet")
    assert response.status_code == 422
    assert "digest does not match snapshot" in response.get_json()["message"]
    assert capture.status(tenant_id="tenant-a", finding_id=finding)["download_count"] == 0


def test_concurrent_fact_during_timestamp_cannot_rebind_export_to_newer_sheet(tmp_path):
    database = tmp_path / "concurrent-web.sqlite3"
    finding = _case(database)
    capture = ChangeCaptureStore(database)
    provider = ConcurrentEditProvider(capture, finding)
    client, _capture, trust = _client(database, provider, capture=capture)

    response = client.get(f"/findings/{finding}/change-sheet")
    assert response.status_code == 200
    exported_digest = response.headers["X-VINDORUM-Sheet-SHA256"]
    assert hashlib.sha256(response.data).hexdigest() == exported_digest
    assert provider.attested_digest == exported_digest
    assert provider.attested_payload == response.data

    current = trust.status(tenant_id="tenant-a", finding_id=finding)
    assert current["current_snapshot_sha256"] != exported_digest
    assert current["current_snapshot_externally_timestamped"] is False
    assert current["stale_attestation_exists_for_older_snapshot"] is True
