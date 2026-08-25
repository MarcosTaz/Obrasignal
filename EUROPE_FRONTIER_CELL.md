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
| 1 | Turkey / Türkiye | FORENSIC_RESEARCH | Does EKAP expose a lawful, stable, machine-readable national route with material works coverage and useful lifecycle/plan depth? | BUILD/HOLD only after live source + reuse + completeness + ROI evidence |
| 2 | Serbia | FORENSIC_RESEARCH | Can the national procurement portal add below-threshold / award / plan intelligence beyond European shared surfaces at acceptable maintenance cost? | Prefer shared/reusable transport; dedicated only if marginal value is material |
| 3 | Ukraine | CANONICAL_HOLD | Is there technical learning worth retaining without pretending normal commercial contractor execution is currently rational? | Do not promote while canonical geopolitical/execution blocker dominates |
| 4 | Georgia | FORENSIC_RESEARCH | Is the national e-procurement surface automatable, reusable and construction-rich enough to justify entry? | Require live proof and commercial reuse evidence |
| 5 | Moldova | FORENSIC_RESEARCH | Does MTender/national infrastructure provide reusable OCDS-like depth and enough market value? | Reuse an existing family only if transport/completeness semantics match |
| 6 | Albania | FORENSIC_RESEARCH | Does the national procurement system expose machine-readable tenders/awards/plans with meaningful construction depth? | No HTML-scraping-first production path |
| 7 | North Macedonia | FORENSIC_RESEARCH | Is national data materially richer than shared European visibility and cheap enough to maintain? | Require source-native construction/lifecycle evidence |
| 8 | Bosnia and Herzegovina | FORENSIC_RESEARCH | Can fragmented procurement be covered coherently without disproportionate jurisdictional maintenance? | HOLD/REMOVE if fragmentation dominates marginal value |
| 9 | Montenegro | FORENSIC_RESEARCH | Is national depth commercially material or merely small-market completeness? | Prefer HOLD/REMOVE unless near-zero-cost reuse is proven |

## Evidence standard

For each market, record separately:

1. **FACT** — official publisher, live endpoint/feed/export, observed fields and pagination/lifecycle behavior.
2. **LEGAL** — commercial reuse/redistribution status and any timing/attribution restrictions.
3. **DATA QUALITY** — freshness, completeness, identifiers, lots, amendments, awards/contracts, plans and documents.
4. **CONSTRUCTION VALUE** — source-native works classification, CPV/local taxonomy, below-threshold depth and early-signal depth.
5. **REUSE** — exact fit or non-fit with `TED_SEARCH`, `EFORMS_XML`, `OCDS_PAGE_API`, `OCDS_OPAQUE_CURSOR`, `OCDS_MONTHLY_BULK`, or a genuinely new repeated contract.
6. **ECONOMICS** — commercial upside versus implementation + annual maintenance burden.
7. **DECISION** — BUILD / SHARED / TECH_LAB / HOLD / REMOVE, with an objective reconsideration trigger where applicable.

No source becomes `ready`, no market becomes commercially active, and no dedicated connector is authorized from documentation claims alone.

## Hard implementation gates

A connector may be implemented only after all of the following are demonstrated:

- official source identity;
- stable machine access without brittle CAPTCHA/manual workflow;
- lawful commercial reuse or a documented gate that prevents production;
- bounded pagination/completeness semantics;
- durable identity and incremental cursor strategy;
- construction filtering that does not depend primarily on guessed keywords;
- lifecycle behavior sufficient to avoid presenting closed/revoked opportunities as live;
- fail-closed behavior when completeness cannot be guaranteed;
- material incremental product value versus current coverage;
- expected engineering/maintenance cost beats the next-best use of the same effort.

## Switzerland — closed reference case

Switzerland is the reference for what "done" means in this cell, not an item to redo. The repository already contains `SIMAPConnector`, a public structured construction search, lot-aware identity, bounded pagination, durable date/tracked-target cursoring, lifecycle closure, and a legal 08:00 Europe/Zurich release gate. Its registry state is `ready` but runtime remains opt-in.

## Current decisions

- **Switzerland:** DONE / BUILD reference; no duplicate work.
- **Ukraine:** HOLD inherited; research may improve technical knowledge but must not silently promote commercial scope.
- **Turkey, Serbia, Georgia, Moldova, Albania, North Macedonia, Bosnia and Herzegovina, Montenegro:** not yet classified by this cell. Absence from the current 135-market canonical registry is not evidence of poor data; each requires source-forensic evaluation before any scope mutation.

## Next executable sequence

1. Turkey: official-source + machine-access + legal-reuse + works-depth probe.
2. Serbia: same forensic gate.
3. Ukraine: technical-source audit only; preserve HOLD unless the canonical blocker changes.
4. Georgia and Moldova: prioritize reusable structured/OCDS-compatible routes.
5. Albania, North Macedonia, Bosnia and Herzegovina, Montenegro: evaluate in descending expected value; stop early where fragmentation or tiny marginal value clearly fails the opportunity-cost test.
6. Only after evidence exists, update portfolio/scope registries and tests in a separate implementation change; do not mix unverified research assertions into production registries.
