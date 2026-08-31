# BATON — Engineering Change Recoverability Assurance

MISSION: build and prove the narrowed independent engineering-change recoverability business without overstating entitlement, recoverability or payment.
CURRENT_TERMINAL: T1 — PILOT CAPABLE; CODE_PRODUCTION_BOUNDARY_CLOSED.
NEXT_TERMINAL: HOSTED_PRODUCTION_VERIFIED, then T2 — MARKET EXPOSED.
CURRENT_WEDGE: independent recoverability assurance for Tier-1/Tier-2 automotive suppliers; no PLM/ERP/CPQ replacement.
REPOSITORY: MarcosTaz/Obrasignal
CANONICAL_FACTORY_BRANCH: factory/engineering-change-recoverability
PRODUCTION_BOUNDARY_BRANCH: factory/engineering-change-production-boundary-20260831
PRODUCTION_BOUNDARY_BASE: 807edf812197edeec77f80639faab06f1bd0902d
PRODUCTION_BOUNDARY_FIRST_GREEN: 727733c9825692f155bb06798d81ff82c3cfaf6d
CI_RUN_FIRST_GREEN: 33347634921 — SUCCESS
VERSION_RULE: verify live branch ref before every new write; repository truth overrides this BATON if branches advance.
DONE_PRODUCT: forensic validation; deterministic recoverability engine; 26-case independent oracle; exact evidence binding; mixed-currency and unsupported-entitlement fail-close; commercial package; correct EUR 0 truth.
DONE_SECURITY: signed tenant principals with bounded TTL/role/JTI; authenticated real-record analyze/persist; cross-tenant rejection; HMAC-SHA256 audit chain; OWNER-only purge; retention purge; AES-256-GCM encrypted backup/restore; wrong-key failure; DB integrity check; fail-closed production readiness; bounded HTTP bodies; security headers; no customer-file upload surface.
DONE_TESTS: 45 unittest cases PASS with ResourceWarning as error; production HTTP smoke PASS; compile PASS. The isolated workflow protects both Factory branches.
PRODUCT_TRUTH: code production boundary is verified; this does NOT prove a hosted confidential-data deployment, real customer value, entitlement, recovered cash, WTP or market validation.
HOSTED_STATE: NOT_VERIFIED_FOR_CONFIDENTIAL_CUSTOMER_DATA.
MALWARE_SCAN: N/A in current slice because there is no customer-file upload endpoint. If upload/storage is introduced, malware/quarantine becomes a release gate.
T2_RESEARCH: ranked prospecting cohort = Lear 97, Yanfeng 96, Magna Seating 94, Aptiv 93, FORVIA 91, ZF 86, Autoliv 78. Scores are heuristics based on public workflow evidence, not proof of leakage.
COMMERCIAL_STATE: CONTACTED=0; REPLIED=0; QUALIFIED=0; REAL_DATA=0; PILOT_OFFERED=0; PAID=0. Pricing hypothesis remains unverified.
BLOCKERS: no verified dedicated hosted production environment for this Factory; no correct dedicated commercial sender identity for clean market exposure; no real customer evidence.
ACTIVE: final CI on latest production-boundary SHA, then fast-forward canonical Factory branch if green.
NEXT: after canonical promotion, pursue hosted deployment only through a provider/project with correct dedicated secrets and persistence; otherwise continue to the next Factory whose canonical source is safely executable.
RESUME_AT: verify latest production-boundary workflow SUCCESS -> fast-forward factory/engineering-change-recoverability -> verify canonical workflow SUCCESS.
