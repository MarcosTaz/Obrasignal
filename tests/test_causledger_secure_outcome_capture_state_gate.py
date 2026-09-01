from __future__ import annotations

import base64

from auth_context import RequestIdentity
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalObjectReceipt
from vertical_apps.industrial_claims.service import IndustrialClaimsService
from vertical_apps.industrial_claims.web import create_app


class Store:
    name = "fake-compliance-worm"

    def __init__(self):
        self._stored: dict[tuple[str, str], bytes] = {}
        self.put_calls = 0

    def put_immutable(self, *, tenant_id, evidence_id, content, content_type, retention_until, legal_hold, metadata):
        self.put_calls += 1
        object_ref = f"{tenant_id}/{evidence_id}"
        version_ref = "v1"
        self._stored[(object_ref, version_ref)] = content
        digests = dual_digest(content)
        return OriginalObjectReceipt(
            provider=self.name,
            object_ref=object_ref,
            version_ref=version_ref,
            sha256=digests["sha256"],
            sha512=digests["sha512"],
            byte_length=digests["byte_length"],
            retention_mode="COMPLIANCE",
            retention_until=retention_until,
            legal_hold=False,
            provider_receipt_ref=f"receipt-{evidence_id}",
            metadata=dict(metadata),
        )

    def read_immutable_version(self, *, tenant_id, evidence_id, object_ref, version_ref):
        return self._stored[(object_ref, version_ref)]


def _operator_identity():
    return RequestIdentity(
        account_id="tenant-a",
        authenticated=True,
        subject="operator-a",
        claims={"sub": "operator-a", "roles": ["operator"]},
    )


def _authorization() -> dict:
    return {
        "authorization_id": "outcome-state-gate-auth",
        "authorized_by_ref": "controller@example.test",
        "authorized_at": "2026-09-01T00:00:00+00:00",
        "expires_at": "2026-09-03T00:00:00+00:00",
        "minimum_immutable_retention_until": "2027-09-03T00:00:00+00:00",
        "transfer_channel_ref": "secure-outcome-channel",
        "data_terms_state": "SIGNED",
        "immutable_retention_acknowledged": True,
        "max_bytes": 1024,
    }


def _payload(evidence_id: str) -> dict:
    return {
        "authorization": _authorization(),
        "evidence_id": evidence_id,
        "source_ref": f"bank-{evidence_id}",
        "content_type": "application/pdf",
        "content_base64": base64.b64encode(b"synthetic settlement evidence").decode("ascii"),
    }


def test_outcome_capture_writes_only_for_current_actioned_finding(tmp_path):
    database = tmp_path / "secure-outcome-state-gate.sqlite3"
    service = IndustrialClaimsService(database)
    result = service.analyze(
        tenant_id="tenant-a",
        actor_id="analyst-a",
        customer_ref="oem-a",
        program_ref="program-a",
        event_ref="change-a",
        claim_family="NRE",
        commercial_basis_ref="po-a",
        cost_evidence_ref="ledger-a",
        gross_cost="10000",
        currency="EUR",
        commercial_basis_content="synthetic signed purchase order",
        event_evidence_content="synthetic customer change",
        cost_evidence_content="synthetic incremental cost ledger",
        notice_deadline_not_applicable=True,
    )
    finding_id = result.finding.finding_id
    store = Store()
    client = create_app(
        database,
        identity_resolver=_operator_identity,
        original_evidence_store=store,
    ).test_client()

    before_action = client.post(
        f"/findings/{finding_id}/secure-outcome-evidence/capture",
        json=_payload("tenant-a:outcome:before-action"),
    )
    assert before_action.status_code == 422
    assert "ACTIONED" in before_action.get_json()["message"]
    assert store.put_calls == 0

    assert service.review(
        tenant_id="tenant-a",
        finding_id=finding_id,
        reviewer="reviewer-b",
        approved=True,
        reason="synthetic review",
    ) == "APPROVED"
    assert service.action(tenant_id="tenant-a", finding_id=finding_id, actor_id="operator-a") == "ACTIONED"

    allowed = client.post(
        f"/findings/{finding_id}/secure-outcome-evidence/capture",
        json=_payload("tenant-a:outcome:allowed"),
    )
    assert allowed.status_code == 201
    assert store.put_calls == 1

    resolved = client.post(
        f"/findings/{finding_id}/secure-resolve",
        json={
            "outcome_id": "payment-1",
            "recovered_amount": "7500",
            "currency": "EUR",
            "evidence_id": "tenant-a:outcome:allowed",
            "evidence_ref": "bank-tenant-a:outcome:allowed",
            "final_cumulative": True,
        },
    )
    assert resolved.status_code == 201
    assert resolved.get_json()["state"] == "RECOVERED"

    after_close = client.post(
        f"/findings/{finding_id}/secure-outcome-evidence/capture",
        json=_payload("tenant-a:outcome:after-close"),
    )
    assert after_close.status_code == 422
    assert "ACTIONED" in after_close.get_json()["message"]
    assert store.put_calls == 1

    nonexistent = client.post(
        "/findings/tenant-a:not-a-real-finding/secure-outcome-evidence/capture",
        json=_payload("tenant-a:outcome:nonexistent"),
    )
    assert nonexistent.status_code == 422
    assert store.put_calls == 1
