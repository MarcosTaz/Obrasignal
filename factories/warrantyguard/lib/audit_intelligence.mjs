import {parseIsoDate,round2,sha256,stableStringify,validCurrency} from './utils.mjs';

function tenantSet(items){return new Set((items||[]).map(x=>x?.tenantId).filter(Boolean));}
function enforceTenant(tenantId,...collections){for(const items of collections){const s=tenantSet(items);if([...s].some(t=>t!==tenantId))throw new Error('TENANT_MISMATCH');}}
function safeMoney(v){const n=Number(v);return Number.isFinite(n)&&n>=0?round2(n):0;}
function daysBetween(from,to){parseIsoDate(from);parseIsoDate(to);return Math.max(0,Math.floor((Date.parse(`${to}T00:00:00Z`)-Date.parse(`${from}T00:00:00Z`))/86400000));}
function median(values){if(!values.length)return 0;const a=[...values].sort((x,y)=>x-y),m=Math.floor(a.length/2);return a.length%2?a[m]:(a[m-1]+a[m])/2;}

export function buildEvidenceGraph({tenantId,debit,analysis,contract,evidence=[],caseDossier=null,reviewDecisions=[]}={}){
  if(!tenantId||debit?.tenantId!==tenantId)throw new Error('TENANT_MISMATCH');
  if(analysis?.id!==debit.id)throw new Error('ANALYSIS_DEBIT_MISMATCH');
  if(contract?.tenantId!==tenantId)throw new Error('TENANT_MISMATCH');
  enforceTenant(tenantId,evidence,reviewDecisions);
  const nodes=[],edges=[];const add=(id,type,label,hash=null,meta={})=>{if(nodes.some(n=>n.id===id))return;nodes.push({id,type,label,hash,meta});};
  add(`debit:${debit.id}`,'DEBIT',debit.id,sha256(debit),{customer:debit.customer,currency:debit.currency,amount:debit.amount});
  add(`analysis:${debit.id}`,'ANALYSIS',analysis.state,sha256(analysis),{supported:analysis.supported??null,disputable:analysis.disputable??null});edges.push({from:`debit:${debit.id}`,to:`analysis:${debit.id}`,type:'ANALYZED_AS'});
  add(`contract:${contract.id}`,'CONTRACT',contract.id,contract.rulesHash||contract.sourceHash||null,{sourceHash:contract.sourceHash||null,rulesHash:contract.rulesHash||null});edges.push({from:`contract:${contract.id}`,to:`analysis:${debit.id}`,type:'GOVERNS'});
  for(const e of evidence){add(`evidence:${e.id}`,'EVIDENCE',e.id,e.contentHash||null,{claims:e.claims||[],reviewedBy:e.reviewedBy||null});edges.push({from:`evidence:${e.id}`,to:`analysis:${debit.id}`,type:'SUPPORTS_REVIEW'});}
  if(caseDossier){if(caseDossier.tenantId!==tenantId||caseDossier.debitId!==debit.id)throw new Error('CASE_DOSSIER_MISMATCH');add(`case:${debit.id}`,'CASE_DOSSIER',caseDossier.actionStatus||'CASE',caseDossier.caseDossierHash||sha256(caseDossier),{deadline:caseDossier.deadline?.state||'UNKNOWN'});edges.push({from:`analysis:${debit.id}`,to:`case:${debit.id}`,type:'MATERIALIZED_IN'});}
  for(const [i,d] of reviewDecisions.entries()){const id=`review:${d.decisionHash||i}`;add(id,'REVIEW_DECISION',`${d.stage}:${d.decision}`,d.decisionHash||sha256(d),{actor:d.actor,at:d.at});edges.push({from:i?`review:${reviewDecisions[i-1].decisionHash||i-1}`:(caseDossier?`case:${debit.id}`:`analysis:${debit.id}`),to:id,type:'REVIEW_CHAIN'});}
  const graph={tenantId,debitId:debit.id,nodes,edges,truthBoundary:{graphRepresentsLineage:true,graphProvesLiability:false,graphProvesRecovery:false}};return {...graph,graphHash:sha256(graph)};
}

export function buildFinancialWaterfall({analysis,outcome=null}={}){
  if(!analysis?.state)throw new Error('ANALYSIS_REQUIRED');
  if(analysis.state==='UNKNOWN')return {state:'UNKNOWN',currency:analysis.currency||null,reason:'UNKNOWN_ANALYSIS_MONEY_SUPPRESSED',steps:[],verifiedRecovery:null};
  const currency=analysis.currency;if(!validCurrency(currency))throw new Error('INVALID_CURRENCY');if(outcome?.currency&&outcome.currency!==currency)throw new Error('OUTCOME_CURRENCY_MISMATCH');
  const received=safeMoney(analysis.amount),priorCredit=safeMoney(analysis.resolvedCredit),outstanding=safeMoney(analysis.outstandingAmount??received-priorCredit),supported=safeMoney(analysis.supported),disputable=safeMoney(analysis.disputable),verifiedRecovery=safeMoney(outcome?.verifiedRecovery);
  if(round2(supported+disputable)>outstanding+.01)throw new Error('WATERFALL_EXCEEDS_OUTSTANDING');if(verifiedRecovery>disputable+.01)throw new Error('RECOVERY_EXCEEDS_DISPUTABLE');
  return {state:'READY',currency,steps:[{key:'received',amount:received},{key:'prior_credit_or_resolution',amount:priorCredit},{key:'outstanding',amount:outstanding},{key:'supported',amount:supported},{key:'known_disputable',amount:disputable},{key:'verified_recovery',amount:verifiedRecovery}],verifiedRecovery,unrecoveredKnownDisputable:round2(Math.max(0,disputable-verifiedRecovery)),truthBoundary:{unknownExcluded:true,recoveryEvidenceRequired:true}};
}

const POLICY_KEYS=['warrantyEligible','costEligible','noFaultFoundSupplierLiable','costCap','noticeDeadline','exclusionTags'];
export function compareContractPolicies(contracts,{tenantId,customer=null}={}){
  if(!Array.isArray(contracts)||!contracts.length)throw new Error('CONTRACTS_REQUIRED');enforceTenant(tenantId,contracts);const selected=contracts.filter(c=>!customer||c.customer===customer).sort((a,b)=>a.effectiveFrom.localeCompare(b.effectiveFrom));if(!selected.length)throw new Error('CONTRACT_NOT_FOUND');
  const rows=POLICY_KEYS.map(key=>{const values=selected.map(c=>({contractId:c.id,effectiveFrom:c.effectiveFrom,effectiveTo:c.effectiveTo||null,value:Object.hasOwn(c.rules||{},key)?c.rules[key]:null,known:Object.hasOwn(c.rules||{},key)}));const knownValues=values.filter(v=>v.known).map(v=>stableStringify(v.value));return {key,values,changed:new Set(knownValues).size>1,missing:values.some(v=>!v.known)};});
  return {tenantId,customer:customer||null,contracts:selected.map(c=>({id:c.id,effectiveFrom:c.effectiveFrom,effectiveTo:c.effectiveTo||null,rulesHash:c.rulesHash,sourceHash:c.sourceHash})),policies:rows,interpretation:'STRUCTURED_POLICY_DIFF_NOT_LEGAL_INTERPRETATION',automaticSupersessionConclusion:false};
}

export function triageAnomalies(records,{amountMultiple=4,minPartCount=4}={}){
  if(!Array.isArray(records))throw new Error('RECORDS_REQUIRED');const tenants=tenantSet(records);if(tenants.size>1)throw new Error('CROSS_TENANT_RECORDS');const signals=[];
  const byCurrency=new Map();for(const r of records){const c=String(r.currency||'').toUpperCase();const n=Number(r.amount);if(validCurrency(c)&&Number.isFinite(n)&&n>=0){const a=byCurrency.get(c)||[];a.push({id:r.id,amount:n,part:r.part||null});byCurrency.set(c,a);}}
  for(const [currency,items] of byCurrency){const med=median(items.map(x=>x.amount));if(med>0)for(const x of items)if(x.amount>=med*amountMultiple)signals.push({type:'AMOUNT_OUTLIER',recordId:x.id,currency,amount:round2(x.amount),baselineMedian:round2(med),classification:'SIGNAL_ONLY_REVIEW_REQUIRED'});}
  const partCounts=new Map();for(const r of records)if(r.part)partCounts.set(r.part,(partCounts.get(r.part)||0)+1);for(const [part,count] of partCounts)if(count>=minPartCount)signals.push({type:'PART_FREQUENCY_CLUSTER',part,count,classification:'SIGNAL_ONLY_REVIEW_REQUIRED'});
  const ids=new Map();for(const r of records)if(r.id){const n=(ids.get(r.id)||0)+1;ids.set(r.id,n);}for(const [id,count] of ids)if(count>1)signals.push({type:'DUPLICATE_ID',recordId:id,count,classification:'DATA_INTEGRITY_SIGNAL'});
  return {state:'TRIAGE_READY',signals,causalConclusion:false,liabilityConclusion:false,automaticRejection:false};
}

export function buildRecoveryAging({cases=[],outcomes=[],asOf}={}){
  parseIsoDate(asOf);const outcomeMap=new Map(outcomes.map(o=>[o.debitId,o]));const buckets={open_0_7:0,open_8_30:0,open_31_60:0,open_61_plus:0,resolved:0,unknown_age:0};const rows=[];
  for(const c of cases){const o=outcomeMap.get(c.debitId),state=o?.state||'OPEN';if(['CREDIT_RECEIVED','CASH_RECEIVED','CLOSED_NO_CHANGE'].includes(state)){buckets.resolved++;rows.push({debitId:c.debitId,state,ageDays:0,resolved:true});continue;}const start=c.createdDate||c.receivedDate||c.failureDate||null;if(!start){buckets.unknown_age++;rows.push({debitId:c.debitId,state,ageDays:null,resolved:false});continue;}const age=daysBetween(start,asOf);const key=age<=7?'open_0_7':age<=30?'open_8_30':age<=60?'open_31_60':'open_61_plus';buckets[key]++;rows.push({debitId:c.debitId,state,ageDays:age,resolved:false});}
  rows.sort((a,b)=>(b.ageDays??-1)-(a.ageDays??-1));return {asOf,buckets,rows,interpretation:'PROCESS_AGING_NOT_RECOVERY_PROBABILITY'};
}

export function buildCohortIntelligence(records,{dimension='part'}={}){
  if(!['part','program','failureMode','customer'].includes(dimension))throw new Error('INVALID_COHORT_DIMENSION');const tenants=tenantSet(records);if(tenants.size>1)throw new Error('CROSS_TENANT_RECORDS');const map=new Map();for(const r of records){const k=String(r?.[dimension]||'').trim();if(!k)continue;const x=map.get(k)||{value:k,count:0,amountByCurrency:{}};x.count++;const c=String(r.currency||'').toUpperCase();if(validCurrency(c))x.amountByCurrency[c]=round2((x.amountByCurrency[c]||0)+safeMoney(r.amount));map.set(k,x);}return {dimension,cohorts:[...map.values()].sort((a,b)=>b.count-a.count),causalConclusion:false,interpretation:'COHORT_OBSERVATION_ONLY'};
}

export function buildAuditPack({tenantId,caseDossier,evidenceGraph,financialWaterfall,reviewChain=null,generatedAt}={}){
  if(!caseDossier||caseDossier.tenantId!==tenantId)throw new Error('TENANT_MISMATCH');if(evidenceGraph?.tenantId!==tenantId)throw new Error('TENANT_MISMATCH');const body={format:'DEBITPROOF_AUDIT_PACK_V1',tenantId,debitId:caseDossier.debitId,generatedAt,caseDossierHash:caseDossier.caseDossierHash,evidenceGraphHash:evidenceGraph?.graphHash||null,financialWaterfall:financialWaterfall||null,reviewChain:reviewChain?{ok:reviewChain.ok,lastDecisionHash:reviewChain.lastDecisionHash||null,approverCount:reviewChain.approverCount||0}:null,actionStatus:caseDossier.actionStatus,unresolvedReasons:caseDossier.unresolvedReasons||[],deadline:caseDossier.deadline,truthBoundary:{draftOnly:true,humanReviewRequired:true,externalSubmission:false}};return {...body,packHash:sha256(body)};
}

export function buildNegotiationPack({auditPack,requestedAction='REVIEW_DEBIT',notes=[]}={}){
  if(!auditPack?.packHash)throw new Error('AUDIT_PACK_REQUIRED');const body={format:'DEBITPROOF_NEGOTIATION_PACK_V1',auditPackHash:auditPack.packHash,debitId:auditPack.debitId,requestedAction,knownFinancialPosition:auditPack.financialWaterfall?.state==='READY'?auditPack.financialWaterfall:null,unresolvedReasons:auditPack.unresolvedReasons||[],deadline:auditPack.deadline||null,notes:[...notes].map(String),status:'DRAFT_HUMAN_REVIEW_REQUIRED',automaticSubmission:false};return {...body,packHash:sha256(body)};
}
