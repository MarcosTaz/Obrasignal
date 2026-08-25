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
| 1 | Turkey / Türkiye | HOLD_MACHINE_ACCESS | EKAP has exceptional national procurement depth, but is there a supported machine route suitable for production rather than the current interactive/captcha search surface? | Reopen immediately on official/stable API, feed or bulk export plus lawful commercial reuse |
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

## Turkey / Türkiye — forensic result 2026-08-25

### FACT

The official Public Procurement Authority/Kamu İhale Kurumu operates EKAP as the national electronic procurement platform. Current official material says the public tender search gives access to more than 100,000 tender notices per year, tender documents and contract information. The refreshed search adds full-document search and more than twenty filters. Official KIK statistics expose current counts for tender notices, tenders, reported contracts and reported contract value. Official notices also confirm that exception procurements are increasingly executed electronically through EKAP, including invitation/notice, qualification information, electronic bids, evaluation, notifications and award-authority workflow.

The legacy public KSP tender-search surface is interactive, JavaScript-dependent and exposes a human challenge/captcha field. A separate result-notice search exists, so lifecycle depth is visibly present on the human surface.

### DATA / CONSTRUCTION VALUE

Turkey therefore passes the **national depth** and **construction relevance potential** tests strongly. EKAP exposes tender type as a structured search dimension and the authority has a dedicated Works (`Yapım İşleri`) regulatory/workgroup domain. Tender documents, result/contract information and richer bidder/document metadata make the potential incremental intelligence materially deeper than a thin notice-only feed.

### MACHINE ACCESS

This investigation did **not** establish an official, stable, documented public API/feed/bulk export suitable for ObraSignal production ingestion. The directly observable public search path is a browser workflow with JavaScript and a challenge field. That fails the current production machine-access gate. ObraSignal must not implement brittle captcha bypassing or pretend that an interactive public website is a production API.

### LEGAL

Official material establishes free public access to notices, documents, contract-result information and qualification information. It does not, by itself, establish a sufficiently explicit commercial redistribution licence for a SaaS ingestion/redistribution product. Commercial reuse therefore remains **UNPROVEN**, not RED and not GREEN.

### REUSE

No existing shared source family can be claimed. There is no proven TED/eForms or OCDS transport contract here. A Turkey adapter would be source-specific unless a future official API/export proves a reusable contract.

### DECISION

**HOLD_MACHINE_ACCESS.** This is not a commercial rejection. Turkey is a high-value source trapped behind two unresolved production gates: supported machine access and commercial reuse. Do not spend connector engineering on scraping/captcha work.

**Reconsideration trigger:** immediately reopen when KIK/EKAP exposes or documents a stable API, feed or bulk export usable without human challenge and commercial reuse/redistribution is established. At that point Turkey should receive a fresh BUILD-vs-HOLD economic comparison because the underlying national data depth is already strong.

## Switzerland — closed reference case

Switzerland is the reference for what "done" means in this cell, not an item to redo. The repository already contains `SIMAPConnector`, a public structured construction search, lot-aware identity, bounded pagination, durable date/tracked-target cursoring, lifecycle closure, and a legal 08:00 Europe/Zurich release gate. Its registry state is `ready` but runtime remains opt-in.

## Current decisions

- **Switzerland:** DONE / BUILD reference; no duplicate work.
- **Turkey / Türkiye:** HOLD_MACHINE_ACCESS; strong data/product potential, no production connector until machine-access + commercial-reuse gates are closed.
- **Ukraine:** HOLD inherited; research may improve technical knowledge but must not silently promote commercial scope.
- **Serbia, Georgia, Moldova, Albania, North Macedonia, Bosnia and Herzegovina, Montenegro:** not yet classified by this cell. Absence from the current 135-market canonical registry is not evidence of poor data; each requires source-forensic evaluation before any scope mutation.

## Next executable sequence

1. Serbia: official-source + machine-access + legal-reuse + works-depth probe.
2. Ukraine: technical-source audit only; preserve HOLD unless the canonical blocker changes.
3. Georgia and Moldova: prioritize reusable structured/OCDS-compatible routes.
4. Albania, North Macedonia, Bosnia and Herzegovina, Montenegro: evaluate in descending expected value; stop early where fragmentation or tiny marginal value clearly fails the opportunity-cost test.
5. Only after evidence exists, update portfolio/scope registries and tests in a separate implementation change; do not mix unverified research assertions into production registries.
