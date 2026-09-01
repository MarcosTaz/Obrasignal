import assert from 'node:assert/strict';
import {ingestDocument,extractDocumentCandidates,approveClause,buildDocumentDossier} from '../lib/documents.mjs';
import {buildContractFromDocumentReview} from '../lib/rules.mjs';
import {makeEvidence} from '../lib/evidence.mjs';
import {analyzeDebit} from '../lib/engine.mjs';
import {buildCaseDossier} from '../lib/case.mjs';
import {createWorkspace,addCase,sealWorkspace,openWorkspace,recordOutcome,verifyWorkspace} from '../lib/workspace.mjs';
import {createBillingSandbox,markOfferReady,recordAcceptanceEvidence,draftInvoiceRecord,recordPaymentEvidence,reviewPaymentEvidence,verifyBillingSandbox} from '../lib/billing.mjs';
import {createSupportTicket,acknowledgeTicket,resolveTicket,verifySupportTicket} from '../lib/support.mjs';
import {buildOperatorQueue} from '../lib/monitoring.mjs';
import {sha256} from '../lib/utils.mjs';

const tenantId='journey-tenant',customer='OEM-1',reviewer='journey-reviewer';
const receivedAt='2026-08-29T20:00:00Z';
const sourceText=[
  'Warranty applies to eligible supplied parts.',
  'Eligible warranty costs are chargeable to the responsible supplier.',
  'Claims must be submitted within 30 calendar days after receipt.',
  'This warranty does not cover misuse.'
].join('\n\n');

const document=ingestDocument({tenantId,id:'DOC-J1',fileName:'warranty.txt',mimeType:'text/plain',receivedAt,sourceText});
const extraction=extractDocumentCandidates(document);
assert.equal(extraction.legalConclusion,false);
assert.equal(extraction.status,'CANDIDATES_ONLY');
const approvals=extraction.materialClauses.map(c=>{
  let effectiveRule=null,classification=c.kinds[0]||'IRRELEVANT';
  if(c.text.includes('Warranty applies')){classification='WARRANTY';effectiveRule={kind:'WARRANTY_ELIGIBLE',value:true};}
  else if(c.text.includes('Eligible warranty costs')){classification='COST';effectiveRule={kind:'COST_ELIGIBLE',value:true};}
  else if(c.text.includes('within 30 calendar days')){classification='DEADLINE';effectiveRule={kind:'NOTICE_DEADLINE',event:'DEBIT_RECEIPT',quantity:30,unit:'calendar days',dayType:'CALENDAR'};}
  else if(c.text.includes('does not cover misuse')){classification='EXCLUSION';effectiveRule={kind:'EXCLUSION_TAG',tag:'MISUSE'};}
  return approveClause(c,{reviewer,reviewedAt:'2026-08-29T20:05:00Z',classification,effectiveRule});
});
const documentDossier=buildDocumentDossier(document,extraction,approvals);
assert.equal(documentDossier.status,'DOCUMENT_REVIEW_COMPLETE');
const contract=buildContractFromDocumentReview({id:'CONTRACT-J1',tenantId,customer,effectiveFrom:'2026-01-01',document,dossier:documentDossier,approvedBy:reviewer,approvedAt:'2026-08-29T20:06:00Z'});
assert.equal(contract.rules.warrantyEligible,true);
assert.equal(contract.rules.costEligible,true);
assert.equal(contract.rules.noticeDeadline.quantity,30);
assert.deepEqual(contract.rules.exclusionTags,['MISUSE']);

const debit={tenantId,id:'DEBIT-J1',customer,amount:1000,currency:'EUR',failureDate:'2026-08-15',part:'P-1',program:'PR-1',asset:'VIN-PSEUDO-1',rootCauseKnown:true,responsibility:'SUPPLIER',warrantyEligible:null,costEligible:null};
const evidence=[makeEvidence({id:'E-J1',tenantId,debitId:debit.id,claims:['ROOT_CAUSE','RESPONSIBILITY','EXCLUSION_FACTS'],facts:{exclusionTags:[]},content:'reviewed root-cause and exclusion assessment',reviewedBy:reviewer,reviewedAt:'2026-08-29T20:07:00Z'})];
const analysis=analyzeDebit(debit,{contracts:[contract],evidence,requireContext:true});
assert.equal(analysis.state,'SUPPORTED');
assert.equal(analysis.supported,1000);
assert.equal(analysis.disputable,0);

const caseDossier=buildCaseDossier({debit,analysis,contract,evidence,documentDossier,eventDates:{DEBIT_RECEIPT:'2026-08-20'},asOf:'2026-08-29'});
assert.equal(caseDossier.actionStatus,'NO_CHALLENGE_INDICATED');
assert.equal(caseDossier.deadline.state,'OPEN');
assert.equal(caseDossier.deadline.deadlineDate,'2026-09-19');
assert.equal(caseDossier.verifiedRecovery,0);

const workspace=createWorkspace({tenantId,id:'WS-J1',createdAt:'2026-08-29T20:08:00Z'});
addCase(workspace,caseDossier,{at:'2026-08-29T20:09:00Z',actor:'operator'});
recordOutcome(workspace,{debitId:debit.id,state:'CLOSED_NO_CHANGE',verifiedRecovery:0,currency:'EUR',at:'2026-08-29T20:10:00Z',actor:'operator'});
assert.equal(verifyWorkspace(workspace).ok,true);
const sealed=sealWorkspace(workspace,'synthetic-e2e-key');
const reopened=openWorkspace(sealed,'synthetic-e2e-key',tenantId);
assert.equal(reopened.cases[debit.id].dossier.caseDossierHash,caseDossier.caseDossierHash);

const queue=buildOperatorQueue({asOf:'2026-08-29',cases:[caseDossier],supportTickets:[]});
assert.equal(queue.externalNotificationsSent,0);
assert.equal(queue.mode,'OPERATOR_QUEUE_ONLY');
assert.equal(queue.alerts.length,0);

const billing=createBillingSandbox({tenantId,id:'BILL-J1',caseId:debit.id,currency:'EUR',amount:2500,pricingModel:'FIXED_DIAGNOSTIC',termsVersion:'pilot-v1',createdAt:'2026-08-29T20:11:00Z'});
markOfferReady(billing,{at:'2026-08-29T20:12:00Z'});
recordAcceptanceEvidence(billing,{evidenceHash:sha256('synthetic acceptance evidence'),at:'2026-08-29T20:13:00Z'});
draftInvoiceRecord(billing,{invoiceRef:'SANDBOX-INVOICE-J1',at:'2026-08-29T20:14:00Z'});
recordPaymentEvidence(billing,{amount:2500,evidenceHash:sha256('synthetic payment evidence'),at:'2026-08-29T20:15:00Z'});
reviewPaymentEvidence(billing,{reviewer,reviewedAt:'2026-08-29T20:16:00Z'});
assert.equal(verifyBillingSandbox(billing).ok,true);
assert.equal(billing.realExternalInvoice,false);
assert.equal(billing.realPayment,false);
assert.equal(billing.revenueRecognized,0);

const ticket=createSupportTicket({tenantId,id:'SUP-J1',caseId:debit.id,severity:'P2',category:'ANALYSIS_REVIEW',summary:'Synthetic journey review question',createdAt:'2026-08-29T20:17:00Z'});
acknowledgeTicket(ticket,{actor:'operator',at:'2026-08-29T20:18:00Z'});
resolveTicket(ticket,{actor:'operator',at:'2026-08-29T20:19:00Z',resolution:'Synthetic review completed'});
assert.equal(verifySupportTicket(ticket).ok,true);
assert.equal(ticket.externalMessageSent,false);

console.log(JSON.stringify({ok:true,mode:'SYNTHETIC_ASSISTED_E2E',marketValidation:false,realCustomer:false,realPayment:false,revenueRecognized:0,externalNotificationsSent:0,journey:['document','review','contract','analysis','dossier','save','return','outcome','monitoring','billing-sandbox','support']}));
