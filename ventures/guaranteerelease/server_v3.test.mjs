import assert from 'node:assert/strict';
import {mkdtemp,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const dir=await mkdtemp(join(tmpdir(),'gr-v3-'));
process.env.GR_DATA_FILE=join(dir,'db.json');
process.env.GR_API_KEYS_JSON=JSON.stringify({'a-key':'tenant-a','b-key':'tenant-b'});
const {server}=await import('./server_v3.mjs');
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const port=server.address().port;
const req=(p,o={})=>fetch(`http://127.0.0.1:${port}${p}`,o);
const hdr=k=>({authorization:`Bearer ${k}`,'content-type':'application/json'});
const meta=(extra={})=>({sourceRef:'SRC-1',observedAt:'2026-08-29T00:00:00Z',projectId:'P1',contractId:'C1',...extra});

try{
  let r=await req('/'); assert.equal(r.status,200); let txt=await r.text(); assert.match(txt,/No checkbox can create verified truth/);
  const base={instrumentId:'I1',company:'Alpha',projectId:'P1',contractId:'C1',instrumentType:'ADVANCE_PAYMENT_GUARANTEE',currency:'EUR',originalAmount:2000000,currentAmount:2000000};
  r=await req('/api/instruments',{method:'POST',headers:hdr('a-key'),body:JSON.stringify({...base,bankCancelled:true})}); assert.equal(r.status,400,'direct verified truth field rejected');
  r=await req('/api/instruments',{method:'POST',headers:hdr('a-key'),body:JSON.stringify(base)}); assert.equal(r.status,201); let j=await r.json(); assert.equal(j.item.assessment.potentialReduction,0,'base creation fabricates no reduction');
  r=await req('/api/instruments/I1',{method:'PATCH',headers:hdr('a-key'),body:JSON.stringify({bankCancelled:true})}); assert.equal(r.status,400,'client cannot assert cancellation bool');
  const apg={reductionRuleEvidence:meta({sourceRef:'CONTRACT-CLAUSE',mode:'ADVANCE_REPAYMENT'}),repaymentEvidence:meta({sourceRef:'PAYCERT-7',amount:1200000})};
  r=await req('/api/instruments/I1',{method:'PATCH',headers:hdr('a-key'),body:JSON.stringify(apg)}); assert.equal(r.status,200); j=await r.json(); assert.equal(j.item.assessment.state,'REDUCTION_EVIDENCE_SUPPORTED'); assert.equal(j.item.assessment.potentialReduction,1200000);
  r=await req('/api/instruments/I1',{method:'PATCH',headers:hdr('a-key'),body:JSON.stringify({repaymentEvidence:{...meta({amount:1500000}),projectId:'WRONG'}})}); j=await r.json(); assert.equal(j.item.assessment.state,'UNKNOWN','wrong-project evidence fails closed');
  r=await req('/api/instruments/I1',{method:'PATCH',headers:hdr('a-key'),body:JSON.stringify({repaymentEvidence:meta({sourceRef:'PAYCERT-8',amount:1200000})})}); j=await r.json(); assert.equal(j.item.assessment.state,'REDUCTION_EVIDENCE_SUPPORTED');
  r=await req('/api/instruments/I1',{method:'PATCH',headers:hdr('a-key'),body:JSON.stringify({bankCancellationEvidence:meta({sourceRef:'BANK-CANCEL',amount:2000000})})}); j=await r.json(); assert.equal(j.item.assessment.state,'BANK_CANCELLED'); assert.equal(j.item.assessment.collateralReleased,0);
  r=await req('/api/instruments/I1',{method:'PATCH',headers:hdr('a-key'),body:JSON.stringify({collateralReleaseEvidence:meta({sourceRef:'BANK-STMT',amount:300000})})}); j=await r.json(); assert.equal(j.item.assessment.state,'VERIFIED_RELEASE'); assert.equal(j.item.assessment.collateralReleased,300000);
  r=await req('/api/instruments/I1',{headers:hdr('b-key')}); assert.equal(r.status,404,'tenant isolation');
  r=await req('/api/audit',{headers:hdr('b-key')}); j=await r.json(); assert.equal(j.items.length,0,'audit isolation');
  r=await req('/api/instruments',{method:'POST',headers:hdr('a-key'),body:JSON.stringify(base)}); assert.equal(r.status,409,'duplicate id idempotency boundary');
  r=await req('/api/instruments/I1',{method:'PATCH',headers:hdr('a-key'),body:'{bad'}); assert.equal(r.status,400,'malformed json rejected');
  const huge='x'.repeat(270000); r=await req('/api/instruments/I1',{method:'PATCH',headers:hdr('a-key'),body:JSON.stringify({note:huge})}); assert.equal(r.status,413,'oversized body rejected');
  const ps=await Promise.all(['I2','I3','I4','I5'].map(id=>req('/api/instruments',{method:'POST',headers:hdr('a-key'),body:JSON.stringify({...base,instrumentId:id})}))); assert.deepEqual(ps.map(x=>x.status),[201,201,201,201],'serialized concurrent writes succeed');
  const db=JSON.parse(await readFile(process.env.GR_DATA_FILE,'utf8')); assert.equal(db.instruments.length,5); assert.ok(db.audit.length>=8);
  console.log('PASS 19/19 evidence-authority + backend assertions');
} finally {
  await new Promise(r=>server.close(r));
}
