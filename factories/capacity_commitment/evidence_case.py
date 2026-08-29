from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .evidence import ExtractedFact, FactType, normalize_confirmed_facts


_REQUIRED_SINGLETON_FACTS = (
    FactType.CUSTOMER_ID,
    FactType.PROGRAM_ID,
    FactType.CONTRACT_ID,
    FactType.CURRENCY,
    FactType.UNIT,
    FactType.COMMITMENT_STATE,
    FactType.COMMITTED_UNITS,
    FactType.DEDICATED_COST,
    FactType.AMORTIZATION_BASIS_UNITS,
)

# These controls are deliberately not inferred from extraction. Even when a
# clause-level fact suggests a value, the operator must explicitly establish the
# integrity gate against the bounded case before recoverability can become positive.
_HUMAN_CONTROL_GATES = (
    "evidence_supported",
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


def _required_company_id(company_id: str) -> str:
    if not isinstance(company_id, str) or not company_id.strip():
        raise ValueError("company_id is required")
    company_id = company_id.strip()
    if len(company_id) > 200:
        raise ValueError("company_id is too long")
    return company_id


def build_case_draft(company_id: str, facts: Iterable[ExtractedFact]) -> EvidenceCaseDraft:
    """Produce a source-backed draft, never an entitlement decision.

    Only CONFIRMED facts participate. Conflicts and missing inputs remain visible.
    The result intentionally omits material engine review booleans; those must be
    supplied by a controlled human review before creating a real RecoveryCase.
    """

    company_id = _required_company_id(company_id)
    normalized = normalize_confirmed_facts(facts)
    values = dict(normalized.singleton_values)
    missing = [fact_type.value for fact_type in _REQUIRED_SINGLETON_FACTS if fact_type.value not in values]
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
