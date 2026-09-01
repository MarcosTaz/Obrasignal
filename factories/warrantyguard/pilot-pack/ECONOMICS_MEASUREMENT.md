# DebitProof — Cost-to-Serve Measurement

## Objective
Measure whether the assisted service can be delivered economically without converting assumptions into observed economics.

## Per pilot/cycle record
Track separately:
- operator processing minutes;
- human contract/review minutes;
- support/remediation minutes;
- number of cases processed;
- number and share of UNKNOWN cases;
- number of draft actionable cases;
- verified customer outcomes where evidenced.

## Cost basis
Use an explicit loaded hourly-cost input. Mark the measurement either:
- `ASSUMPTION` — scenario only; or
- `OBSERVED_REAL` — requires evidence hash for the underlying time/cost record.

The engine computes total minutes, total cost and cost per case. A pricing scenario may compute a hypothetical gross contribution, but `revenueRecognized` remains zero unless a separate real-payment system provides verifiable evidence.

## Pricing validation
A price hypothesis is not validated by an internal margin model. Record the exact quote shown to a real buyer and the buyer's costly behavior: paid diagnostic/pilot, signed commitment with credible procurement/budget path, or equivalent evidence. Meetings, opens, demos and polite interest are not WTP proof.

## Decision use
Use observed pilot data to update:
- minimum viable diagnostic price;
- maximum economically tolerable manual review time;
- automation priority by repeated manual step;
- supported pilot size;
- whether recurring monitoring has positive contribution economics.
