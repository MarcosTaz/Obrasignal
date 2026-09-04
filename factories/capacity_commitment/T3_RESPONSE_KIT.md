# Capacity Commitment — T3 Buyer Response Kit

Status: **READY — EXTERNAL COPY TEMPLATES REQUIRE FACT-SPECIFIC REVIEW**

Use only after reading the complete buyer message/thread. Preserve the buyer’s actual question and do not promote a weak signal into qualification, WTP or payment.

Internal control labels such as `HOLD`, `OWNER APPROVAL`, `DGC`, `COMPLIANCE`, `INTERNAL`, or experiment notes must never appear in external subject/body.

## 1. Buyer: “Send information”

Classification: `INTEREST_NO_CASE` unless their message also supplies a real case signal.

Suggested response:

> Thanks — the scope is deliberately narrow. We review one customer + one automotive programme + one bounded period to determine whether a supportable volume/amortisation basis diverged from actual releases and left customer-specific tooling/capacity/NRE or related investment unrecovered after mitigation and prior payments. The review can correctly conclude zero. I can send the one-page scope; the main qualifying question is whether you have one current/recent programme matching that pattern.

Attach/send `T3_ONE_PAGER.md` in an appropriate external format.

Do not classify `send information` as WTP.

## 2. Buyer asks price

Classification: `PILOT_PRICE_REQUESTED` only if the buyer actually asks about commercial price/terms.

Suggested response:

> For one customer + one programme + one bounded period, the current fixed assisted-pilot price is £3,000 (or €3,500 where appropriate), subject to confirming scope. It includes commitment-vs-actual reconstruction, unrecovered-investment reconciliation, mitigation/prior-recovery review, evidence/deadline state and a reviewable action package. A zero-recoverability conclusion remains a valid result. If you can outline the programme and the strongest commercial anchor, I can confirm whether it fits that bounded scope.

Price remains a hypothesis until accepted and paid.

## 3. Buyer says “We have something like this”

Classification: `CASE_SIGNAL_UNQUALIFIED` until identity/divergence/anchor/exposure/data/buyer are established.

Suggested response:

> That may fit. Before requesting documents, could you give me a bounded outline: which customer/programme changed, what changed in releases/volume/timing, what the strongest commercial anchor is (nomination/LTA/PO/amortisation basis or similar), and what supplier-specific tooling/capacity/NRE/material exposure may remain? No sensitive figures are needed in the first reply if you prefer. If it passes that screen, I’ll request only the minimum one-program dataset.

Do not request a broad data dump at this stage.

## 4. Buyer provides a clearly bounded real case

Classification: `CASE_SIGNAL_QUALIFIED` only if the T3 qualification rule is actually met; otherwise remain unqualified.

Suggested response:

> This is specific enough to run the eligibility gate. I would keep the first review to [customer/programme/period]. The minimum next step is the applicable commercial anchor and amendments, release/actual history, relevant dedicated cost/amortisation basis, mitigation/reuse, prior customer recovery and notice/deadline terms. We can use your preferred authorized confidentiality/data-transfer process. I will separate economic exposure from contractual support and can conclude zero/unknown if the evidence does not support recovery.

Then use `T3_INTAKE.md`.

## 5. Buyer asks for a meeting

Classification: `DISCOVERY_BOOKED` only after a real meeting is actually scheduled/accepted, not merely proposed.

Suggested response:

> Yes. I suggest keeping the first call to 15 minutes and one programme. I’ll focus on five things: trigger, commercial anchor, actual divergence, supplier-specific exposure, and whether the minimum evidence is accessible. That is enough to decide whether a paid bounded pilot is worth proposing.

Do not claim discovery booked until scheduling evidence exists.

## 6. Buyer says “We already handle this internally”

Classification: generally `REJECTED_INTERNAL_CAPABILITY` if clearly declining; otherwise objection/interest remains context-specific.

Suggested response:

> Understood. I’m not trying to replace Commercial/Finance or your existing systems. The narrow question I’m testing is whether all material programme-volume shortfalls are already reconciled systematically against dedicated investment, amortisation, mitigation, prior recovery and notice timing. If that is already controlled end-to-end, this is probably not useful and I’ll close it out.

Respect a clear rejection. Do not argue indefinitely.

## 7. Buyer says “We use SAP / ERP / Campfire / CLM”

Suggested response:

> That is compatible with the intended model. Those systems can remain the source/context. The pilot is an independent bounded reconciliation of commitment → actual → dedicated exposure → mitigation/prior recovery → evidence/deadline/action. I would only continue if there is a real programme where that decision is not already reliably closed.

Do not disparage an incumbent without evidence.

## 8. Buyer asks for success fee only

Classification: not acceptance by itself.

Suggested response:

> I can consider a hybrid only after the case is qualified and attribution can be defined. The current working structure is £1,250 setup plus 7.5% of incremental cash actually received and attributable to the supported recovery action. I would not charge a success percentage on theoretical exposure, claim value, disputed amounts or approved-but-unpaid amounts. First I need to confirm the case fits and that the economics/attribution are workable.

Do not accept a binding success-fee engagement without an appropriate agreement.

## 9. Buyer asks “Can you guarantee recovery?”

Suggested response:

> No. The product is designed specifically not to manufacture a positive claim. It separates economic exposure from contractual/evidential support and can conclude zero, non-recoverable, expired or unknown. Any external recovery also depends on customer response and any required legal/commercial process.

## 10. Wrong owner

Classification:

- `WRONG_OWNER_FORWARD_REQUESTED` if they identify/ask to contact another role but have not confirmed forwarding;
- `WRONG_OWNER_FORWARDED` only with evidence it was actually forwarded/routed.

Suggested response:

> Thanks for pointing me in the right direction. If you are able to forward the note to the person responsible for Commercial/Finance programme close-out, that is sufficient. I won’t treat this as a case signal unless the relevant owner confirms one.

## 11. “Not relevant” / “No”

Classification: `NOT_RELEVANT` or an evidence-backed rejection reason.

Suggested response:

> Understood — thank you for confirming. I’ll close this out and won’t follow up further.

Stop outreach to that route/company unless a materially new authorized context arises.

## 12. Opt-out

Classification: `OPT_OUT`.

Suggested response:

> Understood. I will not send further marketing messages to this address.

Record the opt-out and stop.

## 13. Buyer supplies files/data immediately

Classification can become `DATA_WILLINGNESS` or `DATA_PROVIDED` only after verifying that the files are meaningful to a real bounded case and were supplied through an authorized route.

Actions:

1. acknowledge receipt without interpreting entitlement immediately;
2. freeze tenant/customer/programme identity;
3. preserve original source/version identity;
4. minimize further requests;
5. run `T3_INTAKE.md`;
6. do not place confidential material into public repo/issues/PRs;
7. do not use customer data for model training without explicit permission.

## 14. Buyer accepts pilot verbally/email

Classification: `PILOT_ACCEPTED_UNPAID` if acceptance is clear but payment is not evidenced.

Next:

- confirm bounded scope using `T3_PILOT_SCOPE.md`;
- use an appropriate commercial agreement/order process;
- do not represent invoice as payment;
- do not begin unbounded work merely because interest is strong.

## 15. Payment evidence

Only mark `PAYMENT_RECEIVED` / `PAID_PILOT` when actual payment evidence exists.

A signed agreement, PO, invoice, “approved for payment”, remittance advice without settled funds, or verbal confirmation is not automatically cash received.

## Response truth checklist

Before every reply:

- read full inbound and thread;
- identify exact reply class;
- answer buyer’s actual question first;
- remove internal control labels;
- do not claim entitlement/recovery/payment;
- preserve correct-zero language where relevant;
- request only the smallest next evidence/action;
- record rejection/opt-out accurately;
- update tracker only after evidence exists.
