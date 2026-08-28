import assert from 'node:assert/strict';
import {assessSecurity,STATES} from './engine.mjs';

const cases=[
  ['GR-001',{instrumentId:'APG-1',originalAmount:2000000,currentAmount:2000000,reductionMode:'ADVANCE_REPAYMENT',instrumentWordingSupportsReduction:true,repaymentEvidenceVerified:true,repaidToDate:1200000},STATES.REDUCTION_EVIDENCE_SUPPORTED,1200000,0],
  ['GR-002',{instrumentId:'PB-2',originalAmount:1000000,currentAmount:1000000,reductionMode:'MILESTONE_PERCENT',milestoneEvidenceVerified:true,reductionPercent:50},STATES.REDUCTION_EVIDENCE_SUPPORTED,500000,0],
  ['GR-003',{instrumentId:'WG-3',originalAmount:750000,currentAmount:750000,validOpenDefect:true},STATES.RELEASE_NOT_YET_DUE,0,0],
  ['GR-004',{instrumentId:'PG-4',originalAmount:1500000,currentAmount:1500000,releaseConditionMet:true,releaseConditionEvidenceVerified:true,expiryDatePassed:true},STATES.RELEASE_EVIDENCE_SUPPORTED,0,1500000],
  ['GR-005',{instrumentId:'RG-5',originalAmount:600000,currentAmount:0,bankCancelled:true,cancelledAmount:600000,collateralReleaseVerified:true,collateralReleasedAmount:300000},STATES.VERIFIED_RELEASE,0,0],
  ['GR-006',{instrumentId:'APG-6',originalAmount:900000,currentAmount:900000,evidenceConflict:true,wrongProject:true,supersededEvidence:true},STATES.UNKNOWN,0,0],
  ['GR-007',{instrumentId:'PG-7',originalAmount:1250000,currentAmount:1250000},STATES.REDUCTION_NOT_YET_DUE,0,0],
];

for(const [id,input,state,pr,prel] of cases){
  const got=assessSecurity(input);
  assert.equal(got.state,state,`${id} state`);
  assert.equal(got.potentialReduction,pr,`${id} reduction`);
  assert.equal(got.potentialRelease,prel,`${id} release`);
}

assert.notEqual(
  assessSecurity({instrumentId:'X',currentAmount:100,expiryDatePassed:true}).state,
  STATES.VERIFIED_RELEASE,
  'expiry cannot equal verified release'
);

assert.equal(
  assessSecurity({instrumentId:'X',currentAmount:100,bankCancelled:true}).collateralReleased,
  0,
  'bank cancellation cannot fabricate collateral release'
);

assert.equal(
  assessSecurity({instrumentId:'X',currentAmount:100,crossTenantEvidence:true,releaseConditionMet:true,releaseConditionEvidenceVerified:true}).state,
  STATES.UNKNOWN,
  'cross-tenant evidence fails closed'
);

console.log(`PASS ${cases.length+3} assertions`);
