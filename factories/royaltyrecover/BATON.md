# RoyaltyRecover BATON

BATON_READY: true
BATON_CAPTURE_DATE: 2026-08-29

## MISSION
Build RoyaltyRecover into a real evidence-first contractual royalty/revenue-share recovery company and operational web application that can identify, quantify, evidence, route, monitor and ultimately verify incremental recoveries without invented entitlements or unsupported calculations.

## VERSION / HEAD
HEAD_BEFORE_BATON_WRITE: `3918835d777a4c247207f5f2d7e1c41cc34fcefd`
BASE_MAIN_AT_FACTORY_CREATION: `66d43f6fd51cf9cea08016dad335aaa04b711a24`
ENGINE_VERSION: `0.2.0`

The BATON metadata commit necessarily follows HEAD_BEFORE_BATON_WRITE; source truth on resume is the branch ref.

## BRANCH
`royaltyrecover/company-web-app`

## PR
NONE. A draft-PR creation attempt through the connector was blocked by the connector/OpenAI safety gate. No bypass attempted. No merge performed.

## DONE
- Created isolated RoyaltyRecover branch from verified ObraSignal main.
- Forensically validated that royalty underpayment/recovery is a real high-value problem.
- Persisted quantified audit/recovery evidence and audit-right patterns.
- Mapped serious audit/service/software competition including Connor, Quartiq, IMA360, FADEL, Invotex, Stout, 360 Royalty Audit and others.
- Rejected generic "AI royalty leakage detection + continuous monitoring" as differentiated.
- Rejected broad "patent/technology recoverability assurance" as sufficiently differentiated after Connor collision.
- Identified compound candidate wedge: zero-migration recoverability triage for B2B running-royalty portfolios, combining sourced contract rules, deterministic reconciliation, audit/lookback triage, evidence readiness and professional-audit routing.
- Established Gate 1 PASS; Gate 2 provisional patent/technology with TTO beachhead; Gate 3 OPEN.
- Created initial Portugal legal/professional boundary: pure lawyer quota-litis cannot be assumed lawful; success pricing remains jurisdiction-specific and unverified; formal auditor qualifications remain contract-specific.
- Defined assisted commercial offer and pricing experiments while explicitly marking absolute price bands as hypotheses.
- Built 33-table evidence-first SQLite schema.
- Built deterministic royalty engine v0.2.0 supporting gross/net-sales percentage, per-unit, progressive tiers, minimum guarantee, cap, floor, sublicense share and sourced FX conversion.
- Built fail-closed states: UNKNOWN / NEEDS_DATA / REQUIRES_PROFESSIONAL_REVIEW / NO_DEFENSIBLE_RECOVERY / RECOVERY_CANDIDATE.
- Built deadline assessment that does not infer loss of rights from a passed supplied date.
- Built deadline-first portfolio recoverability ranking.
- Built minimum service pipeline: contract rule -> calculation -> scan -> evidence pack -> information requests, with claim_ready always false absent later review layer.
- Built authenticated minimum Flask scan API in isolated Factory path.
- Added organization-bound API credentials and explicit cross-tenant mismatch rejection before persistence.
- Added isolated GitHub Actions quality workflow.
- CI at commit `4747956dfbc2e486a2c47a7f2693ded916c2778a`: SUCCESS, 40 tests, SQLite schema 33 tables / foreign-key check clean.
- CI at commit `d07dffda94f57460e7af8fd494eb5f2f575921eb`: SUCCESS, includes first Flask web API tests before organization-bound auth revision.

## IN_PROGRESS
- Validate CI for cross-tenant organization-bound credential revision at `3918835d777a4c247207f5f2d7e1c41cc34fcefd`.
- Deepen Gate 3 differentiation through deployment/pricing friction and partner economics versus Connor/Quartiq/enterprise royalty software.
- Turn minimum stateless API into tenant-safe persistent workflow only after auth/isolation invariants remain green.

## ACTIVE
Verify the latest cross-tenant-auth CI result. If green, design tenant-scoped persistent repository layer for Organization/Licensor/Licensee/Agreement/AgreementVersion/Evidence without exposing shared ObraSignal runtime.

## NEXT
1. Verify latest CI and repair immediately if red.
2. Build tenant-scoped SQLite repository/store with every query anchored to authenticated organization.
3. Add agreement/version/evidence ingestion endpoints with SHA-256 lineage and immutable version semantics.
4. Add calculation-run persistence and stale-calculation invalidation when operative agreement version or source dataset changes.
5. Add human review state before any recovery assertion.
6. Add executive recoverability register endpoint/UI.
7. Continue differentiation/pricing/partner research in parallel.
8. Validate initial TTO beachhead commercial-speed/procurement assumptions.
9. Add formal auditor partner routing model.
10. Only after Gate 3/4 evidence improves, expose assisted pilot externally.

## WAIT
- Draft PR creation via connector: blocked by safety gate; not needed for continued branch execution.
- Real-client recovery proof: external commercial gate, cannot be replaced by synthetic data.
- Jurisdiction-specific legal opinion on RoyaltyRecover success-fee/claims-handling model: external professional dependency before real launch using that pricing component.

## BLOCKERS
No blocker to continued safe product/research work.

## OWNER-ONLY DEPENDENCIES
None for current build/research slice. Real contracting, regulated/legal representation decisions and any final engagement requiring owner signature remain owner-only when reached.

## EVIDENCE
Key persisted evidence files:
- `FORENSIC_VALIDATION.md`
- `COMPETITOR_TEARDOWN.md`
- `WEDGE_DECISION_02.md`
- `LEGAL_PROFESSIONAL_BOUNDARY.md`
- `ICP_EVIDENCE.md`
- `COMMERCIAL_OFFER.md`

Key external findings include UC royalty-audit recoveries, Vianix/Invotex quantified underpayment, public SEC audit-right clauses, AUTM audit workflow/staffing/licensing evidence, Connor technology-licensor desk reviews, Quartiq continuous compliance, Tallowe deadline/evidence-pack collision and Portugal Ordem dos Advogados Article 106/107.

## DECISIONS
- THESIS: PROCEED, MODIFIED; current internal prioritization score 75/100 after competition collision, not a probability.
- GATE 1: PASS.
- GATE 2: PROVISIONAL — patent/technology, with university/research TTO as current beachhead to validate.
- GATE 3: OPEN — wedge not frozen.
- GATE 4: PARTIAL / NOT PASSED — legal/professional launch checklist incomplete.
- Never market a deterministic variance as a formal audit conclusion or legal claim.
- Never infer an audit right, lookback deadline, FX rate, deduction permission, rate, product scope or recoverability from market norms.
- Do not integrate into shared ObraSignal runtime until RoyaltyRecover isolation, tenant model and product boundary are stronger.

## PRODUCT TRUTH
Current product is an isolated prototype/minimum operation, not pilot-ready and not production-ready.
It can calculate supported simple/expanded royalty rules, fail closed on unsupported cases, triage licensees, create an analytical evidence-pack object and serve a protected scan API.
It does NOT yet ingest real documents/files, extract clauses automatically, persist tenant data, implement a human review approval workflow, conduct a formal audit, represent a client, send recovery demands, or verify real recovered money.

## BUSINESS TRUTH
Problem is validated and economically material. Generic feature differentiation is not validated. TTO beachhead has stronger observable workflow/channel evidence but university procurement economics are not yet validated. Exact EUR pricing remains experimental. No real client, paid audit or verified recovery exists yet.

## TEST STATE
- Verified green through commit `4747956dfbc2e486a2c47a7f2693ded916c2778a`: 40 unit tests PASS; schema validation PASS with 33 tables and no foreign-key violations.
- Verified green through commit `d07dffda94f57460e7af8fd494eb5f2f575921eb`: Flask dependency install + web API tests PASS.
- Latest auth/isolation revision at `3918835d777a4c247207f5f2d7e1c41cc34fcefd`: CI was IN_PROGRESS at baton capture.

## CI STATE
IN_PROGRESS for latest head-before-baton; prior relevant runs SUCCESS.

## REGRESSIONS
NONE KNOWN. If latest CI fails, that failure becomes BATON.ACTIVE immediately.

## MODIFIED FILES
- `.github/workflows/royaltyrecover-quality.yml`
- `factories/royaltyrecover/FORENSIC_VALIDATION.md`
- `factories/royaltyrecover/COMPETITOR_TEARDOWN.md`
- `factories/royaltyrecover/WEDGE_DECISION_02.md`
- `factories/royaltyrecover/LEGAL_PROFESSIONAL_BOUNDARY.md`
- `factories/royaltyrecover/ICP_EVIDENCE.md`
- `factories/royaltyrecover/COMMERCIAL_OFFER.md`
- `factories/royaltyrecover/schema.sql`
- `factories/royaltyrecover/royalty_engine.py`
- `factories/royaltyrecover/recoverability_scan.py`
- `factories/royaltyrecover/service_pipeline.py`
- `factories/royaltyrecover/web_app.py`
- `factories/royaltyrecover/test_royalty_engine.py`
- `factories/royaltyrecover/test_recoverability_scan.py`
- `factories/royaltyrecover/test_service_pipeline.py`
- `factories/royaltyrecover/test_web_app.py`
- `factories/royaltyrecover/BATON.md`

## UNVERIFIED WORK
At baton capture: organization-bound API-key/cross-tenant revision on commit `3918835d777a4c247207f5f2d7e1c41cc34fcefd` pending CI.

## UNRESOLVED ASSUMPTIONS
- TTOs are commercially faster/cheaper enough to serve as the first beachhead despite institutional procurement.
- Zero-migration triage can be delivered materially cheaper/faster than Connor/other incumbent desk reviews.
- Partner channel economics create a durable acquisition/distribution advantage.
- Experimental scan/monitoring price bands produce acceptable gross margin.
- Exact success-fee structure is lawful/practical in each launch jurisdiction.
- Real customer data will be available at sufficient granularity before exercise of formal audit rights.

## RESUME_AT
Verify check-runs for commit `3918835d777a4c247207f5f2d7e1c41cc34fcefd`; on success proceed directly to tenant-scoped persistence. On failure repair the failing test/code first.

## EXACT NEXT EXECUTABLE ACTION
GET GitHub check-runs for commit `3918835d777a4c247207f5f2d7e1c41cc34fcefd`. If conclusion=success, implement an isolated `repository.py` that initializes `schema.sql` and requires `organization_id` on every create/read path for licensors, licensees, agreements, agreement versions and evidence, then add cross-tenant denial tests.
