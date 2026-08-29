import {parseIsoDate,parseIsoTimestamp,requiredText,sha256,stableStringify} from './utils.mjs';
export function verifyContract(c,tenantId){
  if(!c)return {ok:false,reason:'CONTRACT_MISSING'};
  if(c.tenantId!==tenantId)return {ok:false,reason:'TENANT_MISMATCH'};
  try{requiredText(c.id,'contractId');requiredText(c.customer,'customer');parseIsoDate(c.effectiveFrom);if(c.effectiveTo)parseIsoDate(c.effectiveTo);requiredText(c.approvedBy,'approvedBy');parseIsoTimestamp(c.approvedAt);}
  catch(e){return {ok:false,reason:e.message};}
  if(!c.sourceText||sha256(c.sourceText)!==c.sourceHash)return {ok:false,reason:'CONTRACT_SOURCE_HASH_MISMATCH'};
  if(!c.rules||sha256(stableStringify(c.rules))!==c.rulesHash)return {ok:false,reason:'APPROVED_RULES_TAMPERED'};
  for(const k of ['warrantyEligible','costEligible','noFaultFoundSupplierLiable'])if(Object.hasOwn(c.rules||{},k)&&typeof c.rules[k]!=='boolean')return {ok:false,reason:`CONTRACT_RULE_TYPE_${k.toUpperCase()}`};
  if(Object.hasOwn(c.rules||{},'noticeDeadline')){const r=c.rules.noticeDeadline;if(!r||typeof r!=='object'||Array.isArray(r))return {ok:false,reason:'CONTRACT_RULE_TYPE_NOTICEDEADLINE'};if(typeof r.event!=='string'||!r.event.trim())return {ok:false,reason:'CONTRACT_RULE_NOTICEDEADLINE_EVENT'};if(!Number.isInteger(r.quantity)||r.quantity<0||r.quantity>3650)return {ok:false,reason:'CONTRACT_RULE_NOTICEDEADLINE_QUANTITY'};if(typeof r.unit!=='string'||!r.unit.trim())return {ok:false,reason:'CONTRACT_RULE_NOTICEDEADLINE_UNIT'};if(!['CALENDAR','BUSINESS','UNSPECIFIED_DAY_TYPE'].includes(r.dayType))return {ok:false,reason:'CONTRACT_RULE_NOTICEDEADLINE_DAYTYPE'};}
  if(Object.hasOwn(c.rules||{},'exclusionTags')){const x=c.rules.exclusionTags;if(!Array.isArray(x)||x.some(v=>typeof v!=='string'||!v.trim()))return {ok:false,reason:'CONTRACT_RULE_TYPE_EXCLUSIONTAGS'};}
  return {ok:true};
}
export function selectContract(contracts,debit){
  if(!Array.isArray(contracts))return {ok:false,reason:'CONTRACTS_REQUIRED'};
  const matches=contracts.filter(c=>c.tenantId===debit.tenantId&&c.customer===debit.customer&&c.effectiveFrom<=debit.failureDate&&(!c.effectiveTo||debit.failureDate<c.effectiveTo));
  if(matches.length===0)return {ok:false,reason:'CONTRACT_NOT_FOUND'};
  if(matches.length>1)return {ok:false,reason:'CONTRACT_AMBIGUOUS'};
  const c=matches[0],v=verifyContract(c,debit.tenantId); return v.ok?{ok:true,contract:c}:v;
}
export function makeContract({id,tenantId,customer,effectiveFrom,effectiveTo=null,rules={},sourceText='synthetic contract',approvedBy='synthetic-reviewer',approvedAt='2026-08-29T00:00:00Z'}){
  return {id,tenantId,customer,effectiveFrom,effectiveTo,rules,sourceText,sourceHash:sha256(sourceText),rulesHash:sha256(stableStringify(rules)),approvedBy,approvedAt};
}
