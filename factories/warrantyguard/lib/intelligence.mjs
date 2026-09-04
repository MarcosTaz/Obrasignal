import {round2,parseIsoDate,validCurrency} from './utils.mjs';
import {summarize} from './engine.mjs';

const DEFAULT_REQUIRED=['id','customer','amount','currency','failureDate'];
function isMissing(v){return v===null||v===undefined||String(v).trim()==='';}
function dayMs(){return 86400000;}
function toDay(v){parseIsoDate(v);return Date.parse(`${v}T00:00:00Z`);}
function safeAmount(v){const n=Number(v);return Number.isFinite(n)&&n>=0?n:0;}

export function buildDataQualityReport(records,{requiredFields=DEFAULT_REQUIRED}={}){
  if(!Array.isArray(records))throw new Error('RECORDS_REQUIRED');
  const tenants=new Set(records.map(r=>r?.tenantId).filter(Boolean));if(tenants.size>1)throw new Error('CROSS_TENANT_RECORDS');
  const missingByField={};for(const f of requiredFields)missingByField[f]=0;
  let invalidAmount=0,invalidCurrency=0,invalidDate=0;const ids=new Map();const currencies=new Set();
  for(const r of records){for(const f of requiredFields)if(isMissing(r?.[f]))missingByField[f]++;
    const a=Number(r?.amount);if(!Number.isFinite(a)||a<0)invalidAmount++;
    const c=String(r?.currency||'').toUpperCase();if(c){if(!validCurrency(c))invalidCurrency++;else currencies.add(c);}
    if(r?.failureDate){try{parseIsoDate(r.failureDate);}catch{invalidDate++;}}
    if(r?.id)ids.set(r.id,(ids.get(r.id)||0)+1);
  }
  const duplicateIds=[...ids.entries()].filter(([,n])=>n>1).map(([id,count])=>({id,count}));
  const missingTotal=Object.values(missingByField).reduce((a,b)=>a+b,0);const checks=records.length*Math.max(1,requiredFields.length);
  const completeness=checks?round2(((checks-missingTotal)/checks)*100):100;
  const blocking=missingTotal+invalidAmount+invalidCurrency+invalidDate+duplicateIds.length;
  return {status:blocking?'REVIEW_REQUIRED':'PASS',records:records.length,completenessPct:completeness,missingByField,invalidAmount,invalidCurrency,invalidDate,duplicateIds,currencies:[...currencies].sort(),mixedCurrency:currencies.size>1,interpretation:'DATA_QUALITY_ONLY_NOT_LIABILITY'};
}

export function detectTrendSignals(records,{asOf,windowDays=30,dimensions=['part','program','failureMode'],minCurrentCount=3,minGrowth=2}={}){
  if(!Array.isArray(records))throw new Error('RECORDS_REQUIRED');if(!asOf)throw new Error('AS_OF_REQUIRED');
  const end=toDay(asOf),currentStart=end-(windowDays-1)*dayMs(),previousEnd=currentStart-dayMs(),previousStart=previousEnd-(windowDays-1)*dayMs();
  const buckets=new Map();let invalidDateCount=0;
  for(const r of records){let t;try{t=toDay(r.failureDate);}catch{invalidDateCount++;continue;}if(t<previousStart||t>end)continue;
    for(const dimension of dimensions){const value=String(r?.[dimension]??'').trim();if(!value)continue;const key=`${dimension}\u0000${value}`;const b=buckets.get(key)??{dimension,value,currentCount:0,previousCount:0,currentAmount:0,previousAmount:0};
      if(t>=currentStart){b.currentCount++;b.currentAmount+=safeAmount(r.amount);}else{b.previousCount++;b.previousAmount+=safeAmount(r.amount);}buckets.set(key,b);
    }
  }
  const signals=[];for(const b of buckets.values()){
    const growth=b.previousCount===0?(b.currentCount>0?Infinity:1):b.currentCount/b.previousCount;
    if(b.currentCount<minCurrentCount||growth<minGrowth)continue;
    const priority=b.currentCount>=10?'HIGH':b.currentCount>=5?'MEDIUM':'WATCH';
    signals.push({...b,currentAmount:round2(b.currentAmount),previousAmount:round2(b.previousAmount),growthMultiple:Number.isFinite(growth)?round2(growth):null,newPattern:b.previousCount===0,priority,classification:'SIGNAL_ONLY_NOT_CAUSAL'});
  }
  signals.sort((a,b)=>b.currentAmount-a.currentAmount||b.currentCount-a.currentCount||a.dimension.localeCompare(b.dimension));
  return {state:'SIGNALS_READY',asOf,windowDays,currentWindow:{from:new Date(currentStart).toISOString().slice(0,10),to:asOf},previousWindow:{from:new Date(previousStart).toISOString().slice(0,10),to:new Date(previousEnd).toISOString().slice(0,10)},signals,invalidDateCount,causalConclusion:false,liabilityConclusion:false};
}

export function forecastExposure(records,{monthsAhead=3}={}){
  if(!Array.isArray(records))throw new Error('RECORDS_REQUIRED');if(!Number.isInteger(monthsAhead)||monthsAhead<1||monthsAhead>12)throw new Error('INVALID_FORECAST_HORIZON');
  const byMonth=new Map();const currencies=new Set();
  for(const r of records){try{parseIsoDate(r.failureDate);}catch{continue;}const c=String(r.currency||'').toUpperCase();if(!validCurrency(c))continue;currencies.add(c);const m=r.failureDate.slice(0,7);const key=`${c}:${m}`;byMonth.set(key,round2((byMonth.get(key)||0)+safeAmount(r.amount)));}
  if(currencies.size!==1)return {state:'UNKNOWN',reason:currencies.size?'MIXED_CURRENCY_REQUIRES_SEPARATE_FORECAST':'NO_VALID_CURRENCY',scenarioOnly:true};
  const currency=[...currencies][0],series=[...byMonth.entries()].filter(([k])=>k.startsWith(`${currency}:`)).map(([k,v])=>({month:k.slice(4),amount:v})).sort((a,b)=>a.month.localeCompare(b.month));
  if(series.length<3)return {state:'UNKNOWN',reason:'INSUFFICIENT_MONTHLY_HISTORY',currency,monthsObserved:series.length,scenarioOnly:true};
  const recent=series.slice(-Math.min(6,series.length)),vals=recent.map(x=>x.amount),mean=vals.reduce((a,b)=>a+b,0)/vals.length,min=Math.min(...vals),max=Math.max(...vals);
  return {state:'SCENARIO_READY',currency,monthsObserved:series.length,horizonMonths:monthsAhead,monthly:{low:round2(min),base:round2(mean),high:round2(max)},horizon:{low:round2(min*monthsAhead),base:round2(mean*monthsAhead),high:round2(max*monthsAhead)},basisMonths:recent.map(x=>x.month),scenarioOnly:true,accountingAdvice:false,interpretation:'OBSERVED_RUN_RATE_SCENARIO_NOT_WARRANTY_PROVISION'};
}

export function buildDisputeReadiness({analysis,caseDossier=null,evidenceCount=0,hasReviewedContract=false}={}){
  if(!analysis?.state)throw new Error('ANALYSIS_REQUIRED');
  const checks=[
    ['analysis_known',analysis.state!=='UNKNOWN'],['reviewed_contract',!!hasReviewedContract],['evidence_present',evidenceCount>0],['deadline_known',caseDossier?.deadline?.state&&caseDossier.deadline.state!=='UNKNOWN'],['source_lineage',!!caseDossier?.contract?.sourceHash],['case_hash',!!caseDossier?.caseDossierHash]
  ];
  const passed=checks.filter(([,ok])=>ok).length,score=Math.round((passed/checks.length)*100);const missing=checks.filter(([,ok])=>!ok).map(([name])=>name);
  return {score,band:score===100?'READY_FOR_HUMAN_DECISION':score>=67?'NEAR_READY':'INCOMPLETE',missing,meritsConclusion:false,automaticSubmission:false,interpretation:'EVIDENCE_AND_PROCESS_COMPLETENESS_ONLY'};
}

export function buildExecutiveCommandCenter({analyses=[],cases=[],outcomes=[],dataQuality=null,trendSignals=null,forecast=null,asOf=null}={}){
  const summary=summarize(analyses);const due={dueToday:0,open:0,passed:0,unknown:0};
  for(const c of cases){const s=c?.deadline?.state;if(s==='DUE_TODAY')due.dueToday++;else if(s==='OPEN')due.open++;else if(s==='PASSED')due.passed++;else due.unknown++;}
  const recoveryByCurrency={};for(const o of outcomes){const cur=o?.currency;if(!cur||!validCurrency(cur))continue;const v=safeAmount(o.verifiedRecovery);recoveryByCurrency[cur]=round2((recoveryByCurrency[cur]||0)+v);}
  const attention=cases.filter(c=>['NEEDS_REVIEW','DEADLINE_PASSED_REVIEW_REQUIRED','DRAFT_CHALLENGE_REVIEW'].includes(c?.actionStatus)).map(c=>({debitId:c.debitId,actionStatus:c.actionStatus,deadline:c.deadline?.state||'UNKNOWN',deadlineDate:c.deadline?.deadlineDate||null,disputable:c.analysis?.disputable??null,currency:c.analysis?.currency||null}));
  return {asOf,summary,deadlines:due,recoveryByCurrency,attention,signals:trendSignals?.signals?.slice(0,8)||[],dataQuality:dataQuality||null,forecast:forecast||null,truthBoundary:{unknownCases:summary.unknown,automaticLiabilityDecision:false,automaticExternalSubmission:false,recoveryRequiresEvidence:true}};
}
