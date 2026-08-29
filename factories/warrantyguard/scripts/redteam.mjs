import assert from 'node:assert/strict';import {analyzeDebit,reconcileRecovery,findDuplicates} from '../lib/engine.mjs';import {makeContract} from '../lib/contracts.mjs';import {makeEvidence} from '../lib/evidence.mjs';
let seed=0xC0FFEE;const rnd=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/2**32};let unknown=0,known=0;
for(let i=0;i<10000;i++){
 const tenantId=`t${i%17}`,id=`D${i}`,customer='OEM',missing=i%13===0;const responsibility=i%11===0?'CUSTOMER':i%5===0?'SHARED':'SUPPLIER';const d={tenantId,id,customer,amount:Math.round(rnd()*1e7)/100,currency:i%19===0?'USD':'EUR',failureDate:'2026-06-01',part:missing?null:`P${i%31}`,program:`PR${i%7}`,asset:`A${i}`,rootCauseKnown:i%23!==0,responsibility,responsibilityShare:responsibility==='SHARED'?.5:null,warrantyEligible:i%29!==0,costEligible:i%37!==0};
 const c=makeContract({id:`C-${tenantId}`,tenantId,customer,effectiveFrom:'2026-01-01',rules:{warrantyEligible:true,costEligible:true},sourceText:`s-${tenantId}`});const claims=['WARRANTY','COST_ELIGIBILITY'];if(d.rootCauseKnown)claims.push('ROOT_CAUSE');if(d.responsibility)claims.push('RESPONSIBILITY');const e=makeEvidence({id:`E${i}`,tenantId,debitId:id,claims});
 const a=analyzeDebit(d,{contracts:[c],evidence:[e],requireContext:true});
 assert.ok(['SUPPORTED','PARTIALLY_SUPPORTED','DISPUTABLE','UNKNOWN'].includes(a.state));
 if(a.state==='UNKNOWN'){unknown++;assert.equal(a.supported,null);assert.equal(a.disputable,null);}else{known++;assert.ok(a.supported>=0&&a.supported<=a.amount);assert.ok(a.disputable>=0&&a.disputable<=a.amount);assert.ok(Math.abs((a.supported+a.disputable)-a.amount)<0.011);}
}
assert.ok(unknown>0&&known>0,'REDTEAM_MUST_EXERCISE_UNKNOWN_AND_KNOWN_STATES');
assert.equal(findDuplicates([{tenantId:'a',id:'1',caseId:'x',asset:'a',part:'p',failureDate:'2026-01-01',amount:1,currency:'EUR'},{tenantId:'b',id:'2',caseId:'x',asset:'a',part:'p',failureDate:'2026-01-01',amount:1,currency:'EUR'}]).length,0);
for(let i=0;i<1000;i++){const d=Math.round(rnd()*100000)/100,a=Math.round(rnd()*d*100)/100,c=Math.round(rnd()*a*100)/100;const r=reconcileRecovery({disputable:d,creditApproved:a,creditReceived:c,creditBasis:c?'R':null});assert.ok(r.verifiedRecovery<=d);}
console.log(JSON.stringify({ok:true,cases:10000,unknown,known,recoveryCases:1000,seed:'0xC0FFEE'}));
