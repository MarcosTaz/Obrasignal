# GuaranteeRelease — Test Report v2

Date: 2026-08-29
Branch: `factory/guaranteerelease`
Canonical assessment engine: `engine_v2.mjs`

## Executed evidence

The hardened engine was executed locally after red-team failures were discovered in v1.

### v1 red-team failures discovered

1. `currentAmount > originalAmount` was not rejected.
2. `reductionPercent > 100` was not rejected.
3. `cancelledAmount > originalAmount` was not rejected.

These were treated as regressions/P1 truth-integrity defects and repaired rather than accepted.

### v2 result

```text
PASS 20/20 assertions
```

Composition:

- 7 independent synthetic oracle cases;
- 3 original P0 truth regressions;
- 10 expanded red-team assertions.

Expanded red team covers:

- current amount above original amount;
- negative current amount;
- negative original amount;
- reduction percentage above 100%;
- reduction percentage below 0%;
- cancelled amount above original amount;
- negative collateral release amount;
- valid open claim blocking release;
- asserted but unverified release condition remaining `RELEASE_MAY_BE_DUE`;
- project progress alone creating no reduction right.

## Truth invariants currently passing

- expiry != verified release;
- bank/surety cancellation != collateral release;
- potential release != verified release;
- wrong-project / superseded / conflicting / cross-tenant evidence fails closed;
- valid defect/claim/final-account blocker prevents release classification;
- invalid amounts/percentages fail closed;
- progressive advance-payment reduction requires both governing wording and repayment evidence;
- milestone reduction requires a valid percentage and milestone evidence;
- correct zero remains a valid passing result.

## Verification state

ENGINE_V1 = SUPERSEDED
ENGINE_V2 = PASS_20_OF_20_LOCAL_ASSERTIONS
ORACLE_STATE = INITIAL_7_CASES_PASS
RED_TEAM_STATE = INITIAL_EXPANDED_SET_PASS
P0 = 0 KNOWN OPEN IN CURRENT ENGINE TEST SET
P1 = 0 KNOWN OPEN IN CURRENT ENGINE TEST SET
STATIC_WEB_PRODUCT = CREATED
BROWSER_E2E = NOT_FULLY_VERIFIED
BACKEND_PERSISTENCE = NOT_STARTED
TENANT_ISOLATION_RUNTIME = NOT_TESTABLE_YET
REAL_CUSTOMER_DATA = NONE
REAL_RELEASE_ACTION = NONE
COMMERCIAL_PROOF = NONE

## T1 gate

T1 remains `IN_PROGRESS`, not complete, because browser/E2E verification and a minimally persistent tenant-safe application are still absent.

No synthetic result is represented as market proof, customer proof, verified real-world release, collateral recovery, restored real capacity or revenue.
