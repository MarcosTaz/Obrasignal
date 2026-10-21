#!/usr/bin/env node
import {readFile,writeFile} from 'node:fs/promises';
import {extractDocuments,reviewExtraction,buildCaseAssessment,buildDossier,dossierMarkdown} from './document_pipeline_v2.mjs';

const [,,cmd,inputPath,outputPath]=process.argv;
if(!['extract','assess','dossier'].includes(cmd)||!inputPath){
  console.error('Usage: node case_cli_v2.mjs <extract|assess|dossier> input.json [output]');
  process.exit(2);
}
const input=JSON.parse(await readFile(inputPath,'utf8'));
let output;
if(cmd==='extract'){
  output=extractDocuments(input.documents);
}else{
  const extraction=input.extraction||extractDocuments(input.documents);
  const reviewed=reviewExtraction(extraction,input.reviewDecisions||{});
  const result=buildCaseAssessment(reviewed,{asOf:input.asOf});
  if(cmd==='assess')output={reviewed,result};
  else{
    const dossier=buildDossier(result);
    output={reviewed,result,dossier,markdown:dossierMarkdown(dossier)};
  }
}
const text=JSON.stringify(output,null,2);
if(outputPath)await writeFile(outputPath,text+'\n','utf8');else process.stdout.write(text+'\n');
