import {sha256,parseIsoTimestamp,requiredText} from './utils.mjs';
export function makeEvidence({id,tenantId,debitId,type='ROOT_CAUSE',content='synthetic evidence',claims=['ROOT_CAUSE'],reviewedBy='synthetic-reviewer',reviewedAt='2026-08-29T00:00:00Z',contradictory=false}){
  return {id,tenantId,debitId,type,content,contentHash:sha256(content),claims,reviewedBy,reviewedAt,contradictory};
}
export function verifyEvidenceBundle(items,debit){
  if(!Array.isArray(items)||items.length===0)return {ok:false,reason:'EVIDENCE_MISSING'};
  if(items.length>100)return {ok:false,reason:'EVIDENCE_ITEM_LIMIT'};
  const relevant=items.filter(e=>e.debitId===debit.id);
  if(!relevant.length)return {ok:false,reason:'EVIDENCE_NOT_LINKED'};
  for(const e of relevant){
    if(e.tenantId!==debit.tenantId)return {ok:false,reason:'TENANT_MISMATCH'};
    try{requiredText(e.id,'evidenceId');requiredText(e.reviewedBy,'reviewedBy');parseIsoTimestamp(e.reviewedAt);}catch(err){return {ok:false,reason:err.message};}
    if(!Array.isArray(e.claims)||e.claims.some(c=>typeof c!=='string'||!c.trim()))return {ok:false,reason:'EVIDENCE_CLAIMS_INVALID'};
    if(sha256(e.content||'')!==e.contentHash)return {ok:false,reason:'EVIDENCE_HASH_MISMATCH'};
    if(e.contradictory)return {ok:false,reason:'CONTRADICTORY_EVIDENCE'};
  }
  const claims=new Set(relevant.flatMap(e=>Array.isArray(e.claims)?e.claims:[]));
  if(debit.rootCauseKnown===true&&!claims.has('ROOT_CAUSE'))return {ok:false,reason:'ROOT_CAUSE_EVIDENCE_MISSING'};
  if(debit.responsibility&&!claims.has('RESPONSIBILITY'))return {ok:false,reason:'RESPONSIBILITY_EVIDENCE_MISSING'};
  return {ok:true,items:relevant,claims:[...claims]};
}
