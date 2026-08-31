# Forensic validation — 2026-08-28

## Decision

**NARROW / T0 SURVIVED**

The broad thesis `engineering change -> cost impact -> commercial recovery` is real but not whitespace. It is already addressed partially by PLM/change-management systems, automotive profitability platforms and specialist consulting.

The promoted wedge is:

> **Independent Engineering Change Recoverability Assurance for Tier-1/Tier-2 automotive suppliers** — a no-replacement, evidence-first audit/monitoring layer that finds customer-driven engineering changes with unrecovered or at-risk value, reconstructs the exact technical/commercial baseline, quantifies only causal evidenced deltas, tests mitigation and prior payment, checks entitlement and notice conditions, and prepares a defensible commercial action package.

## Why the problem is real

- Recent engineering-management literature cites roughly 1,000 engineering changes per month at a German automotive OEM with estimated per-change cost of EUR 20k-50k.
- Cross-organisational automotive engineering-change research reports more than 1,000 change orders per month at VDA OEM members and examples of much higher part-change volumes, with manual cross-company communication and material process cost.
- Public supply agreements explicitly connect buyer-requested engineering changes to price, schedule, material-on-hand, obsolete inventory and equitable adjustment/reimbursement mechanisms.
- Current automotive job descriptions explicitly assign engineering-change commercialisation, cost recovery, tooling recovery, piece-price adjustment and payment tracking to Account Management, Program Finance, Purchasing and Program Management roles.

## Collision / why generic positioning is rejected

- PTC Windchill supports engineering-change workflow and recurring/non-recurring cost fields.
- Siemens/Teamcenter and adjacent PLM products reduce ECO processing cost and manage change traceability.
- CONTACT Software combines engineering change, product costing and quotation processes.
- Campfire Interactive directly markets engineering-change cost governance, recovery workflows and contract-intelligence claims for Tier-1/Tier-2 suppliers.
- Specialist consulting also sells engineering-change commercial recovery / margin protection.

Therefore the company must not position itself as a generic engineering-change-management platform or generic automotive profitability OS.

## Initial ICP

Tier-1 / Tier-2 automotive suppliers with:

- frequent OEM engineering changes;
- meaningful tooling / validation / PPAP / obsolete inventory / engineering-hour exposure;
- program-level P&L ownership;
- fragmented commercial records across email, spreadsheets, PLM, ERP and OEM portals;
- existing commercial team that negotiates ECs but lacks independent closed-loop recoverability assurance.

Likely first users / budget influencers:

1. Account / Sales Director or Senior Account Manager
2. Program Controller / Program Finance
3. Program Manager
4. Commercial Director / VP Sales
5. CFO for portfolio-level leakage audits

## Trigger

Strongest trigger for the first assisted offer:

**An OEM/customer engineering change has already occurred or is active, and the supplier cannot prove in one place that all causal cost, tooling/NRE, obsolete inventory, revalidation/PPAP, mitigation, notice obligations, commercial submission and payment status are reconciled.**

## Assisted offer

**Engineering Change Recovery Audit**

Input bundle: EC/ECR/ECO register, old/new drawing or spec revisions, change notices, quote baseline, tooling/NRE records, inventory/WIP/FG, engineering/quality time, supplier quotes/invoices, customer terms/change clauses, notice history, customer approvals, POs/credits/payments.

Output per change:

- revision and baseline truth;
- affected items;
- evidenced cost delta;
- causality classification;
- mitigation and prior-payment reconciliation;
- contractual basis and notice state;
- recoverable / non-recoverable / unknown amount;
- missing evidence;
- next commercial action;
- audit trail.

Commercial hypothesis to test, not yet proven:

- fixed diagnostic/audit fee plus success fee on incremental verified recovery; or
- fixed per-program audit with optional continuous monitoring subscription.

No pricing is frozen until market evidence exists.

## Kill conditions still active

Reject or narrow again if real target suppliers show that:

- Campfire/PLM/ERP already closes this exact recovery gap with no material residual leakage;
- EC data cannot be accessed without enterprise integration that destroys time-to-value;
- contractual recovery is too bespoke to standardise even with assisted human review;
- recoverable values are too infrequent/small relative to audit effort;
- buyers will not allow success-fee or paid diagnostic structures;
- the incremental recovery cannot be independently verified.
