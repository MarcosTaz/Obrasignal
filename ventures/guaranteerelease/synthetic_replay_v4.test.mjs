import assert from 'node:assert/strict';
import {mkdtemp} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const d=await mkdtemp(join(tmpdir(),'gr-replay-'));
process.env.GR_DATA_FILE=join(d,'db.json');
process.env.GR_API_KEYS_JSON=JSON.stringify({'op':{tenantId:'oracle',role:'operator'},'rev':{tenantId:'oracle',role:'reviewer'}});
const {server}=await import('./server_v4.mjs');
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const port=server.address().port;
const H=k=>({authorization:`Bearer ${k}`,'content-type':'application/json'});
async function api(path,key='op',method='GET',body){const r=await fetch(`http://127.0.0.1:${port}${path}`,{method,headers:H(key),body:body===undefined?undefined:JSON.stringify(body)});const j=await r.json();assert.ok(r.ok,`${method} ${path}: ${r.status} ${JSON.stringify(j)}`);return j}
const at='2026-08-29T00:00:00Z';
async function create(c){return (await api('/api/instruments','op','POST',c)).item}
async function evidence(id,projectId,contractId,type,sourceRef,payload={},override={}){const e={type,sourceRef,observedAt:at,projectId,contractId,payload,...override};return (await api(`/api/instruments/${id}/evidence`,'op','POST',e)).evidence}
async function approve(id,eid){return (await api(`/api/instruments/${id}/evidence/${eid}/approve`,'rev','POST',{})).item}
async function get(id){return (await api(`/api/instruments/${id}`)).item}
try{
 const bases=[
  {instrumentId:'GR-001',company:'ALPHA EPC',projectId:'P1',contractId:'C1',instrumentType:'ADVANCE_PAYMENT_GUARANTEE',currency:'EUR',originalAmount:2000000,currentAmount:2000000},
  {instrumentId:'GR-002',company:'NOVA CONSTRUCTION',projectId:'P2',contractId:'C2',instrumentType:'PERFORMANCE_BOND',currency:'GBP',originalAmount:1000000,currentAmount:1000000},
  {instrumentId:'GR-003',company:'TITAN ENERGY',projectId:'P3',contractId:'C3',instrumentType:'WARRANTY_GUARANTEE',currency:'EUR',originalAmount:750000,currentAmount:750000},
  {instrumentId:'GR-004',company:'PRIME INFRASTRUCTURE',projectId:'P4',contractId:'C4',instrumentType:'PERFORMANCE_GUARANTEE',currency:'AUD',originalAmount:1500000,currentAmount:1500000,expiryDate:'2026-01-01T00:00:00Z'},
  {instrumentId:'GR-005',company:'LEGACY INDUSTRIAL',projectId:'P5',contractId:'C5',instrumentType:'RETENTION_GUARANTEE',currency:'EUR',originalAmount:600000,currentAmount:0},
  {instrumentId:'GR-006',company:'REDTEAM CONTRACTING',projectId:'P6',contractId:'C6',instrumentType:'ADVANCE_PAYMENT_GUARANTEE',currency:'EUR',originalAmount:900000,currentAmount:900000},
  {instrumentId:'GR-007',company:'ALPHA EPC',projectId:'P7',contractId:'C7',instrumentType:'PERFORMANCE_GUARANTEE',currency:'EUR',originalAmount:1250000,currentAmount:1250000}
 ];
 for(const b of bases)await create(b);
 let e1=await evidence('GR-001','P1','C1','REDUCTION_RULE','C1-clause',{mode:'ADVANCE_REPAYMENT'}),e2=await evidence('GR-001','P1','C1','REPAYMENT','PC7',{amount:1200000});await approve('GR-001',e1.id);await approve('GR-001',e2.id);
 let a=await get('GR-001');assert.equal(a.assessment.state,'REDUCTION_EVIDENCE_SUPPORTED');assert.equal(a.assessment.potentialReduction,1200000);
 e1=await evidence('GR-002','P2','C2','REDUCTION_RULE','C2-clause',{mode:'MILESTONE_PERCENT',percent:50});e2=await evidence('GR-002','P2','C2','MILESTONE','PC',{achieved:true});await approve('GR-002',e1.id);await approve('GR-002',e2.id);a=await get('GR-002');assert.equal(a.assessment.state,'REDUCTION_EVIDENCE_SUPPORTED');assert.equal(a.assessment.potentialReduction,500000);
 e1=await evidence('GR-003','P3','C3','BLOCKER','defect-notice',{kind:'VALID_OPEN_DEFECT'});await approve('GR-003',e1.id);a=await get('GR-003');assert.equal(a.assessment.state,'RELEASE_NOT_YET_DUE');assert.equal(a.assessment.potentialRelease,0);
 e1=await evidence('GR-004','P4','C4','RELEASE_CONDITION','C4-final-cert',{});e2=await evidence('GR-004','P4','C4','RELEASE_EVENT','final-cert',{occurred:true});await approve('GR-004',e1.id);await approve('GR-004',e2.id);a=await get('GR-004');assert.equal(a.assessment.state,'RELEASE_EVIDENCE_SUPPORTED');assert.equal(a.assessment.potentialRelease,1500000);assert.equal(a.assessment.verifiedRelease,0);
 e1=await evidence('GR-005','P5','C5','BANK_CANCELLATION','bank-cancel',{amount:600000});e2=await evidence('GR-005','P5','C5','COLLATERAL_RELEASE','bank-statement',{amount:300000});await approve('GR-005',e1.id);await approve('GR-005',e2.id);a=await get('GR-005');assert.equal(a.assessment.state,'VERIFIED_RELEASE');assert.equal(a.assessment.verifiedRelease,600000);assert.equal(a.assessment.collateralReleased,300000);
 e1=await evidence('GR-006','P6','C6','REPAYMENT','wrong-project',{amount:500000},{projectId:'P-WRONG'});a=await get('GR-006');assert.equal(a.assessment.state,'UNKNOWN');assert.equal(a.assessment.potentialReduction,0);
 a=await get('GR-007');assert.equal(a.assessment.state,'REDUCTION_NOT_YET_DUE');assert.equal(a.assessment.potentialReduction,0);assert.equal(a.assessment.potentialRelease,0);
 const list=(await api('/api/instruments')).items;assert.equal(list.length,7);const audit=(await api('/api/audit')).items;assert.ok(audit.length>=25);
 console.log('PASS 23/23 synthetic reviewed-evidence replay assertions');
}finally{await new Promise(r=>server.close(r))}
