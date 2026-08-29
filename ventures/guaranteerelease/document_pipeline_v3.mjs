import {extractDocuments as extractV2,reviewExtraction,buildCaseAssessment,buildDossier,dossierMarkdown} from './document_pipeline_v2.mjs';
export {DOCUMENT_TYPES,ingestDocument} from './document_pipeline_v2.mjs';
export {reviewExtraction,buildCaseAssessment,buildDossier,dossierMarkdown};
export function extractDocuments(documents){const out=extractV2(documents),meta=new Map(out.documents.map(d=>[d.documentId,d.metadata||{}]));out.facts=out.facts.map(f=>{const c=meta.get(f.provenance.documentId)?.confidenceClass;return c?{...f,confidence:c}:f});out.extractionVersion='document-pipeline-v3';return out}
export function processCase({documents,reviewDecisions,asOf}){const extraction=extractDocuments(documents),reviewed=reviewExtraction(extraction,reviewDecisions),result=buildCaseAssessment(reviewed,{asOf}),dossier=buildDossier(result);return{extraction,reviewed,result,dossier,markdown:dossierMarkdown(dossier)}}
