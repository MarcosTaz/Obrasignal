from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

from factory_cloud.assurance_kernel import (
    AssuranceKernelError,
    CalculationInput,
    CalculationRecord,
    DeadlineWindow,
    EvidenceEnvelope,
    FindingRecord,
    assert_same_tenant,
)
from factory_cloud.assurance_ops import AssuranceOperationError, AssuranceOperations
from factory_cloud.assurance_store import AssuranceStore, AssuranceStoreError
from factory_cloud.recovery_index import RecoveryIndex
from factory_cloud.recovery_primitives import EntitlementBasis, RecoveryFingerprint
from factory_cloud.shared_platform import AuditEvent, NotificationEvent, TenantContext, assert_tenant_context
from vertical_apps.industrial_claims.case_store import IndustrialCaseMetadata, IndustrialClaimsCaseStore


ALLOWED_CLAIM_FAMILIES = {
    "EXCESS_OBSOLETE_RAW_MATERIAL",
    "WIP",
    "FINISHED_GOODS",
    "TOOLING",
    "NRE",
    "DEDICATED_INVESTMENT",
    "SUPPLIER_COMMITMENT",
    "MITIGATION_COST",
    "OTHER_DOCUMENTED_PROGRAM_EXPOSURE",
}
NOTICE_DEADLINE_EVIDENCE = "notice_deadline_or_declared_none_for_review"
COMMERCIAL_BASIS_DOCUMENT = "commercial_basis_document"
EVENT_DOCUMENT = "event_document"
COST_DOCUMENT = "cost_document"
CLAIM_CURRENCY_EVIDENCE = "claim_currency"
OUTCOME_EVIDENCE_DOCUMENT = "outcome_evidence_document"
MAX_EVIDENCE_BYTES = 1_000_000
MAX_TENANT_CHARS = 64
MAX_REFERENCE_CHARS = 512
MAX_FINDING_ID_CHARS = 2_048
MAX_ACTOR_CHARS = 256
MAX_REASON_CHARS = 4_000
MAX_MISSING_EVIDENCE_ITEMS = 100
MAX_MISSING_EVIDENCE_CHARS = 128
MAX_AMOUNT_TEXT_CHARS = 128
MAX_AMOUNT_SIGNIFICANT_DIGITS = 50
MAX_AMOUNT_INTEGER_DIGITS = 36
MAX_AMOUNT_DECIMAL_PLACES = 18
MAX_AMOUNT_ABS_EXPONENT = 36
DECIMAL_WORKING_PRECISION = MAX_AMOUNT_SIGNIFICANT_DIGITS + 10
_TENANT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


@dataclass(frozen=True)
class IndustrialClaimResult:
    tenant_id: str
    claim_family: str
    evidence: tuple[EvidenceEnvelope, ...]
    entitlement: EntitlementBasis
    fingerprint: RecoveryFingerprint
    calculation: CalculationRecord
    deadline: DeadlineWindow
    notice_deadline_state: str
    finding: FindingRecord
    audit: AuditEvent
    notification: NotificationEvent
    missing_evidence: tuple[str, ...]
    is_new_recovery: bool


class IndustrialClaimsService:
    """Assisted supplier-side industrial claim reconstruction.

    Cost is never treated as money owed by itself. Documentary source content is
    hashed and raw content is not persisted. A reference without source content
    remains REFERENCE_ONLY and cannot make an entitlement review-ready.
    """

    vertical = "industrial-claims"

    def __init__(self, database: str | Path):
        self.store = AssuranceStore(database)
        self.index = RecoveryIndex(database)
        self.case_store = IndustrialClaimsCaseStore(database)
        self.ops = AssuranceOperations(self.store)

    @staticmethod
    def _id(tenant_id: str, local: str) -> str:
        return f"{tenant_id}:{local}"

    @staticmethod
    def _contract_ref(customer_ref: str, program_ref: str, commercial_basis_ref: str) -> str:
        return json.dumps([customer_ref, program_ref, commercial_basis_ref], ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _tenant_id(value: object) -> str:
        tenant = str(value or "").strip()
        if not _TENANT_RE.fullmatch(tenant):
            raise AssuranceKernelError("tenant_id must match the verified account-id contract")
        return tenant

    @staticmethod
    def _operation_tenant_id(value: object) -> str:
        tenant = str(value or "").strip()
        if not _TENANT_RE.fullmatch(tenant):
            raise AssuranceOperationError("tenant_id must match the verified account-id contract")
        return tenant

    @staticmethod
    def _bounded_text(value: object, *, label: str, max_chars: int) -> str:
        text = str(value or "").strip()
        if not text:
            raise AssuranceKernelError(f"{label} is required")
        if len(text) > max_chars:
            raise AssuranceKernelError(f"{label} exceeds {max_chars} characters")
        return text

    @staticmethod
    def _bounded_operation_text(value: object, *, label: str, max_chars: int) -> str:
        text = str(value or "").strip()
        if not text:
            raise AssuranceOperationError(f"{label} is required")
        if len(text) > max_chars:
            raise AssuranceOperationError(f"{label} exceeds {max_chars} characters")
        return text

    @classmethod
    def _bounded_missing_evidence(cls, value: tuple[str, ...]) -> set[str]:
        if isinstance(value, (str, bytes, bytearray)):
            raise AssuranceKernelError("missing_evidence must be a collection of evidence keys")
        items = tuple(value)
        if len(items) > MAX_MISSING_EVIDENCE_ITEMS:
            raise AssuranceKernelError(f"missing_evidence exceeds {MAX_MISSING_EVIDENCE_ITEMS} items")
        normalized: set[str] = set()
        for item in items:
            text = str(item).strip()
            if not text:
                continue
            if len(text) > MAX_MISSING_EVIDENCE_CHARS:
                raise AssuranceKernelError(f"missing evidence key exceeds {MAX_MISSING_EVIDENCE_CHARS} characters")
            normalized.add(text)
        return normalized

    @staticmethod
    def _decimal_within_capacity(value: Decimal) -> bool:
        _sign, digits, exponent = value.as_tuple()
        significant_digits = len(digits)
        decimal_places = max(-exponent, 0)
        integer_digits = 1 if value == 0 else max(len(digits) + exponent, 1)
        return (
            significant_digits <= MAX_AMOUNT_SIGNIFICANT_DIGITS
            and integer_digits <= MAX_AMOUNT_INTEGER_DIGITS
            and decimal_places <= MAX_AMOUNT_DECIMAL_PLACES
            and abs(exponent) <= MAX_AMOUNT_ABS_EXPONENT
        )

    @classmethod
    def _claim_amount(cls, value: object) -> Decimal:
        text = str(value).strip()
        if not text or len(text) > MAX_AMOUNT_TEXT_CHARS:
            raise AssuranceKernelError("industrial claim amount exceeds numeric input capacity")
        try:
            amount = Decimal(text)
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise AssuranceKernelError("industrial claim amounts must be decimals") from exc
        if not amount.is_finite():
            raise AssuranceKernelError("industrial claim amounts must be finite decimals")
        if not cls._decimal_within_capacity(amount):
            raise AssuranceKernelError("industrial claim amount exceeds numeric input capacity")
        return amount

    @classmethod
    def _operation_amount(cls, value: object, *, label: str) -> Decimal:
        text = str(value).strip()
        if not text or len(text) > MAX_AMOUNT_TEXT_CHARS:
            raise AssuranceOperationError(f"{label} exceeds numeric input capacity")
        try:
            amount = Decimal(text)
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise AssuranceOperationError(f"{label} must be decimal") from exc
        if not amount.is_finite():
            raise AssuranceOperationError(f"{label} must be a finite decimal")
        if not cls._decimal_within_capacity(amount):
            raise AssuranceOperationError(f"{label} exceeds numeric input capacity")
        return amount

    @staticmethod
    def _evidence_payload(
        content: bytes | bytearray | memoryview | str | None,
        *,
        source_ref: str,
        missing_key: str,
        missing: set[str],
    ) -> tuple[bytes | str, dict[str, str]]:
        if content is None:
            missing.add(missing_key)
            return f"REFERENCE_ONLY:{source_ref}", {"verification_state": "REFERENCE_ONLY"}
        if isinstance(content, str):
            if not content.strip():
                missing.add(missing_key)
                return f"REFERENCE_ONLY:{source_ref}", {"verification_state": "REFERENCE_ONLY"}
            size = len(content.encode("utf-8"))
        elif isinstance(content, (bytes, bytearray, memoryview)):
            content = bytes(content)
            if not content:
                missing.add(missing_key)
                return f"REFERENCE_ONLY:{source_ref}", {"verification_state": "REFERENCE_ONLY"}
            size = len(content)
        else:
            raise AssuranceKernelError("evidence content must be text or bytes")
        if size > MAX_EVIDENCE_BYTES:
            raise AssuranceKernelError("individual evidence content exceeds assisted intake limit")
        return content, {"verification_state": "CONTENT_HASHED", "raw_content_persisted": "false"}

    @staticmethod
    def _claim_currency(value: str) -> str:
        code = str(value or "").strip().upper()
        if not code:
            return ""
        if len(code) != 3 or not code.isalpha() or not code.isascii():
            raise AssuranceKernelError("claim currency must be a three-letter ASCII code")
        return code

    def _existing_finding(self, *, tenant_id: str, finding_id: str) -> FindingRecord:
        with sqlite3.connect(self.store.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM findings WHERE tenant_id=? AND finding_id=?", (tenant_id, finding_id)).fetchone()
        if row is None:
            raise AssuranceStoreError("registered recovery fingerprint has no persisted finding")
        try:
            evidence_ids = tuple(json.loads(row["evidence_ids_json"]))
            calculation_ids = tuple(json.loads(row["calculation_ids_json"]))
        except (TypeError, ValueError) as exc:
            raise AssuranceStoreError("persisted finding lineage is invalid") from exc
        return FindingRecord(
            finding_id=row["finding_id"], tenant_id=row["tenant_id"], finding_type=row["finding_type"], state=row["state"],
            evidence_ids=evidence_ids, calculation_ids=calculation_ids, reviewer=row["reviewer"], decision_reason=row["decision_reason"],
        )

    def _creator_actor(self, *, tenant_id: str, finding_id: str) -> str:
        with sqlite3.connect(self.store.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT actor_id FROM audit_events
                   WHERE tenant_id=? AND subject_ref=? AND event_type='industrial_finding_created'
                   ORDER BY occurred_at,event_id LIMIT 1""",
                (tenant_id, finding_id),
            ).fetchone()
        if row is None or not str(row["actor_id"]).strip():
            raise AssuranceOperationError("finding creation audit not found")
        return str(row["actor_id"])

    def _validate_replay_without_state_change(
        self,
        *,
        evidence: tuple[EvidenceEnvelope, ...],
        calculation: CalculationRecord,
        deadline: DeadlineWindow,
        finding: FindingRecord,
        audit: AuditEvent,
        notification: NotificationEvent,
    ) -> FindingRecord:
        for item in evidence:
            self.store.put_evidence(item)
        self.store.put_calculation(calculation)
        self.store.put_deadline(deadline)
        self.store.append_audit(audit)
        self.store.enqueue_notification(notification)
        existing = self._existing_finding(tenant_id=finding.tenant_id, finding_id=finding.finding_id)
        if existing.finding_type != finding.finding_type or existing.evidence_ids != finding.evidence_ids or existing.calculation_ids != finding.calculation_ids:
            raise AssuranceStoreError("duplicate finding lineage does not match persisted case")
        return existing

    def _reviewed_net_potential(self, *, tenant_id: str, finding_id: str) -> tuple[Decimal, str]:
        with sqlite3.connect(self.store.path) as conn:
            conn.row_factory = sqlite3.Row
            finding = conn.execute("SELECT calculation_ids_json FROM findings WHERE tenant_id=? AND finding_id=?", (tenant_id, finding_id)).fetchone()
            if finding is None:
                raise AssuranceOperationError("tenant-scoped finding not found")
            try:
                calculation_ids = json.loads(finding["calculation_ids_json"])
            except (TypeError, ValueError) as exc:
                raise AssuranceOperationError("finding calculation lineage is invalid") from exc
            if not isinstance(calculation_ids, list) or len(calculation_ids) != 1:
                raise AssuranceOperationError("industrial finding requires exactly one reviewed calculation")
            calculation = conn.execute("SELECT formula_id,output_value,output_unit FROM calculations WHERE tenant_id=? AND calculation_id=?", (tenant_id, str(calculation_ids[0]))).fetchone()
            if calculation is None or calculation["formula_id"] != "industrial_net_potential_claim":
                raise AssuranceOperationError("reviewed industrial net-potential calculation not found")
        maximum = self._operation_amount(calculation["output_value"], label="reviewed net potential")
        if maximum < 0:
            raise AssuranceOperationError("reviewed net potential cannot be negative")
        reviewed_currency = str(calculation["output_unit"] or "").strip().upper()
        if len(reviewed_currency) != 3 or not reviewed_currency.isalpha() or not reviewed_currency.isascii():
            raise AssuranceOperationError("reviewed claim currency is not verified")
        return maximum, reviewed_currency

    def analyze(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        customer_ref: str,
        program_ref: str,
        event_ref: str,
        claim_family: str,
        commercial_basis_ref: str,
        cost_evidence_ref: str,
        gross_cost: str,
        currency: str = "",
        commercial_basis_content: bytes | bytearray | memoryview | str | None = None,
        event_evidence_content: bytes | bytearray | memoryview | str | None = None,
        cost_evidence_content: bytes | bytearray | memoryview | str | None = None,
        avoided_cost: str = "0",
        resale_reuse: str = "0",
        third_party_recovery: str = "0",
        prior_payment: str = "0",
        other_mitigation: str = "0",
        notice_due: date | None = None,
        notice_deadline_not_applicable: bool = False,
        missing_evidence: tuple[str, ...] = (),
    ) -> IndustrialClaimResult:
        tenant = self._tenant_id(tenant_id)
        actor = self._bounded_text(actor_id, label="actor_id", max_chars=MAX_ACTOR_CHARS)
        customer = self._bounded_text(customer_ref, label="customer_ref", max_chars=MAX_REFERENCE_CHARS)
        program = self._bounded_text(program_ref, label="program_ref", max_chars=MAX_REFERENCE_CHARS)
        event_key = self._bounded_text(event_ref, label="event_ref", max_chars=MAX_REFERENCE_CHARS)
        basis_ref = self._bounded_text(commercial_basis_ref, label="commercial_basis_ref", max_chars=MAX_REFERENCE_CHARS)
        cost_ref = self._bounded_text(cost_evidence_ref, label="cost_evidence_ref", max_chars=MAX_REFERENCE_CHARS)
        context = TenantContext(tenant_id=tenant, actor_id=actor, roles=("analyst",))
        context.require_role("analyst")
        family = claim_family.strip().upper()
        if family not in ALLOWED_CLAIM_FAMILIES:
            raise AssuranceKernelError("unsupported industrial claim family")
        if not isinstance(notice_deadline_not_applicable, bool):
            raise AssuranceKernelError("notice_deadline_not_applicable must be boolean")
        if notice_due is not None and notice_deadline_not_applicable:
            raise AssuranceKernelError("notice due date and declared no-deadline state are mutually exclusive")

        effective_missing = self._bounded_missing_evidence(missing_evidence)
        currency_code = self._claim_currency(currency)
        if not currency_code:
            currency_code = "UNKNOWN"
            effective_missing.add(CLAIM_CURRENCY_EVIDENCE)
        if notice_due is not None:
            notice_deadline_state = "DECLARED_DATE_FOR_REVIEW"
        elif notice_deadline_not_applicable:
            notice_deadline_state = "DECLARED_NONE_FOR_REVIEW"
        else:
            notice_deadline_state = "UNKNOWN"
            effective_missing.add(NOTICE_DEADLINE_EVIDENCE)

        basis_content, basis_metadata = self._evidence_payload(commercial_basis_content, source_ref=basis_ref, missing_key=COMMERCIAL_BASIS_DOCUMENT, missing=effective_missing)
        event_content, event_metadata = self._evidence_payload(event_evidence_content, source_ref=event_key, missing_key=EVENT_DOCUMENT, missing=effective_missing)
        cost_content, cost_metadata = self._evidence_payload(cost_evidence_content, source_ref=cost_ref, missing_key=COST_DOCUMENT, missing=effective_missing)

        amounts = {
            "gross_cost": self._claim_amount(gross_cost),
            "avoided_cost": self._claim_amount(avoided_cost),
            "resale_reuse": self._claim_amount(resale_reuse),
            "third_party_recovery": self._claim_amount(third_party_recovery),
            "prior_payment": self._claim_amount(prior_payment),
            "other_mitigation": self._claim_amount(other_mitigation),
        }
        if any(value < 0 for value in amounts.values()):
            raise AssuranceKernelError("industrial claim amounts cannot be negative")
        with localcontext() as decimal_context:
            decimal_context.prec = DECIMAL_WORKING_PRECISION
            deductions = sum((value for key, value in amounts.items() if key != "gross_cost"), Decimal("0"))
            net_potential = amounts["gross_cost"] - deductions
        if net_potential < 0:
            raise AssuranceKernelError("mitigation/recovery cannot exceed gross cost without review")

        basis = EvidenceEnvelope.create(evidence_id=self._id(tenant, f"{basis_ref}:commercial-basis"), tenant_id=tenant, source_type="commercial_basis", source_ref=basis_ref, content=basis_content, metadata=basis_metadata)
        event = EvidenceEnvelope.create(evidence_id=self._id(tenant, f"{event_key}:event"), tenant_id=tenant, source_type="industrial_commercial_event", source_ref=event_key, content=event_content, metadata=event_metadata)
        cost = EvidenceEnvelope.create(evidence_id=self._id(tenant, f"{cost_ref}:cost"), tenant_id=tenant, source_type="cost_evidence", source_ref=cost_ref, content=cost_content, metadata=cost_metadata)
        evidence = (basis, event, cost)

        documentary_complete = not effective_missing
        entitlement = EntitlementBasis.create(
            entitlement_id=self._id(tenant, f"{event_key}:{family}:basis"),
            tenant_id=tenant,
            domain=self.vertical,
            source_evidence_ids=tuple(item.evidence_id for item in evidence),
            rule_ref="documented-commercial-basis-v3-pre-review",
            confidence="PARTIAL" if documentary_complete else "UNRESOLVED",
        )
        fingerprint = RecoveryFingerprint.create(
            tenant_id=tenant,
            vertical=self.vertical,
            contract_ref=self._contract_ref(customer, program, basis_ref),
            event_ref=event_key,
            remedy_type=family.lower(),
        )
        calculation = CalculationRecord.create(
            calculation_id=self._id(tenant, f"{event_key}:{family}:net-potential"), tenant_id=tenant,
            formula_id="industrial_net_potential_claim", formula_version="1",
            inputs=tuple(CalculationInput(name=name, value=str(value), unit=currency_code, evidence_ids=(cost.evidence_id, basis.evidence_id)) for name, value in amounts.items()),
            output_value=net_potential, output_unit=currency_code,
        )
        deadline = DeadlineWindow.create(deadline_id=self._id(tenant, f"{event_key}:{family}:notice"), tenant_id=tenant, due_date=notice_due or date.max, basis_evidence_ids=(basis.evidence_id, event.evidence_id))
        state = "READY_FOR_REVIEW" if documentary_complete and net_potential > 0 else "UNRESOLVED_EVIDENCE"
        finding = FindingRecord.create(finding_id=self._id(tenant, f"{event_key}:{family}:finding"), tenant_id=tenant, finding_type="industrial_recovery_candidate", evidence_ids=tuple(item.evidence_id for item in evidence), calculation_ids=(calculation.calculation_id,), state=state)
        assert_same_tenant(*evidence, calculation, deadline, finding)
        assert_tenant_context(context, *evidence, calculation, deadline, finding)
        audit = AuditEvent.create(
            event_id=self._id(tenant, f"{event_key}:{family}:audit"), context=context, event_type="industrial_finding_created",
            subject_ref=finding.finding_id, evidence_refs=finding.evidence_ids,
            payload={"claim_family": family, "documentary_complete": documentary_complete, "calculation_hash": calculation.reproducibility_hash, "entitlement_basis_hash": entitlement.basis_hash, "recovery_fingerprint": fingerprint.fingerprint, "currency": currency_code, "notice_deadline_state": notice_deadline_state, "evidence_states": {item.source_type: item.metadata.get("verification_state") for item in evidence}, "missing_evidence": sorted(effective_missing)},
        )
        notification = NotificationEvent.create(event_id=self._id(tenant, f"{event_key}:{family}:notification"), tenant_id=tenant, event_type="finding_ready" if state == "READY_FOR_REVIEW" else "finding_unresolved", subject_ref=finding.finding_id, payload={"vertical": self.vertical, "claim_family": family, "state": state, "currency": currency_code, "notice_deadline_state": notice_deadline_state})
        case_metadata = IndustrialCaseMetadata(
            finding_id=finding.finding_id,
            tenant_id=tenant,
            claim_family=family,
            customer_ref=customer,
            program_ref=program,
            event_ref=event_key,
            entitlement_id=entitlement.entitlement_id,
            deadline_id=deadline.deadline_id,
            recovery_fingerprint=fingerprint.fingerprint,
            notice_deadline_state=notice_deadline_state,
            missing_evidence=tuple(sorted(effective_missing)),
        )

        with self.store.transaction() as conn:
            is_new = self.index.persist_case_index(entitlement, fingerprint, connection=conn)
            self.case_store.put(case_metadata, connection=conn)
            if is_new:
                self.store.persist_case(evidence=evidence, calculation=calculation, deadline=deadline, finding=finding, audit=audit, notification=notification, connection=conn)
        if not is_new:
            finding = self._validate_replay_without_state_change(evidence=evidence, calculation=calculation, deadline=deadline, finding=finding, audit=audit, notification=notification)
        return IndustrialClaimResult(tenant_id=tenant, claim_family=family, evidence=evidence, entitlement=entitlement, fingerprint=fingerprint, calculation=calculation, deadline=deadline, notice_deadline_state=notice_deadline_state, finding=finding, audit=audit, notification=notification, missing_evidence=tuple(sorted(effective_missing)), is_new_recovery=is_new)

    def review(self, *, tenant_id: str, finding_id: str, reviewer: str, approved: bool, reason: str) -> str:
        tenant = self._operation_tenant_id(tenant_id)
        finding_key = self._bounded_operation_text(finding_id, label="finding_id", max_chars=MAX_FINDING_ID_CHARS)
        reviewer_id = self._bounded_operation_text(reviewer, label="reviewer", max_chars=MAX_ACTOR_CHARS)
        decision_reason = self._bounded_operation_text(reason, label="review reason", max_chars=MAX_REASON_CHARS)
        creator = self._creator_actor(tenant_id=tenant, finding_id=finding_key)
        if creator == reviewer_id:
            raise AssuranceOperationError("reviewer must be independent from finding creator")
        return self.ops.review(tenant_id=tenant, finding_id=finding_key, reviewer=reviewer_id, approved=approved, reason=decision_reason)

    def action(self, *, tenant_id: str, finding_id: str, actor_id: str) -> str:
        tenant = self._operation_tenant_id(tenant_id)
        finding_key = self._bounded_operation_text(finding_id, label="finding_id", max_chars=MAX_FINDING_ID_CHARS)
        actor = self._bounded_operation_text(actor_id, label="action actor", max_chars=MAX_ACTOR_CHARS)
        return self.ops.action(tenant_id=tenant, finding_id=finding_key, actor_id=actor)

    def resolve(
        self,
        *,
        tenant_id: str,
        finding_id: str,
        outcome_id: str,
        recovered_amount: str,
        currency: str,
        evidence_ref: str,
        evidence_content: bytes | bytearray | memoryview | str | None = None,
        actor_id: str,
    ):
        tenant = self._operation_tenant_id(tenant_id)
        finding_key = self._bounded_operation_text(finding_id, label="finding_id", max_chars=MAX_FINDING_ID_CHARS)
        outcome_key = self._bounded_operation_text(outcome_id, label="outcome_id", max_chars=MAX_REFERENCE_CHARS)
        scoped_outcome_id = self._id(tenant, outcome_key)
        evidence_reference = self._bounded_operation_text(evidence_ref, label="outcome evidence ref", max_chars=MAX_REFERENCE_CHARS)
        actor = self._bounded_operation_text(actor_id, label="resolution actor", max_chars=MAX_ACTOR_CHARS)
        amount = self._operation_amount(recovered_amount, label="recovered amount")
        recovery_currency = str(currency or "").strip().upper()
        if len(recovery_currency) != 3 or not recovery_currency.isalpha() or not recovery_currency.isascii():
            raise AssuranceOperationError("recovery currency must be a three-letter ASCII code")
        maximum, reviewed_currency = self._reviewed_net_potential(tenant_id=tenant, finding_id=finding_key)
        if recovery_currency != reviewed_currency:
            raise AssuranceOperationError("recovery currency does not match reviewed claim currency")
        if amount > maximum:
            raise AssuranceOperationError("recovered amount exceeds reviewed net potential; amend and re-review the finding")
        outcome_missing: set[str] = set()
        outcome_content, outcome_metadata = self._evidence_payload(evidence_content, source_ref=evidence_reference, missing_key=OUTCOME_EVIDENCE_DOCUMENT, missing=outcome_missing)
        if outcome_missing:
            raise AssuranceOperationError("documentary outcome evidence content is required")
        outcome_evidence = EvidenceEnvelope.create(
            evidence_id=self._id(tenant, f"{outcome_key}:outcome-evidence"), tenant_id=tenant,
            source_type="recovery_outcome_evidence", source_ref=evidence_reference, content=outcome_content, metadata=outcome_metadata,
        )
        with self.store.transaction() as conn:
            self.store._put_evidence(conn, outcome_evidence)
            return self.ops.resolve(
                tenant_id=tenant, finding_id=finding_key, outcome_id=scoped_outcome_id, recovered_amount=str(amount),
                currency=recovery_currency, evidence_ref=outcome_evidence.evidence_id, actor_id=actor, connection=conn,
            )
