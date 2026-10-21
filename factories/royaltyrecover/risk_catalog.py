from __future__ import annotations

from typing import Iterable, Tuple


UC_2023_SOURCE = "University of California — Proposed Royalty Audit Identification Approach, Appendix A, June 2023"
UC_2023_URL = "https://regents.universityofcalifornia.edu/regmeet/july23/s1attach1.pdf"


UC_RISK_FACTORS = {
    "COMPLEX_CONTRACT_TERMS": "Contract terms are difficult to interpret.",
    "AMBIGUOUS_CONTRACT_TERMS": "Contract terms or licensed-product definitions are vague or loosely defined.",
    "COMPLICATED_ROYALTY_CALCULATION": "Royalty calculation contains multiple bases/elements or unusual rate application.",
    "TIME_TO_EXPIRATION": "Agreement is approaching expiration, reducing time available to detect errors.",
    "NET_ROYALTY_BASE": "Net-sales basis uses deductions that create additional reconciliation complexity.",
    "UNIT_ROYALTY_BASE": "Unit-based royalty lacks an easily reconciled financial source.",
    "UNUSUAL_PAYMENT_PATTERN": "Royalty payment/report pattern is unusual, variable, delinquent, or near a minimum threshold.",
    "INCOMPLETE_OR_INACCURATE_REPORTING": "Royalty report is incomplete or contains calculation errors.",
    "REPORTING_REVISIONS": "Reports are frequently revised.",
    "DEDUCTIONS": "Deductions are numerous, unidentified, vague, or large.",
    "MULTI_CURRENCY_STREAMS": "Multiple-country currency/tax streams increase conversion/withholding complexity.",
    "SOURCE_OF_REPORTING": "Reporting ownership comes from an unrelated/changing functional area.",
    "MANUAL_REPORTING_FORMAT": "Reporting appears manually generated rather than system generated.",
    "PAST_RELATIONSHIP_PROBLEMS": "History includes miscommunication, inaccurate reports, or non-compliance.",
    "HOCKEY_STICK_SALES_GROWTH": "Sales growth is not accompanied by a corresponding royalty increase.",
    "DECREASING_ROYALTY_PAYMENTS": "Royalty payments or licensed-product sales decrease unexpectedly.",
    "SUBLICENSING": "Sublicensing reduces direct visibility into underlying reporting accuracy.",
    "NEW_ACCOUNTING_SYSTEM": "Licensee recently changed accounting systems.",
    "NEW_LICENSE_OR_TECHNOLOGY": "A new agreement/technology recently began producing sales.",
    "NEW_FACILITY_PRODUCT_OR_TERRITORY": "New facilities, covered products, or territories may not be reflected in royalty calculations.",
    "RECENT_PRODUCT_LAUNCH": "A recent product launch may use licensed technology without a corresponding royalty increase.",
    "BUSINESS_COMBINATION": "Merger/acquisition may disrupt royalty reporting continuity.",
    "DETERIORATING_FINANCIAL_CONDITION": "Financial distress may increase payment/default/recoverability risk.",
    "INDUSTRY_RISK": "Industry is considered higher risk based on observed underpayment experience.",
    "LOW_TRANSPARENCY_OR_FAMILIARITY": "Low visibility into licensee products/markets creates additional unknowns.",
    "FIRST_TIME_LICENSEE": "Licensee is inexperienced with licensing/reporting obligations.",
    "COMPLAINTS": "Researcher/vendor/third-party complaints indicate a possible reporting problem.",
}


def validate_risk_factors(values: Iterable[str]) -> Tuple[str, ...]:
    factors = tuple(dict.fromkeys(str(value).strip().upper() for value in values if str(value).strip()))
    unknown = tuple(value for value in factors if value not in UC_RISK_FACTORS)
    if unknown:
        raise ValueError(f"unknown risk factor(s): {', '.join(unknown)}")
    return factors
