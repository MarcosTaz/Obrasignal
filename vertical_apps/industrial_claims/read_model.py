from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.case_store import IndustrialClaimsCaseStore


ALLOWED_FINDING_STATES = {
    "UNRESOLVED_EVIDENCE",
    "READY_FOR_REVIEW",
    "APPROVED",
    "REJECTED",
    "ACTIONED",
    "RECOVERED",
    "CLOSED_NO_RECOVERY",
}
EXPECTED_CASE_EVIDENCE_TYPES = {"commercial_basis", "industrial_commercial_event", "cost_evidence"}
MAX_TENANT_CHARS = 64
MAX_FINDING_ID_CHARS = 2_048


@dataclass(frozen=True)
class FindingQueueItem:
    finding_id: str
    state: str
    net_potential: str
    currency_unit: str | None
    creator_actor: str
    created_at: str
    reviewer: str | None
    decision_reason: str | None

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


class IndustrialClaimsReadModel:
    """Tenant-scoped bounded read model with fail-closed dossier lineage."""

    def __init__(self, database: str | Path):
        self.path = Path(database)
        self.case_store = IndustrialClaimsCaseStore(database)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _bounded_key(value: object, *, label: str, max_chars: int) -> str:
        text = str(value or "").strip()
        if not text:
            raise AssuranceStoreError(f"{label} is required")
        if len(text) > max_chars:
            raise AssuranceStoreError(f"{label} exceeds {max_chars} characters")
        return text

    @staticmethod
    def _json_list(value: str, *, error: str) -> tuple[str, ...]:
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise AssuranceStoreError(error) from exc
        if not isinstance(parsed, list):
            raise AssuranceStoreError(error)
        return tuple(str(item) for item in parsed)

    @staticmethod
    def _same_members(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
        return len(left) == len(right) and set(left) == set(right)

    @staticmethod
    def _notice_timing(*, truth_state: str, due_date_raw: object, as_of_date: date) -> dict[str, Any]:
        if truth_state == "UNKNOWN":
            return {
                "timing_state": "UNKNOWN",
                "as_of_date": as_of_date.isoformat(),
                "timing_establishes_recoverability": False,
                "expired_establishes_nonrecoverability": False,
                "expired_requires_human_exception_or_waiver_review": False,
            }
        if truth_state == "DECLARED_NONE_FOR_REVIEW":
            return {
                "timing_state": "NO_DEADLINE_DECLARED_FOR_REVIEW",
                "as_of_date": as_of_date.isoformat(),
                "timing_establishes_recoverability": False,
                "expired_establishes_nonrecoverability": False,
                "expired_requires_human_exception_or_waiver_review": False,
            }
        if truth_state != "DECLARED_DATE_FOR_REVIEW":
            raise AssuranceStoreError("industrial notice truth state is invalid")
        try:
            due_date = date.fromisoformat(str(due_date_raw))
        except (TypeError, ValueError) as exc:
            raise AssuranceStoreError("industrial notice due date is invalid") from exc
        if as_of_date < due_date:
            timing_state = "OPEN"
        elif as_of_date == due_date:
            timing_state = "DUE_TODAY"
        else:
            timing_state = "EXPIRED"
        return {
            "timing_state": timing_state,
            "as_of_date": as_of_date.isoformat(),
            "timing_establishes_recoverability": False,
            "expired_establishes_nonrecoverability": False,
            "expired_requires_human_exception_or_waiver_review": timing_state == "EXPIRED",
        }

    def list_findings(self, *, tenant_id: str, states: tuple[str, ...], limit: int = 100) -> tuple[FindingQueueItem, ...]:
        tenant = self._bounded_key(tenant_id, label="tenant_id", max_chars=MAX_TENANT_CHARS)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 100:
            raise AssuranceStoreError("finding queue limit must be an integer from 1 to 100")
        normalized_states = tuple(dict.fromkeys(str(state).strip().upper() for state in states if str(state).strip()))
        if not normalized_states:
            return ()
        if set(normalized_states) - ALLOWED_FINDING_STATES:
            raise AssuranceStoreError("unsupported finding queue state")

        placeholders = ",".join("?" for _ in normalized_states)
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT f.*,
                       (SELECT a.actor_id FROM audit_events a
                         WHERE a.tenant_id=f.tenant_id AND a.subject_ref=f.finding_id
                           AND a.event_type='industrial_finding_created'
                         ORDER BY a.occurred_at,a.event_id LIMIT 1) AS creator_actor,
                       (SELECT a.occurred_at FROM audit_events a
                         WHERE a.tenant_id=f.tenant_id AND a.subject_ref=f.finding_id
                           AND a.event_type='industrial_finding_created'
                         ORDER BY a.occurred_at,a.event_id LIMIT 1) AS created_at,
                       (SELECT COUNT(*) FROM audit_events a
                         WHERE a.tenant_id=f.tenant_id AND a.subject_ref=f.finding_id
                           AND a.event_type='industrial_finding_created') AS creation_audit_count
                    FROM findings f
                    WHERE f.tenant_id=? AND f.finding_type='industrial_recovery_candidate'
                      AND f.state IN ({placeholders})
                    ORDER BY created_at DESC, f.finding_id DESC LIMIT ?""",
                (tenant, *normalized_states, limit),
            ).fetchall()
            items: list[FindingQueueItem] = []
            for row in rows:
                if int(row["creation_audit_count"]) != 1:
                    raise AssuranceStoreError("industrial finding queue creation audit lineage is ambiguous")
                calculation_ids = self._json_list(row["calculation_ids_json"], error="finding queue calculation lineage is invalid")
                if len(calculation_ids) != 1:
                    raise AssuranceStoreError("industrial finding queue requires exactly one calculation")
                calculation = conn.execute(
                    "SELECT formula_id,output_value,output_unit FROM calculations WHERE tenant_id=? AND calculation_id=?",
                    (tenant, calculation_ids[0]),
                ).fetchone()
                if calculation is None or calculation["formula_id"] != "industrial_net_potential_claim":
                    raise AssuranceStoreError("industrial finding queue calculation not found")
                creator = str(row["creator_actor"] or "").strip()
                created_at = str(row["created_at"] or "").strip()
                if not creator or not created_at:
                    raise AssuranceStoreError("industrial finding queue creation audit is incomplete")
                items.append(FindingQueueItem(
                    finding_id=str(row["finding_id"]), state=str(row["state"]), net_potential=str(calculation["output_value"]),
                    currency_unit=str(calculation["output_unit"]) if calculation["output_unit"] is not None else None,
                    creator_actor=creator, created_at=created_at,
                    reviewer=str(row["reviewer"]) if row["reviewer"] is not None else None,
                    decision_reason=str(row["decision_reason"]) if row["decision_reason"] is not None else None,
                ))
        return tuple(items)

    def get_finding(self, *, tenant_id: str, finding_id: str, as_of_date: date | None = None) -> dict[str, Any]:
        tenant = self._bounded_key(tenant_id, label="tenant_id", max_chars=MAX_TENANT_CHARS)
        finding_key = self._bounded_key(finding_id, label="finding_id", max_chars=MAX_FINDING_ID_CHARS)
        as_of = as_of_date or date.today()
        if not isinstance(as_of, date):
            raise AssuranceStoreError("as_of_date must be a date")
        metadata = self.case_store.get(tenant_id=tenant, finding_id=finding_key)

        with self._connect() as conn:
            finding = conn.execute(
                "SELECT * FROM findings WHERE tenant_id=? AND finding_id=? AND finding_type='industrial_recovery_candidate'",
                (tenant, finding_key),
            ).fetchone()
            if finding is None:
                raise AssuranceStoreError("tenant-scoped industrial finding not found")
            calculation_ids = self._json_list(finding["calculation_ids_json"], error="finding calculation lineage is invalid")
            evidence_ids = self._json_list(finding["evidence_ids_json"], error="finding evidence lineage is invalid")
            if len(calculation_ids) != 1 or len(evidence_ids) != 3:
                raise AssuranceStoreError("industrial finding lineage cardinality is invalid")

            calculation = conn.execute("SELECT * FROM calculations WHERE tenant_id=? AND calculation_id=?", (tenant, calculation_ids[0])).fetchone()
            if calculation is None or calculation["formula_id"] != "industrial_net_potential_claim":
                raise AssuranceStoreError("industrial finding calculation not found")
            calculation_evidence = self._json_list(calculation["evidence_ids_json"], error="industrial calculation evidence lineage is invalid")
            if not calculation_evidence or not set(calculation_evidence).issubset(set(evidence_ids)):
                raise AssuranceStoreError("industrial calculation evidence lineage does not match finding")

            deadline = conn.execute("SELECT * FROM deadlines WHERE tenant_id=? AND deadline_id=?", (tenant, metadata.deadline_id)).fetchone()
            if deadline is None:
                raise AssuranceStoreError("industrial finding deadline lineage not found")
            deadline_evidence = self._json_list(deadline["basis_evidence_ids_json"], error="industrial deadline evidence lineage is invalid")
            if not deadline_evidence or not set(deadline_evidence).issubset(set(evidence_ids)):
                raise AssuranceStoreError("industrial deadline evidence lineage does not match finding")

            entitlement = conn.execute("SELECT * FROM entitlement_basis WHERE tenant_id=? AND entitlement_id=?", (tenant, metadata.entitlement_id)).fetchone()
            if entitlement is None:
                raise AssuranceStoreError("industrial entitlement lineage not found")
            entitlement_evidence = self._json_list(entitlement["source_evidence_ids_json"], error="industrial entitlement evidence lineage is invalid")
            if not self._same_members(entitlement_evidence, evidence_ids):
                raise AssuranceStoreError("industrial entitlement evidence lineage does not match finding")

            fingerprint = conn.execute(
                "SELECT vertical,event_ref FROM recovery_fingerprints WHERE tenant_id=? AND fingerprint=?",
                (tenant, metadata.recovery_fingerprint),
            ).fetchone()
            if fingerprint is None or fingerprint["vertical"] != "industrial-claims" or fingerprint["event_ref"] != metadata.event_ref:
                raise AssuranceStoreError("industrial recovery fingerprint lineage does not match case")

            creation_audits = conn.execute(
                """SELECT actor_id,occurred_at FROM audit_events
                   WHERE tenant_id=? AND subject_ref=? AND event_type='industrial_finding_created'""",
                (tenant, finding_key),
            ).fetchall()
            if len(creation_audits) != 1 or not str(creation_audits[0]["actor_id"] or "").strip():
                raise AssuranceStoreError("industrial finding creation audit lineage is invalid")

            evidence_index = []
            source_types: set[str] = set()
            for evidence_id in evidence_ids:
                row = conn.execute("SELECT * FROM evidence WHERE tenant_id=? AND evidence_id=?", (tenant, evidence_id)).fetchone()
                if row is None:
                    raise AssuranceStoreError("industrial finding evidence lineage not found")
                try:
                    evidence_metadata = json.loads(row["metadata_json"])
                except (TypeError, ValueError) as exc:
                    raise AssuranceStoreError("evidence metadata is invalid") from exc
                source_types.add(str(row["source_type"]))
                evidence_index.append({
                    "evidence_id": str(row["evidence_id"]), "source_type": str(row["source_type"]),
                    "source_ref": str(row["source_ref"]), "content_hash": str(row["content_hash"]),
                    "verification_state": str(evidence_metadata.get("verification_state", "UNKNOWN")),
                    "raw_content_persisted": evidence_metadata.get("raw_content_persisted", "unknown"),
                })
            if source_types != EXPECTED_CASE_EVIDENCE_TYPES:
                raise AssuranceStoreError("industrial finding evidence types do not match case contract")

            outcomes = []
            for row in conn.execute("SELECT * FROM recovery_outcomes WHERE tenant_id=? AND finding_id=? ORDER BY recorded_at,outcome_id", (tenant, finding_key)).fetchall():
                proof = conn.execute(
                    "SELECT source_type,source_ref,content_hash,metadata_json FROM evidence WHERE tenant_id=? AND evidence_id=?",
                    (tenant, row["evidence_ref"]),
                ).fetchone()
                if proof is None or proof["source_type"] != "recovery_outcome_evidence":
                    raise AssuranceStoreError("outcome evidence lineage not found")
                try:
                    proof_metadata = json.loads(proof["metadata_json"])
                except (TypeError, ValueError) as exc:
                    raise AssuranceStoreError("outcome evidence metadata is invalid") from exc
                if proof_metadata.get("verification_state") != "CONTENT_HASHED":
                    raise AssuranceStoreError("outcome evidence verification state is invalid")
                outcomes.append({
                    "outcome_id": str(row["outcome_id"]), "state": str(row["state"]),
                    "recovered_amount": str(row["recovered_amount"]), "currency": str(row["currency"]),
                    "recorded_at": str(row["recorded_at"]),
                    "evidence": {"evidence_id": str(row["evidence_ref"]), "source_ref": str(proof["source_ref"]), "content_hash": str(proof["content_hash"]), "verification_state": str(proof_metadata.get("verification_state", "UNKNOWN"))},
                })

            audits = [
                {"event_id": str(row["event_id"]), "actor_id": str(row["actor_id"]), "event_type": str(row["event_type"]), "occurred_at": str(row["occurred_at"]), "payload_hash": str(row["payload_hash"])}
                for row in conn.execute("SELECT * FROM audit_events WHERE tenant_id=? AND subject_ref=? ORDER BY occurred_at,event_id", (tenant, finding_key)).fetchall()
            ]

        due_date = str(deadline["due_date"]) if metadata.notice_deadline_state == "DECLARED_DATE_FOR_REVIEW" else None
        notice_timing = self._notice_timing(
            truth_state=metadata.notice_deadline_state,
            due_date_raw=deadline["due_date"],
            as_of_date=as_of,
        )
        return {
            "case": {
                "finding_id": metadata.finding_id, "claim_family": metadata.claim_family,
                "customer_ref": metadata.customer_ref, "program_ref": metadata.program_ref, "event_ref": metadata.event_ref,
                "notice_deadline_state": metadata.notice_deadline_state, "missing_evidence": list(metadata.missing_evidence),
                "recovery_fingerprint": metadata.recovery_fingerprint,
            },
            "finding": {"state": str(finding["state"]), "reviewer": finding["reviewer"], "decision_reason": finding["decision_reason"]},
            "calculation": {"formula_id": str(calculation["formula_id"]), "formula_version": str(calculation["formula_version"]), "net_potential": str(calculation["output_value"]), "currency": calculation["output_unit"], "reproducibility_hash": str(calculation["reproducibility_hash"])},
            "entitlement": {"rule_ref": str(entitlement["rule_ref"]), "confidence": str(entitlement["confidence"]), "basis_hash": str(entitlement["basis_hash"]), "recoverability_established": False},
            "notice": {"truth_state": metadata.notice_deadline_state, "due_date": due_date, **notice_timing},
            "evidence_index": evidence_index,
            "outcomes": outcomes,
            "audit_events": audits,
            "raw_document_content_included": False,
        }
