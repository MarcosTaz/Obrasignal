import assert from 'node:assert/strict';
import {assessSecurity,STATES} from './engine_v2.mjs';

const oracle = [
  ['GR-001',{instrumentId:'APG-1',originalAmount:2000000,currentAmount:2000000,reductionMode:'ADVANCE_REPAYMENT',instrumentWordingSupportsReduction:true,repaymentEvidenceVerified:true,repaidToDate:1200000},STATES.REDUCTION_EVIDENCE_SUPPORTED,1200000,0],
  ['GR-002',{instrumentId:'PB-2',originalAmount:1000000,currentAmount:1000000,reductionMode:'MILESTONE_PERCENT',milestoneEvidenceVerified:true,reductionPercent:50},STATES.REDUCTION_EVIDENCE_SUPPORTED,500000,0],
  ['GR-003',{instrumentId:'WG-3',originalAmount:750000,currentAmount:750000,validOpenDefect:true},STATES.RELEASE_NOT_YET_DUE,0,0],
  ['GR-004',{instrumentId:'PG-4',originalAmount:1500000,currentAmount:1500000,releaseConditionMet:true,releaseConditionEvidenceVerified:true,expiryDatePassed:true},STATES.RELEASE_EVIDENCE_SUPPORTED,0,1500000],
  ['GR-005',{instrumentId:'RG-5',originalAmount:600000,currentAmount:0,bankCancelled:true,cancelledAmount:600000,collateralReleaseVerified:true,collateralReleasedAmount:300000},STATES.VERIFIED_RELEASE,0,0],
  ['GR-006',{instrumentId:'APG-6',originalAmount:900000,currentAmount:900000,evidenceConflict:true,wrongProject:true,supersededEvidence:true},STATES.UNKNOWN,0,0],
  ['GR-007',{instrumentId:'PG-7',originalAmount:1250000,currentAmount:1250000},STATES.REDUCTION_NOT_YET_DUE,0,0],
];

let passed = 0;
for(const [id,input,state,pr,prel] of oracle){
  const got=assessSecurity(input);
  assert.equal(got.state,state,`${id} state`);
  assert.equal(got.potentialReduction,pr,`${id} reduction`);
  assert.equal(got.potentialRelease,prel,`${id} release`);
  passed++;
}

const p0 = [
  ['expiry != verified release',()=>assert.notEqual(assessSecurity({instrumentId:'X',originalAmount:100,currentAmount:100,expiryDatePassed:true}).state,STATES.VERIFIED_RELEASE)],
  ['bank cancellation != collateral release',()=>assert.equal(assessSecurity({instrumentId:'X',originalAmount:100,currentAmount:0,bankCancelled:true}).collateralReleased,0)],
  ['cross-tenant evidence fails closed',()=>assert.equal(assessSecurity({instrumentId:'X',originalAmount:100,currentAmount:100,crossTenantEvidence:true,releaseConditionMet:true,releaseConditionEvidenceVerified:true}).state,STATES.UNKNOWN)],
];
for(const [name,fn] of p0){fn(); passed++;}

const redteam = [
  ['current > original fails closed',()=>assert.equal(assessSecurity({instrumentId:'X',originalAmount:100,currentAmount:150}).state,STATES.UNKNOWN)],
  ['negative current fails closed',()=>assert.equal(assessSecurity({instrumentId:'X',originalAmount:100,currentAmount:-1}).state,STATES.UNKNOWN)],
  ['negative original fails closed',()=>assert.equal(assessSecurity({instrumentId:'X',originalAmount:-1,currentAmount:0}).state,STATES.UNKNOWN)],
  ['reduction pct > 100 fails closed',()=>assert.equal(assessSecurity({instrumentId:'X',originalAmount:100,currentAmount:100,reductionMode:'MILESTONE_PERCENT',milestoneEvidenceVerified:true,reductionPercent:120}).state,STATES.UNKNOWN)],
  ['reduction pct < 0 fails closed',()=>assert.equal(assessSecurity({instrumentId:'X',originalAmount:100,currentAmount:100,reductionMode:'MILESTONE_PERCENT',milestoneEvidenceVerified:true,reductionPercent:-10}).state,STATES.UNKNOWN)],
  ['cancelled > original fails closed',()=>assert.equal(assessSecurity({instrumentId:'X',originalAmount:100,currentAmount:0,bankCancelled:true,cancelledAmount:120}).state,STATES.UNKNOWN)],
  ['negative collateral release fails closed',()=>assert.equal(assessSecurity({instrumentId:'X',originalAmount:100,currentAmount:0,bankCancelled:true,collateralReleaseVerified:true,collateralReleasedAmount:-1}).state,STATES.UNKNOWN)],
  ['open claim blocks release',()=>assert.equal(assessSecurity({instrumentId:'X',originalAmount:100,currentAmount:100,validOpenClaim:true,releaseConditionMet:true,releaseConditionEvidenceVerified:true}).state,STATES.RELEASE_NOT_YET_DUE)],
  ['unverified release condition is MAY_BE_DUE',()=>assert.equal(assessSecurity({instrumentId:'X',originalAmount:100,currentAmount:100,releaseConditionMet:true,releaseConditionEvidenceVerified:false}).state,STATES.RELEASE_MAY_BE_DUE)],
  ['progress alone creates no reduction',()=>assert.equal(assessSecurity({instrumentId:'X',originalAmount:100,currentAmount:100,projectProgressPercent:99}).potentialReduction,0)],
];
for(const [name,fn] of redteam){fn(); passed++;}

assert.equal(passed,20);
console.log(`PASS ${passed}/20 assertions`);
