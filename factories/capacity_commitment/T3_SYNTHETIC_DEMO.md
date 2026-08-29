# Capacity Commitment — Synthetic Buyer Demo

Status: **SYNTHETIC ONLY — NOT CUSTOMER EVIDENCE**

This example exists to show the shape of the assisted analysis without presenting fabricated customers, contracts, recoveries, payments or willingness-to-pay.

Nothing below is a real buyer case.

---

## Demo A — supportable shortfall with unrecovered dedicated investment

### Synthetic facts

- Supplier: `SYNTHETIC_TIER1_A`
- Customer/programme: `SYNTHETIC_OEM / PROGRAM_A`
- Currency: `EUR`
- Commitment state: `FIRM`
- Committed/amortisation-basis volume: `100,000 units`
- Actual shipped/consumed volume: `50,000 units`
- Customer-specific dedicated investment: `EUR 500,000`
- Recovery mode: unit-amortised
- Mitigation/reuse: `EUR 0`
- Prior customer payment/recovery: `EUR 0`
- Contract/current-amendment/customer/programme/unit/currency/actual/integrity gates: synthetically set to verified/matching
- Explicit recovery right/evidence: synthetically supported
- Notice window: synthetically valid and verified
- Duplicate claim: `NO`

### Reconstruction

- Unit amortisation = `EUR 500,000 / 100,000 = EUR 5 per unit`
- Amount recovered through 50,000 actual units = `EUR 250,000`
- Economic exposure = `EUR 250,000`
- Net exposure after mitigation/prior recovery = `EUR 250,000`
- Synthetic recoverability state = `RECOVERABLE`
- Synthetic claimable amount = `EUR 250,000`

### What the conclusion does **not** mean

Even in this intentionally clean synthetic case:

- `EUR 250,000 claimable` is not a submitted claim;
- it is not customer acceptance;
- it is not a settlement;
- it is not verified customer cash received;
- it is not our revenue;
- it would still require authorized human review before any external submission.

### Buyer-facing insight

The product is not merely calculating the volume delta. It forces the chain:

`current commercial anchor → actuals → amortisation → dedicated exposure → mitigation → prior recovery → integrity → evidence → notice → recoverability`.

If any material gate becomes unknown or contradictory, the positive result must downgrade rather than remain positive.

---

## Demo B — correct zero after full programme volume

### Synthetic facts

Use the same simplified economic basis:

- committed/amortisation volume: `100,000 units`;
- actual shipped/consumed volume: `100,000 units`;
- dedicated investment: `EUR 500,000`;
- unit amortisation: `EUR 5`.

### Reconstruction

- recovered through actual units = `EUR 500,000`;
- economic exposure = `EUR 0`;
- net exposure = `EUR 0`;
- recoverability state = `ZERO_EXPOSURE`;
- claimable amount = `EUR 0`.

### Why this is a successful product outcome

The correct result is to close the case at zero rather than manufacture a claim.

A paid fixed-fee audit is for the bounded forensic determination and evidence trail, not for guaranteeing that every programme produces recoverable money.

---

## Demo C — economic exposure but evidence/contract integrity unresolved

### Synthetic illustration

Suppose the economics resemble Demo A, but the current applicable amendment or contract match is unknown.

The engine may still show economic exposure, but must classify recoverability as `UNKNOWN` with `claimable_amount = 0` until the missing evidence is resolved.

This demonstrates the central distinction:

**economic pain is not automatically a supportable recovery position.**

---

## Typical real-pilot input categories

For one customer + one programme + one bounded period:

1. nomination/LTA/PO/award or other strongest commercial anchor;
2. applicable amendments/superseding terms;
3. commitment/minimum/flex/amortisation basis;
4. release/call-off history;
5. shipped/consumed actuals;
6. tooling/capex/NRE/material/labour cost basis where relevant;
7. amortisation history;
8. mitigation/reuse evidence;
9. prior credits/payments/recoveries;
10. notice/deadline terms;
11. prior claim/correspondence history if applicable.

The initial request remains bounded; unrelated customers/programmes should not be uploaded.

## Typical deliverable

- executive finding;
- commitment-vs-actual table;
- exposure/amortisation reconciliation;
- mitigation/prior-recovery reconciliation;
- contract/amendment/integrity state;
- recoverability classification/reasons;
- evidence and missing-evidence register;
- notice/deadline state;
- assisted next-action package;
- human review boundary.

## Commercial truth

Current price remains a market-test hypothesis:

- UK: **£3,000 fixed** bounded pilot;
- Euro markets: **€3,500 fixed** bounded pilot.

This synthetic demo is **not** evidence that any real buyer will pay that price.
