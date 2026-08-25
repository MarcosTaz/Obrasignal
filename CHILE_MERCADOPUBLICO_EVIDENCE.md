# Chile Mercado Público — Q060 evidence

Status: **GATED — external production credential required**.

## Official source contract

- ChileCompra publishes the Mercado Público procurement API as public procurement-data infrastructure. Normal use requires an individual ticket. The ticket printed in the official documentation is explicitly for testing and is not a production credential.
- `CodigoExterno` is the durable tender identity used by the API.
- Publisher lifecycle states used by ObraSignal: 5 Publicada → open, 6 Cerrada → closed, 7 Desierta → unsuccessful, 8 Adjudicada → awarded, 18 Revocada → revoked, 19 Suspendida → suspended.
- Publisher construction admission is `Obras == 2` OR an item `CodigoCategoria` in UNSPSC segment 72 (building/construction/maintenance services). This avoids keyword admission and preserves genuine maintenance/construction tenders observed with `Obras == 0`. Construction-material goods such as UNSPSC 30101700 are not admitted to the contractor-works feed.
- `MontoEstimado` is exposed only when `VisibilidadMonto == 1`; otherwise ObraSignal leaves value/currency empty.

## Live validation — 2026-08-25

- Classic API `estado=activas` returned 4,408 active opportunities using the official documentation test ticket in explicit validation mode.
- Live detail `1002588-92-LE26` returned a published building-maintenance tender with `Obras=0`, CLP estimated amount and UNSPSC 72131700, proving that `Obras` alone is insufficient.
- A steel-beam goods tender used UNSPSC 30101700 and is deliberately excluded from the works feed.
- The API returned HTTP 429 / code 10500 for closely spaced requests; the connector is strictly sequential and uses bounded exponential backoff.
- The no-registration OCDS monthly endpoint was not selected for current discovery: 2026-08 returned no records while 2026-07 returned 8,004. Current tender detail lookups on that OCDS endpoint also returned no result.
- Deterministic tests plus a live detail smoke passed on branch validation run #1.

## Production gate

The adapter is intentionally not wired into preload while `MERCADOPUBLICO_TICKET` is unavailable. Registry state is `planned` / `CREDENTIAL_REQUIRED`; this prevents a test credential from becoming commercial infrastructure. Once a real ticket is provisioned, rerun the full production-path live gate before changing the source to `ready`.
