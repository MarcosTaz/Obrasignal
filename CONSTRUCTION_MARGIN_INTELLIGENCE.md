# ObraSignal — Construction Margin Intelligence

**Research / prototype architecture — 2026-08-26**

This is a bounded extension of the existing Contractor Intelligence Operating System. It does not create a second roadmap, does not replace the canonical execution queue, and is not production authorization.

## Strategic thesis

ObraSignal should not stop at finding and prioritizing work. A contractor can win the right project and still destroy the economics through undocumented scope change, late notices, weak evidence, cost leakage, under-recovery, or learning nothing from the final margin.

The target loop is:

`OPPORTUNITY → DECISION → BID → WIN → EXECUTION → CHANGE → ECONOMIC IMPACT → RECOVERY → REALIZED OUTCOME → NEXT BID`

The first wedge is **Change Order / Variation & Margin Recovery Intelligence**. Construction Estimating AI is a later consumer of the observed execution and recovery data rather than the first standalone product.

## Problem to solve

Detect when observed execution may have diverged from the agreed commercial scope, assemble evidence, quantify economic exposure without fabricating entitlement, preserve notice/deadline context, and track the outcome through payment.

The product question is not merely:

> Was there a change order?

It is:

> **Where is margin at risk, what evidence supports the risk, what action is justified now, and what did the company actually recover?**

## Non-goals

Do not build a generic ERP, project-management suite, accounting system, document store, email client, timesheet product, or legal-claims robot.

Prefer integrations/imports for drawings, RFIs, instructions, daily logs, cost records, timesheets, procurement records, invoices, correspondence and programme data. ObraSignal owns the decision-relevant commercial intelligence contract, not every upstream system.

## Canonical evidence chain

Potential inputs may include:

- contract / order / agreed scope;
- BoQ / estimate / priced schedule;
- drawing and specification revisions;
- RFIs and responses;
- site instructions and meeting records;
- daily logs and photos;
- labour hours and equipment usage;
- material orders and supplier invoices;
- subcontractor cost;
- programme / delay evidence;
- submitted variation or change-order records;
- approved value;
- payment evidence;
- final project margin / outcome.

Every material conclusion must retain provenance to the underlying evidence. A document mention or LLM extraction is not authority by itself.

## Truth model

The system must keep these concepts separate:

1. **SCOPE CHANGE CANDIDATE** — observed evidence suggests original and current scope may differ.
2. **EVIDENCE STATUS** — whether the candidate has enough traceable evidence for review.
3. **COST IMPACT** — estimated incremental cost range, with basis and uncertainty.
4. **ENTITLEMENT STATUS** — contractual/legal support. `UNKNOWN` is valid and must never be silently promoted.
5. **VALUATION STATUS** — whether a recoverable valuation is supported by contract/rate/measurement evidence.
6. **SUBMITTED VALUE** — what was actually submitted.
7. **APPROVED VALUE** — what was actually accepted/approved.
8. **PAID VALUE** — what was actually paid.
9. **REALIZED MARGIN EFFECT** — only from observed financial outcome evidence.

`COST IMPACT != RECOVERABLE VALUE != APPROVED VALUE != PAID VALUE != REALIZED MARGIN`.

## Fail-closed legal/economic rules

- The AI must never assert `YOU ARE ENTITLED TO X` from a scope delta alone.
- `ENTITLEMENT_UNKNOWN` remains the default until the applicable contract, jurisdiction/rules where relevant, clause/basis and supporting facts are available.
- A detected change may create **margin-at-risk evidence** without creating a legal entitlement claim.
- A value range must identify whether it is cost impact, proposed valuation, submitted amount, approved amount or paid amount.
- No predicted profit, recovery probability or win probability may be presented as realized fact.
- Notice/deadline advice must preserve contract/jurisdiction provenance and uncertainty.
- Private project documents and employee-level data must remain tenant-safe, least-disclosed and privacy-proportionate.

## Prototype state model

Candidate evidence state:

`DETECTED → EVIDENCE_PARTIAL → EVIDENCE_SUPPORTED`

Commercial recovery state:

`DETECTED → REVIEWED → SUBMITTED → APPROVED → PAID`

Alternative terminal paths include `REJECTED` and `VOID`.

State progression never implies legal entitlement. `APPROVED` and `PAID` require observed external/accounting evidence, not model inference.

## First useful product surface

A bounded Margin-at-Risk worklist can show, per candidate:

- project / work package;
- detected scope delta;
- evidence completeness;
- estimated **cost impact** range;
- entitlement status;
- notice/deadline status where proven;
- submitted / approved / paid values where observed;
- next justified action;
- source links / evidence pack.

Example semantic output:

> Potential scope change detected. Estimated incremental cost: €4.2k–€5.1k. Evidence: drawing revision + site instruction + 31 labour hours. Contractual entitlement: UNKNOWN. Notice deadline: UNKNOWN. Next action: commercial review before submission.

This is intentionally weaker than a fabricated €8k “recoverable” claim and therefore safer and more trustworthy.

## Learning loop and moat

Once real outcomes exist, the system can learn from:

- estimate vs actual cost;
- predicted vs realized productivity;
- change cause;
- evidence completeness;
- time-to-identification;
- time-to-submission;
- submitted vs approved vs paid value;
- buyer / client approval behaviour where lawfully attributable;
- work type / contract type / project type;
- final margin outcome.

This can later improve estimating, bid/no-bid, buyer risk, contingency, contract review and portfolio decisions.

The defensible loop is:

`BID ASSUMPTION → EXECUTION TRUTH → CHANGE TRUTH → RECOVERY OUTCOME → CONTRACTOR DNA → BETTER NEXT BID`

## Estimating AI position

Do not start with generic `PDF → takeoff → estimate` as the primary wedge. That market is crowded and errors directly create commercial risk.

A later **Estimate Intelligence** capability should consume observed Contractor DNA and project outcomes to answer:

> What price/range/contingency is economically defensible for this contractor on this opportunity?

Useful inputs then include historical actual productivity, observed cost variance, change leakage, buyer behaviour, project type, geography, supply economics and capacity constraints.

## Maturity gates

### RESEARCH

Prove with real contractor workflows that:
- undocumented or under-managed change creates material, repeated economic loss;
- required evidence is practically accessible;
- detection can occur early enough to change behaviour;
- users trust evidence-backed candidates;
- the value proposition beats a generic change-order tracker.

### PROTOTYPE

Prove:
- tenant-safe candidate model;
- deterministic truth-state separation;
- evidence links;
- cost-impact range without false entitlement;
- lifecycle invariants;
- bounded import/integration path.

### PILOT

Measure on real projects:
- candidate precision;
- false-positive burden;
- lead time before ordinary discovery;
- documented value surfaced;
- submitted / approved / paid value;
- hours saved;
- user action rate;
- margin protected only where causally defensible.

### PRODUCTION

Requires legal/privacy/security/authorization/data-lineage/contract/economic gates, calibrated product behavior, integration reliability and commercial evidence.

## Queue / ownership rule

This document is architecture and research evidence only. It must not mutate `master_execution_queue.py` or jump the canonical sequence automatically. Promotion into the queue requires the same economic-value, dependency, safety, evidence and maintenance tests as every other significant capability.

## Permanent decision test

Construction Margin Intelligence should advance only if it can become materially better than a change-order log by combining:

`CONTRACT TRUTH × SCOPE TRUTH × EXECUTION TRUTH × COST TRUTH × EVIDENCE × TEMPORAL TRUTH × RECOVERY OUTCOME → BEST NEXT COMMERCIAL ACTION`.
