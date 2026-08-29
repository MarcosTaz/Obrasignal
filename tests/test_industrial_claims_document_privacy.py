import sqlite3

from vertical_apps.industrial_claims.service import IndustrialClaimsService


def test_raw_document_content_is_hashed_but_not_persisted(tmp_path):
    database = tmp_path / "industrial.sqlite3"
    service = IndustrialClaimsService(database)
    secrets = {
        "commercial": "SECRET-COMMERCIAL-CONTENT-6a105d",
        "event": "SECRET-EVENT-CONTENT-f8bd32",
        "cost": "SECRET-COST-CONTENT-19c4ef",
    }

    result = service.analyze(
        tenant_id="alpha",
        actor_id="analyst",
        customer_ref="oem-privacy",
        program_ref="program-privacy",
        event_ref="event-privacy",
        claim_family="TOOLING",
        commercial_basis_ref="basis-privacy",
        cost_evidence_ref="cost-privacy",
        commercial_basis_content=secrets["commercial"],
        event_evidence_content=secrets["event"],
        cost_evidence_content=secrets["cost"],
        gross_cost="1000",
        notice_deadline_not_applicable=True,
    )

    assert result.finding.state == "READY_FOR_REVIEW"
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
