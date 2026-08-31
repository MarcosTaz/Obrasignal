from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import Any, Sequence

from factory_cloud.assurance_kernel import EvidenceEnvelope
from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.change_capture import ChangeCaptureError, ChangeCaptureStore
from vertical_apps.industrial_claims.change_sheet_trust import ChangeSheetTrustError, ChangeSheetTrustService
from vertical_apps.industrial_claims.change_supplement import ChangeSupplementError, LateChangeSupplementStore
from vertical_apps.industrial_claims.proof import ExternalAttestation, build_proof_manifest, verify_proof_manifest
from vertical_apps.industrial_claims.proof_binding import validate_evidence_attestation_bindings
from vertical_apps.industrial_claims.proof_providers import ProofProviderBundle
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


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def _durable_change_chronology(
    *,
    database: str,
    tenant_id: str,
    finding_id: str,
) -> dict[str, Any]:
    with sqlite3.connect(database) as conn:
        if not _table_exists(conn, "causledger_change_capture_windows"):
            return {
                "state": "NOT_CAPTURED",
                "change_capture_available": False,
                "absence_does_not_establish_no_change": True,
            }
        window = conn.execute(
            """SELECT sheet_id FROM causledger_change_capture_windows
               WHERE tenant_id=? AND finding_id=?""",
            (tenant_id, finding_id),
        ).fetchone()
        if window is None:
            return {
                "state": "NOT_CAPTURED",
                "change_capture_available": False,
                "absence_does_not_establish_no_change": True,
            }

    capture = ChangeCaptureStore(database)
    try:
        capture_status = capture.status(tenant_id=tenant_id, finding_id=finding_id)
        _sheet, current_digest = capture.render_sheet(tenant_id=tenant_id, finding_id=finding_id)
        trust = ChangeSheetTrustService(
            database,
            capture_store=capture,
            qualified_timestamp_provider=ProofProviderBundle.fail_closed().qualified_timestamp,
        ).status(tenant_id=tenant_id, finding_id=finding_id)
        supplements = LateChangeSupplementStore(
            database,
            capture_store=capture,
        ).status(tenant_id=tenant_id, finding_id=finding_id)
    except (ChangeCaptureError, ChangeSheetTrustError, ChangeSupplementError) as exc:
        raise AssuranceStoreError("durable change chronology integrity verification failed") from exc

    return {
        "state": "CAPTURED",
        "change_capture_available": True,
        "sheet_id": capture_status["sheet_id"],
        "event_ref": capture_status["event_ref"],
        "requested_change": capture_status["requested_change"],
        "requested_change_source": capture_status["requested_change_source"],
        "declared_change_requested_at": capture_status["declared_change_requested_at"],
        "declared_change_requested_at_is_externally_verified": False,
        "causledger_first_recorded_at": capture_status["recorded_at"],
        "factual_window_closes_at": capture_status["factual_window_closes_at"],
        "factual_window_hours": capture_status["factual_window_hours"],
        "window_state_at_pack_generation": capture_status["window_state"],
        "fact_count": capture_status["fact_count"],
        "fact_chain_head_sha256": capture_status["fact_chain_head_sha256"],
        "current_sheet_sha256": current_digest,
        "export_generation_count": capture_status["download_count"],
        "current_snapshot_time_trust": trust,
        "late_supplements": supplements,
        "chronology_truth_boundaries": {
            "operational_capture_window_is_not_contractual_notice_deadline": True,
            "declared_event_time_is_not_backdated_server_time": True,
            "late_supplement_does_not_rewrite_contemporaneous_sheet": True,
            "change_capture_does_not_establish_customer_responsibility": True,
            "change_capture_does_not_establish_legal_recoverability": True,
        },
    }


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

    This route deliberately reconstructs evidence envelopes from persisted hashes,
    timestamps and metadata. It does not pretend that raw originals exist when
    the existing assisted intake intentionally persisted only their digests.
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
    change_chronology = _durable_change_chronology(
        database=str(service.store.path),
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