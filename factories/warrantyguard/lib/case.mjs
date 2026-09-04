import {sha256} from './utils.mjs';import {evaluateNoticeDeadline} from './deadlines.mjs';import {createDisputePackage} from './engine.mjs';
export function buildCaseDossier({debit,analysis,contract,evidence=[],documentDossier=null,eventDates={},asOf}){
  if(!debit?.id||analysis?.id!==debit.id)throw new Error('CASE_ANALYSIS_MISMATCH');if(!contract)throw new Error('CASE_CONTRACT_REQUIRED');
  const deadline=evaluateNoticeDeadline(contract,{eventDates,asOf});const pack=createDisputePackage(debit,analysis,{contract,evidence});let actionStatus='NO_CHALLENGE_INDICATED';
  const unresolved=[...(analysis.unresolvedReasons||[])];if(deadline.state==='UNKNOWN')unresolved.push(deadline.reason);
  if(unresolved.length)actionStatus='NEEDS_REVIEW';else if(deadline.state==='PASSED'&&analysis.disputable>0)actionStatus='DEADLINE_PASSED_REVIEW_REQUIRED';else if(pack)actionStatus='DRAFT_CHALLENGE_REVIEW';
  const dossier={tenantId:debit.tenantId,debitId:debit.id,analysis,deadline,actionStatus,unresolvedReasons:[...new Set(unresolved)],contract:{id:contract.id,sourceHash:contract.sourceHash,rulesHash:contract.rulesHash,documentSourceHash:contract.documentSourceHash||null,documentDossierHash:contract.documentDossierHash||null},evidence:evidence.map(e=>({id:e.id,contentHash:e.contentHash,claims:e.claims})),documentDossierHash:documentDossier?.dossierHash||null,disputePackage:pack,verifiedRecovery:0};
  return {...dossier,caseDossierHash:sha256(dossier)};
}
