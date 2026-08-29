# Portfolio Maturity & Promotion Truth Audit v0.1

Status: INDEPENDENT_GOVERNANCE_AUDIT / NON_RUNTIME / NO_MERGE_AUTHORIZATION

## Scope

Audit Factory Cloud PR #760 planning/maturity metadata, scheduling priority and portfolio-to-application promotion boundaries so planning state cannot silently become repository/runtime/business authority.

Observed owner implementation:
- PR #760
- branch `factory-cloud/shared-platform-portfolio-architecture`
- observed exact HEAD `02fdfc5422acd9b20b4f05ec511ef7f1cba1bf3a`
- exact-head Quality run `33265278871`: SUCCESS

Related global Control Tower owner:
- PR #722
- branch `factory-cloud/global-control-tower-routing`
- current observed HEAD `cfaca761dfb816ac36ac98627671e9e6502b3090`

## 1. Portfolio metadata is explicitly non-authoritative — PASS

`portfolio_architecture.json` describes its purpose as portfolio maturity/shared-capability planning metadata with no source, production, merge, billing or customer-data authority.

Its notes additionally state:
- maturity entries are provisional planning classifications, not business-completion claims;
- `UNASSESSED` is used where evidence is insufficient;
- unregistered application source truth must block repository mutation;
- shared candidates do not imply shared databases, secrets, production authority or customer data.

`architecture_snapshot.py` preserves that boundary with an explicit authority block:
- `grants_repository_write = false`;
- `grants_production_write = false`;
- `grants_cross_app_data_access = false`;
- `grants_merge = false`.

Independent disposition: `PASS_PLANNING_ONLY`.

## 2. Switchboard registration != application source registration — PASS

The portfolio uses `source_status=registered` to mean the Factory exists in the canonical thin switchboard mapping. This is not sufficient for application dispatch.

`promotion_queue.py` independently checks the application registry. A vertical missing from `apps.json` becomes:

`PROMOTION_BLOCKED / canonical_application_source_truth_required`.

Therefore a research/business Factory may be visible and maturity-ranked without gaining repository mutation authority.

Product Market Access / Legal Product Checker remains a relevant example: it is represented in the Factory portfolio but is not to be treated as a canonical application merely because it has a switchboard entry.

Independent disposition: `PASS_FAIL_CLOSED_APPLICATION_PROMOTION`.

## 3. Scheduling priority does not grant capability — PASS

`portfolio_priority.py` calculates a strict lexicographic scheduling score:

`safety > pilot blocker > evidence integrity > commercial leverage > shared leverage > base priority`.

The score only orders eligible work. It does not add adapter capabilities or bypass runtime/source gates.

This is compatible with the required principle:

`PRIORITY MAY SELECT WHAT TO ATTEMPT; IT MAY NOT CREATE AUTHORITY TO EXECUTE.`

Independent disposition: `PASS_SCHEDULING_ONLY`.

## 4. G3 semantics — PASS only as assisted PILOT-CAPABLE

Portfolio gate G3 is named `pilot_capable`.

`PilotReadinessEvidence.ready` requires:
- registered source;
- deterministic calculation proof;
- evidence lineage;
- tenant isolation;
- durable recovery;
- adversarial tests;
- pricing block defined;
- pilot exit criteria defined;
- assisted API;
- runtime provisioned;
- exact 40-character source SHA.

That is a credible engineering/operational readiness contract for beginning an assisted pilot.

It is **not** evidence that a real pilot has already been validated.

Current Aviation and ContractCredit pilot contracts explicitly show:
- `pricing.status = HYPOTHESIS`;
- real contract/evidence ingestion remains a pilot exit criterion;
- human review remains a pilot exit criterion;
- real outcome or no-recovery record remains a pilot exit criterion;
- delivery-cost measurement remains a pilot exit criterion;
- pricing validation/revision remains a pilot exit criterion.

Therefore:

`G3 READY == ASSISTED PILOT-CAPABLE`.

It does not mean:
- `PILOT_VALIDATED`;
- `MARKET_VALIDATED`;
- `FIRST_PAID_OUTCOME`;
- `COMMERCIAL_READY`;
- `PRICING_VALIDATED`.

This non-escalation boundary was routed to Factory Cloud PR #760 in comment `5464503964`.

## 5. Canonical global command D — source truth PASS; composition required

Factory Cloud switchboard registry on PR #760 already records:

`factory-cloud.signal = D`.

`factory_switchboard.py` derives its packet signal from that registry.

The older static Switchboard UI inherited by the PR #760 base still contains historical `Ω`/clipboard behavior, but PR #760 does not modify that file.

The dedicated Control Tower owner PR #722 contains the newer API-dispatch Switchboard:
- footer says `D = Factory Cloud / orquestração global`;
- `LIGAR TODAS` performs `/v1/dispatch` for scope `all`;
- routing no longer depends on manual per-Factory chat URLs;
- states are rendered from API execution truth.

Independent disposition:

`CANONICAL D / API DISPATCH EXISTS IN OWNER PR #722`.

Composition requirement:

`DO NOT INTEGRATE #760 IN A WAY THAT REGRESSES #722 TO LEGACY Ω OR CLIPBOARD-ONLY LIGAR TODAS.`

## 6. Capability maturity remains separate from portfolio maturity — PASS with known exception

A Factory's G0–G6 maturity is not the same state machine as a shared capability's:
- VERTICAL_ONLY;
- CANDIDATE_SHARED;
- SHARED_CONTRACT_PROPOSED;
- SHARED_VERIFIED;
- SHARED_CORE.

The separation is structurally present.

Known independent exception remains:
`source_truth_verification` is labelled `SHARED_VERIFIED` in capability inventory although live remote source-head verification is not proven in the actual persistent worker path. See `FACTORY_CLOUD_SHARED_CAPABILITY_GATE_AUDIT_V01.md`.

## 7. No customer-facing capability overclaim found in the examined Switchboard

The examined Founder Switchboard UI renders Factory identity, routing/readiness estimates and execution states. It does not directly render `duplicate_overlap_detection`, `outcome_fee_lineage` or other assurance capability ids as customer claims.

Therefore no additional customer-facing UI defect was proven from those capability names in this surface.

The scope/naming findings remain important for architecture snapshots, internal maturity reports and future product UI.

## ACTIVE / NEXT / WAIT

ACTIVE: maintain separation among planning maturity, application registration, runtime execution truth and real pilot validation; re-audit any owner changes that cross those layers.

NEXT: exact-head recheck of PR #760, PR #722 and Side Factory PR #608; persist current BATON with the unresolved source-verifier runtime defect and composition constraints.

WAIT: no planning score/maturity state grants merge, deploy, production write, cross-app data, billing/provider authority or real-pilot validation by itself.
