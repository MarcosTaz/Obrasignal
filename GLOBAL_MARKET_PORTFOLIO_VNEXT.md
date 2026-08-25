# ObraSignal — Global Market Portfolio vNext

**Decision date:** 2026-08-24  
**Policy:** maximize commercial value per engineering hour.  
**Scope:** forensic refinement of the completed international-scope rebase; not a restart of worldwide research.

## Executive result

- **TOTAL REVIEWED JURISDICTIONS: 135**
- **BUILD NOW: 14**
- **SHARED COVERAGE: 31**
- **TECH LAB: 3**
- **HOLD / DEFER: 26**
- **REMOVE CURRENT PHASE: 61**
- **Commercially active product coverage: 45 = 14 BUILD + 31 SHARED**
- **Country-specific dedicated connectors required: 13**
- **TECH LAB dedicated connectors: 0**

The prior 2026-08-24 scope audit already eliminated most scope inflation. It retired 32 of 45 legacy dedicated connector candidates and estimated a 55–65% engineering/maintenance reduction. That range remains the current evidence-backed engineering estimate; this vNext refinement does not pretend to have a more precise hours model.

The prior commercial proxy found BUILD+SHARED captured 95.2% of the scored proxy remaining after REMOVE among markets not frozen by HOLD gates. Since BUILD and SHARED are unchanged in vNext, that specific BUILD+SHARED result is unchanged. The older 96.6% BUILD+SHARED+HOLD proxy is not directly relabelled without recomputation because three former HOLD markets are now TECH LAB and Namibia moves from REMOVE to HOLD.

## Governing distinctions

`COUNTRY SUPPORTED != DEDICATED CONNECTOR`.

- **BUILD**: active commercial market; dedicated engineering is allowed only when economically/architecturally justified.
- **SHARED**: commercially supported through a common family; no country-specific roadmap while common infrastructure is sufficient.
- **TECH LAB**: research-only market retained for reusable technical learning. It is not commercial coverage, not a launch promise and not authorization for a dedicated connector.
- **HOLD**: future option with zero active development until a specific blocker/reconsideration trigger changes.
- **REMOVE**: no work in the current phase; reconsider only on objective customer, partnership, data/API, legal/reuse or strategic evidence.

## BUILD NOW — existing priority order preserved

1. Portugal
2. Spain
3. Italy
4. France
5. Germany
6. Switzerland
7. United Kingdom
8. Netherlands
9. Poland
10. Brazil
11. Canada
12. United States
13. Colombia
14. Chile

The order is not reopened merely because this audit was requested. Q040 CanadaBuys remains the single ACTIVE master-queue item.

## SHARED COVERAGE

### TED / eForms
Austria, Belgium, Bulgaria, Croatia, Cyprus, Czech Republic, Denmark, Estonia, Finland, Greece, Hungary, Iceland, Ireland, Latvia, Liechtenstein, Lithuania, Luxembourg, Malta, Norway, Romania, Slovakia, Slovenia, Sweden.

### OCDS API / bulk
Dominican Republic, Ecuador, Guatemala, Honduras, Paraguay, Peru, South Africa, Uruguay.

Norway and Sweden remain SHARED despite the user's hold-bias list because TED/eForms makes their marginal geographic coverage cheap. Removing them would reduce display/product breadth without meaningfully reducing connector burden.

## TECH LAB

### Uganda
Official e-GP evidence shows procurement plans, bid invitations, best-evaluated-bid notices and contract-award lifecycle. The value is technical/lifecycle learning; lawful machine reuse plus paid regional traction are still required before commercial promotion.

### Zambia
Active official e-GP provides searchable tenders and annual procurement plans, with lifecycle/status structure and explicit OCDS direction. It is a useful test bed for common-family architecture, not a dedicated market build.

### Tanzania
The prior registry already states that its OCDS characteristics are technically strong while ARPU/WTP does not win the next-100-engineering-hours test. TECH LAB is a more accurate classification than HOLD.

## Important forensic exceptions

### Namibia — REMOVE → HOLD
Namibia has official digital procurement with procurement plans, notices, amendments, opening/evaluation information, awards and cancellations. The blocker is commercial scale plus integration/maintenance burden, not absence of procurement digitalization. It remains zero-development until a reusable machine route, cheap shared adapter or customer demand changes the economics.

### Cabo Verde — remains REMOVE, reason corrected
Cabo Verde has active e-Compras/electronic procurement, including planning/procedure/award/contract-management capability. It stays out of the current phase because the commercial scale and likely ARPU do not beat the opportunity cost of engineering and localization. This is **ECONOMIC PRIORITY FAILURE**, not **DATA FAILURE**.

### South Korea — HOLD
The prebuilt KONEPS connector does not justify active status by sunk cost. Reopen immediately only when the project-owned `KONEPS_SERVICE_KEY` exists and live production validation passes.

### Rwanda — HOLD
A technically interesting OCDS feed does not override the current non-commercial/reuse licensing blocker. Reopen only with lawful commercial authorization/licensing.

## Opportunity-cost rule

A BUILD market must beat the next-best use of 100, 50 and 20 engineering hours and survive an annual-maintenance test. A country does not stay BUILD because work already exists.

A SHARED market is judged on **marginal** cost, not its standalone TAM. Small markets can remain supported when the common adapter makes incremental support nearly free.

A large difficult market can remain HOLD when upside is high but machine access, reuse, localization or GTM gates are not ready.

## Engineering reduction

Current evidence-backed position from the completed scope rebase:
- 45 legacy dedicated candidates considered;
- 32 retired from dedicated active development;
- 13 target country-specific dedicated connectors;
- estimated engineering/maintenance reduction: **55–65%**.

This is already greater than the requested 25–40% geographic-work reduction target. The percentage is an effort estimate, not a naive country-count ratio, because Canada/US/Brazil are heavier than an average retired connector.

## Commercial opportunity preservation

The existing evidence-weighted proxy showed **95.2%** BUILD+SHARED preservation among scored, non-HOLD markets after removals. The measure is a decision proxy, not TAM or revenue forecast. No new percentage is invented for TECH LAB/HOLD optionality until the original scoring data is recomputed under the five-tier taxonomy.

## Top portfolio views

### Top 10 BUILD by preserved canonical execution priority
Portugal, Spain, Italy, France, Germany, Switzerland, United Kingdom, Netherlands, Poland, Brazil.

### 10 high-utility SHARED examples — not falsely ranked where no comparable market score exists
Austria, Belgium, Denmark, Ireland, Norway, Sweden, Dominican Republic, Ecuador, Paraguay, Uruguay.

### 10 strategically important HOLD options — not falsely numerically ranked
South Korea, India, Japan, United Arab Emirates, Saudi Arabia, Australia, Mexico, Kenya, Morocco, New Zealand.

## Remove-current-phase rule

The REMOVE set remains intentionally large: **61 jurisdictions** after Namibia is moved to HOLD. Removal means zero active engineering/research in this phase, not permanent exclusion. Existing cheap shared coverage is never removed merely to make the country count look smaller.

The source of truth for the complete country-by-country decision record is `global_market_portfolio.py`, which derives all 135 entries from the evidence-preserving `market_scope_registry.py` and adds category, scores/UNKNOWN state, strategic role, coverage method, connector family, dedicated-connector requirement, blocker, reconsideration trigger and decision reason.

## Execution consequence

No new master-queue priority is created. Q000's scope-rebase decision is refined by this five-tier portfolio; Q040 CanadaBuys remains ACTIVE. TECH LAB work can occur only when a shared-family/architecture task already justifies the learning or a future explicit promotion gate is opened.

**NEVER SACRIFICE PRODUCT-MARKET FIT FOR MAP COVERAGE.**  
**NEVER BUILD A CONNECTOR WITHOUT AN ECONOMIC OR ARCHITECTURAL REASON.**  
**NEVER KEEP A COUNTRY ACTIVE THROUGH INERTIA.**
