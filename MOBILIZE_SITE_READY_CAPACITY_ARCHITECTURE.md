# ObraSignal — MOBILIZE + SITE READY + Capacity Intelligence

Status: official future architecture. This document extends the single ObraSignal product and canonical execution queue. It does not create a parallel project, activate travel/booking functionality, or authorize external actions.

## North-star question

For any opportunity or awarded project, ObraSignal should be able to answer:

> **Qual é a forma economicamente melhor de fazer esta obra acontecer sem desperdiçar pessoas, tempo, capital ou margem?**

The answer must go beyond the contract itself and evaluate the practical cost and feasibility of putting the contractor, crew, vehicles, equipment, suppliers and site services in condition to execute the work.

The integrated product loop becomes:

`SIGNAL → UNLOCK → SUPPLY EDGE → TRUSTBRIDGE → MOBILIZE → SITE READY → CAPACITY OPTIMIZER → OFFICE → DNA → SHADOW → COMMAND → ACTION`

The architecture follows one principle:

> **Complexidade no motor. Simplicidade na decisão.**

No capability is promoted because a demo looks impressive. Promotion remains `RESEARCH → ARCHITECTURE → PROTOTYPE → TEST → PILOT → PRODUCTION`, according to evidence, dependencies and measured value.

---

## 1. ObraSignal MOBILIZE

Central question:

> **Qual é a forma mais barata, segura e produtiva de colocar esta equipa nesta obra durante este período?**

MOBILIZE starts from the contractor's operational state plus the project:

- company/base location;
- site location;
- number of workers and specialties;
- expected start/end dates and duration;
- work schedules;
- available vehicles and equipment;
- productivity assumptions and company-specific history;
- labour cost and internal company rules;
- project constraints already known from SIGNAL, documents, UNLOCK, SUPPLY EDGE and OFFICE.

It must compare strategies, not merely calculate isolated expenses.

### Strategy A — daily travel

Model, where sourceable:

- route distance and travel time;
- kilometres/day and total kilometres;
- fuel consumption and fuel price;
- tolls and parking;
- vehicle wear and maintenance assumptions;
- driver requirement;
- paid/unpaid travel time according to the applicable employment/contract context;
- unproductive hours;
- schedule/fatigue exposure;
- total economic cost.

Travel must never be treated as fuel alone.

### Strategy B — accommodation near site

Model:

- minimum, economic and medium accommodation scenarios;
- site distance and local transport;
- parking;
- fuel;
- meals/per diem where applicable;
- periodic home travel;
- cost per worker/day and total crew cost;
- expected operational effect relative to daily travel.

### Strategy C — hybrid

Example: crew travels Monday, stays locally during the working week, returns Friday.

Model the complete travel/accommodation/local-transport pattern and compare its total economics and productivity exposure with alternatives.

### Strategy D — own vehicle vs local rental

Compare:

- sending company vehicle;
- local van/vehicle rental;
- initial crew transport;
- fuel and mileage;
- parking;
- insurance and source-specific rental conditions;
- available company capacity and opportunity cost.

### Strategy E — optimized configuration

The solver may combine, when evidence permits:

- accommodation;
- local van;
- initial/weekly transport;
- equipment rental;
- local legal workforce/subcontract capacity;
- company-owned resources.

The objective is the best global configuration, not the cheapest individual line item.

---

## 2. Mobilization estimates and uncertainty

MOBILIZE must not display false precision.

At minimum, present three scenarios:

- `MINIMUM`
- `PROBABLE`
- `PRUDENT`

Example output:

- Minimum: €8,400
- Probable: €9,700
- Prudent: €11,300

Every material assumption must carry provenance, timestamp where relevant, and confidence.

Use current legitimate data when available for fuel, tolls, accommodation, rental, parking and local services. Otherwise mark the number as an estimate.

Canonical evidence-quality states for operational prices/availability:

- `LIVE`
- `QUOTED`
- `RECENT`
- `ESTIMATED`
- `UNKNOWN`

Never collapse these states into one apparently precise number.

---

## 3. Margin and GO/NO-GO integration

Mobilization is part of opportunity economics, not an accessory cost panel.

MOBILIZE feeds SHADOW and bid costing directly.

Example:

- bid margin before mobilization: 12.6%
- daily travel scenario: 9.8%
- accommodation + local van: 11.4%

COMMAND may then return:

`RECOMMENDATION — ALOJAMENTO + CARRINHA LOCAL`

with the evidence and assumptions explaining why.

A mobilization change must be capable of changing `GO`, `CONDITIONAL GO` or `NO-GO` where economically material.

---

## 4. Fatigue and productivity effect

Long travel may affect usable working time, punctuality, overtime, safety, absence and productivity.

The product must model these effects prudently only when enough evidence exists.

Rules:

- do not invent generic percentage penalties;
- prioritize the contractor's own OFFICE/DNA history where available;
- otherwise use clearly identified external evidence or conservative scenario ranges;
- separate observed fact, estimate, inference and unknown.

The target is **installed economic cost**, not headline travel cost.

---

## 5. ObraSignal SITE READY

Central question:

> **Há alguma coisa que possa impedir esta obra de começar na data prevista?**

SITE READY produces a `PRE-MOBILIZATION READINESS CHECK` driven by project type, geography, contract evidence, site constraints and planned execution strategy.

Possible checks include only what is contextually relevant:

- accommodation and vehicles;
- fuel and parking;
- site access and heavy-vehicle access;
- containers/site office;
- WC, water, temporary electricity and internet;
- storage, fencing and signage;
- waste handling;
- crane, scaffolding, lifts/platforms and equipment;
- safety arrangements;
- unloading/logistics;
- suppliers and transport;
- local permissions/inspections/documentation;
- inductions;
- insurance evidence;
- location-specific constraints.

A `SITE READY SCORE` is permitted only if it is explainable and tied to real blockers. It must not be a decorative score.

Example:

- Site Ready: 82%
- Resolved: accommodation, vehicles, initial supplier
- Critical blockers: heavy access unconfirmed, temporary power, waste container
- Possible delay if unresolved: 4–7 days

Delay estimates must include their evidence/confidence and may remain `UNKNOWN` if there is no defensible basis.

---

## 6. Contextual local-services discovery

The site location may trigger discovery of operational services, but never a generic directory.

Potential categories:

- fuel;
- vehicle rental;
- equipment/tool hire;
- mechanics and tyres;
- cranes, scaffolding and lifts;
- containers and portable toilets;
- waste disposal;
- storage and parking;
- accommodation and transport;
- legally admissible temporary labour;
- safety services;
- local suppliers.

Discovery is driven by the current project need.

Example incident: a critical drill fails. ObraSignal should compare repair, local rental, local purchase, or redeploying equipment from another project and return the economically best valid options.

The UX must not return “137 hotels” or “82 rental firms”. It should reduce viable choices to a small decision set, for example:

- `ECONOMIC`
- `BALANCED`
- `COMFORT`

plus `RECOMMENDED` and an evidence-backed reason.

The same decision compression applies to vehicles, equipment, services and suppliers.

---

## 7. Capacity Acquisition Optimizer

Central question:

> **Qual é a forma economicamente melhor de obter esta capacidade?**

For equipment, labour, specialty, transport, tools or services compare, when applicable:

- `MAKE / OWN`
- `BUY`
- `RENT`
- `SUBCONTRACT`
- `TEMPORARY`
- `REDEPLOY`

Decision economics must include more than current-project price.

### BUY

Consider acquisition, finance/cost of capital, maintenance, transport, storage, residual value, expected future utilization and operational risk.

### RENT

Consider rental price, delivery/collection, insurance/conditions, duration, availability and schedule risk.

### SUBCONTRACT

Consider package price, management load, quality/control, coordination, schedule, commercial risk and capacity relief.

### REDEPLOY

Consider transport, conflict with another project, lost production/opportunity cost and schedule effect.

### Future-demand rule

A current-project rent decision can become buy if SHADOW/FUTURE DEMAND shows sufficiently credible future utilization. The reverse is equally important: do not buy expensive capacity merely because one project needs it.

Future use is probabilistic, not guaranteed. The optimizer must expose sensitivity to pipeline confidence.

---

## 8. CREW ECONOMICS

Central question:

> **Qual configuração humana entrega o melhor custo total instalado, prazo e risco?**

Potential comparisons:

- own crew + daily travel;
- own crew + accommodation;
- own core + local lawful workers;
- own core + subcontract package;
- other combinations justified by the work package.

Model where relevant:

- labour cost and payroll burden;
- travel/accommodation;
- supervision;
- training/induction;
- overtime;
- productivity;
- mobilization;
- quality/control;
- coordination;
- schedule and risk.

Never optimize salary/hour in isolation.

Contractor-specific productivity and outcomes should progressively come from OFFICE → Outcome Graph → Contractor DNA.

---

## 9. ObraSignal DEAD TIME

Objective: identify and reduce economically material idle capacity without pretending downtime can be eliminated.

Potential causes:

- workers waiting;
- equipment idle;
- material shortage;
- access blocked;
- preceding trade unfinished;
- missing drawing;
- inspection pending;
- supplier delay.

Calculate `IDLE COST` only from defensible labour/equipment/time inputs.

Then ask:

> **Existe utilização economicamente melhor para esta capacidade agora?**

Possible recommendations:

- advance another task;
- redeploy crew/equipment;
- use capacity on another nearby project;
- maintenance;
- preparation;
- training;
- schedule reorganization.

Higher-autonomy actions remain gated by ACTION authorization and operational safety.

---

## 10. Automatic recalculation

Material project changes must propagate into operational economics.

Triggers may include changes in:

- duration;
- dates;
- crew size;
- location;
- schedule;
- material strategy;
- required equipment.

Recalculate, as relevant:

- accommodation;
- vehicles;
- fuel/tolls;
- labour;
- equipment rental;
- local services;
- cash;
- margin;
- readiness.

Alert only when the resulting difference is materially useful. Avoid notification noise.

---

## 11. SHADOW, COMMAND and ACTION integration

### SHADOW

Simulate competing configurations across:

- cash;
- margin;
- capacity;
- productivity;
- schedule;
- risk;
- future flexibility.

Scenarios can include daily travel, accommodation, hybrid, local vehicle rental, company vehicle, buy/rent equipment, subcontract and local labour.

### COMMAND

Reduce analysis to a few actionable decisions, for example:

- `MOBILIZE — reserve local accommodation`
- `RENT — local van is economically superior to sending company vehicle`
- `BUY — future utilization justifies ownership`
- `DON'T BUY — rent for five weeks`
- `SITE BLOCKER — confirm heavy-truck access before mobilization`
- `CREW — 5 own + 3 local is the best validated configuration`
- `IDLE RISK — crew A likely loses two days if supplier X slips`

Every recommendation must expose WHY / SHOW ME / WHAT IF through the Evidence Graph.

### ACTION

When explicitly authorized and inside policy, ACTION may orchestrate low-risk operations such as:

- search accommodation/vehicles/equipment;
- request price and availability;
- contact suppliers/service providers;
- compare quotes;
- prepare or execute pre-authorized low-risk reservations/orders where reversible and lawful;
- escalate material commitments for approval.

ObraSignal must not become a travel agency, lender, insurer, full procurement marketplace or generic booking portal. Prefer integrations and partners for commodity execution.

---

## 12. MOBILIZATION PACK

A future presentation layer may summarize all pre-start decisions in one project view.

Example fields:

- Project / start / duration / crew
- Transport — resolved/unresolved
- Accommodation — resolved/unresolved
- Equipment — resolved/unresolved
- Fuel range
- Tolls range
- Accommodation range
- Vehicle range
- Site setup range
- Total mobilization `MINIMUM / PROBABLE / PRUDENT`
- Margin impact
- Site readiness
- Critical blockers

The pack is a projection of the underlying Evidence Graph and scenario engine, not a separate calculation system.

---

## 13. Data quality, privacy and workforce boundaries

### Data quality

Never state price, fuel, accommodation, vehicle, stock or availability as certain without appropriate evidence.

Canonical operational states remain:

`LIVE / QUOTED / RECENT / ESTIMATED / UNKNOWN`

Every material number should retain source, observation time and confidence where possible.

### Privacy

Mobilization must not become invasive workforce tracking.

- use location only when necessary and authorized;
- prefer project/crew-level operational state over continuous individual surveillance;
- apply data minimization and proportional retention;
- do not infer sensitive worker characteristics.

---

## 14. Success metrics

Measure whether these capabilities create real operating value:

- mobilization-cost accuracy;
- travel cost avoided;
- accommodation savings;
- startup delays avoided;
- idle hours/cost reduced;
- equipment utilization;
- rent-vs-buy economic benefit;
- crew productivity impact;
- margin protected;
- user administrative time saved.

Metrics should distinguish estimated value from verified realized outcomes.

---

## 15. Promotion gates

### MOBILIZE

Do not promote to production until:

- route/distance inputs are reliable;
- cost assumptions are transparent;
- travel/local-service data can be sourced lawfully and consistently;
- scenarios are explainable and materially useful.

### SITE READY

Do not promote until:

- blockers are demonstrably useful;
- false-positive burden is controlled;
- local/project requirements are verifiable;
- blocker severity and delay claims are evidence-backed.

### Capacity Acquisition Optimizer

Do not promote until:

- make/buy/rent/subcontract/redeploy economics are internally consistent;
- future utilization from SHADOW/FUTURE DEMAND is integrated probabilistically;
- opportunity cost and residual value are represented where material;
- recommendations survive sensitivity testing.

### CREW ECONOMICS

Do not promote until labour/travel/productivity/supervision assumptions are legally and operationally defensible and contractor-specific learning is possible without invasive tracking.

### DEAD TIME

Do not promote until idle causes/time are captured with enough reliability to produce useful recommendations and measurable savings rather than surveillance/noise.

---

## 16. Anti-bloat rule

Do **not** build:

- a Booking clone;
- a Rentalcars clone;
- a generic travel portal;
- yellow pages;
- full fleet management;
- a full HR system;
- a generic ERP;
- a supplier dump.

Build only the intelligence and orchestration necessary to answer:

> **Como colocar esta empresa em condições reais de executar esta obra pelo menor custo económico total, com risco e margem explicitamente modelados?**

Commodity execution should normally be delegated to integrations/partners while ObraSignal owns the decision model, evidence, scenario comparison, orchestration logic and learning loop.
