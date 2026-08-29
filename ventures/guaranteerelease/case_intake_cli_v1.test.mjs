import assert from 'node:assert/strict';
import {mkdtemp,writeFile,readFile,mkdir,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
const dir=await mkdtemp(join(tmpdir(),'gr-intake-'));
try{
  await mkdir(join(dir,'docs'));
  await writeFile(join(dir,'docs','guarantee.txt'),'Project ID: P1\nContract ID: C1\nGuarantee No: G1\nInstrument Type: PERFORMANCE_GUARANTEE\nOriginal Amount: EUR 10,000\nCurrent Amount: EUR 10,000');
  const manifest={caseId:'INTAKE-1',documents:[{path:'docs/guarantee.txt',documentId:'g1',type:'SECURITY_INSTRUMENT'}]};
  const manifestPath=join(dir,'manifest.json'),out=join(dir,'packet.json');await writeFile(manifestPath,JSON.stringify(manifest));
  let r=spawnSync(process.execPath,[new URL('./case_intake_cli_v1.mjs',import.meta.url).pathname,manifestPath,out],{encoding:'utf8'});assert.equal(r.status,0,r.stderr);const packet=JSON.parse(await readFile(out,'utf8'));assert.equal(packet.documents.length,1);assert.equal(packet.extractionSummary.documentCount,1);assert.ok(packet.extractionSummary.factCount>=6);assert.equal(packet.extractionSummary.ocrFactCount,0);assert.equal(packet.documents[0].sourceSha256.length,64);
  await writeFile(manifestPath,JSON.stringify({caseId:'BAD',documents:[{path:'../outside.txt',documentId:'x',type:'OTHER'}]}));r=spawnSync(process.execPath,[new URL('./case_intake_cli_v1.mjs',import.meta.url).pathname,manifestPath],{encoding:'utf8'});assert.notEqual(r.status,0);assert.match(r.stderr,/escapes manifest directory/);
  await writeFile(manifestPath,JSON.stringify({caseId:'BAD2',documents:[{path:'/tmp/absolute.txt',documentId:'x',type:'OTHER'}]}));r=spawnSync(process.execPath,[new URL('./case_intake_cli_v1.mjs',import.meta.url).pathname,manifestPath],{encoding:'utf8'});assert.notEqual(r.status,0);assert.match(r.stderr,/absolute document paths are not allowed/);
  console.log('PASS 9/9 case intake assertions');
}finally{await rm(dir,{recursive:true,force:true})}
