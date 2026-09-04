import {normalizeAmount,round2,validCurrency} from './utils.mjs';
import {selectContract} from './contracts.mjs';
import {verifyEvidenceBundle} from './evidence.mjs';

const VALID_RESP=new Set(['SUPPLIER','CUSTOMER','THIRD_PARTY','SHARED','NO_FAULT_FOUND','UNDETERMINED']);
function unknown(id,amount,currency,flags,reasons){return {id,amount,outstandingAmount:null,resolvedCredit:null,supported:null,disputable:null,state:'UNKNOWN',confidence:'LOW',currency,flags:[...new Set(flags)],unresolvedReasons:[...new Set(reasons)]};}
export function analyzeDebit(d,{contracts=null,evidence=null,requireContext=false}={}){
  if(!d||!d.id)throw new Error('MISSING_ID'); if(!d.tenantId)throw new Error('MISSING_TENANT');
  const amount=normalizeAmount(d.amount); const flags=[],reasons=[]; const currency=d.currency;
  if(!validCurrency(currency)){flags.push('CURRENCY_UNKNOWN');reasons.push('CURRENCY_UNKNOWN');}
  if(d.currencyMismatch===true){flags.push('CURRENCY_CONFLICT');reasons.push('CURRENCY_CONFLICT');}
  for(const f of ['part','program','asset'])if(!d[f]){flags.push(`MISSING_${f.toUpperCase()}`);reasons.push('MAPPING_INCOMPLETE');}
  let contract=null;
  if(contracts){const s=selectContract(contracts,d); if(!s.ok){flags.push(s.reason);reasons.push(s.reason);} else contract=s.contract;}
  else if(requireContext||d.contractKnown!==true){flags.push('CONTRACT_BASIS_UNKNOWN');reasons.push('CONTRACT_BASIS_UNKNOWN');}
  let ev=null; const evidenceClaims=new Set(); let evidenceFacts={exclusionTags:[]};
  if(evidence){ev=verifyEvidenceBundle(evidence,d);if(!ev.ok){flags.push(ev.reason);reasons.push(ev.reason);}else{for(const c of ev.claims)evidenceClaims.add(c);evidenceFacts=ev.facts??evidenceFacts;}}
  else if(requireContext){flags.push('EVIDENCE_MISSING');reasons.push('EVIDENCE_MISSING');}
  else {if(d.rootCauseKnown!==true){flags.push('RESPONSIBILITY_UNKNOWN');reasons.push('RESPONSIBILITY_UNKNOWN');}if(d.evidenceContradictory===true){flags.push('CONTRADICTORY_EVIDENCE');reasons.push('CONTRADICTORY_EVIDENCE');}}
  if(d.rootCauseKnown!==true||!d.responsibility){flags.push('RESPONSIBILITY_UNKNOWN');reasons.push('RESPONSIBILITY_UNKNOWN');}
  if(d.responsibility&&!VALID_RESP.has(d.responsibility)){flags.push('RESPONSIBILITY_INVALID');reasons.push('RESPONSIBILITY_INVALID');}
  if(d.responsibility==='UNDETERMINED'){flags.push('RESPONSIBILITY_UNKNOWN');reasons.push('RESPONSIBILITY_UNKNOWN');}
  const mappingChallenge=d.wrongPart===true||d.wrongProgram===true||d.wrongAsset===true||d.wrongCustomer===true;
  if(mappingChallenge&&evidence&&ev?.ok&&!evidenceClaims.has('MAPPING')){flags.push('MAPPING_EVIDENCE_MISSING');reasons.push('MAPPING_EVIDENCE_MISSING');}
  if(d.wrongPart===true&&d.part)flags.push('WRONG_PART');
  if(d.wrongProgram===true&&d.program)flags.push('WRONG_PROGRAM');
  if(d.wrongAsset===true&&d.asset)flags.push('WRONG_ASSET');
  if(d.wrongCustomer===true)flags.push('WRONG_CUSTOMER');
  if(d.warrantyEligible!=null&&evidence&&ev?.ok&&!evidenceClaims.has('WARRANTY')){flags.push('WARRANTY_EVIDENCE_MISSING');reasons.push('WARRANTY_EVIDENCE_MISSING');}
  if((d.costEligible!=null||d.ineligibleCost!=null||d.costCap!=null)&&evidence&&ev?.ok&&!evidenceClaims.has('COST_ELIGIBILITY')){flags.push('COST_EVIDENCE_MISSING');reasons.push('COST_EVIDENCE_MISSING');}
  let priorCreditAmount=0;if(d.priorCredit!=null){priorCreditAmount=normalizeAmount(d.priorCredit);if(priorCreditAmount>0&&evidence&&ev?.ok&&!evidenceClaims.has('PRIOR_CREDIT')){flags.push('PRIOR_CREDIT_EVIDENCE_MISSING');reasons.push('PRIOR_CREDIT_EVIDENCE_MISSING');}if(priorCreditAmount>amount){flags.push('PRIOR_CREDIT_EXCEEDS_AMOUNT');reasons.push('PRIOR_CREDIT_EXCEEDS_AMOUNT');}}
  const duplicateTrusted=d.duplicateConfirmed===true&&(d.duplicateConfirmedSource==='ENGINE_EXACT'||(evidence&&ev?.ok&&evidenceClaims.has('DUPLICATE')));
  if(d.duplicateConfirmed===true&&!duplicateTrusted){flags.push('DUPLICATE_EVIDENCE_MISSING');reasons.push('DUPLICATE_EVIDENCE_MISSING');}
  const warrantyEligible=d.warrantyEligible ?? contract?.rules?.warrantyEligible;
  const costEligible=d.costEligible ?? contract?.rules?.costEligible;
  if(warrantyEligible==null){flags.push('WARRANTY_ELIGIBILITY_UNKNOWN');reasons.push('WARRANTY_ELIGIBILITY_UNKNOWN');}
  if(costEligible==null){flags.push('COST_ELIGIBILITY_UNKNOWN');reasons.push('COST_ELIGIBILITY_UNKNOWN');}
  const contractExclusions=Array.isArray(contract?.rules?.exclusionTags)?contract.rules.exclusionTags:[];let exclusionMatches=[];
  if(warrantyEligible!==false&&contractExclusions.length){if(!evidenceClaims.has('EXCLUSION_FACTS')){flags.push('EXCLUSION_ASSESSMENT_MISSING');reasons.push('EXCLUSION_ASSESSMENT_MISSING');}else{const observed=new Set((evidenceFacts.exclusionTags||[]).map(x=>String(x).trim().toUpperCase()));exclusionMatches=contractExclusions.filter(x=>observed.has(String(x).trim().toUpperCase()));if(exclusionMatches.length)flags.push('CONTRACT_EXCLUSION_MATCH');}}
  const nffLiable=contract?.rules?.noFaultFoundSupplierLiable;
  if(d.responsibility==='NO_FAULT_FOUND'&&nffLiable==null){flags.push('NO_FAULT_FOUND_RULE_UNKNOWN');reasons.push('NO_FAULT_FOUND_RULE_UNKNOWN');}
  if(reasons.length)return unknown(d.id,amount,currency,flags,reasons);
  let supported=amount;
  const nffZero=d.responsibility==='NO_FAULT_FOUND'&&nffLiable===false;
  const hardZero=(warrantyEligible===false)||exclusionMatches.length>0||(d.wrongPart===true&&!!d.part)||(d.wrongProgram===true&&!!d.program)||(d.wrongAsset===true&&!!d.asset)||d.wrongCustomer===true||duplicateTrusted||d.responsibility==='CUSTOMER'||d.responsibility==='THIRD_PARTY'||nffZero;
  if(warrantyEligible===false)flags.push('OUTSIDE_WARRANTY');
  if(duplicateTrusted)flags.push('DUPLICATE_CONFIRMED');
  if(d.responsibility==='NO_FAULT_FOUND')flags.push(nffLiable===true?'NO_FAULT_FOUND_SUPPLIER_LIABLE':'NO_FAULT_FOUND_NOT_SUPPLIER_LIABLE');
  if(exclusionMatches.length)flags.push(...exclusionMatches.map(x=>`EXCLUSION_${String(x).trim().toUpperCase().replace(/[^A-Z0-9]+/g,'_')}`));
  if(hardZero)supported=0;
  if(costEligible===false){flags.push('COST_INELIGIBLE');supported=0;}
  if(d.ineligibleCost!=null){const x=normalizeAmount(d.ineligibleCost);flags.push('INELIGIBLE_COST');supported=Math.max(0,supported-x);}
  if(d.costCap!=null){const cap=normalizeAmount(d.costCap);if(supported>cap){flags.push('COST_CAP');supported=cap;}}
  if(d.responsibility==='SHARED'){if(d.responsibilityShare===null||d.responsibilityShare===undefined||d.responsibilityShare==='')throw new Error('INVALID_RESPONSIBILITY_SHARE');const s=Number(d.responsibilityShare); if(!Number.isFinite(s)||s<0||s>1)throw new Error('INVALID_RESPONSIBILITY_SHARE'); supported*=s;} else if(d.responsibilityShare!=null && d.responsibility!=='SHARED') throw new Error('RESPONSIBILITY_SHARE_REQUIRES_SHARED');
  if(priorCreditAmount>0)flags.push('PRIOR_CREDIT_APPLIED');
  if(d.priorPayment!=null){normalizeAmount(d.priorPayment);flags.push('PRIOR_PAYMENT_OBSERVED');}
  const outstandingAmount=round2(Math.max(0,amount-priorCreditAmount));supported=round2(Math.min(supported,outstandingAmount));const disputable=round2(Math.max(0,outstandingAmount-supported));
  let state='SUPPORTED';if(outstandingAmount===0&&priorCreditAmount>0)state='RESOLVED';else if(supported===0&&outstandingAmount>0)state='DISPUTABLE';else if(disputable>0)state='PARTIALLY_SUPPORTED';
  return {id:d.id,amount,outstandingAmount,resolvedCredit:round2(priorCreditAmount),supported,disputable,state,confidence:'HIGH',currency,flags:[...new Set(flags)],unresolvedReasons:[]};
}
export function duplicateKey(r){return [r.tenantId,r.caseId||'',r.asset||'',r.part||'',r.failureDate||'',r.repairDate||'',r.invoice||'',normalizeAmount(r.amount),r.currency||''].join('|');}
export function findDuplicates(rows){const seen=new Map(),confirmed=[];for(const r of rows){const k=duplicateKey(r);if(seen.has(k))confirmed.push({originalId:seen.get(k),duplicateId:r.id,key:k});else seen.set(k,r.id);}return confirmed;}
export function findPotentialDuplicates(rows){const out=[];for(let i=0;i<rows.length;i++)for(let j=i+1;j<rows.length;j++){const a=rows[i],b=rows[j];if(a.tenantId!==b.tenantId)continue;const same=[a.caseId&&a.caseId===b.caseId,a.asset&&a.asset===b.asset,a.part&&a.part===b.part,a.invoice&&a.invoice===b.invoice].filter(Boolean).length;if(same>=2&&duplicateKey(a)!==duplicateKey(b))out.push({a:a.id,b:b.id,state:'POTENTIAL_DUPLICATE'});}return out;}
export function summarize(results){const byCurrency={};let unknown=0,resolved=0;for(const r of results){if(r.state==='UNKNOWN'){unknown++;continue;}if(r.state==='RESOLVED')resolved++;const b=byCurrency[r.currency]??={received:0,outstanding:0,resolvedCredit:0,supported:0,knownDisputable:0};b.received=round2(b.received+r.amount);b.outstanding=round2(b.outstanding+(r.outstandingAmount??r.amount));b.resolvedCredit=round2(b.resolvedCredit+(r.resolvedCredit??0));b.supported=round2(b.supported+r.supported);b.knownDisputable=round2(b.knownDisputable+r.disputable);}return {cases:results.length,unknown,resolved,byCurrency,mixedCurrency:Object.keys(byCurrency).length>1,grandTotal:Object.keys(byCurrency).length===1?Object.values(byCurrency)[0]:null};}
export function createDisputePackage(debit,analysis,{contract=null,evidence=[]}={}){if(analysis.state==='UNKNOWN'||analysis.state==='RESOLVED'||analysis.disputable<=0)return null;return {status:'DRAFT_REVIEW_REQUIRED',tenantId:debit.tenantId,debitId:debit.id,currency:analysis.currency,disputable:analysis.disputable,verifiedRecovery:0,flags:analysis.flags,contractId:contract?.id??null,contractSourceHash:contract?.sourceHash??null,evidence:[...evidence].map(e=>({id:e.id,contentHash:e.contentHash,factsHash:e.factsHash??null,claims:e.claims})),measurementBasis:'INCREMENTAL_VERIFIED_CREDIT_OR_CASH_ONLY'};}
export function reconcileRecovery({disputable,creditApproved=0,creditReceived=0,cashReceived=0,creditBasis=null,cashBasis=null}){const d=normalizeAmount(disputable),a=normalizeAmount(creditApproved),c=normalizeAmount(creditReceived),cash=normalizeAmount(cashReceived);if(a>d)throw new Error('APPROVED_EXCEEDS_DISPUTABLE');if(c>a)throw new Error('CREDIT_RECEIVED_EXCEEDS_APPROVED');if(c>0&&!creditBasis)throw new Error('CREDIT_BASIS_REQUIRED');if(cash>d)throw new Error('CASH_EXCEEDS_DISPUTABLE');if(cash>0&&!cashBasis)throw new Error('CASH_BASIS_REQUIRED');const verified=round2(Math.min(d,Math.max(c,cash)));return {disputable:d,creditApproved:a,creditReceived:c,cashReceived:cash,verifiedRecovery:verified,state:cash>0?'CASH_RECEIVED':c>0?'CREDIT_RECEIVED':a>0?'CREDIT_APPROVED':'NO_VERIFIED_RECOVERY'};}
