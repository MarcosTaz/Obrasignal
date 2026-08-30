import {analyzeDebit} from '../lib/engine.mjs';
import {makeEvidence} from '../lib/evidence.mjs';
import {ingestDocument,extractDocumentCandidates,approveClause,buildDocumentDossier} from '../lib/documents.mjs';
import {buildContractFromDocumentReview} from '../lib/rules.mjs';

const tenantId='doc-redteam',customer='OEM',ts='2026-08-29T20:00:00Z';
const text='Warranty applies to eligible parts.\n\nEligible warranty costs are reimbursable.\n\nClaims must be submitted within 30 calendar days after receipt.';
const document=ingestDocument({tenantId,id:'DOC-CLEAN-PROBE',fileName:'clean.txt',mimeType:'text/plain',receivedAt:ts,sourceText:text});
const extraction=extractDocumentCandidates(document);
const approvals=extraction.materialClauses.map(clause=>{
  let classification='CONDITION',effectiveRule=null;
  if(clause.kinds.includes('DEADLINE')){classification='DEADLINE';effectiveRule={kind:'NOTICE_DEADLINE',event:'DEBIT_RECEIPT',quantity:30,unit:'calendar days',dayType:'CALENDAR'};}
  else if(clause.kinds.includes('WARRANTY')&&clause.kinds.includes('COST')){classification='COST';effectiveRule={kind:'COST_ELIGIBLE',value:true};}
  else if(clause.kinds.includes('WARRANTY')){classification='WARRANTY';effectiveRule={kind:'WARRANTY_ELIGIBLE',value:true};}
  return approveClause(clause,{reviewer:'r',reviewedAt:ts,classification,effectiveRule});
});
const dossier=buildDocumentDossier(document,extraction,approvals);
const contract=buildContractFromDocumentReview({id:'CDOC-PROBE',tenantId,customer,effectiveFrom:'2026-01-01',document,dossier,approvedBy:'r',approvedAt:ts});
const debit={tenantId,id:'CLEAN-PROBE',customer,amount:1000,currency:'EUR',failureDate:'2026-06-01',part:'P1',program:'PR1',asset:'A1',rootCauseKnown:true,responsibility:'SUPPLIER',warrantyEligible:null,costEligible:null};
const evidence=[makeEvidence({id:'E-CLEAN-PROBE',tenantId,debitId:debit.id,claims:['ROOT_CAUSE','RESPONSIBILITY'],facts:{}})];
const result=analyzeDebit(debit,{contracts:[contract],evidence,requireContext:true});
console.log(JSON.stringify({probe:'CLEAN_WARRANTY',state:result.state,unresolvedReasons:result.unresolvedReasons,flags:result.flags,contractRules:contract.rules,dossierStatus:dossier.status}));
