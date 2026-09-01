# Cloud Switching — Prospect Delta 0.3

Status: public-source research only. No outreach authorized or sent.

## Strongest newly discovered acquisition pattern

A repeatable procurement phrase is emerging across current European buyers:

`VMware ... OR EQUIVALENT`

This is materially stronger than a mechanical VMware renewal because it proves, at minimum, that the formal procurement permits a non-identical solution and that the buyer is within a dated decision window. It still does **not** prove that the buyer intends to leave VMware or that all alternatives are operationally realistic.

## P19 — Bank Gospodarstwa Krajowego (BGK)

- Country: Poland
- Stage: `PRE_DECISION`
- Published: 2026-08-28
- Deadline: 2026-09-07
- TED notice: `592460-2026`
- Trigger: subscriptions corresponding to the buyer's existing VMware licences (Broadcom Site ID publicly referenced in the notice) **or equivalent**, with technical support.
- Decision within 12 months: YES.
- Multiple credible alternatives: YES at formal procurement category level; named alternatives are UNKNOWN.
- Challengeability: `EXPLICIT_ALTERNATIVES`.
- Estate size: UNKNOWN.
- Original business case/billing/telemetry/willingness-to-freeze/FinOps involvement: UNKNOWN.
- Canonical public score: 35/100.
- Research overlay: +15.
- Research priority: 50.
- Why high-value: named financial institution + open current deadline + explicit equivalence language + known installed VMware estate.
- Outreach state: `NOT_AUTHORIZED`.

## P20 — National Health Fund Headquarters (Poland)

- Country: Poland
- Stage: `PRE_DECISION`
- Published: 2026-08-10
- Deadline: 2026-09-09
- Notice: `2026/S 152-552320`
- Trigger: purchase of VMware **or equivalent** temporary licences plus software service and substantive support.
- Decision within 12 months: YES.
- Multiple credible alternatives: YES at formal procurement category level.
- Challengeability: `EXPLICIT_ALTERNATIVES`.
- Estate size and original business case/billing/telemetry/willingness-to-freeze/FinOps involvement: UNKNOWN.
- Canonical public score: 35/100.
- Research priority: 50.
- Outreach state: `NOT_AUTHORIZED`.

## P21 — Procurement Centre for the Judiciary / Court of Appeal in Kraków

- Country: Poland
- Stage: `PRE_DECISION`
- Published: 2026-08-24/25 depending source rendering
- Deadline: 2026-09-24
- TED notice: `585332-2026`
- Trigger: framework agreement for procurement and delivery of all licence types/subscriptions for VMware **or equivalent software** for common courts, including technical, expert and consulting support.
- Decision within 12 months: YES.
- Multiple credible alternatives: YES at procurement category level.
- Challengeability: `EXPLICIT_ALTERNATIVES`.
- Estate size: aggregate judicial-system footprint is likely material but remains UNKNOWN because no quantified estate was verified in the current source.
- Original business case/billing/telemetry/willingness-to-freeze/FinOps involvement: UNKNOWN.
- Canonical public score: 35/100.
- Research priority: 50.
- Why high-value: framework affects multiple court units, making it potentially a cohort-level acquisition surface rather than one isolated buyer.
- Outreach state: `NOT_AUTHORIZED`.

## P22 — Centralny Ośrodek Informatyki (Central IT Center, Poland)

- Country: Poland
- Stage: `RECENT_DECISION` as of current research date; deadline 2026-08-26 has passed.
- Published: 2026-08-19
- TED notice: `573563-2026`
- Trigger: subscriptions matching existing VMware licences **or equivalent**, with technical support and optional extensions.
- Procurement evidence includes a formal parameters schedule for offered products, indicating alternatives have to be demonstrated against requirements rather than merely named.
- Challengeability: `EXPLICIT_ALTERNATIVES`.
- Acquisition value now: reduced because deadline passed, but highly valuable archetype for future early detection.
- Strategic lesson: the system should detect notices at publication, not days before deadline.
- Outreach state: `NOT_AUTHORIZED`.

## P23 — LapIT Oy, expanded timing evidence

- Country: Finland
- Stage: `PRE_DECISION / MARKET_DIALOGUE`
- Registration deadline: 2026-08-28
- Planned formal tender: late autumn 2026 according to the market-survey source.
- Market dialogue is scheduled before the planned procurement and explicitly concerns VMware by Broadcom products **or similar licences**.
- This is currently the strongest trigger archetype because it occurs **before the formal tender** and therefore offers the longest realistic window to freeze the buyer's pre-decision business case.
- Canonical public score remains 35/100; the importance comes from timing quality, not invented score inputs.
- Outreach state: `NOT_AUTHORIZED`.

## Channel conclusion after 23 records

Public procurement appears capable of producing a repeatable stream of **decision-timed VMware/equivalent signals**. It is not yet proven that this stream can generate customers for independent switching assurance.

The key acquisition ranking should now be:

1. `MARKET_DIALOGUE + EQUIVALENT` — best timing.
2. `OPEN TENDER + EQUIVALENT/ALTERNATIVES` — strong challengeability, shorter clock.
3. `OPEN RENEWAL + PLATFORM/LICENSING REVIEW` — medium.
4. `MECHANICAL VMWARE RENEWAL` — timing evidence only.
5. `IN_PROGRESS MIGRATION` — only if original forecast preserved.
6. `COMPLETED` — dataset bootstrap, not first-customer sourcing.

## New operational requirement

A viable acquisition process needs an **early-trigger latency metric**:

`days_between_publication_and_detection`

and a second commercial metric:

`days_remaining_before_decision_deadline`

If prospects are usually detected after procurement specifications are frozen, the public-procurement channel may be too late for the strongest `PROMISE → ACTUAL` wedge. Market-dialogue/RFI detection therefore deserves disproportionate priority.
