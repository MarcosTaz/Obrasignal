import {spawn} from 'node:child_process';
import assert from 'node:assert/strict';
import {createWorkspace,sealWorkspace,openWorkspace} from '../lib/workspace.mjs';

const port=43191,token='security-redteam-token',key='security-redteam-workspace-key';
const proc=spawn(process.execPath,['server.mjs'],{cwd:new URL('..',import.meta.url).pathname,env:{...process.env,PORT:String(port),DEBITPROOF_OPERATOR_TOKEN:token,DEBITPROOF_WORKSPACE_KEY:key},stdio:['ignore','pipe','pipe']});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const base=`http://127.0.0.1:${port}`;
const post=(path,body,headers={})=>fetch(base+path,{method:'POST',headers:{'content-type':'application/json',...headers},body:typeof body==='string'?body:JSON.stringify(body)});
try{
  await sleep(300);
  let r=await fetch(base+'/api/health');assert.equal(r.status,200);const healthText=await r.text();assert.ok(!healthText.includes(token));assert.ok(!healthText.includes(key));assert.equal(r.headers.get('x-frame-options'),'DENY');assert.equal(r.headers.get('x-content-type-options'),'nosniff');assert.ok((r.headers.get('content-security-policy')||'').includes("frame-ancestors 'none'"));
  r=await fetch(base+'/../package.json');assert.equal(r.status,404);
  r=await fetch(base+'/api/health',{method:'PUT'});assert.equal(r.status,404);
  r=await post('/api/analyze-context',{tenantId:'t1',csv:'x',contracts:[],evidence:[]},{'x-tenant-id':'t1'});assert.equal(r.status,401);
  r=await post('/api/analyze-context',{tenantId:'t1',csv:'x',contracts:[],evidence:[]},{'x-tenant-id':'t1','x-operator-token':'wrong'});assert.equal(r.status,401);
  r=await post('/api/analyze-context',{tenantId:'t1',csv:'x',contracts:[],evidence:[]},{'x-tenant-id':'evil','x-operator-token':token});assert.equal(r.status,403);
  const doc={tenantId:'t1',id:'D',fileName:'w.txt',mimeType:'text/plain',receivedAt:'2026-08-29T20:00:00Z',sourceText:'Warranty applies.'};
  r=await post('/api/document-candidates',{tenantId:'t1',document:doc},{'x-tenant-id':'evil','x-operator-token':token});assert.equal(r.status,403);
  r=await post('/api/operator-queue',{tenantId:'t1',asOf:'2026-08-29',cases:[],supportTickets:[{tenantId:'t2',id:'S',state:'OPEN',severity:'P0',category:'SECURITY'}]},{'x-tenant-id':'t1','x-operator-token':token});assert.equal(r.status,403);
  r=await post('/api/analyze','{"tenantId":');assert.equal(r.status,400);
  const huge=JSON.stringify({tenantId:'t1',csv:'x'.repeat(2_000_100)});r=await post('/api/analyze',huge,{'x-tenant-id':'t1'});assert.equal(r.status,413);
  r=await fetch(base+'/api/demo');assert.equal(r.status,200);const demo=await r.json();assert.equal(demo.synthetic,true);assert.ok(!JSON.stringify(demo).includes('realCustomer":true'));
  const w=createWorkspace({tenantId:'t1',id:'W1',createdAt:'2026-08-29T20:00:00Z'}),sealed=sealWorkspace(w,key);assert.throws(()=>openWorkspace(sealed,key,'t2'),/WORKSPACE_TENANT_MISMATCH/);const env=JSON.parse(sealed);env.payload.id='tampered';assert.throws(()=>openWorkspace(JSON.stringify(env),key,'t1'),/WORKSPACE_HASH_MISMATCH/);
  console.log(JSON.stringify({ok:true,mode:'ASSISTED_LOCAL_SECURITY_REDTEAM',publicSaaSProven:false,operatorAuth:'PASS',tenantIsolation:'PASS',payloadBound:'PASS',headers:'PASS',workspaceTamper:'PASS',secretReflection:'BLOCKED',externalSideEffects:0}));
}finally{proc.kill('SIGTERM');}
