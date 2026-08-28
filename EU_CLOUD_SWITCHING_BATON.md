# EU CLOUD SWITCHING / MIGRATION CAPITAL NETWORK — BATON

## Mission
Build a pilot-ready commercial product that answers whether an expensive infrastructure switching event should happen, what it will really cost, what migration capital is available, and whether promised economics materialized.

## Source truth
- Repository: `MarcosTaz/Obrasignal`
- Branch: `factory/eu-cloud-switching-migration-capital`
- Branch base: main `66d43f6fd51cf9cea08016dad335aaa04b711a24`
- Canonical branch established because no pre-existing cloud-switching branch or implementation was found.

## Product truth
Strongest current wedge: customer-paid independent switching economic assurance, with VMware/Broadcom exit as first trigger cohort. Generic calculator, generic RFQ, generic marketplace and provider-funded routing are not the wedge.

Initial deterministic core implemented:
- gross switching cost kept separate from provider/partner subsidies;
- approved incentives kept separate from received incentives;
- status-quo avoidance and current-cost savings kept explicit;
- economic payback separated from customer-cash payback;
- non-positive savings fail closed for payback;
- promised-vs-actual outcome fields expose absolute and percentage variance;
- partner/public/unverified evidence cannot enter the verified benchmark.

## Safety invariants
- Potential credit != approved credit != received value.
- Provider subsidy != operating saving.
- No payback when the denominator is non-positive.
- Migration executor cannot self-certify its outcome into the verified benchmark.
- Unknown material inputs must not be silently converted to zero in later ingestion layers.
- Synthetic evidence proves calculation reliability, not market demand.

## ACTIVE
Run the new deterministic tests against exact branch HEAD, repair any failures, then add synthetic estates + independent oracle fixtures covering simple, multi-destination, complex, incomplete and adversarial cases.

## NEXT
1. Add phased migration/wave economics and renewal overlap.
2. Add explicit missing-input fail-closed validation.
3. Add evidence lineage IDs and confidence/comparability grades.
4. Add synthetic company factory and independent oracle.
5. Add adversarial double-count/false-credit/currency/workload tests.
6. Expose a minimal analysis API/UI only after the economic core is green.
7. Add tenant isolation and persistence/backup tests before PILOT_READY.

## WAIT
Only genuine external dependencies: real customer estate/contract data, real provider incentive approval, real migration quote, customer authorization, external outreach/payment/contracts/deployment.

## Test state
NOT_FULLY_VERIFIED: code and tests were added through GitHub connector, but no exact-HEAD test runner result has yet been observed.

## Resume at
Execute tests for exact branch HEAD. If the available environment cannot execute the repository, use CI or establish the smallest safe test workflow without touching main.
