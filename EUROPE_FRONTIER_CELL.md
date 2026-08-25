# ObraSignal — Europe Frontier Forensic Cell

Status: autonomous research cell
Decision date: 2026-08-25
Branch: `research/europe-frontier-forensic`

## Mission

Evaluate European/frontier national procurement sources only where they can add material construction intelligence beyond existing shared coverage, while minimizing engineering and maintenance burden.

This cell is subordinate to the canonical portfolio. It does **not** silently enlarge commercial coverage, authorize production ingestion, or weaken the rule `COUNTRY SUPPORTED != DEDICATED CONNECTOR`.

## Baseline confirmed in repository

- Canonical portfolio: 135 jurisdictions; 14 BUILD; 31 SHARED; 3 TECH_LAB; 26 HOLD; 61 REMOVE.
- Commercially active coverage remains 45 markets (14 BUILD + 31 SHARED).
- Dedicated connector target remains 13.
- Switzerland is already BUILD and `CH_SIMAP` is implemented/ready, so Switzerland is not frontier backlog.
- Ukraine is already HOLD. The canonical reopening condition is geopolitical/execution risk, not a missing-source claim.
- The current shared-family architecture must be reused only where the publisher transport/lifecycle contract genuinely matches; format similarity alone is insufficient.

## Frontier queue

| Priority | Market | Cell state | Immediate question | Promotion rule |
| --- | --- | --- | --- | --- |
| 1 | Turkey / Türkiye | HOLD_MACHINE_ACCESS | EKAP has exceptional national procurement depth, but the supported production machine route is unproven. | Reopen immediately on official/stable API, feed or bulk export plus lawful commercial reuse |
| 2 | Serbia | TECH_LAB_CANDIDATE | Portal has unusually rich notices/procedures/decisions/plans/contracts; public API is unproven and available exports appear analytically useful but incomplete for live detail. | Promote only if an official/reliable incremental route and commercial reuse are closed |
| 3 | Ukraine | CANONICAL_HOLD | Is there technical learning worth retaining without pretending normal commercial contractor execution is currently rational? | Do not promote while canonical geopolitical/execution blocker dominates |
| 4 | Georgia | FORENSIC_RESEARCH | Is the national e-procurement surface automatable, reusable and construction-rich enough to justify entry? | Require live proof and commercial reuse evidence |
| 5 | Moldova | FORENSIC_RESEARCH | Does MTender/national infrastructure provide reusable OCDS-like depth and enough market value? | Reuse an existing family only if transport/completeness semantics match |
| 6 | Albania | FORENSIC_RESEARCH | Does the national procurement system expose machine-readable tenders/awards/plans with meaningful construction depth? | No HTML-scraping-first production path |
| 7 | North Macedonia | FORENSIC_RESEARCH | Is national data materially richer than shared European visibility and cheap enough to maintain? | Require source-native construction/lifecycle evidence |
| 8 | Bosnia and Herzegovina | FORENSIC_RESEARCH | Can fragmented procurement be covered coherently without disproportionate jurisdictional maintenance? | HOLD/REMOVE if fragmentation dominates marginal value |
| 9 | Montenegro | FORENSIC_RESEARCH | Is national depth commercially material or merely small-market completeness? | Prefer HOLD/REMOVE unless near-zero-cost reuse is proven |

## Evidence standard

For each market, record separately: official publisher/live access; legal reuse; freshness/completeness/identity/lifecycle; construction and early-signal value; exact shared-family fit; economics; and a final BUILD/SHARED/TECH_LAB/HOLD/REMOVE decision. No source becomes `ready`, no market becomes commercially active, and no dedicated connector is authorized from documentation claims alone.

## Hard implementation gates

A connector may be implemented only after official source identity, stable non-manual machine access, lawful commercial reuse, bounded completeness semantics, durable identity/cursor strategy, source-native construction filtering, safe lifecycle closure, fail-closed behavior, material incremental value and acceptable engineering/maintenance opportunity cost are demonstrated.

## Turkey / Türkiye — forensic result 2026-08-25

**FACT / VALUE.** KIK operates EKAP nationally. Official material states that the public tender search exposes more than 100,000 tender notices per year plus tender documents and contract information; the refreshed search adds full-document search and more than twenty filters. Current KIK statistics expose tender notices, tenders, reported contracts and reported contract value. Exception procurements are also increasingly executed electronically through EKAP. This is high national and lifecycle depth, including strong construction potential.

**MACHINE ACCESS.** The directly observable legacy public tender-search route is JavaScript-dependent and includes a human challenge/captcha. This cell did not establish an official stable public API/feed/bulk export suitable for production ingestion. ObraSignal must not build captcha bypassing or label browser automation as an API.

**LEGAL.** Free public access is established; commercial SaaS redistribution permission is not sufficiently established. Reuse is UNPROVEN.

**DECISION: HOLD_MACHINE_ACCESS.** Reopen immediately when KIK/EKAP exposes/documents a stable API, feed or bulk export without human challenge and commercial reuse is established. Turkey then deserves a fresh BUILD-vs-HOLD economic comparison because the underlying product value is strong.

## Serbia — forensic result 2026-08-25

**FACT / LIVE DEPTH.** The official Public Procurement Portal is live and national. At inspection it exposed 2026 counters for roughly 98k notices and 29k procedures, almost 10k procedures still within deadline, recent award/suspension decisions, and 3.7k procurement plans. The portal explicitly surfaces notices, procedures, decisions and plans. The Public Procurement Office states that from 1 January 2024 contracting authorities must publish contract and contract-amendment data on the portal. Unauthenticated users can search procedures, notices, plans, decisions and rights-protection decisions, and inspect procedure detail through the mobile/public experience.

**EARLY SIGNAL / LIFECYCLE.** Serbia is technically attractive because plans are first-class portal objects, while awards, suspensions, contracts and contract amendments provide downstream lifecycle. The legal framework uses CPV and standard publication forms. This is materially more useful for ObraSignal research than a notice-only portal.

**MACHINE ACCESS.** This investigation did not prove a public official API. Independent 2024 open-data analysis reports that portal data can be downloaded in Excel/JSON, including lists of procedures, but detailed procedure data lacks a publicly available open API endpoint and exports are limited/not real-time. Treat that report as supporting evidence, not an official API contract. A production connector therefore remains blocked until the exact current export/endpoints, completeness, pagination and incremental semantics are live-validated.

**LEGAL.** Free public search is established. Commercial redistribution/reuse for an automated SaaS feed remains UNPROVEN and must be closed separately.

**REUSE.** Do not claim OCDS/eForms family compatibility merely because JSON/export exists. Transport and lifecycle semantics are not yet proven to match any existing family.

**DECISION: TECH_LAB_CANDIDATE, not commercial BUILD.** Serbia has enough plan + procedure + award/contract lifecycle depth to justify continued technical investigation. It does not yet justify a dedicated production connector. Reopen commercial promotion when a stable incremental machine route and lawful reuse are demonstrated; then compare marginal value against the 13-connector target rather than expanding it automatically.

## Switzerland — closed reference case

Switzerland is the reference for what "done" means in this cell, not an item to redo. The repository already contains `SIMAPConnector`, a public structured construction search, lot-aware identity, bounded pagination, durable date/tracked-target cursoring, lifecycle closure, and a legal 08:00 Europe/Zurich release gate. Its registry state is `ready` but runtime remains opt-in.

## Current decisions

- **Switzerland:** DONE / BUILD reference; no duplicate work.
- **Turkey / Türkiye:** HOLD_MACHINE_ACCESS; strong product potential, no connector until machine-access + commercial-reuse gates close.
- **Serbia:** TECH_LAB_CANDIDATE; unusually useful plans/lifecycle, but public incremental API + reuse are unproven.
- **Ukraine:** HOLD inherited; research may improve technical knowledge but must not silently promote commercial scope.
- **Georgia, Moldova, Albania, North Macedonia, Bosnia and Herzegovina, Montenegro:** still require source-forensic evaluation.

## Next executable sequence

1. Ukraine: technical-source audit only; preserve HOLD unless the canonical blocker changes.
2. Georgia and Moldova: prioritize reusable structured/OCDS-compatible routes.
3. Albania, North Macedonia, Bosnia and Herzegovina, Montenegro: evaluate in descending expected value; stop early where fragmentation or tiny marginal value clearly fails the opportunity-cost test.
4. Only after evidence exists, update canonical portfolio/scope registries and tests in a separate implementation change; do not mix unverified research assertions into production registries.
