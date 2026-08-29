# Project-to-Factory v0.12.1 — source durability checkpoint

STATE: METADATA_ONLY / NO PR / NO MERGE / NO DEPLOY.

This isolated branch preserves deterministic recovery metadata for the validated Project-to-Factory source checkpoint. It MUST NOT be described as a full source mirror.

## Canonical restorable source

Complete validated artifact:

`project-to-factory-v0.12.1.zip`

ZIP SHA-256:

`840a20007e1fce5ba84f4b87b90bd2b0791f75103bbbd203dc1e942a8549ba6f`

Source tree inside the ZIP: `project-to-factory-vertical-slice/`.

The connected GitHub text-write surface used for this checkpoint does not mirror the binary ZIP. `manifest.sha256` on this branch inventories the complete validated artifact. The versioned ZIP remains the canonical complete restorable source.

## Version / validation

Version: `0.12.1`

Validated after the 2026-08-29 public-buyer evidence and fail-closed prospect-contract audit:

- `npm run check` — PASS
- schema suite — 11 valid/expected fixtures + 8 adversarial cases PASS
- buyer-prospect schema prevents public discovery from becoming buyer authorization and requires exact-panel evidence for exact-panel public-demand states
- 10 machine-readable endpoints — GET/HEAD 200 and POST 405 fail-closed
- `npm run check:browser` — PASS
- browser-generated evidence package validates against buyer, RFQ-dispatch, normalized-quote, award and order schemas
- `manifest.sha256` — 61 entries, verification PASS
- `unzip -t project-to-factory-v0.12.1.zip` — PASS

## Business truth

BUSINESS_STATE: SIGNAL.

First cell under validation: sandwich-panel + accessory packages × repeat professional construction buyers with non-captive procurement × Central Portugal.

Public buyer ranking is evidence-weighted, not a sales claim:

1. Prosertã — Priority A / FIRST_CELL / exact sandwich-panel demand publicly proven; direct procurement workflow still UNKNOWN.
2. Manuel Mateus Frazão — Priority B / FIRST_CELL / real 2026 roof-rehabilitation demand, but exact sandwich-panel requirement remains UNPROVEN.
3. Construções Silvano Santos — Priority B / ADJACENT_GEOGRAPHY / exact sandwich-panel demand publicly proven; procurement method UNKNOWN.
4. João Matos & Ribeiro — integrated-executor negative control; roof demand exists but metal-fabrication integration raises captive-procurement risk.
5. Coberfer — integrated-executor negative control; public offer includes sandwich-panel execution, so it is not promoted as evidence of non-captive buying.

`CONTACTABLE != CONTACTED != VALIDATED`.

Public contact routes for Prosertã, Manuel Mateus Frazão and Silvano Santos are prepared for controlled buyer validation, but no external contact has been made.

Real transaction truth:

- directly validated buyers: 0
- buyer-authorized live projects: 0
- externally dispatched platform RFQs: 0
- verified real supplier quotes: 0
- real awards: 0
- confirmed real orders: 0
- verified GMV: EUR 0
- verified revenue: EUR 0

## Resume rule

On X, recover this metadata plus the exact versioned ZIP/manifest. Repository/source truth overrides narrative history.

ACTIVE: direct buyer procurement-workflow falsification on Prosertã, owner-gated for external communication.

NEXT after authorization: validate procurement method, authority/influence, supplier captivity, alternative-comparison willingness, payer/WTP and one genuine upcoming project. Buyer validation comes before any live supplier RFQ.

If outbound authorization is absent: continue safe exact-panel buyer evidence, negative-control research and evidence-chain hardening without sending messages.
