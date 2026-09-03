from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from vertical_apps.industrial_claims.change_capture import ChangeCaptureStore
from vertical_apps.industrial_claims.change_sheet_trust import ChangeSheetTrustError, ChangeSheetTrustService
from vertical_apps.industrial_claims.proof import ExternalAttestation
from vertical_apps.industrial_claims.proof_providers import ProofProviderBundle, ProofRequest
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _case(database) -> str:
    service = IndustrialClaimsService(database)
    result = service.analyze(
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
        return ExternalAttestation(
            kind=self.kind,
            provider=self.name,
            state="VERIFIED",
            digest_algorithm=request.digest_algorithm,
            digest=request.digest,
            provider_ref=f"qtsp-receipt:{request.digest[:16]}",
            issued_at="2026-09-01T00:00:00+00:00",
            validation_ref=f"validation:{request.digest[:16]}",
            details={
                "subject_ref": request.subject_ref,
                "purpose": request.purpose,
            },
        )


class WrongDigestTimestampProvider(VerifiedTimestampProvider):
    name = "malicious-or-broken-qtsp"

    def attest(self, request: ProofRequest) -> ExternalAttestation:
        return ExternalAttestation(
            kind=self.kind,
            provider=self.name,
            state="VERIFIED",
            digest_algorithm="SHA-256",
            digest="f" * 64,
            provider_ref="wrong-receipt",
            issued_at="2026-09-01T00:00:00+00:00",
            validation_ref="wrong-validation",
            details={"subject_ref": request.subject_ref, "purpose": request.purpose},
        )


def test_unconfigured_timestamp_provider_is_persisted_but_never_upgraded_to_verified(tmp_path):
    database = tmp_path / "unconfigured.sqlite3"
    finding = _case(database)
    capture = ChangeCaptureStore(database)
    trust = ChangeSheetTrustService(
        database,
        capture_store=capture,
        qualified_timestamp_provider=ProofProviderBundle.fail_closed().qualified_timestamp,
    )

    receipt = trust.attest_current(tenant_id="tenant-a", finding_id=finding)
    assert receipt["kind"] == "QUALIFIED_TIMESTAMP"
    assert receipt["state"] == "UNAVAILABLE"
    assert receipt["provider"] == "UNCONFIGURED"

    status = trust.status(tenant_id="tenant-a", finding_id=finding)
    assert status["current_snapshot_externally_timestamped"] is False
    assert status["qualified_timestamp_claim_is_fail_closed"] is True


def test_verified_timestamp_is_exact_snapshot_specific_and_new_fact_makes_old_one_stale(tmp_path):
    database = tmp_path / "digest-specific.sqlite3"
    finding = _case(database)
    capture = ChangeCaptureStore(database)
    trust = ChangeSheetTrustService(
        database,
        capture_store=capture,
        qualified_timestamp_provider=VerifiedTimestampProvider(),
    )

    first = trust.attest_current(tenant_id="tenant-a", finding_id=finding)
    before = trust.status(tenant_id="tenant-a", finding_id=finding)
    assert first["state"] == "VERIFIED"
    assert before["current_snapshot_externally_timestamped"] is True
    old_digest = before["current_snapshot_sha256"]

    capture.add_fact(
        tenant_id="tenant-a",
        finding_id=finding,
        actor_id="client-a",
        fact_type="REQUESTED_CHANGE",
        fact_text="Move the bracket hole pattern by 8 mm.",
        source_ref="customer-email-1",
    )
    changed = trust.status(tenant_id="tenant-a", finding_id=finding)
    assert changed["current_snapshot_sha256"] != old_digest
    assert changed["current_snapshot_externally_timestamped"] is False
    assert changed["stale_attestation_exists_for_older_snapshot"] is True
    assert changed["historical_attested_snapshot_count"] == 1

    second = trust.attest_current(tenant_id="tenant-a", finding_id=finding)
    assert second["state"] == "VERIFIED"
    assert second["sheet_sha256"] == changed["current_snapshot_sha256"]
    assert second["sheet_sha256"] != first["sheet_sha256"]
    assert trust.status(tenant_id="tenant-a", finding_id=finding)["current_snapshot_externally_timestamped"] is True


def test_verified_timestamp_with_wrong_digest_is_rejected_before_persistence(tmp_path):
    database = tmp_path / "wrong-digest.sqlite3"
    finding = _case(database)
    capture = ChangeCaptureStore(database)
    trust = ChangeSheetTrustService(
        database,
        capture_store=capture,
        qualified_timestamp_provider=WrongDigestTimestampProvider(),
    )

    with pytest.raises(ChangeSheetTrustError, match="digest does not match"):
        trust.attest_current(tenant_id="tenant-a", finding_id=finding)

    with sqlite3.connect(database) as conn:
        count = conn.execute("SELECT COUNT(*) FROM causledger_change_sheet_attestations").fetchone()[0]
    assert count == 0


def test_change_sheet_attestation_history_is_append_only(tmp_path):
    database = tmp_path / "append-only.sqlite3"
    finding = _case(database)
    capture = ChangeCaptureStore(database)
    trust = ChangeSheetTrustService(
        database,
        capture_store=capture,
        qualified_timestamp_provider=VerifiedTimestampProvider(),
    )
    receipt = trust.attest_current(tenant_id="tenant-a", finding_id=finding)

    with sqlite3.connect(database) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(
                "UPDATE causledger_change_sheet_attestations SET state='UNAVAILABLE' WHERE attestation_id=?",
                (receipt["attestation_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(
                "DELETE FROM causledger_change_sheet_attestations WHERE attestation_id=?",
                (receipt["attestation_id"],),
            )
