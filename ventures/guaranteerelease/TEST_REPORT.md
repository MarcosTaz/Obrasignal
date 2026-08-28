# GuaranteeRelease — Test Report

Date: 2026-08-29
Branch: `factory/guaranteerelease`

## Executed tests

The assessment engine was executed locally with Node against seven independent oracle scenarios plus three P0 regression assertions.

Result:

```text
PASS 10 assertions
```

Covered scenarios:

1. Advance-payment guarantee with proven progressive reduction.
2. Performance bond with milestone-based 50% reduction.
3. Warranty guarantee correctly returning zero while a valid defect remains open.
4. Release condition evidenced while issuer cancellation remains unverified.
5. Historical verified cancellation plus independently evidenced collateral release.
6. Wrong-project / superseded evidence conflict failing closed to `UNKNOWN`.
7. Project progress without a contractual reduction right correctly returning zero.
8. Expiry by date must not become `VERIFIED_RELEASE`.
9. Bank cancellation must not fabricate collateral release.
10. Cross-tenant evidence must fail closed.

## Current verification state

ENGINE_TESTS = PASS
ORACLE_ALIGNMENT = PASS_FOR_INITIAL_7_CASES
P0_TRUTH_REGRESSIONS = PASS_FOR_INITIAL_3_ASSERTIONS
STATIC_WEB_PRODUCT = CREATED
BROWSER_E2E = NOT_FULLY_VERIFIED
PRODUCTION_INTEGRATION = NOT_STARTED
REAL_CUSTOMER_DATA = NONE

## Why browser E2E is not marked green

The current execution environment did not expose the browser automation CLI and its container network could not retrieve the branch from GitHub for local rendering. No visual/browser PASS is claimed without evidence.

This is a local technical limitation, not a Factory stop condition. Other safe work remains executable.

## Next test expansion

Add explicit tests for:

- auto-extension deadline;
- beneficiary release received but bank not cancelled;
- bank cancelled but facility not restored;
- partial collateral release;
- multiple amendments where latest amendment changes reduction rule;
- duplicate instrument / duplicate release;
- wrong currency;
- amount greater than original guarantee;
- partial claim reducing available balance;
- final-account blocker;
- release letter missing;
- evidence date after instrument cancellation;
- conflicting bank and internal register amounts;
- zero-value valid-security case;
- tenant isolation at persistence/API layer once a backend exists.

## Gate

T1 remains `IN_PROGRESS` until the minimum product is browser/E2E verified and the red-team set is materially expanded.
