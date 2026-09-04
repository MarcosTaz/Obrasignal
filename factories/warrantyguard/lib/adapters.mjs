import {parseCsv} from './csv.mjs';
import {requiredText,sha256} from './utils.mjs';

export const CANONICAL_DEBIT_FIELDS=['tenantId','id','customer','amount','currency','failureDate','part','program','asset','caseId','invoice','repairDate','rootCauseKnown','responsibility','responsibilityShare','warrantyEligible','costEligible','wrongPart','wrongProgram','wrongAsset','wrongCustomer','duplicateConfirmed','currencyMismatch','evidenceContradictory','ineligibleCost','priorCredit','priorPayment','costCap'];
export const REQUIRED_CANONICAL_FIELDS=['tenantId','id','customer','amount','currency','failureDate'];

function cleanHeader(v){return String(v??'').trim();}
export function makeAdapterProfile({id,version,customer,headerMap,constants={},description=''}){
  const profileId=requiredText(id,'adapter_id'),v=requiredText(version,'adapter_version'),c=requiredText(customer,'customer');
  if(!headerMap||typeof headerMap!=='object'||Array.isArray(headerMap))throw new Error('ADAPTER_HEADER_MAP_REQUIRED');
  const seen=new Set();const normalized={};
  for(const [source,targetRaw] of Object.entries(headerMap)){
    const sourceHeader=cleanHeader(source),target=cleanHeader(targetRaw);
    if(!sourceHeader||!CANONICAL_DEBIT_FIELDS.includes(target))throw new Error('ADAPTER_MAPPING_INVALID');
    if(seen.has(target))throw new Error(`ADAPTER_DUPLICATE_TARGET_${target}`);seen.add(target);normalized[sourceHeader]=target;
  }
  for(const k of Object.keys(constants)){if(!CANONICAL_DEBIT_FIELDS.includes(k))throw new Error(`ADAPTER_CONSTANT_UNKNOWN_${k}`);if(seen.has(k))throw new Error(`ADAPTER_CONSTANT_COLLISION_${k}`);}
  const missing=REQUIRED_CANONICAL_FIELDS.filter(f=>!seen.has(f)&&constants[f]==null&&(f!=='customer'||c===''));
  if(missing.length)throw new Error(`ADAPTER_REQUIRED_MAPPING_MISSING_${missing.join('_')}`);
  const body={id:profileId,version:v,customer:c,description:String(description||''),headerMap:normalized,constants:{...constants}};
  return {...body,profileHash:sha256(body)};
}

export function normalizeWithAdapter(csv,profile,{tenantId}={}){
  if(!profile?.profileHash)throw new Error('ADAPTER_PROFILE_REQUIRED');
  const rows=parseCsv(csv);const mapped=[];const sourceHeaders=rows.length?Object.keys(rows[0]):[];
  const unknownHeaders=sourceHeaders.filter(h=>!profile.headerMap[h]);
  for(const [idx,row] of rows.entries()){
    const out={...profile.constants};
    for(const [source,target] of Object.entries(profile.headerMap))if(row[source]!==undefined)out[target]=row[source];
    if(out.customer==null||out.customer==='')out.customer=profile.customer;
    if(tenantId){if(out.tenantId&&out.tenantId!==tenantId)throw new Error(`ADAPTER_TENANT_MISMATCH_ROW_${idx+2}`);out.tenantId=tenantId;}
    mapped.push(out);
  }
  const mappedTargets=new Set([...Object.values(profile.headerMap),...Object.keys(profile.constants),'customer']);
  const missingCanonical=REQUIRED_CANONICAL_FIELDS.filter(f=>!mappedTargets.has(f)&&(f!=='tenantId'||tenantId));
  return {adapter:{id:profile.id,version:profile.version,customer:profile.customer,profileHash:profile.profileHash},rows:mapped,quality:{sourceHeaders,unknownHeaders,missingCanonical,rowCount:mapped.length,status:missingCanonical.length?'BLOCKED':unknownHeaders.length?'REVIEW_REQUIRED':'PASS'}};
}
