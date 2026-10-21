import assert from 'node:assert/strict';
import {mkdtemp,writeFile,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
const d=await mkdtemp(join(tmpdir(),'gr-cli-'));
const input=join(d,'input.json'),extracted=join(d,'extracted.json'),assessed=join(d,'assessed.json'),dossier=join(d,'dossier.json');
const documents=[
 {documentId:'g1',type:'SECURITY_INSTRUMENT',pages:[{pageNumber:1,text:'Project ID: P1\nContract ID: C1\nGuarantee No: APG-1\nInstrument Type: ADVANCE_PAYMENT_GUARANTEE\nOriginal Amount: EUR 100,000\nCurrent Amount: EUR 100,000'}]},
 {documentId:'c1',type:'CONTRACT',pages:[{pageNumber:1,text:'Project ID: P1\nContract ID: C1\nThe guarantee may be progressively reduced by certified advance repayment.'}]},
 {documentId:'p1',type:'PAYMENT_CERTIFICATE',pages:[{pageNumber:1,text:'Project ID: P1\nContract ID: C1\nCertified Advance Repaid To Date: EUR 40,000'}]}
];
await writeFile(input,JSON.stringify({documents},null,2));
let r=spawnSync(process.execPath,['case_cli_v2.mjs','extract',input,extracted],{cwd:new URL('.',import.meta.url),encoding:'utf8'});assert.equal(r.status,0,r.stderr);
const e=JSON.parse(await readFile(extracted,'utf8'));assert.ok(e.facts.length>=10);
const decisions=Object.fromEntries(e.facts.map(f=>[f.factId,'APPROVED']));
await writeFile(input,JSON.stringify({extraction:e,reviewDecisions:decisions,asOf:'2026-08-29T12:00:00Z'},null,2));
r=spawnSync(process.execPath,['case_cli_v2.mjs','assess',input,assessed],{cwd:new URL('.',import.meta.url),encoding:'utf8'});assert.equal(r.status,0,r.stderr);
const a=JSON.parse(await readFile(assessed,'utf8'));assert.equal(a.result.assessment.state,'REDUCTION_EVIDENCE_SUPPORTED');assert.equal(a.result.assessment.potentialReduction,40000);
r=spawnSync(process.execPath,['case_cli_v2.mjs','dossier',input,dossier],{cwd:new URL('.',import.meta.url),encoding:'utf8'});assert.equal(r.status,0,r.stderr);
const z=JSON.parse(await readFile(dossier,'utf8'));assert.ok(z.markdown.includes('EUR 40,000'));assert.ok(z.markdown.includes('SHA-256'));assert.ok(z.dossier.truthBoundary.includes('No external action is authorized'));
console.log('PASS 8/8 case CLI assertions');
