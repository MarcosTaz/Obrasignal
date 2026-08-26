# ObraSignal — Product Superiority Forensic Gap Map

**Base truth:** canonical `main@66d43f6fd51cf9cea08016dad335aaa04b711a24`  
**Purpose:** translate the Contractor Intelligence OS direction into an evidence-based map of what exists now, what is only partial, and what must be proven before ObraSignal can credibly claim decision, timing or execution superiority.

This document does **not** create a second execution queue. `master_execution_queue.py` remains the sole canonical execution queue. This map exists to help the queue and domain owners distinguish competitive advantage from feature breadth.

## Permanent superiority test

For the same contractor, market and decision window:

> **Does ObraSignal enable a materially better and faster commercial decision than the best available alternative, with evidence strong enough that the customer can understand why?**

If that cannot be demonstrated, the capability is not yet a competitive moat regardless of internal sophistication.

---

## 1. Contractor Graph — PARTIAL

### Proven current foundation

The canonical company profile already carries materially useful contractor-specific fields:

- activity;
- contract interests;
- countries;
- CPV prefixes;
- min/max contract value;
- preferred/excluded procedure types;
- geography/regions/radius;
- services;
- capability tags;
- project scales;
- certifications;
- hard exclusions.

The profile is account-scoped and durably persisted.

### Missing for strategic target

The current profile is still predominantly **declared configuration**, not a living Contractor Graph.

Missing or not yet canonical/proven:

- observed pursuit history;
- explicit no-bid reasons;
- wins/losses/outcomes as learning inputs;
- buyer affinity/history;
- project-type performance history;
- execution capacity over time;
- crew/equipment availability;
- cash/guarantee constraints;
- mobilisation constraints;
- supplier/subcontractor relationships;
- observed versus predicted performance;
- learned risk tolerance;
- decision-memory feedback loop.

### Classification

`CONTRACTOR_GRAPH = PARTIAL / DECLARED_PROFILE_STRONGER_THAN_MEMORY`

### Canonical queue relationship

- `Q090_COMPANY_STATE_CONTRACT`
- `Q100_OUTCOME_GRAPH_V1`
- `Q120_OFFICE_SENSOR_RESEARCH`
- `Q140_CONTRACTOR_DNA_V1`

Do not bypass those gates by adding unrelated profile fields ad hoc.

---

## 2. Decision Engine — PARTIAL / STRONG CURRENT BASE

### Proven current foundation

`opportunity_match_pipeline.py` already composes:

- company profile;
- capability profile;
- lot matching;
- CPV evidence;
- geography;
- economic fit;
- hard capability blockers;
- account-specific personalized score;
- structured explanation;
- durable decision log.

It explicitly prevents broad CPV-family matches from being treated as strong evidence and caps customer-visible scores when positive commercial evidence is absent or hard blockers exist.

Current canonical decision states are:

- `QUALIFIED`
- `REVIEW`
- `REJECT`

### Strategic gap

The target product language is more useful if the product can eventually support semantically proven:

- `PURSUE`
- `REVIEW`
- `WATCH`
- `PASS`

But this must **not** be implemented as a rename.

`PURSUE` requires stronger evidence than current `QUALIFIED` if it is presented as an allocation recommendation.  
`WATCH` requires a temporal/future-change contract.  
`PASS` must distinguish rational no-bid from low-score or missing-information states.

### Missing decision dimensions

Current decisioning does not yet prove independent, calibrated layers for:

- competitive position;
- pursuit effort/cost;
- management/bid capacity;
- mobilisation readiness;
- guarantee/cash burden;
- incumbent/buyer context;
- opportunity cost against other pursuits;
- portfolio-level constraints;
- future change probability;
- outcome-calibrated decision quality.

### Classification

`DECISION_ENGINE = PARTIAL / EXPLAINABLE_RULE_ENGINE / NOT_YET_PORTFOLIO_OR_OUTCOME_CALIBRATED`

### Canonical queue relationship

- `Q080_EVIDENCE_GRAPH_V1` is correctly ACTIVE first.
- `Q100_OUTCOME_GRAPH_V1` is required for learning from decisions.
- `Q110_DYNAMIC_ELIGIBILITY_RESEARCH` is required before unlockable blockers become decision inputs.
- `Q150/Q160 SHADOW` are required before portfolio-aware PURSUE claims.
- `Q170_COMMAND_NEXT_BEST_ACTION` is the natural target for a true next-best decision layer.

---

## 3. Customer decision presentation — PARTIAL

### Proven current foundation

Radar enrichment already surfaces layers for:

- profile score;
- lot score;
- geography;
- capability evidence;
- economic fit;
- blockers.

The current summary can distinguish account-scoped decision state and expose a reason.

### Current limitation

The customer experience still centers heavily on score/status presentation rather than a compact **Decision Brief**.

Current status mapping is still built around `QUALIFIED / RELEVANT / REVIEW / REJECT` style states rather than:

- what deserves attention now;
- why now;
- what changed;
- what blocks action;
- what evidence is missing;
- what the next action should be.

### Target

A future evidence-backed Decision Brief should prefer:

1. **Decision** — what should I do?
2. **Why** — strongest positive/negative factors.
3. **Why now** — deadline/change/timing signal.
4. **Unknowns** — what could change the decision?
5. **Next action** — what is the lowest-friction useful step?

No opaque composite score should substitute for those answers.

### Classification

`DECISION_BRIEF = PARTIAL / SCORE_AND_LAYER_PRESENTATION_EXISTS`

---

## 4. Evidence / trust — CURRENT CRITICAL PATH

The strategic direction depends on being able to say WHY / SHOW ME / WHAT IF without presenting inferred facts as source truth.

Current queue correctly places:

`Q080_EVIDENCE_GRAPH_V1 = ACTIVE`

before higher-autonomy COMMAND/ACTION work.

This is not bureaucratic overhead. It is a direct product-superiority dependency because stronger decisions without stronger evidence create stronger-looking mistakes.

### Superiority requirement

For every material recommendation the system should eventually distinguish:

- source fact;
- normalized fact;
- company fact;
- derived feature;
- rule/inference;
- assumption;
- uncertainty;
- counterfactual sensitivity.

### Classification

`EVIDENCE_GRAPH = ACTIVE_CRITICAL_PATH`

---

## 5. Buyer Graph — NOT YET A CANONICAL PRODUCT GRAPH

### Current evidence

Buyer appears in opportunity records and scoring context, but there is no canonical buyer-intelligence subsystem proving a durable buyer entity graph with behavioural history.

### Missing target capabilities

- buyer identity resolution across sources;
- spend/history by work type;
- procurement-route preferences;
- award frequency;
- incumbent/supplier history;
- framework/contract cycles;
- amendment/cancellation behaviour;
- planning/future demand;
- contractor-specific buyer relevance.

### Classification

`BUYER_GRAPH = NOT_BUILT_AS_CANONICAL_INTELLIGENCE_GRAPH`

Do not fake buyer intelligence by aggregating unverified text labels.

---

## 6. Competitor Graph — NOT YET CANONICAL

No current canonical subsystem proves competitor identity, awards, buyer relationships, geography, categories or trajectory as a decision input.

### Required foundations

- award/outcome source authority;
- supplier identity resolution;
- cross-source dedupe;
- temporal history;
- confidence/provenance;
- legal/privacy-safe use;
- explanation contract.

### Classification

`COMPETITOR_GRAPH = NOT_BUILT / RESEARCH_REQUIRED`

Competitive position must remain UNKNOWN until those foundations exist.

---

## 7. Timing superiority — FOUNDATION EXISTS, MOAT NOT YET PROVEN

### Current strength

The generic Signal architecture can already represent non-tender signal classes without forcing them into legacy tender semantics.

This is strategically important because it allows future:

- procurement plans;
- forecasts;
- capital projects;
- market dialogue;
- contract expiry;
- buyer signals;
- competitor signals;
- asset/obligation signals.

### Current gap

There is not yet a proven customer-facing **Lead Time Advantage** benchmark showing that ObraSignal consistently produces actionable intelligence materially before formal tender publication.

### Required proof

For each early-signal family measure:

- first source timestamp;
- first ObraSignal actionable timestamp;
- tender publication timestamp when it later exists;
- days/weeks of useful lead;
- false-signal rate;
- contractor action enabled;
- willingness to pay.

### Classification

`TIMING_SUPERIORITY = ARCHITECTURALLY_ENABLED / MARKET_PROOF_PENDING`

Relevant queue items include `Q190_FUTURE_DEMAND_ASSET_CLOCK`, `Q200_FORCED_DEMAND`, `Q220_WORK_PACKAGE_RELEASE`.

---

## 8. Economic pursuit — EARLY FOUNDATION ONLY

### Current strength

`economic_fit.py` is disciplined about not pretending to predict profit. It can evaluate company-defined value bands, deadline windows and procedure preferences/exclusions and explicitly returns UNKNOWN when contract value is missing.

### Gap

This is not yet an economic pursuit model.

Missing:

- bid preparation cost;
- mobilisation cost;
- cash exposure;
- guarantee burden;
- equipment/crew constraints;
- management capacity;
- probability/scenario uncertainty;
- capacity displacement/opportunity cost;
- portfolio comparison;
- predicted-vs-actual economic feedback.

### Classification

`ECONOMIC_PURSUIT = EARLY_RULE_FOUNDATION / NOT_EXPECTED_RETURN_MODEL`

Do not rename economic fit into expected profit or ROI.

---

## 9. MOBILIZE / execution readiness — STRATEGIC ARCHITECTURE EXISTS, PRODUCT GATED

The repository already contains substantial future architecture for:

- Dynamic Eligibility / Opportunity Unlock;
- Supply Edge;
- TrustBridge;
- Trade Agent;
- MOBILIZE;
- Site Ready;
- Capacity Optimizer;
- Crew Economics;
- Capacity Unit;
- Continuous Opportunity Hunting.

This means the strategic conversation is directionally consistent with existing architecture rather than requiring a restart.

### Critical discipline

Do not turn this into a visible generic marketplace.

Correct future flow:

`PURSUE/REVIEW`  
→ identify execution blocker  
→ determine whether blocker is legally/economically unlockable  
→ compare resolution options  
→ obtain explicit authority  
→ execute the narrow action.

### Classification

`MOBILIZE = STRATEGICALLY_DESIGNED / MATURITY_GATED`

The existence of architecture documents is not production evidence.

---

## 10. Portfolio allocation — FUTURE / DEPENDENCY-HEAVY

A contractor with resources for four bids should not be encouraged to pursue twelve individually attractive opportunities.

True portfolio allocation requires reliable inputs for:

- capacity;
- cash;
- schedule overlap;
- bid effort;
- management bandwidth;
- strategic buyers;
- execution risk;
- outcome learning.

Without these, an optimizer would produce false precision.

### Classification

`PORTFOLIO_ALLOCATION = FUTURE / SHADOW_DEPENDENT`

Do not accelerate ahead of Company State, Outcome Graph and Contractor DNA.

---

## 11. International depth — STRONG SCALE FOUNDATION, PRODUCT DEPTH MUST REMAIN EXPLICIT

The repository already has substantial multi-country/source infrastructure. The competitive risk is claiming national depth from shared-family coverage alone.

Permanent product rule:

- number of countries is a scale metric;
- **useful, legal, fresh, explainable market depth is the product metric**.

A country should not be marketed as deeply supported merely because TED/OCDS includes records from it.

### Classification

`GLOBAL_SCALE = STRONG_FOUNDATION`

`MARKET_DEPTH = COUNTRY_SPECIFIC / MUST_BE_PROVEN`

---

## 12. Distribution — STRATEGIC GAP OUTSIDE CORE CODE

The repository has strong product/engineering strategy but no code artifact can prove distribution superiority.

Required business evidence must eventually include:

- acquisition channel by ICP/country;
- association/partner leverage;
- sales cycle;
- conversion;
- first value;
- retained payment;
- reasons for non-adoption;
- partner economics.

### Classification

`DISTRIBUTION_MOAT = UNPROVEN`

Engineering must not mistake a stronger product for automatic distribution.

---

# Highest-value execution sequence

This map does **not** supersede the canonical queue. It clarifies why the current queue order is strategically sensible and where additional evidence should be routed.

## Phase A — Decision superiority

1. `Q080 Evidence Graph v1`
2. preserve/fix account-specific decision authority and reason fidelity
3. create a real decision-quality evaluation protocol
4. establish contractor-specific Top-K benchmark
5. evolve customer presentation toward Decision Brief without semantic overclaim

**Exit evidence:** same contractor + same market → measurably better/faster useful decision than baseline.

## Phase B — Learning moat

1. Company State contract
2. Outcome Graph
3. real pursuit/no-bid/win/loss capture
4. Contractor DNA

**Exit evidence:** system improves from observed outcomes rather than only static profile declarations.

## Phase C — Context moat

Research and prove canonical:

- Buyer Graph;
- Competitor Graph;
- award/contract history;
- change intelligence.

**Exit evidence:** buyer/competitor context changes a material decision correctly and explainably.

## Phase D — Timing moat

Promote only early-signal families that demonstrate useful lead time and acceptable false-signal rates.

**Exit evidence:** Lead Time Advantage with customer action value.

## Phase E — Execution moat

Dynamic Eligibility → SHADOW → ACTION architecture → Supply Edge → MOBILIZE/Site Ready/Capacity.

**Exit evidence:** a real blocker is identified, correctly classified, economically resolved, and changes an opportunity decision or execution readiness without compromising trust.

## Phase F — Economic network

Only after repeated blocker-resolution demand exists should supplier/equipment/finance/insurance transaction rails scale.

**Exit evidence:** repeated transaction value, independent ranking, retained trust and measurable economics.

---

# Things to deliberately NOT build now

Unless evidence changes the decision, do not divert execution into:

- generic CRM;
- generic ERP;
- full project management;
- generic chat;
- generic file storage;
- generic marketplace directory;
- supplier pay-to-rank;
- proprietary lending/insurance infrastructure;
- opaque AI scores without benchmark evidence;
- broad international expansion whose product depth cannot be defended.

---

# Executive product scorecard

The company should progressively be able to answer these without narrative inflation:

| Advantage | Required proof | Current forensic state |
|---|---|---|
| Selection superiority | real contractor Top-K benchmark | PARTIAL / synthetic & rule evidence exists, market benchmark still required |
| Decision superiority | faster/better PURSUE/PASS-style decision vs baseline | PARTIAL |
| Trust superiority | WHY / SHOW ME / WHAT IF | ACTIVE CRITICAL PATH (`Q080`) |
| Context superiority | buyer + competitor + history changes decision | NOT YET PROVEN |
| Timing superiority | useful lead before formal tender | ARCHITECTURALLY ENABLED / UNPROVEN |
| Learning superiority | outcomes materially improve future decisions | QUEUED FOUNDATIONS |
| Execution superiority | blocker detection + economically valid resolution | STRATEGICALLY DESIGNED / GATED |
| Portfolio superiority | better allocation of scarce bid/execution resources | FUTURE / SHADOW DEPENDENT |
| Distribution superiority | repeatable qualified acquisition + retention | UNPROVEN |
| International superiority | deep useful market support, not country count | PARTIAL / country-specific |

---

# Governing rule

> **Complexity is justified only when it creates a measurable increase in decision quality, timing advantage, execution capacity, trust, retention or economic value.**

The target is not the largest feature set.

The target is for a construction company to say:

> **“ObraSignal shows me what deserves our attention, before we would otherwise know, explains why, and helps us become ready to act.”**
