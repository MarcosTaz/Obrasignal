import assert from 'node:assert/strict';
import {assessSecurity,STATES} from './engine_v3.mjs';
const V={baselineEvidenceVerified:true};let n=0;
const eq=(a,b,m)=>{assert.equal(a,b,m);n++};
const cases=[
 [{...V,instrumentId:'A',originalAmount:2000000,currentAmount:2000000,reductionMode:'ADVANCE_REPAYMENT',instrumentWordingSupportsReduction:true,repaymentEvidenceVerified:true,repaidToDate:1200000},STATES.REDUCTION_EVIDENCE_SUPPORTED,1200000,0],
 [{...V,instrumentId:'B',originalAmount:1000000,currentAmount:1000000,reductionMode:'MILESTONE_PERCENT',milestoneEvidenceVerified:true,reductionPercent:50},STATES.REDUCTION_EVIDENCE_SUPPORTED,500000,0],
 [{...V,instrumentId:'C',originalAmount:750000,currentAmount:750000,validOpenDefect:true},STATES.RELEASE_NOT_YET_DUE,0,0],
 [{...V,instrumentId:'D',originalAmount:1500000,currentAmount:1500000,releaseConditionMet:true,releaseConditionEvidenceVerified:true,expiryDatePassed:true},STATES.RELEASE_EVIDENCE_SUPPORTED,0,1500000],
 [{...V,instrumentId:'E',originalAmount:600000,currentAmount:0,bankCancelled:true,cancelledAmount:600000,collateralReleaseVerified:true,collateralReleasedAmount:300000},STATES.VERIFIED_RELEASE,0,0],
 [{...V,instrumentId:'F',originalAmount:900000,currentAmount:900000,evidenceConflict:true},STATES.UNKNOWN,0,0],
 [{...V,instrumentId:'G',originalAmount:1250000,currentAmount:1250000},STATES.REDUCTION_NOT_YET_DUE,0,0]
];
for(const [i,s,r,l] of cases){const g=assessSecurity(i);assert.equal(g.state,s);assert.equal(g.potentialReduction,r);assert.equal(g.potentialRelease,l);n++}
const checks=[
 ()=>eq(assessSecurity({instrumentId:'X',originalAmount:100,currentAmount:100}).state,STATES.UNKNOWN,'baseline required'),
 ()=>eq(assessSecurity({instrumentId:'X',originalAmount:100,currentAmount:100,baselineEvidenceVerified:false}).potentialReduction,0,'no baseline no value'),
 ()=>eq(assessSecurity({...V,instrumentId:'X',originalAmount:100,currentAmount:100,expiryDatePassed:true}).verifiedRelease,0,'expiry not verified'),
 ()=>eq(assessSecurity({...V,instrumentId:'X',originalAmount:100,currentAmount:0,bankCancelled:true}).collateralReleased,0,'cancellation not collateral'),
 ()=>eq(assessSecurity({...V,instrumentId:'X',originalAmount:100,currentAmount:100,crossTenantEvidence:true}).state,STATES.UNKNOWN,'identity conflict'),
 ()=>eq(assessSecurity({...V,instrumentId:'X',originalAmount:100,currentAmount:150}).state,STATES.UNKNOWN,'current above original'),
 ()=>eq(assessSecurity({...V,instrumentId:'X',originalAmount:100,currentAmount:-1}).state,STATES.UNKNOWN,'negative current'),
 ()=>eq(assessSecurity({...V,instrumentId:'X',originalAmount:-1,currentAmount:0}).state,STATES.UNKNOWN,'negative original'),
 ()=>eq(assessSecurity({...V,instrumentId:'X',originalAmount:100,currentAmount:100,reductionMode:'MILESTONE_PERCENT',milestoneEvidenceVerified:true,reductionPercent:120}).state,STATES.UNKNOWN,'percent high'),
 ()=>eq(assessSecurity({...V,instrumentId:'X',originalAmount:100,currentAmount:100,reductionMode:'MILESTONE_PERCENT',milestoneEvidenceVerified:true,reductionPercent:-1}).state,STATES.UNKNOWN,'percent low'),
 ()=>eq(assessSecurity({...V,instrumentId:'X',originalAmount:100,currentAmount:0,bankCancelled:true,cancelledAmount:120}).state,STATES.UNKNOWN,'cancelled amount invalid'),
 ()=>eq(assessSecurity({...V,instrumentId:'X',originalAmount:100,currentAmount:0,bankCancelled:true,collateralReleaseVerified:true,collateralReleasedAmount:-1}).state,STATES.UNKNOWN,'collateral invalid'),
 ()=>eq(assessSecurity({...V,instrumentId:'X',originalAmount:100,currentAmount:100,validOpenClaim:true,releaseConditionMet:true,releaseConditionEvidenceVerified:true}).state,STATES.RELEASE_NOT_YET_DUE,'claim blocks'),
 ()=>eq(assessSecurity({...V,instrumentId:'X',originalAmount:100,currentAmount:100,releaseConditionMet:true,releaseConditionEvidenceVerified:false}).state,STATES.RELEASE_MAY_BE_DUE,'unverified release'),
 ()=>eq(assessSecurity({...V,instrumentId:'X',originalAmount:100,currentAmount:100,projectProgressPercent:99}).potentialReduction,0,'progress no right'),
 ()=>eq(assessSecurity({instrumentId:'X',originalAmount:100,currentAmount:100,reductionMode:'MILESTONE_PERCENT',milestoneEvidenceVerified:true,reductionPercent:50}).state,STATES.UNKNOWN,'baseline gates rule')
];
for(const f of checks)f();assert.equal(n,23);console.log('PASS 23/23 engine_v3 assertions');
