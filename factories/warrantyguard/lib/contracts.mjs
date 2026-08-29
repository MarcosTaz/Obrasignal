import {parseIsoDate,requiredText,sha256,stableStringify} from './utils.mjs';
export function verifyContract(c,tenantId){
  if(!c)return {ok:false,reason:'CONTRACT_MISSING'};
  if(c.tenantId!==tenantId)return {ok:false,reason:'TENANT_MISMATCH'};
  try{requiredText(c.id,'contractId');requiredText(c.customer,'customer');parseIsoDate(c.effectiveFrom);if(c.effectiveTo)parseIsoDate(c.effectiveTo);requiredText(c.approvedBy,'approvedBy');requiredText(c.approvedAt,'approvedAt');}
  catch(e){return {ok:false,reason:e.message};}
  if(!c.sourceText||sha256(c.sourceText)!==c.sourceHash)return {ok:false,reason:'CONTRACT_SOURCE_HASH_MISMATCH'};
  if(!c.rules||sha256(stableStringify(c.rules))!==c.rulesHash)return {ok:false,reason:'APPROVED_RULES_TAMPERED'};
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
