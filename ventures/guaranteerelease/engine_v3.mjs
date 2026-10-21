export const STATES = Object.freeze({
  REQUIRED:'REQUIRED',
  REDUCTION_NOT_YET_DUE:'REDUCTION_NOT_YET_DUE',
  REDUCTION_MAY_BE_DUE:'REDUCTION_MAY_BE_DUE',
  REDUCTION_EVIDENCE_SUPPORTED:'REDUCTION_EVIDENCE_SUPPORTED',
  RELEASE_NOT_YET_DUE:'RELEASE_NOT_YET_DUE',
  RELEASE_MAY_BE_DUE:'RELEASE_MAY_BE_DUE',
  RELEASE_EVIDENCE_SUPPORTED:'RELEASE_EVIDENCE_SUPPORTED',
  BANK_CANCELLED:'BANK_CANCELLED',
  COLLATERAL_RELEASED:'COLLATERAL_RELEASED',
  VERIFIED_RELEASE:'VERIFIED_RELEASE',
  UNKNOWN:'UNKNOWN'
});

const nz = n => Number.isFinite(Number(n)) ? Number(n) : 0;
const fail = reason => ({state:STATES.UNKNOWN,potentialReduction:0,potentialRelease:0,verifiedRelease:0,collateralReleased:0,reason});

export function assessSecurity(input){
  if (!input || !input.instrumentId) return fail('Instrument identity missing.');
  if (input.evidenceConflict || input.wrongProject || input.supersededEvidence || input.crossTenantEvidence) {
    return fail('Evidence identity/version conflict; fail closed.');
  }

  const current = nz(input.currentAmount);
  const original = nz(input.originalAmount);
  if (current < 0 || original < 0) return fail('Instrument amount invalid.');
  if (input.originalAmount != null && current > original) return fail('Current amount exceeds original amount.');
  if (input.cancelledAmount != null && (nz(input.cancelledAmount) < 0 || (input.originalAmount != null && nz(input.cancelledAmount) > original))) return fail('Cancelled amount invalid.');
  if (input.collateralReleasedAmount != null && nz(input.collateralReleasedAmount) < 0) return fail('Collateral release amount invalid.');
  if (input.baselineEvidenceVerified !== true) return fail('Instrument baseline is not independently evidenced.');

  if (input.bankCancelled || input.suretyCancelled) {
    const collateral = input.collateralReleaseVerified ? nz(input.collateralReleasedAmount) : 0;
    return {
      state: input.collateralReleaseVerified ? STATES.VERIFIED_RELEASE : STATES.BANK_CANCELLED,
      potentialReduction:0,
      potentialRelease:0,
      verifiedRelease:nz(input.cancelledAmount || input.originalAmount),
      collateralReleased:collateral,
      reason: input.collateralReleaseVerified ? 'Cancellation and downstream collateral release are independently evidenced.' : 'Issuer cancellation is evidenced; collateral/facility restoration remains separate.'
    };
  }

  if (input.validOpenClaim || input.validOpenDefect || input.finalAccountBlocker) {
    return {state:STATES.RELEASE_NOT_YET_DUE,potentialReduction:0,potentialRelease:0,verifiedRelease:0,collateralReleased:0,reason:'A valid contractual blocker remains open.'};
  }

  if (input.reductionMode === 'ADVANCE_REPAYMENT') {
    if (!input.instrumentWordingSupportsReduction) {
      return {state:STATES.REDUCTION_NOT_YET_DUE,potentialReduction:0,potentialRelease:0,verifiedRelease:0,collateralReleased:0,reason:'No evidenced progressive reduction right in instrument/contract wording.'};
    }
    if (!input.repaymentEvidenceVerified) {
      return {state:STATES.REDUCTION_MAY_BE_DUE,potentialReduction:0,potentialRelease:0,verifiedRelease:0,collateralReleased:0,reason:'Reduction logic exists but repayment evidence is not verified.'};
    }
    const repaid = Math.max(0, Math.min(nz(input.repaidToDate), original));
    const requiredNow = Math.max(0, original - repaid);
    const reducible = Math.max(0, current - requiredNow);
    return {state:reducible>0?STATES.REDUCTION_EVIDENCE_SUPPORTED:STATES.REDUCTION_NOT_YET_DUE,potentialReduction:reducible,potentialRelease:0,verifiedRelease:0,collateralReleased:0,reason:reducible>0?'Certified repayment plus governing wording supports a reduction candidate.':'Current amount does not exceed the evidenced remaining secured advance.'};
  }

  if (input.reductionMode === 'MILESTONE_PERCENT') {
    const pct = nz(input.reductionPercent);
    if (pct < 0 || pct > 100) return fail('Reduction percentage invalid.');
    if (!input.milestoneEvidenceVerified) {
      return {state:STATES.REDUCTION_MAY_BE_DUE,potentialReduction:0,potentialRelease:0,verifiedRelease:0,collateralReleased:0,reason:'A milestone rule exists but the milestone is not evidenced.'};
    }
    const target=Math.max(0, Math.min(original, original*(1-pct/100)));
    const reducible=Math.max(0,current-target);
    return {state:reducible>0?STATES.REDUCTION_EVIDENCE_SUPPORTED:STATES.REDUCTION_NOT_YET_DUE,potentialReduction:reducible,potentialRelease:0,verifiedRelease:0,collateralReleased:0,reason:reducible>0?'Contractual milestone and reduction percentage are evidenced.':'Milestone does not create additional reducible amount.'};
  }

  if (input.releaseConditionMet) {
    if (!input.releaseConditionEvidenceVerified) {
      return {state:STATES.RELEASE_MAY_BE_DUE,potentialReduction:0,potentialRelease:0,verifiedRelease:0,collateralReleased:0,reason:'Release condition is asserted but not yet evidenced.'};
    }
    return {state:STATES.RELEASE_EVIDENCE_SUPPORTED,potentialReduction:0,potentialRelease:current,verifiedRelease:0,collateralReleased:0,reason:'Governing release condition is evidenced; issuer implementation is not yet verified.'};
  }

  if (input.expiryDatePassed) {
    return {state:STATES.RELEASE_MAY_BE_DUE,potentialReduction:0,potentialRelease:0,verifiedRelease:0,collateralReleased:0,reason:'Expiry by date alone is insufficient to prove cancellation or release entitlement.'};
  }

  return {state:STATES.REDUCTION_NOT_YET_DUE,potentialReduction:0,potentialRelease:0,verifiedRelease:0,collateralReleased:0,reason:'No evidenced reduction or release condition has been met.'};
}
