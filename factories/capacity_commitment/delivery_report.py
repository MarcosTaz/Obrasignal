from __future__ import annotations

from datetime import date
from typing import Any

from .engine import evaluate_recoverability
from .recovery_package import RecoveryPackage, build_recovery_package
from .state import AssistedCaseState, dump_state
from .temporal import assess_temporal_state


def _text(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())


def _code(value: Any) -> str:
    """Render untrusted case/source text inside a non-breakable Markdown code span.

    Newlines are already collapsed by `_text`. Source backticks are replaced with
    a visually similar modifier mark so user-controlled values cannot close the
    code span and inject headings, links, HTML, emphasis or false report states.
    """

    return f"`{_text(value).replace('`', 'ˋ')}`"


def _tri(value: Any) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    return "UNKNOWN"


def _bullet_items(values) -> list[str]:
    items = [_code(value) for value in values]
    return [f"- {item}" for item in items] if items else ["- None recorded"]


def render_delivery_report(state: AssistedCaseState, package: RecoveryPackage) -> str:
    """Render a reviewable Markdown findings report without upgrading truth state.

    The report is deliberately derived only from persisted case identity and the
    truth-preserving RecoveryPackage. It never changes recoverability, invents
    evidence, marks recovery as verified, or marks payment as received.
    """

    # A report is a customer-facing truth surface. Validate the complete assisted
    # state here as well as in the service layer so direct callers cannot bypass
    # identity/evidence/deadline consistency gates.
    dump_state(state)

    if package.case_id != state.recovery_case.case_id:
        raise ValueError("package does not belong to state")
    if not package.assessment_date:
        raise ValueError("package assessment date is required")
    try:
        assessment_date = date.fromisoformat(package.assessment_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("package assessment date is invalid") from exc

    temporal = assess_temporal_state(state, as_of_date=assessment_date)
    expected_package = build_recovery_package(
        temporal.effective_case,
        evaluate_recoverability(temporal.effective_case),
        evidence_refs=state.evidence_refs,
        missing_evidence=state.missing_evidence,
        deadline=state.deadline,
        assessment_date=package.assessment_date,
        deadline_expired_by_date=temporal.deadline_expired_by_date,
    )
    if package != expected_package:
        raise ValueError("package does not match current state")

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
        f"- Case ID: {_code(package.case_id)}",
        f"- Supplier/company: {_code(state.company_id)}",
        f"- Customer: {_code(state.customer_id)}",
        f"- Programme: {_code(state.program_id)}",
        f"- Contract: {_code(state.contract_id)}",
        f"- Nomination/award: {_code(state.nomination_id)}",
        f"- Currency: {_code(currency)}",
        f"- Assessment date: {_code(package.assessment_date)}",
        f"- Absolute notice deadline: {_code(package.deadline)}",
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
        f"- Commitment state: {_code(baseline.get('commitment_state'))}",
        f"- Committed units: {_code(baseline.get('committed_units'))}",
        f"- Forecast units (context only): {_code(state.forecast_units)}",
        f"- Actual units: {_code(actual.get('actual_units'))}",
        f"- Shortfall units: {_code(package.shortfall.get('shortfall_units'))}",
        f"- Actuals complete: {_code(_tri(actual.get('actuals_complete')))}",
        f"- Actuals deduplicated: {_code(_tri(actual.get('actuals_deduplicated')))}",
        f"- Cancelled orders excluded: {_code(_tri(actual.get('cancelled_orders_excluded')))}",
        "",
        "## Dedicated investment and net exposure",
        "",
        f"- Exposure type: {_code(capacity.get('exposure_type'))}",
        f"- Cost recovery mode: {_code(exposure.get('cost_recovery_mode'))}",
        f"- Dedicated cost basis: {_code(f'{currency} {_text(exposure.get("dedicated_cost"))}')}",
        f"- Amortisation basis units: {_code(exposure.get('amortization_basis_units'))}",
        f"- Recovered through actual units: {_code(f'{currency} {_text(exposure.get("recovered_via_actual_units"))}')}",
        f"- Mitigation/reuse deduction: {_code(f'{currency} {_text(mitigation.get("mitigation"))}')}",
        f"- Prior payment/recovery deduction: {_code(f'{currency} {_text(mitigation.get("prior_payment"))}')}",
        f"- Asset dedicated: {_code(_tri(capacity.get('asset_dedicated')))}",
        f"- Asset dedication verified: {_code(_tri(basis.get('asset_dedication_verified')))}",
        f"- Amortisation verified: {_code(_tri(basis.get('amortization_verified')))}",
        "",
        "## Contract / amendment / notice integrity",
        "",
        f"- Customer matches: {_code(_tri(basis.get('customer_matches')))}",
        f"- Programme matches: {_code(_tri(basis.get('program_matches')))}",
        f"- Period matches: {_code(_tri(basis.get('period_matches')))}",
        f"- Currency matches: {_code(_tri(basis.get('currency_matches')))}",
        f"- Unit matches: {_code(_tri(basis.get('unit_matches')))}",
        f"- Explicit recovery right supported: {_code(_tri(basis.get('explicit_recovery_right')))}",
        f"- Contract matches: {_code(_tri(basis.get('contract_matches')))}",
        f"- Current contract: {_code(_tri(basis.get('contract_current')))}",
        f"- Amendments reviewed: {_code(_tri(basis.get('amendment_reviewed')))}",
        f"- Applicable amendment matches: {_code(_tri(basis.get('amendment_matches')))}",
        f"- Mitigation reviewed: {_code(_tri(basis.get('mitigation_reviewed')))}",
        f"- Prior recovery reviewed: {_code(_tri(basis.get('prior_recovery_reviewed')))}",
        f"- Notice window verified: {_code(_tri(basis.get('notice_window_verified')))}",
        f"- Notice/deadline valid as assessed: {_code(_tri(basis.get('notice_valid')))}",
        f"- Deadline elapsed by assessment date: {_code(_tri(audit.get('deadline_expired_by_date')))}",
        f"- Duplicate claim: {_code(_tri(basis.get('duplicate_claim')))}",
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
        f"- Engine version: {_code(audit.get('engine_version'))}",
        f"- Assessment date: {_code(audit.get('assessment_date'))}",
        f"- Human review required before external submission: {_code(_tri(audit.get('human_review_required_before_external_submission')))}",
        "- A positive engine classification is not evidence that a customer accepted, settled or paid the amount.",
        "- Any external claim/submission/negotiation remains an authorized human action outside this report.",
        "",
    ]
    return "\n".join(lines)
