from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping

from .engine import CommitmentState, CostRecoveryMode, ExposureType, RecoveryCase
from .evidence import ExtractedFact, FactType, ReviewState, normalize_confirmed_facts
from .state import AssistedCaseState


_REQUIRED_SINGLETON_FACTS = (
    FactType.CUSTOMER_ID,
    FactType.PROGRAM_ID,
    FactType.PERIOD_ID,
    FactType.CURRENCY,
    FactType.UNIT,
    FactType.COMMITMENT_STATE,
    FactType.COMMITTED_UNITS,
    FactType.DEDICATED_COST,
    FactType.AMORTIZATION_BASIS_UNITS,
    FactType.MITIGATION,
    FactType.PRIOR_PAYMENT,
)

_OPTIONAL_ENTITLEMENT_FACTS = (
    FactType.EXPLICIT_RECOVERY_RIGHT,
    FactType.NOTICE_VALID,
    FactType.DEADLINE,
)

_HUMAN_CONTROL_GATES = (
    "evidence_supported",
    "asset_dedicated",
    "already_fully_amortized",
    "already_paid",
    "exposure_type",
    "cost_recovery_mode",
    "customer_matches",
    "program_matches",
    "period_matches",
    "currency_matches",
    "unit_matches",
    "actuals_complete",
    "actuals_deduplicated",
    "cancelled_orders_excluded",
    "amortization_verified",
    "asset_dedication_verified",
    "mitigation_reviewed",
    "prior_recovery_reviewed",
    "notice_window_verified",
    "contract_matches",
    "contract_current",
    "amendment_reviewed",
    "amendment_matches",
    "duplicate_claim_reviewed",
    "duplicate_claim",
)


@dataclass(frozen=True)
class EvidenceCaseDraft:
    company_id: str
    case_inputs: Mapping[str, str]
    evidence_refs: tuple[str, ...]
    conflicts: tuple[str, ...]
    missing_required: tuple[str, ...]
    human_control_gates: tuple[str, ...] = _HUMAN_CONTROL_GATES

    @property
    def ready_for_human_case_creation(self) -> bool:
        return not self.conflicts and not self.missing_required


@dataclass(frozen=True)
class HumanCaseControls:
    evidence_supported: bool
    asset_dedicated: bool
    already_fully_amortized: bool
    already_paid: bool
    exposure_type: ExposureType
    cost_recovery_mode: CostRecoveryMode
    duplicate_claim: bool
    customer_matches: bool | None = None
    program_matches: bool | None = None
    period_matches: bool | None = None
    currency_matches: bool | None = None
    unit_matches: bool | None = None
    actuals_complete: bool | None = None
    actuals_deduplicated: bool | None = None
    cancelled_orders_excluded: bool | None = None
    amortization_verified: bool | None = None
    asset_dedication_verified: bool | None = None
    mitigation_reviewed: bool | None = None
    prior_recovery_reviewed: bool | None = None
    notice_window_verified: bool | None = None
    contract_matches: bool | None = None
    contract_current: bool | None = None
    amendment_reviewed: bool | None = None
    amendment_matches: bool | None = None
    duplicate_claim_reviewed: bool | None = None


def _required_company_id(company_id: str) -> str:
    if not isinstance(company_id, str) or not company_id.strip():
        raise ValueError("company_id is required")
    company_id = company_id.strip()
    if len(company_id) > 200:
        raise ValueError("company_id is too long")
    return company_id


def _source_tri_bool(values: Mapping[str, str], fact_type: FactType) -> bool | None:
    raw = values.get(fact_type.value)
    if raw in (None, "unknown"):
        return None
    if raw == "true":
        return True
    if raw == "false":
        return False
    raise ValueError(f"{fact_type.value} is not a canonical tri-state boolean")


def _source_decimal(values: Mapping[str, str], fact_type: FactType) -> Decimal:
    raw = values[fact_type.value]
    value = Decimal(raw)
    if not value.is_finite() or value < 0:
        raise ValueError(f"{fact_type.value} must be finite and non-negative")
    return value


def _validate_controls(controls: HumanCaseControls) -> None:
    required_bools = {
        "evidence_supported": controls.evidence_supported,
        "asset_dedicated": controls.asset_dedicated,
        "already_fully_amortized": controls.already_fully_amortized,
        "already_paid": controls.already_paid,
        "duplicate_claim": controls.duplicate_claim,
    }
    for name, value in required_bools.items():
        if type(value) is not bool:
            raise ValueError(f"{name} must be boolean")
    if not isinstance(controls.exposure_type, ExposureType):
        raise ValueError("exposure_type must be an ExposureType")
    if not isinstance(controls.cost_recovery_mode, CostRecoveryMode):
        raise ValueError("cost_recovery_mode must be a CostRecoveryMode")
    optional = {
        name: getattr(controls, name)
        for name in _HUMAN_CONTROL_GATES
        if name not in required_bools and name not in {"exposure_type", "cost_recovery_mode"}
    }
    for name, value in optional.items():
        if value is not None and type(value) is not bool:
            raise ValueError(f"{name} must be boolean or null")


def build_case_draft(company_id: str, facts: Iterable[ExtractedFact]) -> EvidenceCaseDraft:
    company_id = _required_company_id(company_id)
    normalized = normalize_confirmed_facts(facts)
    values = dict(normalized.singleton_values)
    missing = [
        fact_type.value
        for fact_type in _REQUIRED_SINGLETON_FACTS
        if fact_type.value not in values
    ]
    if FactType.CONTRACT_ID.value not in values and FactType.NOMINATION_ID.value not in values:
        missing.append("CONTRACT_ID_OR_NOMINATION_ID")
    if normalized.actual_units is None:
        missing.append(FactType.ACTUAL_UNITS.value)
    else:
        values[FactType.ACTUAL_UNITS.value] = format(normalized.actual_units, "f")

    return EvidenceCaseDraft(
        company_id=company_id,
        case_inputs=dict(sorted(values.items())),
        evidence_refs=normalized.evidence_refs,
        conflicts=normalized.conflicts,
        missing_required=tuple(sorted(missing)),
    )


def build_state_from_confirmed_evidence(
    *,
    tenant_id: str,
    company_id: str,
    case_id: str,
    facts: Iterable[ExtractedFact],
    controls: HumanCaseControls,
) -> AssistedCaseState:
    """Commit reviewed source facts into the deterministic engine input shape.

    Economic/identity values come only from CONFIRMED evidence. The immutable
    snapshot also freezes the exact reviewed fact IDs used to build it.
    """

    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("tenant_id is required")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id is required")
    _validate_controls(controls)
    facts = tuple(facts)
    draft = build_case_draft(company_id, facts)
    if not draft.ready_for_human_case_creation:
        problems = list(draft.conflicts) + [f"missing {item}" for item in draft.missing_required]
        raise ValueError("evidence case draft is not ready: " + "; ".join(problems))

    confirmed_fact_refs = tuple(sorted(fact.fact_id for fact in facts if fact.review_state is ReviewState.CONFIRMED))
    if len(set(confirmed_fact_refs)) != len(confirmed_fact_refs):
        raise ValueError("duplicate confirmed fact_id in case input")

    values = draft.case_inputs
    try:
        commitment_state = CommitmentState(values[FactType.COMMITMENT_STATE.value])
    except ValueError as exc:
        raise ValueError("confirmed COMMITMENT_STATE is invalid") from exc

    explicit_recovery_right = _source_tri_bool(values, FactType.EXPLICIT_RECOVERY_RIGHT)
    notice_valid = _source_tri_bool(values, FactType.NOTICE_VALID)
    deadline = values.get(FactType.DEADLINE.value)

    recovery_case = RecoveryCase(
        case_id=case_id.strip(),
        currency=values[FactType.CURRENCY.value],
        committed_units=_source_decimal(values, FactType.COMMITTED_UNITS),
        actual_units=_source_decimal(values, FactType.ACTUAL_UNITS),
        dedicated_cost=_source_decimal(values, FactType.DEDICATED_COST),
        amortization_basis_units=_source_decimal(values, FactType.AMORTIZATION_BASIS_UNITS),
        mitigation=_source_decimal(values, FactType.MITIGATION),
        prior_payment=_source_decimal(values, FactType.PRIOR_PAYMENT),
        commitment_state=commitment_state,
        explicit_recovery_right=explicit_recovery_right,
        evidence_supported=controls.evidence_supported,
        notice_valid=notice_valid,
        asset_dedicated=controls.asset_dedicated,
        already_fully_amortized=controls.already_fully_amortized,
        already_paid=controls.already_paid,
        exposure_type=controls.exposure_type,
        cost_recovery_mode=controls.cost_recovery_mode,
        customer_matches=controls.customer_matches,
        program_matches=controls.program_matches,
        period_matches=controls.period_matches,
        currency_matches=controls.currency_matches,
        unit_matches=controls.unit_matches,
        actuals_complete=controls.actuals_complete,
        actuals_deduplicated=controls.actuals_deduplicated,
        cancelled_orders_excluded=controls.cancelled_orders_excluded,
        amortization_verified=controls.amortization_verified,
        asset_dedication_verified=controls.asset_dedication_verified,
        mitigation_reviewed=controls.mitigation_reviewed,
        prior_recovery_reviewed=controls.prior_recovery_reviewed,
        notice_window_verified=controls.notice_window_verified,
        contract_matches=controls.contract_matches,
        contract_current=controls.contract_current,
        amendment_reviewed=controls.amendment_reviewed,
        amendment_matches=controls.amendment_matches,
        duplicate_claim_reviewed=controls.duplicate_claim_reviewed,
        duplicate_claim=controls.duplicate_claim,
    )

    missing_evidence = tuple(
        f"source_fact:{fact_type.value}"
        for fact_type in _OPTIONAL_ENTITLEMENT_FACTS
        if fact_type.value not in values
    )
    return AssistedCaseState(
        tenant_id=tenant_id.strip(),
        company_id=draft.company_id,
        customer_id=values[FactType.CUSTOMER_ID.value],
        program_id=values[FactType.PROGRAM_ID.value],
        period_id=values[FactType.PERIOD_ID.value],
        unit=values[FactType.UNIT.value],
        recovery_case=recovery_case,
        evidence_refs=draft.evidence_refs,
        fact_refs=confirmed_fact_refs,
        missing_evidence=missing_evidence,
        deadline=deadline,
        contract_id=values.get(FactType.CONTRACT_ID.value),
        nomination_id=values.get(FactType.NOMINATION_ID.value),
    )
