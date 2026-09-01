from __future__ import annotations

import json
import sqlite3
from datetime import date

from vertical_apps.industrial_claims.durable_proof import build_durable_claim_proof_pack
from vertical_apps.industrial_claims.proof_attestation_archive import ProofAttestationArchive
from vertical_apps.industrial_claims.proof_externalization_audit import ProofExternalizationAuditStore
from vertical_apps.industrial_claims.proof_externalization_integrity import verify_externalization_operation_integrity
from vertical_apps.industrial_claims.proof_externalization_operation import externalize_proof_with_audit
from vertical_apps.industrial_claims.proof_providers import ProofProviderBundle
from vertical_apps.industrial_claims.service import IndustrialClaimsService


GENERATED_AT = "2026-09-01T12:00:00+00:00"


def _case(database):
    service = IndustrialClaimsService(database)
    finding_id = service.analyze(
        tenant_id="tenant-a",
        actor_id="analyst-a",
        customer_ref="oem-a",
        program_ref="program-a",
        event_ref="ECO-INTEGRITY",
        claim_family="NRE",
        commercial_basis_ref="po-integrity",
        cost_evidence_ref="ledger-integrity",
        gross_cost="15000",
        currency="EUR",
        commercial_basis_content="signed change basis",
        event_evidence_content="documented customer change",
        cost_evidence_content="incremental engineering ledger",
        notice_due=date(2026, 9, 30),
    ).finding.finding_id
    pack = build_durable_claim_proof_pack(
        service,
        tenant_id="tenant-a",
        finding_id=finding_id,
        generated_at=GENERATED_AT,
    )
    target = pack["proof_manifest"]["attestation_target"]["sha256"]
    return service, finding_id, target


def _externalize(service, audit, archive, finding_id, target):
    return externalize_proof_with_audit(
        service,
        audit_store=audit,
        attestation_archive=archive,
        tenant_id="tenant-a",
        finding_id=finding_id,
        actor_id="operator-a",
        providers=ProofProviderBundle.fail_closed(),
        expected_target_sha256=target,
        generated_at=GENERATED_AT,
    )


def test_later_receipts_advance_subject_chain_without_invalidating_older_operation(tmp_path):
    database = tmp_path / "cross-integrity.sqlite3"
    service, finding_id, target = _case(database)
    audit = ProofExternalizationAuditStore(database)
    archive = ProofAttestationArchive(database)

    first = _externalize(service, audit, archive, finding_id, target)
    first_operation = first["externalization_operation"]
    first_id = first_operation["operation_id"]
    first_frozen_head = first_operation["attestation_archive_chain_head_sha256"]

    first_before = verify_externalization_operation_integrity(
        audit_store=audit,
        attestation_archive=archive,
        tenant_id="tenant-a",
        finding_id=finding_id,
        operation_id=first_id,
    )
    assert first_before["valid"] is True
    assert first_before["operation_archive_chain_head_sha256"] == first_frozen_head
    assert first_before["current_subject_archive_chain_head_sha256"] == first_frozen_head

    second = _externalize(service, audit, archive, finding_id, target)
    second_id = second["externalization_operation"]["operation_id"]
    assert second_id != first_id

    first_after = verify_externalization_operation_integrity(
        audit_store=audit,
        attestation_archive=archive,
        tenant_id="tenant-a",
        finding_id=finding_id,
        operation_id=first_id,
    )
    second_after = verify_externalization_operation_integrity(
        audit_store=audit,
        attestation_archive=archive,
        tenant_id="tenant-a",
        finding_id=finding_id,
        operation_id=second_id,
    )
    assert first_after["valid"] is True
    assert second_after["valid"] is True
    assert first_after["operation_archive_chain_head_sha256"] == first_frozen_head
    assert first_after["current_subject_archive_chain_head_sha256"] != first_frozen_head
    assert first_after["current_subject_archive_chain_head_sha256"] == second_after["operation_archive_chain_head_sha256"]
    assert first_after["later_subject_receipts_do_not_invalidate_operation_head"] is True


def test_cross_integrity_detects_archive_payload_tampering(tmp_path):
    database = tmp_path / "cross-tamper.sqlite3"
    service, finding_id, target = _case(database)
    audit = ProofExternalizationAuditStore(database)
    archive = ProofAttestationArchive(database)
    result = _externalize(service, audit, archive, finding_id, target)
    operation_id = result["externalization_operation"]["operation_id"]

    with sqlite3.connect(database) as conn:
        conn.execute("DROP TRIGGER causledger_external_attestation_no_update")
        row = conn.execute(
            """SELECT sequence,payload_json FROM causledger_external_attestation_receipts
               WHERE operation_id=? ORDER BY sequence LIMIT 1""",
            (operation_id,),
        ).fetchone()
        payload = json.loads(row[1])
        payload["details"]["fail_closed"] = False
        conn.execute(
            "UPDATE causledger_external_attestation_receipts SET payload_json=? WHERE sequence=?",
            (json.dumps(payload, sort_keys=True, separators=(",", ":")), row[0]),
        )
        conn.commit()

    checked = verify_externalization_operation_integrity(
        audit_store=audit,
        attestation_archive=archive,
        tenant_id="tenant-a",
        finding_id=finding_id,
        operation_id=operation_id,
    )
    assert checked["valid"] is False
    assert "ATTESTATION_ARCHIVE_CHAIN_INVALID" in checked["errors"]


def test_cross_integrity_rejects_operation_from_another_finding(tmp_path):
    database = tmp_path / "cross-scope.sqlite3"
    service, finding_id, target = _case(database)
    audit = ProofExternalizationAuditStore(database)
    archive = ProofAttestationArchive(database)
    result = _externalize(service, audit, archive, finding_id, target)
    operation_id = result["externalization_operation"]["operation_id"]

    other_id = service.analyze(
        tenant_id="tenant-a",
        actor_id="analyst-a",
        customer_ref="oem-b",
        program_ref="program-b",
        event_ref="ECO-OTHER",
        claim_family="NRE",
        commercial_basis_ref="po-other",
        cost_evidence_ref="ledger-other",
        gross_cost="9000",
        currency="EUR",
        commercial_basis_content="basis b",
        event_evidence_content="change b",
        cost_evidence_content="cost b",
        notice_due=date(2026, 9, 30),
    ).finding.finding_id

    try:
        verify_externalization_operation_integrity(
            audit_store=audit,
            attestation_archive=archive,
            tenant_id="tenant-a",
            finding_id=other_id,
            operation_id=operation_id,
        )
    except Exception as exc:
        assert "does not belong" in str(exc)
    else:
        raise AssertionError("cross-finding operation verification must be rejected")
