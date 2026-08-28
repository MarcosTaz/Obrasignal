# Capacity Commitment — T1 Recoverability Engine

Status: **T1 IN PROGRESS / NOT YET PILOT CAPABLE**

This lane implements the narrowed wedge validated by the Capacity Commitment Factory:

> automotive supplier volume shortfall and dedicated-investment recoverability assurance.

It is deliberately not a forecasting, S&OP, ERP, CLM, or generic claims replacement.

## Truth invariants

1. Economic exposure is not entitlement.
2. Forecast-only volume is never promoted into a firm commitment.
3. Ambiguous or missing contract/evidence/integrity states fail closed.
4. Mitigation and prior customer payments reduce exposure before recoverability.
5. Shared capex is not treated as dedicated capex.
6. Fully amortized/already-paid cost cannot become a new recovery.
7. Duplicate claims are blocked.
8. Wrong program, period, currency, superseded contract, and unreconciled amendment block claimability.
9. Expired notice/deadline means zero claimable amount.
10. Correct zero recovery is a successful result.

## Domain path

`commitment -> actual consumption -> exposure -> mitigation/prior payment -> integrity -> contractual/commercial right -> evidence -> notice/deadline -> recoverability`

## Current implemented exposure modes

- unit-amortized dedicated capex/tooling;
- direct unrecovered NRE;
- direct unused labor capacity;
- direct committed material exposure;
- mitigation/reuse;
- prior payment/customer credit.

## Synthetic oracle

`synthetic_cases.py` freezes independent expected outcomes for the mandatory matrix, including full/minor/major shortfall, delay/cancellation, forecast-only, firm/flex windows, capex/tooling/NRE/labor/material, mitigation, prior credit, duplicate claim, wrong program/period/currency, superseded contract, amendment, expiry, and explicit zero-recovery cases.

The production evaluator does not generate its own expected values.

## Verification

The repository's existing `.github/workflows/quality.yml` runs root `test_*.py` files on every pull request. `test_capacity_commitment.py` wires this oracle into that exact-head CI without adding or changing deployment/runtime configuration.

## Not yet implemented

- tenant/auth/persistence model;
- document ingestion and evidence provenance;
- contract/amendment extraction;
- claim/action package generation;
- save/return state preservation;
- backup/restore;
- web UI;
- customer data import;
- real-customer verification or WTP.

No T1 claim is allowed until applicable P0/P1 checks are green and the assisted end-to-end journey exists.
