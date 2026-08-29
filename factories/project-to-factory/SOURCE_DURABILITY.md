# Project-to-Factory v0.12.0 — source durability checkpoint

STATE: METADATA_ONLY / NO MERGE / NO DEPLOY.

This isolated branch exists only to make Factory recovery deterministic after a continuity failure in which narrative execution had advanced beyond the last actually persisted source artifact.

## Canonical restorable source

The complete validated v0.12.0 source is the versioned conversation artifact:

`project-to-factory-v0.12.0.zip`

ZIP SHA-256:

`882a8435eff231c3dfda461ce9dec5bc5ced380f405f19f9ddbe0b7ffa5414b1`

The source tree inside the ZIP is `project-to-factory-vertical-slice/`.

The connected GitHub write surface accepts UTF-8 file content but does not accept the local ZIP as a file argument, so this branch MUST NOT be represented as a full source mirror. `manifest.sha256` on this branch inventories the validated artifact. The ZIP remains the canonical complete restorable source for this checkpoint.

## Version / validation

Version: `0.12.0`

Validated after the final 2026-08-29 ICP/contact/adjacent-buyer evidence audit:

- `npm run check` — PASS
- schema suite — 10 valid/expected fixtures + 6 adversarial cases PASS
- 10 machine-readable endpoints — GET/HEAD 200 and POST 405 fail-closed
- `npm run check:browser` — PASS
- browser-generated evidence package validates against buyer, RFQ-dispatch, normalized-quote, award and order schemas
- `manifest.sha256` — 58 entries, verification PASS
- `unzip -t project-to-factory-v0.12.0.zip` — PASS

## Business truth

BUSINESS_STATE: SIGNAL.

Winning cell under validation: sandwich-panel + accessory packages × repeat professional construction buyers with non-captive procurement × Central Portugal.

The former installer-first wording was corrected: company type is not qualification. Direct evidence must establish repeat procurement, authority/influence, non-captive supplier choice, alternative-comparison willingness, pain and a plausible payer.

Real transaction truth at this checkpoint:

- directly validated buyers: 0
- buyer-authorized live projects: 0
- externally dispatched platform RFQs: 0
- verified real supplier quotes: 0
- real awards: 0
- confirmed real orders: 0
- verified GMV: EUR 0
- verified revenue: EUR 0

Priority-A public demand signal remains Prosertã. A current public general contact route is prepared as `PUBLIC_CONTACT_ROUTE_ONLY`; no outreach was sent. Its internal procurement method, supplier captivity, switching willingness and WTP remain UNKNOWN.

A second general-contractor exact-panel public-demand control was found in adjacent geography: Construções Silvano Santos — Unipessoal, Lda, with an explicit 2025 sandwich-panel roofing contract and ongoing 2026 construction-contract activity. Its purchasing method is also UNKNOWN and it does not establish Central Portugal cell liquidity.

## Resume rule

On X, recover this metadata plus the versioned ZIP/manifest. Do not reconstruct v0.12.0 from narrative claims if the ZIP is unavailable. Repository/source truth overrides chat history.

ACTIVE: direct buyer procurement-workflow falsification on Prosertã, owner-gated for external contact.

If outbound authorization is absent: continue safe exact-panel buyer evidence and product/evidence hardening. Do not send supplier RFQs without a genuine buyer project plus auditable sourcing authorization.
