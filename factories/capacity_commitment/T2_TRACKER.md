# Capacity Commitment — T2 Market Tracker

Status: **T2 — MARKET EXPOSED**

Truth rule: a researched target or unsent draft is **not CONTACTED**. A sent message/contact-form submission is CONTACTED only after authorized external transmission occurs. Gmail `SENT` proves transmission from our account; it does **not** prove recipient delivery/read/reply.

| Target | Country | Segment | Trigger | Commitment type hypothesis | Contact route | CONTACTED | DELIVERED | REPLIED | QUALIFIED | CASE_EXISTS | DATA_AVAILABLE | DISCOVERY | PILOT_PROPOSED | PILOT_ACCEPTED | PAID | REJECTED | REASON |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sodecia | Portugal | Automotive Tier supplier | VW/Ford customer-specific investment + VW restructuring context | nomination / volume-linked amortization / dedicated capacity — UNKNOWN until buyer confirms | sgps@sodecia.com | NO | NO | NO | PUBLIC_SIGNAL_ONLY | UNKNOWN | UNKNOWN | NO | NO | NO | NO | NO | DGC list check pending |
| Simoldes Plásticos | Portugal | Automotive plastics / injection | high disclosed VW/Stellantis concentration + current VW restructuring + capacity expansion | program tooling / nomination / customer-specific investment — UNKNOWN | corporate route unresolved | NO | NO | NO | PUBLIC_SIGNAL_ONLY | UNKNOWN | UNKNOWN | NO | NO | NO | NO | NO | No legitimate generic commercial route confirmed yet |
| Fehst Componentes | Portugal | Automotive plastics / tooling / assembly | VW program/tool/assembly-line responsibility + capacity expansion | tooling / dedicated line / program-volume basis — UNKNOWN | fehst.comp@fehstgroup.com | NO | NO | NO | PUBLIC_SIGNAL_ONLY | UNKNOWN | UNKNOWN | NO | NO | NO | NO | NO | DGC list check pending |
| Teknia | Spain | Automotive components | demand volatility / H1 2026 sales decline + OEM exposure | program-specific capex/tooling / nomination — UNKNOWN | info@tekniagroup.com | NO | NO | NO | PUBLIC_SIGNAL_ONLY | UNKNOWN | UNKNOWN | NO | NO | NO | NO | NO | LSSI lawful-basis route unresolved |
| COINDU | Portugal | Automotive interiors / seat covers | OEM program exposure + recent investment; weaker public current trigger | program/tooling/capacity — UNKNOWN | info@coindu.com | NO | NO | NO | PUBLIC_SIGNAL_ONLY | UNKNOWN | UNKNOWN | NO | NO | NO | NO | NO | DGC list check pending |
| CT Automotive Group plc | United Kingdom | Automotive interiors / tooling | 77% of 2025 revenue concentrated in top 3 customers; $13.5m tooling revenue; 2024/25 production-volume pressure / end-of-production programs | bespoke tooling + serial-production program commitment / customer acceptance — UNKNOWN | sales@ct-automotive.net | YES | UNKNOWN/PENDING | NO | PUBLIC_SIGNAL_ONLY | UNKNOWN | UNKNOWN | NO | YES — eligibility screen CTA | NO | NO | NO | Initial message `1a04ad907dae4739`; subject accidentally retained internal HOLD label; transparent correction sent `1a04b1d3c9e08987` |
| Autins Group plc | United Kingdom | Automotive NVH / acoustic & thermal components | UK revenue -20.3% in H1 FY26 due major-customer demand interruption; tooling for new programs | major-customer program volumes / tooling / component awards — UNKNOWN | sales@autins.com | YES | UNKNOWN/PENDING | NO | PUBLIC_SIGNAL_ONLY | UNKNOWN | UNKNOWN | NO | YES — eligibility screen CTA | NO | NO | NO | Initial message `1a04ad9158ab6f1b`; subject accidentally retained internal HOLD label; transparent correction sent `1a04b1d5308bfbf0` |
| Castings plc | United Kingdom | Commercial-vehicle foundry / machining | >70% heavy-truck revenue; demand around 10% below OEM-normalised level; FY26 capex £20.5m | program volume / dedicated foundry-machining capacity / tooling — UNKNOWN | sales@castings.plc.uk | YES | UNKNOWN/PENDING | NO | PUBLIC_SIGNAL_ONLY | UNKNOWN | UNKNOWN | NO | YES — eligibility screen CTA | NO | NO | NO | Sent via Gmail; message `1a04adae56e38c0b` |
| Trifast plc | United Kingdom | Engineered fastenings to automotive OEM/Tier suppliers | FY26 revenue -7.3% CER; company reported weaker volumes particularly in automotive | program/customer volume / engineering-manufacturing commitment — UNKNOWN | corporate.enquiries@trifast.com | YES | UNKNOWN/PENDING | NO | PUBLIC_SIGNAL_ONLY | UNKNOWN | UNKNOWN | NO | YES — eligibility screen CTA | NO | NO | NO | Sent via Gmail; message `1a04adb25afe9d0b` |
| Strip Tinning Holdings plc | United Kingdom | Automotive glazing / EV electrical connectors | high-volume Tier-1/OEM supply with customer/application-specific automation and production-line investment; no public shortfall asserted | customer programme volume / dedicated automated line / tooling-NRE basis — UNKNOWN | sales@striptinning.com | YES | UNKNOWN/PENDING | NO | PUBLIC_SIGNAL_ONLY | UNKNOWN | UNKNOWN | NO | YES — eligibility screen CTA | NO | NO | NO | Sent via Gmail; message `1a04b1bd28e1da3b`; capacity-fit qualification, not a claimed shortfall |

## Channel/compliance state

### Portugal

Owner authorization is granted, but Article 13-B requires direct marketers to consult the DGC's monthly-updated national list of legal persons that opted out. The current list is made available by DGC on request. A regulatory inquiry requesting the current list/clarification has been **sent** to DGC (Gmail message `1a04ad94d7f104c5`).

Until that list is obtained/checked, Sodecia, Fehst and COINDU remain **HOLD — DGC LIST CHECK**, despite owner authorization.

### Spain

Owner authorization is granted, but unsolicited commercial email remains **HOLD — LSSI LAWFUL BASIS** unless a lawful authorization/prior-relationship or equivalent compliant route is established. Teknia remains unsent.

### United Kingdom

First market test is live. Generic corporate mailboxes are used; sender identity and opt-out language are included. No personal email route is used in the live cohort.

## Outbound hygiene incident

The first CT Automotive and Autins messages were transmitted after owner authorization but their subjects still contained the internal drafting prefix `[HOLD — OWNER APPROVAL]`. Their bodies were intended external copy and did not claim an unauthorized result; the defect was the subject label.

The defect was detected by re-reading the exact sent Gmail messages. It was repaired transparently with short correction emails using clean subjects:

- CT Automotive correction: `1a04b1d3c9e08987`.
- Autins correction: `1a04b1d5308bfbf0`.

This incident may reduce conversion and therefore remains part of experiment truth. It does not change the number of unique companies contacted: CT and Autins are still one target each.

Control change: before any future external send created from a HOLD draft, re-read the exact stored draft/message metadata and reject any subject containing internal control tokens such as `HOLD`, `OWNER APPROVAL`, `DGC`, `COMPLIANCE` or similar labels.

## Send state

- CT Automotive — SENT initial → `1a04ad907dae4739`; correction → `1a04b1d3c9e08987`.
- Autins — SENT initial → `1a04ad9158ab6f1b`; correction → `1a04b1d5308bfbf0`.
- Castings — SENT → `1a04adae56e38c0b`.
- Trifast — SENT → `1a04adb25afe9d0b`.
- Strip Tinning — SENT → `1a04b1bd28e1da3b`.
- Sodecia — draft `r9030987917445416142` — UNSENT / HOLD DGC.
- Fehst — draft `r3228309606481883657` — UNSENT / HOLD DGC.
- COINDU — draft `r-2357619079086902254` — UNSENT / HOLD DGC.
- Teknia — draft `r1319900680223442801` — UNSENT / HOLD Spain LSSI.
- DGC legal-list inquiry — SENT → `1a04ad94d7f104c5`.

## Funnel scoreboard

- TARGETS_RESEARCHED = 10
- PUBLIC_SIGNAL_QUALIFIED = 10
- UNIQUE_COMPANIES_CONTACTED = 5
- OUTBOUND_TRANSMISSIONS = 7 commercial + 1 DGC regulatory inquiry
- DELIVERED = 0 confirmed / 5 company targets pending
- REPLIED = 0
- QUALIFIED_BY_BUYER = 0
- CASE_EXISTS = 0 confirmed
- DATA_AVAILABLE = 0 confirmed
- DISCOVERY = 0
- PILOT_PROPOSED = 5 low-friction eligibility CTAs / 0 priced pilot proposals
- PILOT_ACCEPTED = 0
- PAID = 0
- REJECTED = 0

## Terminal decision

**T2 — MARKET EXPOSED = ACHIEVED.**

Reason: the pilot-capable offer has been externally transmitted to five real, public-signal-qualified UK automotive/commercial-vehicle supplier targets through corporate routes. This is market exposure only; it is **not** delivery proof, reply, qualification, WTP, commercial proof, customer proof, recovery proof or revenue.

## Next terminal

**T3 — COMMERCIAL PROOF**

Meaningful evidence required includes a paid audit/pilot, signed recovery engagement/success-fee agreement, or real proprietary case data supplied in a credible buying process. Reply or interest alone is not WTP.

## Current bottleneck

**BUYER RESPONSE / QUALIFICATION / COSTLY COMMITMENT.**

Current monitoring snapshot (2026-08-29 Europe/Lisbon): no reply or bounce detected from the live UK cohort and no DGC response yet. This remains `NO_REPLY_YET`, not delivery proof or rejection.

ACTIVE:
- monitor bounces/replies and DGC response;
- qualify any buyer reply without promoting interest into WTP;
- convert fit into one bounded paid-pilot proposal using the T3 conversion kit;
- preserve rejection reasons;
- do not send premature follow-ups within the initial response window;
- keep Portuguese/Spanish routes fail-closed until lawful basis is actually established.
