import {requiredText,parseIsoDate,parseIsoTimestamp,stableStringify,sha256} from './utils.mjs';
import {makeContract,verifyContract} from './contracts.mjs';
const BOOL_RULES=new Map([['WARRANTY_ELIGIBLE','warrantyEligible'],['COST_ELIGIBLE','costEligible'],['NO_FAULT_FOUND_SUPPLIER_LIABLE','noFaultFoundSupplierLiable']]);
function same(a,b){return stableStringify(a)===stableStringify(b);}
export function compileApprovedRules(approvedClauses=[]){
  if(!Array.isArray(approvedClauses))throw new Error('APPROVED_CLAUSES_REQUIRED');const rules={},provenance={};
  for(const a of approvedClauses){if(a?.status!=='HUMAN_APPROVED')throw new Error('CLAUSE_NOT_HUMAN_APPROVED');if(!a.effectiveRule)continue;const er=a.effectiveRule,kind=requiredText(er.kind,'ruleKind');let key,value;
    if(BOOL_RULES.has(kind)){key=BOOL_RULES.get(kind);if(typeof er.value!=='boolean')throw new Error(`RULE_VALUE_TYPE_${kind}`);value=er.value;}
    else if(kind==='NOTICE_DEADLINE'){key='noticeDeadline';const event=requiredText(er.event,'deadlineEvent');const quantity=Number(er.quantity);if(!Number.isInteger(quantity)||quantity<0||quantity>3650)throw new Error('INVALID_DEADLINE_QUANTITY');const unit=requiredText(er.unit,'deadlineUnit').toLowerCase();const dayType=requiredText(er.dayType,'dayType');if(!['CALENDAR','BUSINESS','UNSPECIFIED_DAY_TYPE'].includes(dayType))throw new Error('INVALID_DAY_TYPE');value={event,quantity,unit,dayType};}
    else if(kind==='EXCLUSION_TAG'){key='exclusionTags';const tag=requiredText(er.tag,'exclusionTag');value=[tag];}
    else throw new Error('UNSUPPORTED_EFFECTIVE_RULE');
    if(key==='exclusionTags'){const current=rules[key]||[];rules[key]=[...new Set([...current,...value])].sort();}
    else if(Object.hasOwn(rules,key)&&!same(rules[key],value))throw new Error(`RULE_CONFLICT_${key.toUpperCase()}`);else rules[key]=value;
    const p=provenance[key]??=[];p.push({clauseHash:a.clauseHash,classification:a.classification,reviewer:a.reviewer,reviewedAt:a.reviewedAt});provenance[key]=p;
  }
  return {rules,provenance,rulesHash:sha256(stableStringify(rules)),status:'HUMAN_APPROVED_RULES'};
}
export function buildContractFromDocumentReview({id,tenantId,customer,effectiveFrom,effectiveTo=null,document,dossier,approvedBy,approvedAt}){
  requiredText(id,'contractId');requiredText(tenantId,'tenantId');requiredText(customer,'customer');parseIsoDate(effectiveFrom);if(effectiveTo)parseIsoDate(effectiveTo);requiredText(approvedBy,'approvedBy');parseIsoTimestamp(approvedAt);
  if(!document||!dossier)throw new Error('DOCUMENT_REVIEW_REQUIRED');if(document.tenantId!==tenantId)throw new Error('TENANT_MISMATCH');if(dossier.status!=='DOCUMENT_REVIEW_COMPLETE')throw new Error('DOCUMENT_REVIEW_INCOMPLETE');if(dossier.document?.sourceHash!==document.sourceHash||dossier.document?.textHash!==document.textHash)throw new Error('DOCUMENT_LINEAGE_MISMATCH');
  const compiled=compileApprovedRules(dossier.approvedClauses);const contract=makeContract({id,tenantId,customer,effectiveFrom,effectiveTo,rules:compiled.rules,sourceText:document.text,approvedBy,approvedAt});const out={...contract,documentId:document.id,documentSourceHash:document.sourceHash,documentTextHash:document.textHash,ruleProvenance:compiled.provenance,documentDossierHash:dossier.dossierHash};const v=verifyContract(out,tenantId);if(!v.ok)throw new Error(v.reason);return Object.freeze(out);
}
