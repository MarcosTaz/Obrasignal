# Italy ANAC PVL — implementation evidence

This file records the source contract used by the `IT_ANAC` connector so the production gate is auditable.

## Official source

- Publisher: Autorità Nazionale Anticorruzione (ANAC).
- System: Banca Dati Nazionale dei Contratti Pubblici (BDNCP), Pubblicità a Valore Legale (PVL).
- Public UI: `https://pubblicitalegale.anticorruzione.it`.
- Public JSON list endpoint observed live: `GET https://pubblicitalegale.anticorruzione.it/api/v0/avvisi`.
- No API credential was required by the observed public endpoint.

## Live machine-contract evidence

A public network probe dated 2026-08-19 recorded HTTP 200 from `/api/v0/avvisi` for a bounded publication-date window. The response is a Spring-style page with `content`, `number`, `totalPages`, and `totalElements`.

Observed publisher fields include:

- `idAvviso` — notice/version identity.
- `idAppalto` — procurement identity.
- `tipo` — including `avviso` and `rettifica`.
- `attivo` / `oscurato` — publisher visibility state.
- `dataPubblicazione`, `dataCreazione`, `dataScadenza`.
- embedded `SEZ. C - Oggetto` lot items.
- lot `cig` — publisher-native lot/commercial identity.
- lot `natura_principale` — observed values include `Lavori`, `Servizi`, `Forniture`.
- lot `termine_ricezione`, value, location, work categories, document URL and CPV label.

The same probe contained a live `rettifica` for a `Lavori` lot, proving that correction records can carry the lot payload again.

## Production semantics chosen

- Only publisher-native `natura_principale == Lavori` may create an ObraSignal opportunity.
- No keyword inference from title, description, categories, or CPV label.
- CIG is the lot-level `external_id`.
- A later record for the same CIG supersedes an older version.
- `rettifica` is treated as a version update, not a new commercial opportunity.
- A later version changing away from `Lavori`, becoming inactive, or becoming obscured can close a previously visible lot.
- A future structured deadline is required before exposure as actionable.
- PVL's observed CPV field is a human label in this payload. It is preserved as `anac_cpv_label`; the connector does not invent a numeric CPV code.
- Runtime is opt-in through the existing global-source gate. This implementation does not change deployment environment configuration.

## Scope deliberately not claimed

This connector is TENDER-only. Awards, contracts, suppliers, historical OCDS coverage and numeric CPV mapping are not claimed by this implementation. They require separate evidence and implementation before registry promotion.
