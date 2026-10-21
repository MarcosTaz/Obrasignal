# ObraSignal — Customer Journey Friction Register

Specialist lane inside the existing ObraSignal Factory. This is not a separate product.

| Customer | Journey state | Expected action/result | Actual result | Friction | Severity | Value blocked / truth risk | Fix | Regression test | Status |
|---|---|---|---|---|---|---|---|---|---|
| Company E — zero-opportunity electrical contractor | DATA_READY → ZERO_VALUE | Product may truthfully conclude that nothing material matches | Mobile empty state says `Sem resultados com estes filtros. Reduz a relevância mínima ou ajusta os critérios da empresa.` | A genuine zero-opportunity state is conflated with a search/filter miss and nudges the user to loosen criteria | P1 | False-value / abandonment risk: customer may be encouraged to manufacture weaker signals instead of receiving a valid zero-value result | Add canonical zero-value semantics and a clear `NADA MATERIAL ENCONTRADO` terminal/next-action state without lowering evidence thresholds | `tests/test_customer_journey_zero_value.py` + UI regression once current integrated mobile surface is editable | OPEN |
| Any customer recording WON/LOST | ACTION_TAKEN → OUTCOME_PENDING | User-reported terminal workflow must not become verified outcome | Canonical workflow exposed `WON/LOST`; mobile displayed unqualified `Ganho/Ganhos` | Workflow report could be read as verified award/outcome | P1 | Fabricated customer-success interpretation | Backend now returns `CUSTOMER_REPORTED_UNVERIFIED`, funnel labels reported states, detail explicitly says report is not adjudication/economic/payment verification | `tests/test_customer_journey_outcome_integrity.py` | MITIGATED — exact-head Python GREEN; global mobile gate blocked by Expo/RN drift |
| Evaluation customer | FIRST_SIGNAL / VALUE_EXPOSURE | Exposure must remain distinct from FIRST_VERIFIED_VALUE | `evaluation_metrics()` derived `TIME_TO_FIRST_VALUE_SECONDS` from shortlist/view/alert/action exposure | Metric theater / false first-value semantics | P1 | Activation can appear to prove value when only exposure/action occurred | Preserve exposure metric separately; verified first value remains absent until canonical evidence-backed event exists | `tests/test_customer_journey_first_value_semantics.py` | FIXED — exact-head Python GREEN |
| Mobile release | RELEASE_GATE | Mobile critical journey must execute on exact candidate | Expo Doctor now expects react-native 0.86.3; repository has 0.86.2 | Quality stops before mobile smoke | P1 release blocker | Cannot claim global customer-journey/mobile GREEN | Main Mobile/Release Engineering owner must align dependency and rerun exact-head gates | ObraSignal Quality mobile job | OPEN / OWNER COMPOSITION BLOCKER |

## Ranking rule

Priority = customer abandonment risk × value blocked / truth risk. Cosmetic preference is not a release blocker.

## Truth boundary

A resolved engine assertion does not prove real customer understanding, willingness to pay, retention, or real economic outcome. Synthetic journey gates only prove deterministic product behavior against an independent oracle.
