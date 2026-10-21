import assert from 'node:assert/strict';
import {mkdtemp} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const dir=await mkdtemp(join(tmpdir(),'gr-v4-'));
process.env.GR_DATA_FILE=join(dir,'db.json');
process.env.GR_API_KEYS_JSON=JSON.stringify({'op-a':{tenantId:'tenant-a',role:'operator'},'rev-a':{tenantId:'tenant-a',role:'reviewer'},'op-b':{tenantId:'tenant-b',role:'operator'}});
const {server}=await import('./server_v4.mjs');
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const port=server.address().port;
const q=(p,o={})=>fetch(`http://127.0.0.1:${port}${p}`,o);
const h=k=>({authorization:`Bearer ${k}`,'content-type':'application/json'});
const meta=(type,src,payload={},ids={})=>({type,sourceRef:src,observedAt:'2026-08-29T00:00:00Z',projectId:ids.projectId||'P1',contractId:ids.contractId||'C1',payload});
async function post(path,key,b){const r=await q(path,{method:'POST',headers:h(key),body:JSON.stringify(b)});let j={};try{j=await r.json()}catch{}return[r,j]}
try{
  let r=await q('/'); assert.equal(r.status,200); assert.match(await r.text(),/Submitted ≠ approved ≠ verified outcome/);
  const base={instrumentId:'I1',company:'Alpha',projectId:'P1',contractId:'C1',instrumentType:'ADVANCE_PAYMENT_GUARANTEE',currency:'EUR',originalAmount:2000000,currentAmount:2000000}; let j;
  [r,j]=await post('/api/instruments','op-a',base); assert.equal(r.status,201); assert.equal(j.item.assessment.potentialReduction,0);
  [r,j]=await post('/api/instruments/I1/evidence','op-a',meta('REDUCTION_RULE','CONTRACT',{mode:'ADVANCE_REPAYMENT'})); assert.equal(r.status,201); const ruleId=j.evidence.id; assert.equal(j.evidence.reviewStatus,'PENDING'); assert.equal(j.item.assessment.potentialReduction,0,'pending rule cannot affect assessment');
  [r,j]=await post('/api/instruments/I1/evidence','op-a',meta('REPAYMENT','PAYCERT',{amount:1200000})); const repayId=j.evidence.id; assert.equal(j.item.assessment.potentialReduction,0,'pending repayment cannot affect assessment');
  [r,j]=await post(`/api/instruments/I1/evidence/${ruleId}/approve`,'op-a',{}); assert.equal(r.status,403,'operator cannot approve evidence');
  [r,j]=await post(`/api/instruments/I1/evidence/${ruleId}/approve`,'rev-a',{}); assert.equal(r.status,200); assert.equal(j.item.assessment.potentialReduction,0,'one approved evidence item is insufficient');
  [r,j]=await post(`/api/instruments/I1/evidence/${repayId}/approve`,'rev-a',{}); assert.equal(j.item.assessment.state,'REDUCTION_EVIDENCE_SUPPORTED'); assert.equal(j.item.assessment.potentialReduction,1200000);
  [r,j]=await post('/api/instruments/I1/evidence','op-a',meta('REPAYMENT','WRONG',{amount:1500000},{projectId:'P-X'})); const wrongId=j.evidence.id; assert.equal(j.item.assessment.state,'UNKNOWN','unrejected identity mismatch fails closed');
  [r,j]=await post(`/api/instruments/I1/evidence/${wrongId}/approve`,'rev-a',{}); assert.equal(r.status,409,'reviewer cannot approve mismatched evidence');
  [r,j]=await post(`/api/instruments/I1/evidence/${wrongId}/reject`,'rev-a',{note:'wrong project'}); assert.equal(r.status,200); assert.equal(j.item.assessment.state,'REDUCTION_EVIDENCE_SUPPORTED','rejecting mismatch restores prior approved truth');
  [r,j]=await post('/api/instruments/I1/evidence','op-a',meta('BANK_CANCELLATION','BANK-CANCEL',{amount:2000000})); const cancelId=j.evidence.id; assert.equal(j.item.assessment.state,'REDUCTION_EVIDENCE_SUPPORTED','pending cancellation cannot create verified cancellation');
  [r,j]=await post(`/api/instruments/I1/evidence/${cancelId}/approve`,'rev-a',{}); assert.equal(j.item.assessment.state,'BANK_CANCELLED'); assert.equal(j.item.assessment.collateralReleased,0);
  [r,j]=await post('/api/instruments/I1/evidence','op-a',meta('COLLATERAL_RELEASE','BANK-STMT',{amount:300000})); const collId=j.evidence.id; assert.equal(j.item.assessment.state,'BANK_CANCELLED');
  [r,j]=await post(`/api/instruments/I1/evidence/${collId}/approve`,'rev-a',{}); assert.equal(j.item.assessment.state,'VERIFIED_RELEASE'); assert.equal(j.item.assessment.collateralReleased,300000);
  r=await q('/api/instruments/I1',{headers:h('op-b')}); assert.equal(r.status,404);
  r=await q('/api/audit',{headers:h('op-b')}); j=await r.json(); assert.equal(j.items.length,0);
  [r,j]=await post('/api/instruments/I1/evidence','op-a',{...meta('REPAYMENT','X',{amount:1}),reviewStatus:'APPROVED'}); assert.equal(r.status,400,'client cannot forge review state');
  [r,j]=await post(`/api/instruments/I1/evidence/${collId}/approve`,'rev-a',{}); assert.equal(r.status,409,'review is one-time/idempotent boundary');
  console.log('PASS 20/20 reviewer-authority assertions');
} finally {
  await new Promise(r=>server.close(r));
}
