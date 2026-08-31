from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from vertical_apps.industrial_claims.change_capture import ChangeCaptureStore
from vertical_apps.industrial_claims.change_sheet_trust import ChangeSheetTrustError, ChangeSheetTrustService
from vertical_apps.industrial_claims.proof import ExternalAttestation
from vertical_apps.industrial_claims.proof_providers import ProofRequest
from vertical_apps.industrial_claims.service import IndustrialClaimsService


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
            provider_ref="provider-receipt-1",
            issued_at="2026-09-01T00:00:00+00:00",
            validation_ref="validation-material-1",
            details={"subject_ref": request.subject_ref, "purpose": request.purpose},
        )


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


def test_timestamp_receipt_tampering_is_detected_even_if_database_trigger_is_bypassed(tmp_path):
    database = tmp_path / "tamper.sqlite3"
    finding = _case(database)
    capture = ChangeCaptureStore(database)
    trust = ChangeSheetTrustService(
        database,
        capture_store=capture,
        qualified_timestamp_provider=VerifiedTimestampProvider(),
    )
    receipt = trust.attest_current(tenant_id="tenant-a", finding_id=finding)
    assert receipt["state"] == "VERIFIED"

    with sqlite3.connect(database) as conn:
        conn.execute("DROP TRIGGER causledger_change_sheet_attestations_no_update")
        conn.execute(
            "UPDATE causledger_change_sheet_attestations SET provider_ref='forged-provider-ref' WHERE attestation_id=?",
            (receipt["attestation_id"],),
        )

    with pytest.raises(ChangeSheetTrustError, match="receipt hash is invalid"):
        trust.status(tenant_id="tenant-a", finding_id=finding)
