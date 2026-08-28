import assert from 'node:assert/strict';
import {mkdtemp,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const dir=await mkdtemp(join(tmpdir(),'gr-test-'));
process.env.GR_DATA_FILE=join(dir,'db.json');
process.env.GR_API_KEYS_JSON=JSON.stringify({'key-a':'tenant-a','key-b':'tenant-b'});
const {server}=await import('./server.mjs');
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const port=server.address().port;
const req=(path,opts={})=>fetch(`http://127.0.0.1:${port}${path}`,opts);
const auth=(key,extra={})=>({authorization:`Bearer ${key}`,'content-type':'application/json',...extra});

try{
  let r=await req('/api/instruments'); assert.equal(r.status,401);
  const base={instrumentId:'A-1',company:'Alpha',projectId:'P1',contractId:'C1',instrumentType:'ADVANCE_PAYMENT_GUARANTEE',currency:'EUR',originalAmount:2000000,currentAmount:2000000,reductionMode:'ADVANCE_REPAYMENT',instrumentWordingSupportsReduction:true,repaymentEvidenceVerified:true,repaidToDate:1200000};
  r=await req('/api/instruments',{method:'POST',headers:auth('key-a'),body:JSON.stringify(base)});assert.equal(r.status,201);let j=await r.json();assert.equal(j.item.assessment.state,'REDUCTION_EVIDENCE_SUPPORTED');assert.equal(j.item.assessment.potentialReduction,1200000);assert.equal('tenantId' in j.item,false);
  r=await req('/api/instruments/A-1',{headers:auth('key-b')});assert.equal(r.status,404,'tenant B cannot read tenant A item');
  r=await req('/api/instruments',{headers:auth('key-b')});j=await r.json();assert.equal(j.items.length,0,'tenant B list is isolated');
  r=await req('/api/instruments/A-1',{method:'PATCH',headers:auth('key-a'),body:JSON.stringify({tenantId:'tenant-b'})});assert.equal(r.status,400,'tenant cannot be patched');
  r=await req('/api/instruments/A-1',{method:'PATCH',headers:auth('key-a'),body:JSON.stringify({bankCancelled:true,cancelledAmount:2000000})});assert.equal(r.status,200);j=await r.json();assert.equal(j.item.assessment.state,'BANK_CANCELLED');assert.equal(j.item.assessment.collateralReleased,0);
  r=await req('/api/instruments/A-1',{method:'PATCH',headers:auth('key-a'),body:JSON.stringify({collateralReleaseVerified:true,collateralReleasedAmount:300000})});assert.equal(r.status,200);j=await r.json();assert.equal(j.item.assessment.state,'VERIFIED_RELEASE');assert.equal(j.item.assessment.collateralReleased,300000);
  r=await req('/api/audit',{headers:auth('key-a')});j=await r.json();assert.equal(j.items.length,3);assert.deepEqual(j.items.map(x=>x.event),['INSTRUMENT_CREATED','INSTRUMENT_REASSESSED','INSTRUMENT_REASSESSED']);
  r=await req('/api/audit',{headers:auth('key-b')});j=await r.json();assert.equal(j.items.length,0,'audit is tenant isolated');
  const persisted=JSON.parse(await readFile(process.env.GR_DATA_FILE,'utf8'));assert.equal(persisted.instruments.length,1);assert.equal(persisted.instruments[0].tenantId,'tenant-a');assert.equal(persisted.audit.length,3);
  console.log('PASS 12/12 backend assertions');
} finally {
  await new Promise(r=>server.close(r));
}
