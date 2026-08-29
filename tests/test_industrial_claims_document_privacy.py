import sqlite3

import pytest

from factory_cloud.assurance_kernel import AssuranceKernelError
from vertical_apps.industrial_claims.service import MAX_EVIDENCE_BYTES, IndustrialClaimsService


def _base(service):
    return dict(
        tenant_id="alpha",
        actor_id="analyst",
        customer_ref="oem-privacy",
        program_ref="program-privacy",
        event_ref="event-privacy",
        claim_family="TOOLING",
        commercial_basis_ref="basis-privacy",
        cost_evidence_ref="cost-privacy",
        currency="EUR",
        commercial_basis_content="signed commercial basis",
        event_evidence_content="documented commercial event",
        cost_evidence_content="documented cost evidence",
        gross_cost="1000",
        notice_deadline_not_applicable=True,
    )


def test_raw_document_content_is_hashed_but_not_persisted(tmp_path):
    database = tmp_path / "industrial.sqlite3"
    service = IndustrialClaimsService(database)
    secrets = {
        "commercial": "SECRET-COMMERCIAL-CONTENT-6a105d",
        "event": "SECRET-EVENT-CONTENT-f8bd32",
        "cost": "SECRET-COST-CONTENT-19c4ef",
    }
    payload = _base(service)
    payload.update(
        commercial_basis_content=secrets["commercial"],
        event_evidence_content=secrets["event"],
        cost_evidence_content=secrets["cost"],
    )

    result = service.analyze(**payload)

    assert result.finding.state == "READY_FOR_REVIEW"
    assert result.calculation.output_unit == "EUR"
    assert {item.metadata["verification_state"] for item in result.evidence} == {"CONTENT_HASHED"}
    assert {item.metadata["raw_content_persisted"] for item in result.evidence} == {"false"}

    with sqlite3.connect(database) as conn:
        evidence_rows = conn.execute(
            "SELECT source_ref,content_hash,metadata_json FROM evidence WHERE tenant_id=?",
            ("alpha",),
        ).fetchall()
    assert len(evidence_rows) == 3
    assert all(row[1] for row in evidence_rows)

    raw_database = database.read_bytes()
    for secret in secrets.values():
        assert secret.encode("utf-8") not in raw_database


def test_document_content_rejects_non_text_non_bytes_types(tmp_path):
    service = IndustrialClaimsService(tmp_path / "invalid-type.sqlite3")
    payload = _base(service)
    payload["commercial_basis_content"] = 7

    with pytest.raises(AssuranceKernelError, match="text or bytes"):
        service.analyze(**payload)

    assert service.index.count_fingerprints("alpha") == 0
    assert service.store.count("evidence", "alpha") == 0


def test_individual_document_content_is_bounded_before_persistence(tmp_path):
    service = IndustrialClaimsService(tmp_path / "oversized.sqlite3")
    payload = _base(service)
    payload["cost_evidence_content"] = "x" * (MAX_EVIDENCE_BYTES + 1)

    with pytest.raises(AssuranceKernelError, match="exceeds assisted intake limit"):
        service.analyze(**payload)

    assert service.index.count_fingerprints("alpha") == 0
    assert service.store.count("evidence", "alpha") == 0


def test_binary_document_content_is_supported_without_raw_persistence(tmp_path):
    database = tmp_path / "binary.sqlite3"
    service = IndustrialClaimsService(database)
    payload = _base(service)
    payload["commercial_basis_content"] = b"binary-commercial-evidence"

    result = service.analyze(**payload)

    assert result.finding.state == "READY_FOR_REVIEW"
    assert b"binary-commercial-evidence" not in database.read_bytes()
