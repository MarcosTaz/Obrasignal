#!/usr/bin/env node
import {readFile,writeFile} from 'node:fs/promises';
import {resolve,dirname,relative,isAbsolute} from 'node:path';
import {sourceFileToDocument} from './native_document_adapter_v2.mjs';
import {extractDocuments} from './document_pipeline_v3.mjs';

const [,,manifestPath,outputPath]=process.argv;
if(!manifestPath){console.error('Usage: node case_intake_cli_v1.mjs manifest.json [output.json]');process.exit(2)}
const manifestAbs=resolve(manifestPath),root=dirname(manifestAbs);
const manifest=JSON.parse(await readFile(manifestAbs,'utf8'));
if(!manifest||typeof manifest!=='object'||!Array.isArray(manifest.documents)||!manifest.documents.length)throw Error('manifest documents required');
if(manifest.documents.length>50)throw Error('manifest document limit exceeded');
const resolveInsideRoot=(raw)=>{
  if(typeof raw!=='string'||!raw.trim())throw Error('manifest document path required');
  if(isAbsolute(raw))throw Error('absolute document paths are not allowed');
  const target=resolve(root,raw),rel=relative(root,target);
  if(rel===''||rel.startsWith('..')||isAbsolute(rel))throw Error('document path escapes manifest directory');
  return target;
};
const documents=[];
for(const d of manifest.documents){
  if(!d||typeof d!=='object')throw Error('manifest document invalid');
  const path=resolveInsideRoot(d.path);
  documents.push(await sourceFileToDocument(path,{documentId:d.documentId,type:d.type,sourceName:d.sourceName,supersedes:d.supersedes||[],metadata:d.metadata||{},ocrFallback:d.ocrFallback??manifest.ocrFallback??false}));
}
const extraction=extractDocuments(documents);
const packet={caseId:manifest.caseId,asOf:manifest.asOf,documents,extractionSummary:{documentCount:extraction.documents.length,factCount:extraction.facts.length,ocrFactCount:extraction.facts.filter(f=>f.confidence==='OCR_UNVERIFIED').length,duplicateGroups:extraction.duplicateGroups}};
const text=JSON.stringify(packet,null,2)+'\n';
if(outputPath)await writeFile(outputPath,text,'utf8');else process.stdout.write(text);
