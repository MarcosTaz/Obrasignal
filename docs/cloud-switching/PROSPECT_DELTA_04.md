# Cloud Switching — Prospect Delta 0.4

Status: public-source research only. No outreach authorized or sent.

This delta completes the first **30-record trigger sweep**. Records 24–30 intentionally include both actionable and control-group cases; stage remains explicit so completed/recent cases are never counted as fresh acquisition opportunities.

## P24 — Fraunhofer-Gesellschaft virtualization replacement

- Country: Germany
- Stage: `PRE_DECISION`
- Deadline: 2026-09-02
- Trigger: procurement and implementation of a new virtualization platform **to replace the existing VMware licence infrastructure**.
- Challengeability: `EXPLICIT_ALTERNATIVES / REPLACEMENT`.
- Decision within 12 months: YES.
- Multiple alternatives: the replacement category is explicit; exact bidders/vendors remain UNKNOWN.
- Estate size/business case/billing/telemetry/willingness/FinOps: UNKNOWN.
- Canonical score: 35/100 at most from timing + genuine platform alternative, without inventing the remaining inputs.
- Research overlay: +15.
- Why high-value: this is a direct replacement event rather than a renewal proxy.
- Outreach state: `NOT_AUTHORIZED`.

## P25 — Centrum e-Zdrowia

- Country: Poland
- Stage: `RECENT_DECISION / HISTORICAL EARLY-TRIGGER ARCHETYPE`
- Procurement published: 2026-04-03, following an earlier public value-estimation request visible from 2026-01-21.
- Trigger: VMware licences **or equivalent software licences**.
- Quantified option scope in the procurement includes thousands/tens of thousands of per-core VMware-equivalent licence units.
- Challengeability: `EXPLICIT_ALTERNATIVES`.
- Current acquisition value: low because the specific procedure is no longer at the desired early stage.
- Strategic value: extremely high for acquisition-system design because the buyer exposed a **pre-procurement estimation request months before the formal tender**. This validates monitoring `request for estimate / market consultation` as an earlier trigger than the contract notice.
- Outreach state: `NOT_AUTHORIZED`.

## P26 — Aplikacje Krytyczne Sp. z o.o.

- Country: Poland
- Stage: `RECENT_DECISION`
- Published: 2026-04-22
- Trigger: renewal of VMware vSphere Foundation subscription/support for 12 months **or equivalent solution**.
- Estate signal: at least 148 physical processor cores in the base requirement are publicly specified.
- Challengeability: `EXPLICIT_ALTERNATIVES` in procurement language.
- Market consultation before procedure: public notice explicitly says NO.
- Current acquisition value: low due age/closed window; valuable comparator for evidence burden and estate quantification.
- Outreach state: `NOT_AUTHORIZED`.

## P27 — Imprimerie Nationale / IN Groupe

- Country: France
- Stage: `RECENT_DECISION`
- Published: 2026-06-24/25
- Deadline: 2026-07-24
- Trigger: system-architecture virtualization licences of type VMware Cloud Foundation **or equivalent**.
- Estimated value: EUR 10,000,000.
- Contract horizon: 5 years.
- Technical scope publicly includes compute, storage, networking, containers and cloud management.
- Challengeability: `EXPLICIT_ALTERNATIVES`.
- Evidence-access signal: detailed administrative/technical/security documents require NDA, illustrating a realistic assisted-pilot problem — public trigger detection may be easy while decision evidence remains private.
- Current acquisition value: recent control case rather than fresh lead.
- Outreach state: `NOT_AUTHORIZED`.

## P28 — French Ministry for the Economy and Finance / Bercy

- Country: France
- Stage: `IN_PROGRESS / STRATEGIC EXIT EXPLORATION`
- Source: 2026 French parliamentary testimony/reporting on technological dependencies.
- Trigger: ministry officials state they are working on VMware exit points and **testing Proxmox alternatives in depth**.
- Current VMware spend signal: approximately EUR 2.5M/year, annualized from multiyear contracts, stated in the parliamentary testimony.
- Architectural context: VMware is used broadly across the stack for an internal cloud; officials say exit is complex and not short-term. Other parts of the ministry already use OpenStack/free-software infrastructure.
- Challengeability: `EXPLICIT_ALTERNATIVES`.
- Stage nuance: not a simple procurement deadline; this is a long strategic transition, which may actually be a better fit for baseline→checkpoint→outcome assurance if a concrete decision/workload boundary can be identified.
- Original business case/billing/telemetry/willingness: UNKNOWN despite strong public technical context.
- Outreach state: `NOT_AUTHORIZED`.

## P29 — Vlaamse Overheid

- Country: Belgium
- Stage: `RECENT_DECISION / MIXED-PLATFORM CONTROL`
- Trigger: 2026 procurement for management/maintenance and further expansion of **both Nutanix and VMware** virtualization environments.
- Challengeability: heterogeneous infrastructure is proven, but migration/substitution is NOT proven.
- Strategic value: a control case showing that coexistence can be the economically rational outcome; do not force a binary VMware-exit narrative.
- Acquisition value: current tender deadline has passed.
- Outreach state: `NOT_AUTHORIZED`.

## P30 — Kassenärztliche Vereinigung Baden-Württemberg

- Country: Germany
- Stage: `RECENT_DECISION`
- Trigger: VCF successor solution to an existing VMware vSphere Enterprise Plus environment.
- Public secondary procurement detail describes a large core footprint spanning server infrastructure and VDI, reinforcing material estate scale.
- Challengeability: low for the completed/current procurement because the successor was specified as VCF; use as a `RETAIN/EXPAND VMWARE` control rather than an exit prospect.
- Strategic value: proves large integrated Tanzu/NSX/VDI estates exist where migration complexity may rationally outweigh licence savings — exactly the cases the independent decision product must be able to reject.
- Outreach state: `NOT_AUTHORIZED`.

## 30-record sweep conclusion

### What survived

Public signals are sufficiently frequent and structured to support a **trigger-based acquisition research process**. The sweep found multiple live European events in a narrow time window, including direct replacement, explicit equivalent-solution procurement, market dialogue and platform/licensing review.

### What did not survive

The simplistic thesis `VMware renewal = switching lead` is rejected. Many renewals are deliberate stay decisions or merely procurement mechanics.

### Strongest sourcing pattern

`PRE-PROCUREMENT ESTIMATE / MARKET DIALOGUE`
→ `OR EQUIVALENT / REPLACEMENT / ALTERNATIVES`
→ `FORMAL TENDER`
→ `DECISION`

The earlier two states are much more valuable to the forecast-freeze product than discovering the formal tender near its deadline.

### New acquisition metric set

Track per trigger:
- publication date;
- first detection timestamp;
- current deadline + full amendment history;
- days remaining at detection;
- stage;
- challengeability;
- public qualification score;
- whether a pre-procurement event existed;
- whether the original business case can still be frozen: `YES / NO / UNKNOWN`.

### Gate before claiming a scalable channel

Thirty researched records prove **discoverability**, not conversion. Next gate is to estimate the monthly count of `EARLY_DIALOGUE` + `ACTIONABLE` challengeable triggers and determine whether, under conservative conversion assumptions, that flow could support five paid pilots without generic cold-list acquisition.
