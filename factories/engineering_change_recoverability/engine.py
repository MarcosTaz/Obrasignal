from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Tuple

TRUTH_STATES = {
    "CHANGE_DETECTED", "IMPACT_POTENTIAL", "IMPACT_EVIDENCE_SUPPORTED", "COST_ESTIMATED",
    "COST_VERIFIED", "POTENTIAL_ENTITLEMENT", "CONTRACTUALLY_SUPPORTED", "RECOVERABLE",
    "NOTICE_REQUIRED", "NOTICE_SENT", "CHANGE_REQUEST_SUBMITTED", "CLAIMED", "DISPUTED",
    "APPROVED", "PARTIALLY_APPROVED", "SETTLED", "PAID", "REJECTED", "EXPIRED", "UNKNOWN",
}
CAUSAL_STATES = {"DIRECTLY_CAUSED", "PARTIALLY_CAUSED", "PRE_EXISTING", "UNRELATED", "UNKNOWN"}
CONTRACT_STATES = {"CONTRACTUALLY_SUPPORTED", "UNSUPPORTED", "AMBIGUOUS", "UNKNOWN"}


def money(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"invalid money value: {value!r}") from exc


def iso_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"invalid date: {value!r}") from exc


def _evidence_index(case: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    index: Dict[str, Dict[str, Any]] = {}
    flags: List[str] = []
    for item in case.get("evidence", []) or []:
        eid = str(item.get("id") or "").strip()
        if not eid:
            flags.append("EVIDENCE_ID_MISSING")
            continue
        if eid in index:
            flags.append("DUPLICATE_EVIDENCE_ID")
            continue
        index[eid] = dict(item)
    return index, flags


def _refs_verified(refs: Any, evidence: Dict[str, Dict[str, Any]]) -> Tuple[bool, List[str]]:
    normalized = [str(x).strip() for x in (refs or []) if str(x).strip()]
    if not normalized:
        return False, []
    missing = [ref for ref in normalized if ref not in evidence or evidence[ref].get("verified") is not True]
    return not missing, missing


def _require_refs(refs: Any, evidence: Dict[str, Dict[str, Any]], code: str, missing: List[str]) -> bool:
    ok, unresolved = _refs_verified(refs, evidence)
    if not ok:
        if unresolved:
            missing.extend(f"{code}:{ref}" for ref in unresolved)
        else:
            missing.append(code)
    return ok


def _evidence_graph(case: Dict[str, Any]) -> Dict[str, Any]:
    nodes = []
    edges = []
    for item in case.get("evidence", []) or []:
        eid = str(item.get("id") or "").strip()
        if eid:
            nodes.append({"id": f"evidence:{eid}", "type": item.get("type"), "verified": item.get("verified") is True})
    change_id = str(case.get("change_id") or "")
    if change_id:
        nodes.append({"id": f"change:{change_id}", "type": "ENGINEERING_CHANGE", "verified": True})
    for ref in case.get("change_evidence_refs", []) or []:
        edges.append({"from": f"evidence:{ref}", "to": f"change:{change_id}", "relation": "PROVES_CHANGE"})
    for cost in case.get("costs", []) or []:
        cid = str(cost.get("id") or "cost")
        nodes.append({"id": f"cost:{cid}", "type": cost.get("class") or "COST", "amount": float(money(cost.get("amount")))})
        for ref in cost.get("evidence_refs", []) or []:
            edges.append({"from": f"evidence:{ref}", "to": f"cost:{cid}", "relation": "PROVES_COST"})
        for ref in cost.get("causality_evidence_refs", []) or []:
            edges.append({"from": f"evidence:{ref}", "to": f"cost:{cid}", "relation": "SUPPORTS_CAUSALITY"})
    for ref in (case.get("entitlement") or {}).get("basis_evidence_refs", []) or []:
        edges.append({"from": f"evidence:{ref}", "to": f"change:{change_id}", "relation": "SUPPORTS_ENTITLEMENT"})
    return {"nodes": nodes, "edges": edges}


def _line_amounts(cost: Dict[str, Any], evidence: Dict[str, Dict[str, Any]], missing_evidence: List[str]) -> Tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, List[str]]:
    flags: List[str] = []
    amount = money(cost.get("amount"))
    if amount < 0:
        raise ValueError("cost amount cannot be negative")
    cid = str(cost.get("id") or "cost")

    if cost.get("duplicate_of"):
        flags.append("DUPLICATE_COST_LINE")
        return *(Decimal("0.00") for _ in range(6)), flags

    cost_refs_ok = _require_refs(cost.get("evidence_refs"), evidence, f"COST_EVIDENCE_REQUIRED:{cid}", missing_evidence)
    if not bool(cost.get("cost_verified")) or not cost_refs_ok:
        flags.append("UNVERIFIED_COST")
        return Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), amount, Decimal("0.00"), Decimal("0.00"), flags

    causal_state = str(cost.get("causal_state") or "UNKNOWN").upper()
    if causal_state not in CAUSAL_STATES:
        raise ValueError(f"invalid causal_state: {causal_state}")

    verified = amount
    if causal_state != "UNKNOWN":
        causal_refs_ok = _require_refs(cost.get("causality_evidence_refs"), evidence, f"CAUSALITY_EVIDENCE_REQUIRED:{cid}", missing_evidence)
        if not causal_refs_ok:
            flags.append("CAUSALITY_EVIDENCE_MISSING")
            return verified, Decimal("0.00"), Decimal("0.00"), verified, Decimal("0.00"), Decimal("0.00"), flags

    if causal_state == "DIRECTLY_CAUSED":
        attribution = Decimal("1")
    elif causal_state == "PARTIALLY_CAUSED":
        pct = Decimal(str(cost.get("attribution_pct", 0)))
        if pct < 0 or pct > 100:
            raise ValueError("attribution_pct must be between 0 and 100")
        attribution = pct / Decimal("100")
        flags.append("PARTIAL_CAUSALITY")
    elif causal_state in {"PRE_EXISTING", "UNRELATED"}:
        attribution = Decimal("0")
        flags.append(causal_state)
    else:
        attribution = Decimal("0")
        flags.append("CAUSALITY_UNKNOWN")

    causal = (verified * attribution).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    unknown = Decimal("0.00")
    nonrecoverable = Decimal("0.00")
    if causal_state == "UNKNOWN":
        unknown = verified
    elif causal_state in {"PRE_EXISTING", "UNRELATED"}:
        nonrecoverable = verified
    elif causal_state == "PARTIALLY_CAUSED":
        nonrecoverable = verified - causal

    mitigation_requested = min(money(cost.get("mitigation_amount")), causal)
    prior_payment_requested = min(money(cost.get("prior_payment_amount")), max(causal - mitigation_requested, Decimal("0")))

    # Unknown mitigation/payment changes the net exposure, so fail closed on the causal amount.
    if mitigation_requested > 0 and not _require_refs(cost.get("mitigation_evidence_refs"), evidence, f"MITIGATION_EVIDENCE_REQUIRED:{cid}", missing_evidence):
        flags.append("MITIGATION_UNVERIFIED")
        return verified, Decimal("0.00"), nonrecoverable, unknown + causal, Decimal("0.00"), Decimal("0.00"), flags
    if prior_payment_requested > 0 and not _require_refs(cost.get("prior_payment_evidence_refs"), evidence, f"PRIOR_PAYMENT_EVIDENCE_REQUIRED:{cid}", missing_evidence):
        flags.append("PRIOR_PAYMENT_UNVERIFIED")
        return verified, Decimal("0.00"), nonrecoverable, unknown + causal, mitigation_requested, Decimal("0.00"), flags

    net = max(causal - mitigation_requested - prior_payment_requested, Decimal("0"))
    return verified, net, nonrecoverable, unknown, mitigation_requested, prior_payment_requested, flags


def analyze_case(case: Dict[str, Any], analysis_date: str | date = "2026-08-28") -> Dict[str, Any]:
    analysis_day = iso_date(analysis_date)
    assert analysis_day is not None
    tenant_id = str(case.get("tenant_id") or "").strip()
    change_id = str(case.get("change_id") or "").strip()
    if not tenant_id or not change_id:
        raise ValueError("tenant_id and change_id are required")

    evidence, evidence_flags = _evidence_index(case)
    flags: List[str] = list(evidence_flags)
    missing_evidence: List[str] = []
    change_evidence_ok = _require_refs(case.get("change_evidence_refs"), evidence, "CHANGE_EVIDENCE_REQUIRED", missing_evidence)
    baseline_evidence_ok = _require_refs(case.get("baseline_evidence_refs"), evidence, "BASELINE_EVIDENCE_REQUIRED", missing_evidence)
    revision_evidence_ok = _require_refs(case.get("revision_evidence_refs"), evidence, "REVISION_EVIDENCE_REQUIRED", missing_evidence)

    currencies = {str(c.get("currency") or "").upper() for c in case.get("costs", []) if c.get("currency")}
    if len(currencies) > 1:
        return _result(case, analysis_day, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), "UNKNOWN", flags + ["MIXED_CURRENCY"], ["Normalize currency with evidenced FX basis before analysis."], missing_evidence=missing_evidence)
    currency = next(iter(currencies), str(case.get("currency") or "EUR").upper())

    totals = {k: Decimal("0.00") for k in ("verified", "net", "nonrecoverable", "unknown", "mitigated", "prior_payment")}
    for cost in case.get("costs", []) or []:
        verified, net, nonrec, unknown, mitigated, prior_payment, line_flags = _line_amounts(cost, evidence, missing_evidence)
        totals["verified"] += verified
        totals["net"] += net
        totals["nonrecoverable"] += nonrec
        totals["unknown"] += unknown
        totals["mitigated"] += mitigated
        totals["prior_payment"] += prior_payment
        flags.extend(line_flags)

    if not change_evidence_ok:
        flags.append("CHANGE_EVIDENCE_MISSING")

    if case.get("duplicate_of"):
        flags.append("DUPLICATE_CHANGE")
        return _result(case, analysis_day, totals["verified"], Decimal("0"), totals["nonrecoverable"], totals["unknown"], "ZERO_RECOVERY", flags, ["Do not submit duplicate recovery; reconcile against original change."], currency, totals["mitigated"], totals["prior_payment"], missing_evidence)

    baseline_ok = bool(case.get("baseline_verified")) and baseline_evidence_ok
    revision_ok = bool(case.get("revision_verified")) and revision_evidence_ok
    if not baseline_ok or not revision_ok or not change_evidence_ok:
        flags.append("REVISION_OR_BASELINE_UNVERIFIED")
        unresolved = totals["net"] + totals["unknown"]
        return _result(case, analysis_day, totals["verified"], Decimal("0"), totals["nonrecoverable"], unresolved, "UNKNOWN", flags, ["Verify the change, baseline and exact revision chain with linked evidence before commercial classification."], currency, totals["mitigated"], totals["prior_payment"], missing_evidence)

    entitlement = case.get("entitlement") or {}
    contract_state = str(entitlement.get("contract_state") or "UNKNOWN").upper()
    if contract_state not in CONTRACT_STATES:
        raise ValueError(f"invalid contract_state: {contract_state}")
    contract_evidence_ok = _require_refs(entitlement.get("basis_evidence_refs"), evidence, "CONTRACT_BASIS_EVIDENCE_REQUIRED", missing_evidence)
    if contract_state != "UNKNOWN" and not contract_evidence_ok:
        flags.append("CONTRACT_EVIDENCE_MISSING")
        contract_state = "UNKNOWN"

    candidate = totals["net"]
    nonrecoverable = totals["nonrecoverable"]
    unknown = totals["unknown"]
    recoverable = Decimal("0.00")
    actions: List[str] = []

    if contract_state == "UNSUPPORTED":
        nonrecoverable += candidate
        flags.append("NO_CONTRACTUAL_RIGHT")
        candidate = Decimal("0.00")
    elif contract_state in {"AMBIGUOUS", "UNKNOWN"}:
        unknown += candidate
        flags.append("CONTRACT_BASIS_UNRESOLVED")
        candidate = Decimal("0.00")
        actions.append("Resolve contractual/commercial basis with linked governing evidence before representing any amount as recoverable.")

    if candidate > 0 and entitlement.get("prior_approval_required") is True:
        if entitlement.get("prior_approval_obtained") is not True:
            unknown += candidate
            flags.append("PRIOR_APPROVAL_UNRESOLVED")
            actions.append("Obtain or evidence required prior approval / waiver.")
            candidate = Decimal("0.00")
        elif not _require_refs(entitlement.get("prior_approval_evidence_refs"), evidence, "PRIOR_APPROVAL_EVIDENCE_REQUIRED", missing_evidence):
            unknown += candidate
            flags.append("PRIOR_APPROVAL_EVIDENCE_MISSING")
            candidate = Decimal("0.00")

    if candidate > 0:
        notice_required = entitlement.get("notice_required")
        deadline = iso_date(entitlement.get("notice_deadline"))
        sent_raw = iso_date(entitlement.get("notice_sent"))
        if notice_required is True:
            if deadline is None:
                unknown += candidate
                flags.append("NOTICE_DEADLINE_UNKNOWN")
                actions.append("Determine notice deadline from governing terms.")
                candidate = Decimal("0.00")
            elif sent_raw is not None and not _require_refs(entitlement.get("notice_evidence_refs"), evidence, "NOTICE_PROOF_REQUIRED", missing_evidence):
                unknown += candidate
                flags.append("NOTICE_PROOF_MISSING")
                actions.append("Link verified proof of notice delivery before treating notice as satisfied.")
                candidate = Decimal("0.00")
            elif sent_raw is not None and sent_raw > deadline:
                nonrecoverable += candidate
                flags.append("NOTICE_MISSED")
                candidate = Decimal("0.00")
            elif sent_raw is None and analysis_day > deadline:
                nonrecoverable += candidate
                flags.append("NOTICE_EXPIRED")
                candidate = Decimal("0.00")
            elif sent_raw is None:
                unknown += candidate
                flags.append("NOTICE_NOT_SENT_AT_RISK")
                actions.append(f"Send compliant notice before {deadline.isoformat()} and preserve proof of delivery.")
                candidate = Decimal("0.00")
            else:
                flags.append("NOTICE_ON_TIME")
        elif notice_required is None:
            unknown += candidate
            flags.append("NOTICE_REQUIREMENT_UNKNOWN")
            actions.append("Determine whether notice is required.")
            candidate = Decimal("0.00")

    if candidate > 0:
        recoverable = candidate

    if recoverable > 0 and (unknown > 0 or nonrecoverable > 0):
        status = "PARTIAL"
    elif recoverable > 0:
        status = "RECOVERABLE"
    elif unknown > 0:
        status = "UNKNOWN"
    elif nonrecoverable > 0:
        status = "NON_RECOVERABLE"
    else:
        status = "ZERO_RECOVERY"

    if recoverable > 0:
        actions.append("Prepare commercial change package with revision delta, linked cost evidence, mitigation, clause basis and notice proof.")
    elif status == "ZERO_RECOVERY":
        actions.append("Record zero recovery as a valid verified outcome.")

    return _result(case, analysis_day, totals["verified"], recoverable, nonrecoverable, unknown, status, flags, actions, currency, totals["mitigated"], totals["prior_payment"], missing_evidence)


def _result(case: Dict[str, Any], analysis_day: date, verified: Decimal, recoverable: Decimal, nonrecoverable: Decimal, unknown: Decimal, status: str, flags: Iterable[str], actions: Iterable[str], currency: str = "EUR", mitigated: Decimal = Decimal("0"), prior_payment: Decimal = Decimal("0"), missing_evidence: Iterable[str] = ()) -> Dict[str, Any]:
    return {
        "tenant_id": case.get("tenant_id"), "change_id": case.get("change_id"), "customer": case.get("customer"),
        "program": case.get("program"), "part": case.get("part"), "revision_from": case.get("revision_from"),
        "revision_to": case.get("revision_to"), "analysis_date": analysis_day.isoformat(), "currency": currency,
        "cost_verified": float(verified), "recoverable_amount": float(recoverable), "nonrecoverable_amount": float(nonrecoverable),
        "unknown_amount": float(unknown), "mitigated_amount": float(mitigated), "prior_payment_amount": float(prior_payment),
        "status": status, "flags": list(dict.fromkeys(flags)), "missing_evidence": list(dict.fromkeys(missing_evidence)),
        "next_actions": list(dict.fromkeys(actions)), "evidence_graph": _evidence_graph(case),
    }
