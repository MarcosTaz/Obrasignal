from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Tuple

CAUSAL_STATES = {"DIRECTLY_CAUSED","PARTIALLY_CAUSED","PRE_EXISTING","UNRELATED","UNKNOWN"}
CONTRACT_STATES = {"CONTRACTUALLY_SUPPORTED","UNSUPPORTED","AMBIGUOUS","UNKNOWN"}

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
    index, flags = {}, []
    for raw in case.get("evidence", []) or []:
        item=dict(raw)
        eid=str(item.get("id") or "").strip()
        if not eid:
            flags.append("EVIDENCE_ID_MISSING"); continue
        if eid in index:
            flags.append("DUPLICATE_EVIDENCE_ID"); continue
        index[eid]=item
    return index, flags

def _ctx(case: Dict[str,Any]) -> Dict[str,Any]:
    return {k:case.get(k) for k in ("change_id","customer","program","part")}

def _same(actual: Any, expected: Any) -> bool:
    if isinstance(expected, Decimal):
        try: return money(actual)==expected
        except ValueError: return False
    return actual == expected

def _valid_item(item: Dict[str,Any]) -> bool:
    return item.get("verified") is True and item.get("superseded") is not True

def _refs_exist(refs: Any, evidence: Dict[str,Dict[str,Any]], code: str, missing: List[str]) -> List[Dict[str,Any]]:
    normalized=[str(x).strip() for x in (refs or []) if str(x).strip()]
    if not normalized:
        missing.append(code); return []
    items=[]
    for ref in normalized:
        item=evidence.get(ref)
        if item is None:
            missing.append(f"{code}:{ref}:MISSING"); continue
        if item.get("verified") is not True:
            missing.append(f"{code}:{ref}:UNVERIFIED"); continue
        if item.get("superseded") is True:
            missing.append(f"{code}:{ref}:SUPERSEDED"); continue
        items.append(item)
    return items

def _require_claim(refs: Any, evidence: Dict[str,Dict[str,Any]], expected: Dict[str,Any], code: str, missing: List[str]) -> bool:
    items=_refs_exist(refs,evidence,code,missing)
    if not items: return False
    for item in items:
        asserts=item.get("asserts") or {}
        if all(k in asserts and _same(asserts.get(k), v) for k,v in expected.items()):
            return True
    missing.append(f"{code}:ASSERTION_MISMATCH")
    return False

def _evidence_graph(case: Dict[str,Any]) -> Dict[str,Any]:
    nodes=[]; edges=[]
    for item in case.get("evidence",[]) or []:
        eid=str(item.get("id") or "").strip()
        if eid:
            nodes.append({"id":f"evidence:{eid}","type":item.get("type"),"verified":_valid_item(item)})
    change_id=str(case.get("change_id") or "")
    if change_id: nodes.append({"id":f"change:{change_id}","type":"ENGINEERING_CHANGE","verified":True})
    for ref in case.get("change_evidence_refs",[]) or []:
        edges.append({"from":f"evidence:{ref}","to":f"change:{change_id}","relation":"PROVES_CHANGE"})
    for cost in case.get("costs",[]) or []:
        cid=str(cost.get("id") or "cost")
        nodes.append({"id":f"cost:{cid}","type":cost.get("class") or "COST","amount":float(money(cost.get("amount")))})
        for ref in cost.get("evidence_refs",[]) or []:
            edges.append({"from":f"evidence:{ref}","to":f"cost:{cid}","relation":"PROVES_COST"})
        for ref in cost.get("causality_evidence_refs",[]) or []:
            edges.append({"from":f"evidence:{ref}","to":f"cost:{cid}","relation":"SUPPORTS_CAUSALITY"})
    return {"nodes":nodes,"edges":edges}

def _line_amounts(case: Dict[str,Any], cost: Dict[str,Any], evidence: Dict[str,Dict[str,Any]], missing: List[str]):
    z=Decimal("0.00"); flags=[]
    amount=money(cost.get("amount"))
    if amount<0: raise ValueError("cost amount cannot be negative")
    cid=str(cost.get("id") or "cost")
    if cost.get("duplicate_of"):
        return z,z,z,z,z,z,["DUPLICATE_COST_LINE"]
    currency=str(cost.get("currency") or case.get("currency") or "EUR").upper()
    base={**_ctx(case),"cost_id":cid}
    cost_ok=bool(cost.get("cost_verified")) and _require_claim(
        cost.get("evidence_refs"), evidence,
        {**base,"amount":amount,"currency":currency},
        f"COST_EVIDENCE_REQUIRED:{cid}", missing)
    if not cost_ok:
        return z,z,z,amount,z,z,["UNVERIFIED_COST"]
    causal_state=str(cost.get("causal_state") or "UNKNOWN").upper()
    if causal_state not in CAUSAL_STATES: raise ValueError(f"invalid causal_state: {causal_state}")
    verified=amount
    if causal_state=="UNKNOWN":
        return verified,z,z,verified,z,z,["CAUSALITY_UNKNOWN"]
    causal_expected={**base,"causal_state":causal_state}
    if causal_state=="PARTIALLY_CAUSED":
        causal_expected["attribution_pct"]=str(cost.get("attribution_pct"))
    if not _require_claim(cost.get("causality_evidence_refs"),evidence,causal_expected,
                          f"CAUSALITY_EVIDENCE_REQUIRED:{cid}",missing):
        return verified,z,z,verified,z,z,["CAUSALITY_EVIDENCE_MISSING"]
    if causal_state=="DIRECTLY_CAUSED":
        attribution=Decimal("1")
    elif causal_state=="PARTIALLY_CAUSED":
        pct=Decimal(str(cost.get("attribution_pct",0)))
        if pct<0 or pct>100: raise ValueError("attribution_pct must be between 0 and 100")
        attribution=pct/Decimal("100"); flags.append("PARTIAL_CAUSALITY")
    else:
        attribution=Decimal("0"); flags.append(causal_state)
    causal=(verified*attribution).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
    nonrec=z
    if causal_state in {"PRE_EXISTING","UNRELATED"}: nonrec=verified
    elif causal_state=="PARTIALLY_CAUSED": nonrec=verified-causal
    if causal<=0: return verified,z,nonrec,z,z,z,flags
    mitigation=min(money(cost.get("mitigation_amount")),causal)
    prior=min(money(cost.get("prior_payment_amount")),max(causal-mitigation,z))
    if not _require_claim(cost.get("mitigation_evidence_refs"),evidence,
                          {**base,"mitigation_amount":mitigation},
                          f"MITIGATION_EVIDENCE_REQUIRED:{cid}",missing):
        return verified,z,nonrec,causal,z,z,flags+["MITIGATION_UNVERIFIED"]
    if not _require_claim(cost.get("prior_payment_evidence_refs"),evidence,
                          {**base,"prior_payment_amount":prior},
                          f"PRIOR_PAYMENT_EVIDENCE_REQUIRED:{cid}",missing):
        return verified,z,nonrec,causal,mitigation,z,flags+["PRIOR_PAYMENT_UNVERIFIED"]
    net=max(causal-mitigation-prior,z)
    return verified,net,nonrec,z,mitigation,prior,flags

def analyze_case(case: Dict[str,Any], analysis_date: str|date="2026-08-28")->Dict[str,Any]:
    day=iso_date(analysis_date); assert day is not None
    if not str(case.get("tenant_id") or "").strip() or not str(case.get("change_id") or "").strip():
        raise ValueError("tenant_id and change_id are required")
    evidence,evidence_flags=_evidence_index(case)
    flags=list(evidence_flags); missing=[]
    ctx=_ctx(case)
    change_ok=_require_claim(case.get("change_evidence_refs"),evidence,
                             {**ctx,"revision_from":case.get("revision_from"),"revision_to":case.get("revision_to")},
                             "CHANGE_EVIDENCE_REQUIRED",missing)
    baseline_ok=bool(case.get("baseline_verified")) and _require_claim(case.get("baseline_evidence_refs"),evidence,
                             {**ctx,"revision_from":case.get("revision_from")},
                             "BASELINE_EVIDENCE_REQUIRED",missing)
    revision_ok=bool(case.get("revision_verified")) and _require_claim(case.get("revision_evidence_refs"),evidence,
                             {**ctx,"revision_to":case.get("revision_to")},
                             "REVISION_EVIDENCE_REQUIRED",missing)
    currencies={str(c.get("currency") or case.get("currency") or "EUR").upper() for c in case.get("costs",[]) or []}
    if len(currencies)>1:
        return _result(case,day,Decimal("0"),Decimal("0"),Decimal("0"),Decimal("0"),"UNKNOWN",
                       flags+["MIXED_CURRENCY"],["Normalize currency with evidenced FX basis before analysis."],
                       "MIXED",Decimal("0"),Decimal("0"),missing)
    currency=next(iter(currencies),str(case.get("currency") or "EUR").upper())
    totals={k:Decimal("0.00") for k in ("verified","net","nonrecoverable","unknown","mitigated","prior_payment")}
    for cost in case.get("costs",[]) or []:
        vals=_line_amounts(case,cost,evidence,missing)
        verified,net,nonrec,unknown,mitigated,prior,line_flags=vals
        for k,v in (("verified",verified),("net",net),("nonrecoverable",nonrec),("unknown",unknown),("mitigated",mitigated),("prior_payment",prior)):
            totals[k]+=v
        flags.extend(line_flags)
    if case.get("duplicate_of"):
        return _result(case,day,totals["verified"],Decimal("0"),totals["nonrecoverable"],totals["unknown"],
                       "ZERO_RECOVERY",flags+["DUPLICATE_CHANGE"],
                       ["Do not submit duplicate recovery; reconcile against original change."],currency,
                       totals["mitigated"],totals["prior_payment"],missing)
    if not (change_ok and baseline_ok and revision_ok):
        unresolved=totals["net"]+totals["unknown"]
        return _result(case,day,totals["verified"],Decimal("0"),totals["nonrecoverable"],unresolved,"UNKNOWN",
                       flags+["REVISION_OR_BASELINE_UNVERIFIED"],
                       ["Verify exact change/baseline/revision context before commercial classification."],
                       currency,totals["mitigated"],totals["prior_payment"],missing)
    ent=case.get("entitlement") or {}
    contract_state=str(ent.get("contract_state") or "UNKNOWN").upper()
    if contract_state not in CONTRACT_STATES: raise ValueError(f"invalid contract_state: {contract_state}")
    contract_expected={**ctx,"contract_state":contract_state,
                       "notice_required":ent.get("notice_required"),
                       "notice_deadline":ent.get("notice_deadline"),
                       "prior_approval_required":ent.get("prior_approval_required")}
    if contract_state!="UNKNOWN" and not _require_claim(ent.get("basis_evidence_refs"),evidence,contract_expected,
                                                        "CONTRACT_BASIS_EVIDENCE_REQUIRED",missing):
        flags.append("CONTRACT_EVIDENCE_MISMATCH"); contract_state="UNKNOWN"
    candidate=totals["net"]; nonrec=totals["nonrecoverable"]; unknown=totals["unknown"]; rec=Decimal("0.00"); actions=[]
    if contract_state=="UNSUPPORTED":
        nonrec+=candidate; candidate=Decimal("0"); flags.append("NO_CONTRACTUAL_RIGHT")
    elif contract_state in {"AMBIGUOUS","UNKNOWN"}:
        unknown+=candidate; candidate=Decimal("0"); flags.append("CONTRACT_BASIS_UNRESOLVED")
        actions.append("Resolve contractual/commercial basis with governing evidence.")
    if candidate>0 and ent.get("prior_approval_required") is True:
        if ent.get("prior_approval_obtained") is not True:
            unknown+=candidate; candidate=Decimal("0"); flags.append("PRIOR_APPROVAL_UNRESOLVED")
        elif not _require_claim(ent.get("prior_approval_evidence_refs"),evidence,
                                {**ctx,"prior_approval_obtained":True},"PRIOR_APPROVAL_EVIDENCE_REQUIRED",missing):
            unknown+=candidate; candidate=Decimal("0"); flags.append("PRIOR_APPROVAL_EVIDENCE_MISSING")
    if candidate>0:
        nr=ent.get("notice_required"); deadline=iso_date(ent.get("notice_deadline")); sent=iso_date(ent.get("notice_sent"))
        if nr is True:
            if deadline is None:
                unknown+=candidate; candidate=Decimal("0"); flags.append("NOTICE_DEADLINE_UNKNOWN")
            elif sent is not None and not _require_claim(ent.get("notice_evidence_refs"),evidence,
                                {**ctx,"notice_sent":sent.isoformat()},"NOTICE_PROOF_REQUIRED",missing):
                unknown+=candidate; candidate=Decimal("0"); flags.append("NOTICE_PROOF_MISSING")
            elif sent is not None and sent>deadline:
                nonrec+=candidate; candidate=Decimal("0"); flags.append("NOTICE_MISSED")
            elif sent is None and day>deadline:
                nonrec+=candidate; candidate=Decimal("0"); flags.append("NOTICE_EXPIRED")
            elif sent is None:
                unknown+=candidate; candidate=Decimal("0"); flags.append("NOTICE_NOT_SENT_AT_RISK")
            else:
                flags.append("NOTICE_ON_TIME")
        elif nr is None:
            unknown+=candidate; candidate=Decimal("0"); flags.append("NOTICE_REQUIREMENT_UNKNOWN")
    if candidate>0: rec=candidate
    if rec>0 and (unknown>0 or nonrec>0): status="PARTIAL"
    elif rec>0: status="RECOVERABLE"
    elif unknown>0: status="UNKNOWN"
    elif nonrec>0: status="NON_RECOVERABLE"
    else: status="ZERO_RECOVERY"
    if rec>0: actions.append("Prepare commercial change package with linked evidence.")
    elif status=="ZERO_RECOVERY": actions.append("Record zero recovery as a valid verified outcome.")
    return _result(case,day,totals["verified"],rec,nonrec,unknown,status,flags,actions,currency,totals["mitigated"],totals["prior_payment"],missing)

def _result(case,day,verified,recoverable,nonrecoverable,unknown,status,flags,actions,currency="EUR",mitigated=Decimal("0"),prior_payment=Decimal("0"),missing_evidence=()):
    return {
        "tenant_id":case.get("tenant_id"),"change_id":case.get("change_id"),"customer":case.get("customer"),
        "program":case.get("program"),"part":case.get("part"),"revision_from":case.get("revision_from"),"revision_to":case.get("revision_to"),
        "analysis_date":day.isoformat(),"currency":currency,"cost_verified":float(verified),
        "recoverable_amount":float(recoverable),"nonrecoverable_amount":float(nonrecoverable),"unknown_amount":float(unknown),
        "mitigated_amount":float(mitigated),"prior_payment_amount":float(prior_payment),"status":status,
        "flags":list(dict.fromkeys(flags)),"missing_evidence":list(dict.fromkeys(missing_evidence)),
        "next_actions":list(dict.fromkeys(actions)),"evidence_graph":_evidence_graph(case),
    }
