import {requiredText,parseIsoTimestamp,sha256} from './utils.mjs';

export const REVIEW_STAGES=['ANALYSIS_REVIEW','DISPUTE_DRAFT_REVIEW','EXTERNAL_SUBMISSION_APPROVAL','RECOVERY_EVIDENCE_REVIEW','CASE_CLOSE'];
export const REVIEW_DECISIONS=['APPROVE','REJECT','RETURN_FOR_EVIDENCE','NO_ACTION','ACKNOWLEDGE'];

export function approvalRequirement({amount=0,currency='EUR',stage='DISPUTE_DRAFT_REVIEW',highValueThreshold=50000}={}){
  const a=Number(amount);if(!Number.isFinite(a)||a<0)throw new Error('INVALID_REVIEW_AMOUNT');if(!REVIEW_STAGES.includes(stage))throw new Error('INVALID_REVIEW_STAGE');
  const dual=stage==='EXTERNAL_SUBMISSION_APPROVAL'&&a>=highValueThreshold;
  return {stage,amount:a,currency,minimumReviewers:dual?2:1,segregationOfDuties:dual,externalEffect:stage==='EXTERNAL_SUBMISSION_APPROVAL',autoApprove:false};
}

export function makeReviewDecision({tenantId,caseId,stage,decision,actor,role='OPERATOR',at,rationale,evidenceHashes=[],previousDecisionHash=null}){
  const t=requiredText(tenantId,'tenantId'),c=requiredText(caseId,'caseId'),a=requiredText(actor,'actor'),r=requiredText(rationale,'rationale');parseIsoTimestamp(at);
  if(!REVIEW_STAGES.includes(stage))throw new Error('INVALID_REVIEW_STAGE');if(!REVIEW_DECISIONS.includes(decision))throw new Error('INVALID_REVIEW_DECISION');
  const unique=[...new Set(evidenceHashes.filter(Boolean))];if(['APPROVE','REJECT','RETURN_FOR_EVIDENCE'].includes(decision)&&!unique.length)throw new Error('REVIEW_EVIDENCE_REQUIRED');
  const body={tenantId:t,caseId:c,stage,decision,actor:a,role:String(role||'OPERATOR'),at,rationale:r,evidenceHashes:unique,previousDecisionHash:previousDecisionHash||null};return {...body,decisionHash:sha256(body)};
}

export function verifyReviewChain(decisions,{requirement=null}={}){
  if(!Array.isArray(decisions)||!decisions.length)return {ok:false,reason:'NO_REVIEW_DECISIONS'};
  const tenant=decisions[0].tenantId,caseId=decisions[0].caseId;let prev=null;const actors=new Set();
  for(const d of decisions){if(d.tenantId!==tenant||d.caseId!==caseId)return {ok:false,reason:'CROSS_CASE_OR_TENANT_REVIEW'};const {decisionHash,...body}=d;if(sha256(body)!==decisionHash)return {ok:false,reason:'REVIEW_HASH_MISMATCH'};if((d.previousDecisionHash||null)!==prev)return {ok:false,reason:'REVIEW_CHAIN_BREAK'};prev=d.decisionHash;if(d.decision==='APPROVE')actors.add(d.actor);}
  if(requirement?.minimumReviewers&&actors.size<requirement.minimumReviewers)return {ok:false,reason:'INSUFFICIENT_APPROVERS',required:requirement.minimumReviewers,observed:actors.size};
  return {ok:true,tenantId:tenant,caseId,lastDecisionHash:prev,approverCount:actors.size,externalEffectAuthorized:!!(requirement?.externalEffect&&actors.size>=requirement.minimumReviewers)};
}
