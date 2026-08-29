from __future__ import annotations

from typing import Any

from .recovery_package import RecoveryPackage
from .state import AssistedCaseState


def _text(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())


def _tri(value: Any) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    return "UNKNOWN"


def _bullet_items(values) -> list[str]:
    items = [_text(value) for value in values]
    return [f"- {item}" for item in items] if items else ["- None recorded"]


def render_delivery_report(state: AssistedCaseState, package: RecoveryPackage) -> str:
    """Render a reviewable Markdown findings report without upgrading truth state.

    The report is deliberately derived only from persisted case identity and the
    truth-preserving RecoveryPackage. It never changes recoverability, invents
    evidence, marks recovery as verified, or marks payment as received.
    """

    if package.case_id != state.recovery_case.case_id:
        raise ValueError("package does not belong to state")

    summary = package.executive_summary
    baseline = package.commitment_baseline
    actual = package.actual_consumption
    capacity = package.dedicated_capacity
    exposure = package.investment_exposure
    mitigation = package.mitigation
    basis = package.contractual_basis
    recoverability = package.recoverability
    audit = package.audit_trail
    currency = _text(summary.get("currency"))

    lines = [
        "# Capacity Commitment Recovery Audit — Assisted Findings",
        "",
        "> **Truth boundary:** this is an assisted evidence/reconciliation report, not legal advice, not a guarantee of recovery, and not proof of payment. `verified_recovery=false` and `payment_received=false` unless separately evidenced outside this report.",
        "",
        "## Case identity",
        "",
        f"- Case ID: `{_text(package.case_id)}`",
        f"- Supplier/company: `{_text(state.company_id)}`",
        f"- Customer: `{_text(state.customer_id)}`",
        f"- Programme: `{_text(state.program_id)}`",
        f"- Contract: `{_text(state.contract_id)}`",
        f"- Nomination/award: `{_text(state.nomination_id)}`",
        f"- Currency: `{currency}`",
        f"- Absolute notice deadline: `{_text(package.deadline)}`",
        "",
        "## Executive result",
        "",
        f"- Recoverability state: **{_text(recoverability.get('state'))}**",
        f"- Economic exposure: **{currency} {_text(summary.get('economic_exposure'))}**",
        f"- Net exposure after mitigation/prior recovery: **{currency} {_text(summary.get('net_exposure'))}**",
        f"- Recoverable amount: **{currency} {_text(summary.get('recoverable_amount'))}**",
        f"- Claimable amount: **{currency} {_text(summary.get('claimable_amount'))}**",
        f"- Verified recovery: **{_tri(summary.get('verified_recovery'))}**",
        f"- Payment received: **{_tri(summary.get('payment_received'))}**",
        "",
        "## Commitment vs actual",
        "",
        f"- Commitment state: `{_text(baseline.get('commitment_state'))}`",
        f"- Committed units: `{_text(baseline.get('committed_units'))}`",
        f"- Forecast units (context only): `{_text(state.forecast_units)}`",
        f"- Actual units: `{_text(actual.get('actual_units'))}`",
        f"- Shortfall units: `{_text(package.shortfall.get('shortfall_units'))}`",
        f"- Actuals complete: `{_tri(actual.get('actuals_complete'))}`",
        f"- Actuals deduplicated: `{_tri(actual.get('actuals_deduplicated'))}`",
        f"- Cancelled orders excluded: `{_tri(actual.get('cancelled_orders_excluded'))}`",
        "",
        "## Dedicated investment and net exposure",
        "",
        f"- Exposure type: `{_text(capacity.get('exposure_type'))}`",
        f"- Cost recovery mode: `{_text(exposure.get('cost_recovery_mode'))}`",
        f"- Dedicated cost basis: `{currency} {_text(exposure.get('dedicated_cost'))}`",
        f"- Amortisation basis units: `{_text(exposure.get('amortization_basis_units'))}`",
        f"- Recovered through actual units: `{currency} {_text(exposure.get('recovered_via_actual_units'))}`",
        f"- Mitigation/reuse deduction: `{currency} {_text(mitigation.get('mitigation'))}`",
        f"- Prior payment/recovery deduction: `{currency} {_text(mitigation.get('prior_payment'))}`",
        f"- Asset dedicated: `{_tri(capacity.get('asset_dedicated'))}`",
        f"- Asset dedication verified: `{_tri(basis.get('asset_dedication_verified'))}`",
        f"- Amortisation verified: `{_tri(basis.get('amortization_verified'))}`",
        "",
        "## Contract / amendment / notice integrity",
        "",
        f"- Customer matches: `{_tri(basis.get('customer_matches'))}`",
        f"- Programme matches: `{_tri(basis.get('program_matches'))}`",
        f"- Period matches: `{_tri(basis.get('period_matches'))}`",
        f"- Currency matches: `{_tri(basis.get('currency_matches'))}`",
        f"- Unit matches: `{_tri(basis.get('unit_matches'))}`",
        f"- Explicit recovery right supported: `{_tri(basis.get('explicit_recovery_right'))}`",
        f"- Contract matches: `{_tri(basis.get('contract_matches'))}`",
        f"- Current contract: `{_tri(basis.get('contract_current'))}`",
        f"- Amendments reviewed: `{_tri(basis.get('amendment_reviewed'))}`",
        f"- Applicable amendment matches: `{_tri(basis.get('amendment_matches'))}`",
        f"- Mitigation reviewed: `{_tri(basis.get('mitigation_reviewed'))}`",
        f"- Prior recovery reviewed: `{_tri(basis.get('prior_recovery_reviewed'))}`",
        f"- Notice window verified: `{_tri(basis.get('notice_window_verified'))}`",
        f"- Notice/deadline valid: `{_tri(basis.get('notice_valid'))}`",
        f"- Duplicate claim: `{_tri(basis.get('duplicate_claim'))}`",
        "",
        "## Engine reasons",
        "",
        *_bullet_items(recoverability.get("reasons", ())),
        "",
        "## Evidence references",
        "",
        *_bullet_items(package.evidence),
        "",
        "## Missing evidence",
        "",
        *_bullet_items(package.missing_evidence),
        "",
        "## Next actions",
        "",
        *_bullet_items(package.next_actions),
        "",
        "## Audit boundary",
        "",
        f"- Engine version: `{_text(audit.get('engine_version'))}`",
        f"- Human review required before external submission: `{_tri(audit.get('human_review_required_before_external_submission'))}`",
        "- A positive engine classification is not evidence that a customer accepted, settled or paid the amount.",
        "- Any external claim/submission/negotiation remains an authorized human action outside this report.",
        "",
    ]
    return "\n".join(lines)
