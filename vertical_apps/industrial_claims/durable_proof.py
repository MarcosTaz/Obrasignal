from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import Any, Sequence

from factory_cloud.assurance_kernel import EvidenceEnvelope
from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.change_chronology_reader import read_change_chronology
from vertical_apps.industrial_claims.intake_authorization import (
    BOUNDED_RAPID_SCAN_PURPOSE,
    IntakeAuthorizationError,
    recompute_intake_authorization_scope_sha256,
)
from vertical_apps.industrial_claims.outcome_authorization import (
    DOCUMENTED_FINAL_OUTCOME_PURPOSE,
    OutcomeAuthorizationError,
    recompute_outcome_authorization_scope_sha256,
)
from vertical_apps.industrial_claims.proof import (
    ExternalAttestation,
    build_proof_manifest,
    sha256_hex,
    verify_proof_manifest,
)
from vertical_apps.industrial_claims.proof_binding import validate_evidence_attestation_bindings
from vertical_apps.industrial_claims.proof_readiness import evaluate_proof_strength
from vertical_apps.industrial_claims.service import IndustrialClaimsService


_CASE_ROLE_BY_SOURCE_TYPE = {
    "commercial_basis": "commercial_basis",
    "industrial_commercial_event": "event",
    "cost_evidence": "cost",
}


def _json_list(value: object, *, label: str) -> list[Any]:
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError) as exc:
        raise AssuranceStoreError(f"{label} is invalid") from exc
    if not isinstance(parsed, list):
        raise AssuranceStoreError(f"{label} is invalid")
    return parsed


def _json_object(value: object, *, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError) as exc:
        raise AssuranceStoreError(f"{label} is invalid") from exc
    if not isinstance(parsed, dict):
        raise AssuranceStoreError(f"{label} is invalid")
    return parsed


def _true(value: object) -> bool:
    return value is True or str(value or "").strip().lower() == "true"


def _outcome_evidence_ids(detail: dict[str, Any], *, case_evidence_ids: set[str]) -> list[str]:
    raw_outcomes = detail.get("outcomes")
    if not isinstance(raw_outcomes, list):
        raise AssuranceStoreError("durable proof pack outcome lineage is invalid")
    result: list[str] = []
    seen: set[str] = set()
    for outcome in raw_outcomes:
        if not isinstance(outcome, dict):
            raise AssuranceStoreError("durable proof pack outcome lineage is invalid")
        evidence = outcome.get("evidence")
        if not isinstance(evidence, dict):
            raise AssuranceStoreError("durable proof pack outcome evidence lineage is invalid")
        evidence_id = str(evidence.get("evidence_id") or "").strip()
        if not evidence_id:
            raise AssuranceStoreError("durable proof pack outcome evidence identity is missing")
        if evidence_id in case_evidence_ids or evidence_id in seen:
            raise AssuranceStoreError("durable proof pack outcome evidence identity is duplicated")
        seen.add(evidence_id)
        result.append(evidence_id)
    return result


def _validate_resolution_audit(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    finding_id: str,
    case_evidence_ids: Sequence[str],
    outcome: dict[str, Any],
) -> None:
    outcome_id = str(outcome.get("outcome_id") or "").strip()
    evidence = outcome.get("evidence")
    if not outcome_id or not isinstance(evidence, dict):
        raise AssuranceStoreError("durable proof pack outcome audit binding is invalid")
    evidence_id = str(evidence.get("evidence_id") or "").strip()
    row = conn.execute(
        "SELECT * FROM recovery_outcomes WHERE tenant_id=? AND finding_id=? AND outcome_id=?",
        (tenant_id, finding_id, outcome_id),
    ).fetchone()
    if row is None:
        raise AssuranceStoreError("durable proof pack outcome row is missing")
    expected_row = (
        str(outcome.get("state") or ""),
        str(outcome.get("recovered_amount") or ""),
        str(outcome.get("currency") or ""),
        evidence_id,
    )
    actual_row = (
        str(row["state"]),
        str(row["recovered_amount"]),
        str(row["currency"]),
        str(row["evidence_ref"]),
    )
    if actual_row != expected_row:
        raise AssuranceStoreError("durable proof pack outcome row drift")

    expected_event_id = f"{tenant_id}:{outcome_id}:resolve"
    audit_rows = conn.execute(
        "SELECT * FROM audit_events WHERE tenant_id=? AND subject_ref=? AND event_type='finding_resolved'",
        (tenant_id, finding_id),
    ).fetchall()
    matching = [audit for audit in audit_rows if str(audit["event_id"]) == expected_event_id]
    if len(matching) != 1 or len(audit_rows) != 1:
        raise AssuranceStoreError("durable proof pack resolution audit lineage is missing or ambiguous")
    audit = matching[0]
    if not str(audit["actor_id"] or "").strip():
        raise AssuranceStoreError("durable proof pack resolution audit actor is missing")
    audit_evidence = [
        str(item)
        for item in _json_list(audit["evidence_refs_json"], label="resolution audit evidence lineage")
    ]
    expected_evidence = tuple(sorted(set(tuple(case_evidence_ids) + (evidence_id,))))
    if len(audit_evidence) != len(expected_evidence) or set(audit_evidence) != set(expected_evidence):
        raise AssuranceStoreError("durable proof pack resolution audit evidence binding mismatch")
    expected_payload_hash = sha256_hex({
        "state": str(row["state"]),
        "outcome_id": str(row["outcome_id"]),
        "recovered_amount": str(row["recovered_amount"]),
        "currency": str(row["currency"]),
        "evidence_ref": str(row["evidence_ref"]),
    })
    if str(audit["payload_hash"]) != expected_payload_hash:
        raise AssuranceStoreError("durable proof pack resolution audit payload binding mismatch")


def _validate_secure_case_registry_binding(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    envelope: EvidenceEnvelope,
) -> tuple[str, ...] | None:
    metadata = dict(envelope.metadata or {})
    raw_persisted = _true(metadata.get("raw_content_persisted"))
    direct_secure = str(metadata.get("capture_mode") or "").strip() == "DIRECT_SECURE_ORIGINAL_CAPTURE"
    if not raw_persisted and not direct_secure:
        return None
    if not raw_persisted or not direct_secure:
        raise AssuranceStoreError("durable proof pack secure case custody semantics are inconsistent")
    role = _CASE_ROLE_BY_SOURCE_TYPE.get(envelope.source_type)
    if role is None:
        raise AssuranceStoreError("durable proof pack secure case evidence source type is invalid")
    if str(metadata.get("intake_evidence_role") or "").strip().lower() != role:
        raise AssuranceStoreError("durable proof pack secure case intake role mismatch")
    if str(metadata.get("intake_purpose") or "").strip().upper() != BOUNDED_RAPID_SCAN_PURPOSE:
        raise AssuranceStoreError("durable proof pack secure case intake purpose mismatch")
    if str(metadata.get("immutability") or "").strip().upper() != "WORM_LOCKED":
        raise AssuranceStoreError("durable proof pack secure case immutability mismatch")
    if not _true(metadata.get("original_version_readback_verified")) or not _true(metadata.get("worm_lock_verified")):
        raise AssuranceStoreError("durable proof pack secure case immutable readback is not verified")
    if str(metadata.get("original_retention_mode") or "").strip().upper() != "COMPLIANCE":
        raise AssuranceStoreError("durable proof pack secure case retention mode mismatch")

    stored_scope_sha256 = str(metadata.get("intake_authorization_scope_sha256") or "").strip().lower()
    try:
        recomputed_scope_sha256 = recompute_intake_authorization_scope_sha256(
            metadata,
            tenant_id=tenant_id,
        )
    except IntakeAuthorizationError as exc:
        raise AssuranceStoreError("durable proof pack secure case authorization scope cannot be recomputed") from exc
    if recomputed_scope_sha256 != stored_scope_sha256:
        raise AssuranceStoreError("durable proof pack secure case authorization scope hash mismatch")
    raw_authorized_roles = metadata.get("intake_authorized_evidence_roles")
    if not isinstance(raw_authorized_roles, list):
        raise AssuranceStoreError("durable proof pack secure case authorized role scope is missing")
    authorized_roles = tuple(dict.fromkeys(str(item or "").strip().lower() for item in raw_authorized_roles))
    if role not in authorized_roles:
        raise AssuranceStoreError("durable proof pack secure case role is outside authorization scope")

    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='causledger_secure_capture_envelopes'"
    ).fetchone()
    if table is None:
        raise AssuranceStoreError("durable proof pack secure capture registry is missing")
    registry = conn.execute(
        "SELECT * FROM causledger_secure_capture_envelopes WHERE tenant_id=? AND evidence_id=? AND evidence_role=? AND source_ref=?",
        (tenant_id, envelope.evidence_id, role, envelope.source_ref),
    ).fetchone()
    if registry is None:
        raise AssuranceStoreError("durable proof pack secure case registry binding is missing")
    registry_metadata_json = str(registry["metadata_json"])
    if sha256_hex(registry_metadata_json.encode("utf-8")) != str(registry["metadata_sha256"]):
        raise AssuranceStoreError("durable proof pack secure case registry metadata hash mismatch")
    registry_metadata = _json_object(registry_metadata_json, label="secure case registry metadata")
    if registry_metadata != metadata:
        raise AssuranceStoreError("durable proof pack secure case registry metadata drift")
    if str(registry["source_type"]) != envelope.source_type:
        raise AssuranceStoreError("durable proof pack secure case registry source-type drift")
    if str(registry["content_hash"]).lower() != envelope.content_hash.lower():
        raise AssuranceStoreError("durable proof pack secure case registry digest drift")
    if str(registry["original_receipt_ref"]) != str(metadata.get("original_provider_receipt_ref") or ""):
        raise AssuranceStoreError("durable proof pack secure case original receipt drift")

    scope = (
        str(metadata.get("intake_authorization_id") or "").strip(),
        stored_scope_sha256,
        str(metadata.get("intake_case_ref") or "").strip(),
        str(metadata.get("intake_purpose") or "").strip().upper(),
        str(metadata.get("intake_authorized_at") or "").strip(),
        str(metadata.get("intake_authorization_expires_at") or "").strip(),
        str(metadata.get("intake_minimum_immutable_retention_until") or "").strip(),
        json.dumps(list(authorized_roles), separators=(",", ":")),
        str(metadata.get("intake_data_terms_state") or "").strip().upper(),
        str(metadata.get("intake_authorized_by_sha256") or "").strip().lower(),
        str(metadata.get("intake_transfer_channel_sha256") or "").strip().lower(),
        str(metadata.get("intake_max_bytes_per_evidence") or "").strip(),
    )
    if any(not value for value in scope):
        raise AssuranceStoreError("durable proof pack secure case authorization scope is incomplete")
    return scope


def _validate_secure_outcome_registry_binding(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    finding_id: str,
    envelope: EvidenceEnvelope,
) -> None:
    metadata = dict(envelope.metadata or {})
    raw_persisted = _true(metadata.get("raw_content_persisted"))
    direct_secure = str(metadata.get("capture_mode") or "").strip() == "DIRECT_SECURE_ORIGINAL_CAPTURE"
    if not raw_persisted and not direct_secure:
        return
    if not raw_persisted or not direct_secure:
        raise AssuranceStoreError("durable proof pack secure outcome custody semantics are inconsistent")
    if str(metadata.get("outcome_finding_id") or "").strip() != finding_id:
        raise AssuranceStoreError("durable proof pack secure outcome finding authorization mismatch")
    if str(metadata.get("outcome_purpose") or "").strip().upper() != DOCUMENTED_FINAL_OUTCOME_PURPOSE:
        raise AssuranceStoreError("durable proof pack secure outcome authorization purpose mismatch")
    if str(metadata.get("verification_state") or "").strip().upper() != "CONTENT_HASHED":
        raise AssuranceStoreError("durable proof pack secure outcome verification state mismatch")
    if str(metadata.get("immutability") or "").strip().upper() != "WORM_LOCKED":
        raise AssuranceStoreError("durable proof pack secure outcome immutability mismatch")
    if not _true(metadata.get("original_version_readback_verified")) or not _true(metadata.get("worm_lock_verified")):
        raise AssuranceStoreError("durable proof pack secure outcome immutable readback is not verified")
    if str(metadata.get("original_retention_mode") or "").strip().upper() != "COMPLIANCE":
        raise AssuranceStoreError("durable proof pack secure outcome retention mode mismatch")

    stored_scope_sha256 = str(metadata.get("outcome_authorization_scope_sha256") or "").strip().lower()
    try:
        recomputed_scope_sha256 = recompute_outcome_authorization_scope_sha256(
            metadata,
            tenant_id=tenant_id,
        )
    except OutcomeAuthorizationError as exc:
        raise AssuranceStoreError("durable proof pack secure outcome authorization scope cannot be recomputed") from exc
    if recomputed_scope_sha256 != stored_scope_sha256:
        raise AssuranceStoreError("durable proof pack secure outcome authorization scope hash mismatch")

    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='causledger_secure_outcome_envelopes'"
    ).fetchone()
    if table is None:
        raise AssuranceStoreError("durable proof pack secure outcome registry is missing")
    registry = conn.execute(
        "SELECT * FROM causledger_secure_outcome_envelopes WHERE tenant_id=? AND finding_id=? AND evidence_id=? AND source_ref=?",
        (tenant_id, finding_id, envelope.evidence_id, envelope.source_ref),
    ).fetchone()
    if registry is None:
        raise AssuranceStoreError("durable proof pack secure outcome registry binding is missing")
    registry_metadata_json = str(registry["metadata_json"])
    if sha256_hex(registry_metadata_json.encode("utf-8")) != str(registry["metadata_sha256"]):
        raise AssuranceStoreError("durable proof pack secure outcome registry metadata hash mismatch")
    registry_metadata = _json_object(
        registry_metadata_json,
        label="secure outcome registry metadata",
    )
    if registry_metadata != metadata:
        raise AssuranceStoreError("durable proof pack secure outcome registry metadata drift")
    if str(registry["content_hash"]).lower() != envelope.content_hash.lower():
        raise AssuranceStoreError("durable proof pack secure outcome registry digest drift")
    if str(registry["authorization_id"]) != str(metadata.get("outcome_authorization_id") or ""):
        raise AssuranceStoreError("durable proof pack secure outcome authorization id drift")
    if str(registry["authorization_scope_sha256"]).lower() != stored_scope_sha256:
        raise AssuranceStoreError("durable proof pack secure outcome authorization scope drift")
    if str(registry["original_receipt_ref"]) != str(metadata.get("original_provider_receipt_ref") or ""):
        raise AssuranceStoreError("durable proof pack secure outcome original receipt drift")


def build_durable_claim_proof_pack(
    service: IndustrialClaimsService,
    *,
    tenant_id: str,
    finding_id: str,
    as_of_date: date | None = None,
    attestations: Sequence[ExternalAttestation] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a Proof Pack exclusively from tenant-scoped durable case truth.

    Evidence and change chronology are reconstructed with SELECT-only reads. Proof
    generation never creates missing proof tables or requests external attestations.
    Missing proof therefore stays missing rather than being repaired by observation.
    Secure originals are re-bound to their append-only authorization registries and
    their authorization scope hashes are independently recomputed at Proof Pack time.
    """
    revision = service.revision_store.require_current(tenant_id=tenant_id, finding_id=finding_id)
    detail = service.read_model.get_finding(
        tenant_id=tenant_id,
        finding_id=finding_id,
        as_of_date=as_of_date,
    )
    if detail["revision"]["number"] != revision.revision or detail["revision"]["is_current"] is not True:
        raise AssuranceStoreError("durable proof pack revision truth is inconsistent")

    with sqlite3.connect(service.store.path) as conn:
        conn.row_factory = sqlite3.Row
        finding = conn.execute(
            "SELECT * FROM findings WHERE tenant_id=? AND finding_id=? AND finding_type='industrial_recovery_candidate'",
            (tenant_id, finding_id),
        ).fetchone()
        if finding is None:
            raise AssuranceStoreError("durable proof pack finding not found")
        evidence_ids = [str(item) for item in _json_list(finding["evidence_ids_json"], label="evidence lineage")]
        calculation_ids = [str(item) for item in _json_list(finding["calculation_ids_json"], label="calculation lineage")]
        if len(calculation_ids) != 1 or not evidence_ids:
            raise AssuranceStoreError("durable proof pack lineage cardinality is invalid")

        detail_evidence_ids = [str(item["evidence_id"]) for item in detail["evidence_index"]]
        if len(detail_evidence_ids) != len(evidence_ids) or set(detail_evidence_ids) != set(evidence_ids):
            raise AssuranceStoreError("durable proof pack evidence lineage does not match read model")
        outcome_evidence_ids = _outcome_evidence_ids(
            detail,
            case_evidence_ids=set(evidence_ids),
        )
        for outcome in detail.get("outcomes") or []:
            _validate_resolution_audit(
                conn,
                tenant_id=tenant_id,
                finding_id=finding_id,
                case_evidence_ids=evidence_ids,
                outcome=outcome,
            )

        calculation = conn.execute(
            "SELECT * FROM calculations WHERE tenant_id=? AND calculation_id=?",
            (tenant_id, calculation_ids[0]),
        ).fetchone()
        if calculation is None:
            raise AssuranceStoreError("durable proof pack calculation not found")
        calculation_inputs = _json_list(calculation["inputs_json"], label="calculation inputs")

        envelopes: list[EvidenceEnvelope] = []
        evidence_index: list[dict[str, Any]] = []
        secure_case_scopes: list[tuple[str, ...]] = []
        for evidence_id in evidence_ids:
            row = conn.execute(
                "SELECT * FROM evidence WHERE tenant_id=? AND evidence_id=?",
                (tenant_id, evidence_id),
            ).fetchone()
            if row is None:
                raise AssuranceStoreError("durable proof pack evidence not found")
            try:
                metadata = json.loads(str(row["metadata_json"]))
            except (TypeError, ValueError) as exc:
                raise AssuranceStoreError("durable proof pack evidence metadata is invalid") from exc
            if not isinstance(metadata, dict):
                raise AssuranceStoreError("durable proof pack evidence metadata is invalid")
            envelope = EvidenceEnvelope(
                evidence_id=str(row["evidence_id"]),
                tenant_id=str(row["tenant_id"]),
                source_type=str(row["source_type"]),
                source_ref=str(row["source_ref"]),
                received_at=str(row["received_at"]),
                content_hash=str(row["content_hash"]),
                metadata=metadata,
            )
            secure_scope = _validate_secure_case_registry_binding(
                conn,
                tenant_id=tenant_id,
                envelope=envelope,
            )
            if secure_scope is not None:
                secure_case_scopes.append(secure_scope)
            envelopes.append(envelope)
            evidence_index.append({
                "evidence_id": envelope.evidence_id,
                "source_type": envelope.source_type,
                "source_ref": envelope.source_ref,
                "received_at": envelope.received_at,
                "content_hash": envelope.content_hash,
                "content_sha512": metadata.get("content_sha512"),
                "verification_state": metadata.get("verification_state", "UNKNOWN"),
                "source_authentication": metadata.get("source_authentication", "UNVERIFIED"),
                "time_attestation": metadata.get("time_attestation", "LOCAL_SERVER_ONLY"),
                "immutability": metadata.get("immutability", "NOT_PROVEN"),
                "raw_content_persisted": metadata.get("raw_content_persisted", "unknown"),
            })
        if secure_case_scopes:
            if len(secure_case_scopes) != len(evidence_ids):
                raise AssuranceStoreError("durable proof pack mixes secure and non-secure case evidence custody")
            if any(scope != secure_case_scopes[0] for scope in secure_case_scopes[1:]):
                raise AssuranceStoreError("durable proof pack secure case evidence authorization scope diverged")

        for evidence_id in outcome_evidence_ids:
            row = conn.execute(
                "SELECT * FROM evidence WHERE tenant_id=? AND evidence_id=?",
                (tenant_id, evidence_id),
            ).fetchone()
            if row is None or str(row["source_type"]) != "recovery_outcome_evidence":
                raise AssuranceStoreError("durable proof pack outcome evidence not found")
            try:
                metadata = json.loads(str(row["metadata_json"]))
            except (TypeError, ValueError) as exc:
                raise AssuranceStoreError("durable proof pack outcome evidence metadata is invalid") from exc
            if not isinstance(metadata, dict):
                raise AssuranceStoreError("durable proof pack outcome evidence metadata is invalid")
            envelope = EvidenceEnvelope(
                evidence_id=str(row["evidence_id"]),
                tenant_id=str(row["tenant_id"]),
                source_type=str(row["source_type"]),
                source_ref=str(row["source_ref"]),
                received_at=str(row["received_at"]),
                content_hash=str(row["content_hash"]),
                metadata=metadata,
            )
            outcome_record = next(
                (
                    item
                    for item in detail["outcomes"]
                    if str((item.get("evidence") or {}).get("evidence_id") or "") == evidence_id
                ),
                None,
            )
            if outcome_record is None:
                raise AssuranceStoreError("durable proof pack outcome evidence is not bound to an outcome")
            expected_hash = str((outcome_record.get("evidence") or {}).get("content_hash") or "").strip().lower()
            if not expected_hash or envelope.content_hash.lower() != expected_hash:
                raise AssuranceStoreError("durable proof pack outcome evidence digest drift")
            _validate_secure_outcome_registry_binding(
                conn,
                tenant_id=tenant_id,
                finding_id=finding_id,
                envelope=envelope,
            )
            envelopes.append(envelope)

    validate_evidence_attestation_bindings(tuple(envelopes), tuple(attestations))
    change_chronology = read_change_chronology(
        service.store.path,
        tenant_id=tenant_id,
        finding_id=finding_id,
    )
    core_package = {
        "schema_version": 2,
        "deliverable": "CAUSLEDGER_DURABLE_PROOF_CORE",
        "vertical": "industrial-claims",
        "tenant_id": tenant_id,
        "case": detail["case"],
        "revision": detail["revision"],
        "finding": {
            "finding_id": finding_id,
            "state": detail["finding"]["state"],
            "reviewer": detail["finding"]["reviewer"],
            "decision_reason": detail["finding"]["decision_reason"],
        },
        "calculation": {
            **detail["calculation"],
            "inputs": calculation_inputs,
            "calculation_id": str(calculation["calculation_id"]),
        },
        "entitlement": detail["entitlement"],
        "notice": detail["notice"],
        "evidence_index": evidence_index,
        "change_chronology": change_chronology,
        "outcomes": detail["outcomes"],
        "audit_events": detail["audit_events"],
        "truth_boundaries": {
            "raw_document_content_included": False,
            "customer_action_authorized": False,
            "external_claim_submission_authorized": False,
            "recoverability_established": False,
            "legal_conclusion": None,
            "change_capture_is_evidence_preservation_not_entitlement": True,
            "proof_pack_generation_is_read_only": True,
            "secure_case_registry_binding_enforced_when_declared_secure": True,
            "secure_authorization_scope_recomputed_from_persisted_metadata": True,
            "final_outcome_evidence_in_manifest_when_present": True,
            "final_outcome_bound_to_resolution_audit": True,
            "secure_outcome_bound_to_authorization_registry": True,
        },
    }
    manifest = build_proof_manifest(
        core_package=core_package,
        evidence=tuple(envelopes),
        revision_number=revision.revision,
        supersedes_finding_id=revision.supersedes_finding_id,
        attestations=tuple(attestations),
        generated_at=generated_at,
    )
    verification = verify_proof_manifest(core_package, manifest)
    if not verification["valid"]:
        raise AssuranceStoreError("durable CausLedger Proof Pack failed self-verification")
    return {
        "proof_pack_schema_version": 3,
        "brand": "CausLedger",
        "core_package": core_package,
        "proof_manifest": manifest,
        "proof_strength": evaluate_proof_strength(manifest),
        "self_verification": verification,
        "external_verification_required": any(manifest["required_external_gates"].values()),
    }