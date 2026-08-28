# Engineering Change Recoverability Assurance — assisted prototype

This is the first tested product slice for the narrowed Engineering Change Exposure thesis.

It is intentionally **not** a PLM, ERP, CPQ, program-management or profitability operating system. The wedge is an independent layer that reconciles:

`engineering change -> exact revision delta -> linked evidence -> causal cost -> mitigation/prior payment -> contractual basis -> notice/deadline -> recoverability -> commercial action package`

## Truth rules

- A detected change is not a cost.
- A cost is not entitlement.
- Entitlement is not recoverability.
- Recoverability is not payment.
- A boolean saying “evidence supported” is not evidence.
- Unknown remains unknown.
- Correct EUR 0 is a successful output.
- Mixed currency, unverified revision/baseline, missing linked cost/causality evidence, ambiguous contract basis and unresolved notice conditions fail closed.

## What exists

- deterministic recoverability engine;
- 10 synthetic companies/cases with an independent oracle;
- explicit recoverable / non-recoverable / unknown / mitigated / prior-payment buckets;
- evidence objects + evidence graph + missing-evidence output;
- append-only SQLite case and analysis history;
- tenant-scoped storage with signed expiring bearer tokens;
- concurrent version writes protected by `BEGIN IMMEDIATE`;
- atomic case + analysis + commercial-package persistence;
- backup, restore and SQLite integrity checks;
- commercial action package with input SHA-256 audit fingerprint;
- local web UI and JSON API.

## Tests

```bash
python -W error::ResourceWarning -m unittest -v
```

Current tested slice: **21 tests passing**.

The tests cover independent-oracle outcomes, mixed currency, missing evidence, notice risk, evidence self-assertion, token tampering/expiry, cross-tenant isolation, append-only history, concurrent writes, restart persistence, backup/restore and commercial-package truth including correct zero recovery.

## Run assisted web prototype

The real-record API fails closed without an authentication secret:

```bash
export ECE_AUTH_SECRET='replace-with-at-least-32-random-bytes'
python app.py
```

Then open `http://127.0.0.1:8765` for the synthetic demo. Real-record endpoints require a signed bearer token. Tokens are intended for an assisted pilot and are issued out-of-band with `auth.issue_token`.

## Current maturity

- T0: **NARROW / SURVIVED**
- T1: **IN PROGRESS — strong local pilot slice, not yet promoted**
- Real customer data: **NONE**
- Commercial proof: **NONE**
- Market exposure: **NOT YET**

Why T1 is not yet promoted: customer/program/part identity assertions still need stronger evidence-content matching and more adversarial context-mismatch tests before the Factory can claim the complete fail-closed T1 journey.

Do not expose this prototype as production truth.
