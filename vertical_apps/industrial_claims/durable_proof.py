from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import Any, Sequence

from factory_cloud.assurance_kernel import EvidenceEnvelope
from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.change_chronology_reader import read_change_chronology
from vertical_apps.industrial_claims.proof import ExternalAttestation, build_proof_manifest, verify_proof_manifest
from vertical_apps.industrial_claims.proof_binding import validate_evidence_attestation_bindings
from vertical_apps.industrial_claims.proof_readiness import evaluate_proof_strength
from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _json_list(value: object, *, label: str) -> list[Any]:
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError) as exc:
        raise AssuranceStoreError(f"{label} is invalid") from exc
    if not isinstance(parsed, list):
        raise AssuranceStoreError(f"{label} is invalid")
    return parsed


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

        calculation = conn.execute(
            "SELECT * FROM calculations WHERE tenant_id=? AND calculation_id=?",
            (tenant_id, calculation_ids[0]),
        ).fetchone()
        if calculation is None:
            raise AssuranceStoreError("durable proof pack calculation not found")
        calculation_inputs = _json_list(calculation["inputs_json"], label="calculation inputs")

        envelopes: list[EvidenceEnvelope] = []
        evidence_index: list[dict[str, Any]] = []
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