import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {extractDocuments,reviewExtraction,buildCaseAssessment,buildDossier,dossierMarkdown} from './document_pipeline_v2.mjs';
const corpus=JSON.parse(await readFile(new URL('./SYNTHETIC_DOCUMENT_CORPUS_V1.json',import.meta.url),'utf8'));
let pass=0;
for(const c of corpus.cases){
 const e=extractDocuments(c.documents);
 const decisions=Object.fromEntries(e.facts.map(f=>[f.factId,'APPROVED']));
 const reviewed=reviewExtraction(e,decisions);
 const result=buildCaseAssessment(reviewed,{asOf:'2026-08-29T12:00:00Z'});
 for(const [k,v] of Object.entries(c.expected)){assert.equal(result.assessment[k],v,`${c.id} ${k}`);pass++;}
 const dossier=buildDossier(result),md=dossierMarkdown(dossier);
 assert.equal(dossier.executiveSummary.state,c.expected.state,`${c.id} dossier state`);pass++;
 assert.ok(md.includes('## Evidence')&&md.includes('## Recommended Next Action'),`${c.id} dossier sections`);pass++;
 if(c.expected.state==='UNKNOWN'){assert.equal(dossier.executiveSummary.confidence,'UNKNOWN',`${c.id} unknown confidence`);pass++;}
}
console.log(`PASS ${pass}/${pass} independent document-corpus assertions`);
