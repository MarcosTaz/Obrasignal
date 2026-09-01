import {sha256,requiredText,parseIsoDate,parseIsoTimestamp} from './utils.mjs';

const TEXT_MIME=new Set(['text/plain','text/markdown','text/csv','application/json']);
const DOCX_MIME='application/vnd.openxmlformats-officedocument.wordprocessingml.document';
const KEYWORDS={
  WARRANTY:/\b(warrant(?:y|ies)|guarantee(?:s|d)?)\b/i,
  EXCLUSION:/\b(exclud(?:e|ed|es|ing)|exclusion|not covered|does not cover)\b/i,
  CONDITION:/\b(condition(?:s)?|provided that|subject to|only if|required to|must)\b/i,
  DEADLINE:/\b(within|no later than|not later than|before|deadline|days?|months?|years?)\b/i,
  NOTICE:/\b(notice|notify|notification|written notice|claim submission|submit(?:ted)?)\b/i,
  LIABILITY:/\b(liab(?:le|ility)|responsib(?:le|ility)|attribut(?:e|ion)|fault)\b/i,
  COST:/\b(costs?|charges?|debits?|credits?|reimburs(?:e|ed|es|ing|able|ement)|expenses?|amounts?)\b/i,
  PARTY:/\b(supplier|customer|buyer|seller|oem|manufacturer|party|parties)\b/i
};

function reviewedBinaryText(input,{kind,mode}){
  if(!input.sourceHash)throw new Error(`${kind}_SOURCE_HASH_REQUIRED`);
  const text=requiredText(input.reviewedExtractedText,'reviewedExtractedText');
  requiredText(input.reviewer,'reviewer');
  parseIsoTimestamp(input.reviewedAt);
  return {text,sourceHash:input.sourceHash,mode};
}

export function ingestDocument(input){
  if(!input||typeof input!=='object')throw new Error('MISSING_DOCUMENT');
  const tenantId=requiredText(input.tenantId,'tenantId');
  const id=requiredText(input.id,'id');
  const fileName=requiredText(input.fileName,'fileName');
  const mimeType=requiredText(input.mimeType,'mimeType').toLowerCase();
  const receivedAt=parseIsoTimestamp(input.receivedAt);
  let text='',mode='';let sourceHash=input.sourceHash||null;
  if(TEXT_MIME.has(mimeType)){
    text=requiredText(input.sourceText,'sourceText');sourceHash=sourceHash||sha256(text);mode='NATIVE_TEXT';
  }else if(mimeType==='application/pdf'){
    ({text,sourceHash,mode}=reviewedBinaryText(input,{kind:'PDF',mode:'HUMAN_REVIEWED_PDF_TEXT'}));
  }else if(mimeType===DOCX_MIME){
    ({text,sourceHash,mode}=reviewedBinaryText(input,{kind:'DOCX',mode:'HUMAN_REVIEWED_DOCX_TEXT'}));
  }else throw new Error('UNSUPPORTED_DOCUMENT_TYPE');
  return Object.freeze({tenantId,id,fileName,mimeType,receivedAt,sourceHash,textHash:sha256(text),text,mode,reviewer:input.reviewer||null,reviewedAt:input.reviewedAt||null,status:'INGESTED'});
}

function splitClauses(text){return text.replace(/\r/g,'').split(/\n{2,}|(?<=\.)\s+(?=[A-Z0-9])/).map((s,i)=>({index:i,text:s.trim()})).filter(x=>x.text);}
function dateCandidates(text){
  const out=[];let m;const iso=/\b(20\d{2}-\d{2}-\d{2})\b/g;while((m=iso.exec(text)))out.push({raw:m[1],normalized:parseIsoDate(m[1]),offset:m.index});
  const dmy=/\b([0-3]?\d)[\/-]([01]?\d)[\/-](20\d{2})\b/g;while((m=dmy.exec(text))){const d=String(Number(m[1])).padStart(2,'0'),mo=String(Number(m[2])).padStart(2,'0'),v=`${m[3]}-${mo}-${d}`;try{out.push({raw:m[0],normalized:parseIsoDate(v),offset:m.index});}catch{out.push({raw:m[0],normalized:null,offset:m.index,invalid:true});}}
  return out;
}
function deadlineCandidates(text){
  const out=[];const re=/\b(?:within|no later than|not later than)\s+(\d{1,4})\s+(calendar\s+days?|business\s+days?|working\s+days?|days?|months?|years?)\b/ig;let m;while((m=re.exec(text))){const unit=m[2].toLowerCase().replace(/\s+/g,' ');const n=Number(m[1]);out.push({raw:m[0],quantity:n,unit,dayType:/business|working/.test(unit)?'BUSINESS':/calendar/.test(unit)?'CALENDAR':/days?/.test(unit)?'UNSPECIFIED_DAY_TYPE':'NOT_DAYS',offset:m.index,computedDate:null});}return out;
}
export function extractDocumentCandidates(doc){
  if(!doc||doc.status!=='INGESTED')throw new Error('DOCUMENT_NOT_INGESTED');
  const clauses=splitClauses(doc.text).map(c=>{const kinds=Object.entries(KEYWORDS).filter(([,re])=>re.test(c.text)).map(([k])=>k);return {...c,clauseHash:sha256(`${doc.sourceHash}:${c.index}:${c.text}`),kinds,dates:dateCandidates(c.text),deadlines:deadlineCandidates(c.text),reviewStatus:'NEEDS_HUMAN_REVIEW'};});
  return {documentId:doc.id,documentSourceHash:doc.sourceHash,textHash:doc.textHash,clauses,materialClauses:clauses.filter(c=>c.kinds.length>0),status:'CANDIDATES_ONLY',legalConclusion:false};
}

export function computeDeadlineCandidate({anchorDate,quantity,unit,dayType}){
  const anchor=parseIsoDate(anchorDate);const q=Number(quantity);if(!Number.isInteger(q)||q<0||q>3650)throw new Error('INVALID_DEADLINE_QUANTITY');const u=String(unit||'').toLowerCase();
  if(/business|working/.test(u)||dayType==='BUSINESS')return {anchorDate:anchor,quantity:q,unit:u,dayType:'BUSINESS',computedDate:null,status:'NEEDS_CALENDAR_RULE'};
  if(/days?/.test(u)){if(dayType!=='CALENDAR')return {anchorDate:anchor,quantity:q,unit:u,dayType:dayType||'UNSPECIFIED_DAY_TYPE',computedDate:null,status:'NEEDS_DAY_TYPE_REVIEW'};const d=new Date(`${anchor}T00:00:00Z`);d.setUTCDate(d.getUTCDate()+q);return {anchorDate:anchor,quantity:q,unit:u,dayType:'CALENDAR',computedDate:d.toISOString().slice(0,10),status:'COMPUTED_CANDIDATE'};}
  return {anchorDate:anchor,quantity:q,unit:u,dayType:dayType||null,computedDate:null,status:'NEEDS_UNIT_RULE'};
}

export function approveClause(candidate,{reviewer,reviewedAt,classification,notes='',effectiveRule=null}={}){
  if(!candidate?.clauseHash)throw new Error('INVALID_CLAUSE_CANDIDATE');requiredText(reviewer,'reviewer');parseIsoTimestamp(reviewedAt);const cls=requiredText(classification,'classification');const allowed=new Set(['WARRANTY','EXCLUSION','CONDITION','DEADLINE','NOTICE','LIABILITY','COST','PARTY','IRRELEVANT']);if(!allowed.has(cls))throw new Error('INVALID_CLAUSE_CLASSIFICATION');
  return Object.freeze({clauseHash:candidate.clauseHash,sourceText:candidate.text,classification:cls,reviewer,reviewedAt,notes:String(notes||''),effectiveRule:effectiveRule??null,status:'HUMAN_APPROVED'});
}

export function buildDocumentDossier(doc,extraction,approvedClauses=[]){
  if(extraction.documentId!==doc.id||extraction.documentSourceHash!==doc.sourceHash)throw new Error('DOCUMENT_LINEAGE_MISMATCH');const hashes=new Set(extraction.clauses.map(c=>c.clauseHash));for(const a of approvedClauses)if(!hashes.has(a.clauseHash))throw new Error('APPROVED_CLAUSE_NOT_IN_DOCUMENT');
  const unresolved=extraction.materialClauses.filter(c=>!approvedClauses.some(a=>a.clauseHash===c.clauseHash)).map(c=>c.clauseHash);
  return {document:{id:doc.id,fileName:doc.fileName,mimeType:doc.mimeType,sourceHash:doc.sourceHash,textHash:doc.textHash,mode:doc.mode},approvedClauses,unresolvedMaterialClauseHashes:unresolved,status:unresolved.length?'NEEDS_REVIEW':'DOCUMENT_REVIEW_COMPLETE',dossierHash:sha256({sourceHash:doc.sourceHash,textHash:doc.textHash,approvedClauses:approvedClauses.map(a=>({clauseHash:a.clauseHash,classification:a.classification,reviewer:a.reviewer,reviewedAt:a.reviewedAt,effectiveRule:a.effectiveRule}))})};
}
