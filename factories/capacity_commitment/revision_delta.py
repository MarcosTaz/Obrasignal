from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .service import _validate_revision_identity, process_state
from .state import AssistedCaseState


@dataclass(frozen=True)
class FieldDelta:
    field: str
    before: Any
    after: Any


@dataclass(frozen=True)
class RevisionDelta:
    parent_case_id: str
    child_case_id: str
    source_changes: tuple[FieldDelta, ...]
    evidence_added: tuple[str, ...]
    evidence_removed: tuple[str, ...]
    missing_evidence_added: tuple[str, ...]
    missing_evidence_resolved: tuple[str, ...]
    result_changes: tuple[FieldDelta, ...]
    reasons_added: tuple[str, ...]
    reasons_removed: tuple[str, ...]

    @property
    def finding_changed(self) -> bool:
        return bool(self.result_changes or self.reasons_added or self.reasons_removed)


def _value(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if hasattr(value, "value"):
        return value.value
    return value


def _delta(field: str, before, after) -> FieldDelta | None:
    before = _value(before)
    after = _value(after)
    if before == after:
        return None
    return FieldDelta(field=field, before=before, after=after)


def compare_revisions(parent: AssistedCaseState, child: AssistedCaseState) -> RevisionDelta:
    """Explain source and finding changes between immutable revisions.

    The function requires the same bounded identity and reprocesses each immutable
    state through the deterministic engine. It never accepts a display-only finding
    or caller-provided amount as authoritative.
    """

    _validate_revision_identity(parent, child)
    if parent.tenant_id != child.tenant_id:
        raise PermissionError("revision tenant mismatch")
    if parent.recovery_case.case_id == child.recovery_case.case_id:
        raise ValueError("revision comparison requires distinct case_ids")

    source_pairs = (
        ("contract_id", parent.contract_id, child.contract_id),
        ("nomination_id", parent.nomination_id, child.nomination_id),
        ("deadline", parent.deadline, child.deadline),
        ("forecast_units", parent.forecast_units, child.forecast_units),
        ("committed_units", parent.recovery_case.committed_units, child.recovery_case.committed_units),
        ("actual_units", parent.recovery_case.actual_units, child.recovery_case.actual_units),
        ("dedicated_cost", parent.recovery_case.dedicated_cost, child.recovery_case.dedicated_cost),
        (
            "amortization_basis_units",
            parent.recovery_case.amortization_basis_units,
            child.recovery_case.amortization_basis_units,
        ),
        ("mitigation", parent.recovery_case.mitigation, child.recovery_case.mitigation),
        ("prior_payment", parent.recovery_case.prior_payment, child.recovery_case.prior_payment),
        ("commitment_state", parent.recovery_case.commitment_state, child.recovery_case.commitment_state),
        (
            "explicit_recovery_right",
            parent.recovery_case.explicit_recovery_right,
            child.recovery_case.explicit_recovery_right,
        ),
        ("evidence_supported", parent.recovery_case.evidence_supported, child.recovery_case.evidence_supported),
        ("notice_valid", parent.recovery_case.notice_valid, child.recovery_case.notice_valid),
        ("asset_dedicated", parent.recovery_case.asset_dedicated, child.recovery_case.asset_dedicated),
        (
            "already_fully_amortized",
            parent.recovery_case.already_fully_amortized,
            child.recovery_case.already_fully_amortized,
        ),
        ("already_paid", parent.recovery_case.already_paid, child.recovery_case.already_paid),
        ("exposure_type", parent.recovery_case.exposure_type, child.recovery_case.exposure_type),
        ("cost_recovery_mode", parent.recovery_case.cost_recovery_mode, child.recovery_case.cost_recovery_mode),
        ("customer_matches", parent.recovery_case.customer_matches, child.recovery_case.customer_matches),
        ("program_matches", parent.recovery_case.program_matches, child.recovery_case.program_matches),
        ("period_matches", parent.recovery_case.period_matches, child.recovery_case.period_matches),
        ("currency_matches", parent.recovery_case.currency_matches, child.recovery_case.currency_matches),
        ("unit_matches", parent.recovery_case.unit_matches, child.recovery_case.unit_matches),
        ("actuals_complete", parent.recovery_case.actuals_complete, child.recovery_case.actuals_complete),
        (
            "actuals_deduplicated",
            parent.recovery_case.actuals_deduplicated,
            child.recovery_case.actuals_deduplicated,
        ),
        (
            "cancelled_orders_excluded",
            parent.recovery_case.cancelled_orders_excluded,
            child.recovery_case.cancelled_orders_excluded,
        ),
        (
            "amortization_verified",
            parent.recovery_case.amortization_verified,
            child.recovery_case.amortization_verified,
        ),
        (
            "asset_dedication_verified",
            parent.recovery_case.asset_dedication_verified,
            child.recovery_case.asset_dedication_verified,
        ),
        ("mitigation_reviewed", parent.recovery_case.mitigation_reviewed, child.recovery_case.mitigation_reviewed),
        (
            "prior_recovery_reviewed",
            parent.recovery_case.prior_recovery_reviewed,
            child.recovery_case.prior_recovery_reviewed,
        ),
        (
            "notice_window_verified",
            parent.recovery_case.notice_window_verified,
            child.recovery_case.notice_window_verified,
        ),
        ("contract_matches", parent.recovery_case.contract_matches, child.recovery_case.contract_matches),
        ("contract_current", parent.recovery_case.contract_current, child.recovery_case.contract_current),
        (
            "amendment_reviewed",
            parent.recovery_case.amendment_reviewed,
            child.recovery_case.amendment_reviewed,
        ),
        ("amendment_matches", parent.recovery_case.amendment_matches, child.recovery_case.amendment_matches),
        (
            "duplicate_claim_reviewed",
            parent.recovery_case.duplicate_claim_reviewed,
            child.recovery_case.duplicate_claim_reviewed,
        ),
        ("duplicate_claim", parent.recovery_case.duplicate_claim, child.recovery_case.duplicate_claim),
    )
    source_changes = tuple(
        item for item in (_delta(field, before, after) for field, before, after in source_pairs) if item is not None
    )

    parent_processed = process_state(parent)
    child_processed = process_state(child)
    before = parent_processed.result
    after = child_processed.result
    result_pairs = (
        ("recoverability_state", before.recoverability_state, after.recoverability_state),
        ("shortfall_units", before.shortfall_units, after.shortfall_units),
        ("unit_amortization", before.unit_amortization, after.unit_amortization),
        ("recovered_via_actual_units", before.recovered_via_actual_units, after.recovered_via_actual_units),
        ("economic_exposure", before.economic_exposure, after.economic_exposure),
        ("net_exposure", before.net_exposure, after.net_exposure),
        ("recoverable_amount", before.recoverable_amount, after.recoverable_amount),
        ("claimable_amount", before.claimable_amount, after.claimable_amount),
    )
    result_changes = tuple(
        item for item in (_delta(field, before_value, after_value) for field, before_value, after_value in result_pairs) if item is not None
    )

    parent_evidence = set(parent.evidence_refs)
    child_evidence = set(child.evidence_refs)
    parent_missing = set(parent.missing_evidence)
    child_missing = set(child.missing_evidence)
    before_reasons = set(before.reasons)
    after_reasons = set(after.reasons)
    return RevisionDelta(
        parent_case_id=parent.recovery_case.case_id,
        child_case_id=child.recovery_case.case_id,
        source_changes=source_changes,
        evidence_added=tuple(sorted(child_evidence - parent_evidence)),
        evidence_removed=tuple(sorted(parent_evidence - child_evidence)),
        missing_evidence_added=tuple(sorted(child_missing - parent_missing)),
        missing_evidence_resolved=tuple(sorted(parent_missing - child_missing)),
        result_changes=result_changes,
        reasons_added=tuple(sorted(after_reasons - before_reasons)),
        reasons_removed=tuple(sorted(before_reasons - after_reasons)),
    )
