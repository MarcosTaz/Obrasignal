export {DOCUMENT_TYPES,ingestDocument} from './document_ingest_v1.mjs';
export {extractDocuments} from './document_extract_v1.mjs';
export {reviewExtraction,buildCaseAssessment} from './case_assessment_v1.mjs';
export {buildDossier,dossierMarkdown} from './dossier_v2.mjs';
import {extractDocuments} from './document_extract_v1.mjs';import {reviewExtraction,buildCaseAssessment} from './case_assessment_v1.mjs';import {buildDossier,dossierMarkdown} from './dossier_v2.mjs';
export function processCase({documents,reviewDecisions,asOf}){const extraction=extractDocuments(documents),reviewed=reviewExtraction(extraction,reviewDecisions),result=buildCaseAssessment(reviewed,{asOf}),dossier=buildDossier(result);return{extraction,reviewed,result,dossier,markdown:dossierMarkdown(dossier)}}
