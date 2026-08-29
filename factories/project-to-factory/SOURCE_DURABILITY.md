# Project-to-Factory v0.12.0 — source durability checkpoint

STATE: METADATA_ONLY / NO MERGE / NO DEPLOY.

This isolated branch exists only to make Factory recovery deterministic after a continuity failure in which narrative execution had advanced beyond the last actually persisted source artifact.

## Canonical restorable source

The complete validated v0.12.0 source is the versioned conversation artifact:

`project-to-factory-v0.12.0.zip`

ZIP SHA-256:

`61a3fa9d40eb05e1404948567383f98de71d0dfdf80c6d7fc53d37afd0d0883b`

The source tree inside the ZIP is `project-to-factory-vertical-slice/`.

The connected GitHub write surface accepts UTF-8 file content but does not accept the local ZIP as a file argument, so this branch MUST NOT be represented as a full source mirror. `manifest.sha256` on this branch inventories the validated artifact. The ZIP remains the canonical complete restorable source for this checkpoint.

## Version / validation

Version: `0.12.0`

Validated before packaging:

- `npm run check` — PASS
- schema suite — 10 valid/expected fixtures + 6 adversarial cases PASS
- 10 machine-readable endpoints — GET/HEAD 200 and POST 405 fail-closed
- `npm run check:browser` — PASS
- browser-generated evidence package validates against buyer, RFQ-dispatch, normalized-quote, award and order schemas
- `unzip -t project-to-factory-v0.12.0.zip` — PASS
- artifact manifest verification — PASS

## Business truth

BUSINESS_STATE: SIGNAL.

Winning cell under validation: sandwich-panel + accessory packages × repeat professional construction buyers with non-captive procurement × Central Portugal.

Real transaction truth at this checkpoint:

- directly validated buyers: 0
- buyer-authorized live projects: 0
- externally dispatched platform RFQs: 0
- verified real supplier quotes: 0
- real awards: 0
- confirmed real orders: 0
- verified GMV: EUR 0
- verified revenue: EUR 0

Priority-A public demand signal remains Prosertã. Its internal procurement method, supplier captivity, switching willingness and WTP remain UNKNOWN.

## Resume rule

On X, recover this metadata plus the versioned ZIP/manifest. Do not reconstruct v0.12.0 from narrative claims if the ZIP is unavailable. Repository/source truth overrides chat history.

ACTIVE: direct buyer procurement-workflow falsification, owner-gated for external contact.

If outbound authorization is absent: continue safe exact-panel buyer evidence and product/evidence hardening. Do not send supplier RFQs without a genuine buyer project plus auditable sourcing authorization.
