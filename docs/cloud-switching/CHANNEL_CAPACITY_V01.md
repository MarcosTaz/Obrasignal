# Cloud Switching — Trigger Channel Capacity v0.1

Status: scenario analysis only. No conversion rate below is proven.

## Observed lower bound from first sweep

The 30-record research sweep found at least six current/recent European triggers with materially stronger challengeability than a mechanical renewal, including market dialogue, `or equivalent`, explicit alternatives, or direct VMware replacement language.

This **does not estimate the true monthly market volume**. The search was non-exhaustive and biased toward public/indexed procurement. Treat `6 challengeable triggers/month` only as an observed lower-bound scenario for kill-testing.

## Paid-pilot capacity scenarios

Formula:

`paid_pilots/year = challengeable_triggers_per_month × 12 × discovery_conversion × paid_pilot_conversion`

| Challengeable triggers / month | 10% discovery × 25% paid | 15% discovery × 30% paid | 20% discovery × 30% paid |
|---:|---:|---:|---:|
| 6 | 1.8 | 3.24 | 4.32 |
| 10 | 3.0 | 5.4 | 7.2 |
| 15 | 4.5 | 8.1 | 10.8 |
| 20 | 6.0 | 10.8 | 14.4 |
| 30 | 9.0 | 16.2 | 21.6 |

All conversion figures are hypotheses. They are deliberately separated from observed trigger counts.

## Implication

At the observed lower-bound scenario of six challengeable triggers/month, **public procurement alone does not comfortably support five paid pilots/year** under conservative or middle conversion assumptions.

Approximate trigger volume required for five paid pilots/year:

- 10% discovery × 25% paid: ~16.7 challengeable triggers/month;
- 15% discovery × 30% paid: ~9.3/month;
- 20% discovery × 30% paid: ~6.9/month.

Therefore the current public-procurement channel remains `ALIVE_BUT_NOT_PROVEN_SUFFICIENT`.

## Acquisition strategy consequence

Do not discard public procurement. It has two high-value roles:

1. **high-intent trigger source** — especially market dialogue / equivalent / replacement events;
2. **ground-truth training set** for a trigger detector that can later expand into other public signals.

But first-revenue acquisition should also investigate adjacent pre-decision signals that occur outside formal procurement:

- public budget/board approvals;
- renewal or licensing-cost disclosures;
- architecture/sovereignty strategy documents;
- RFI / request-for-estimate / preliminary market consultations;
- technology job postings tied to migration/replatforming;
- partner project announcements before cutover;
- cloud/data-center exit announcements.

These sources must preserve the same evidence/UNKNOWN rules and cannot be treated as proof of buyer willingness.

## Kill gate for procurement-only acquisition

After building an exhaustive or near-exhaustive rolling 60–90 day sample across target EU markets, downgrade `PUBLIC_PROCUREMENT_AS_SOLE_ACQUISITION_CHANNEL` if:

- challengeable `EARLY_DIALOGUE + ACTIONABLE` triggers remain below ~10/month; **and**
- real discovery conversion is below 15%; **or**
- paid conversion from qualified discovery is below 30%.

This does not kill the company. It kills the assumption that public procurement alone can feed the first-revenue engine.

## Next executable work

1. Add non-procurement trigger families while preserving public evidence lineage.
2. Measure their incremental qualified-volume contribution without duplicates.
3. Build an assisted-hours model for the first paid baseline.
4. Define the real pilot acceptance/report package.
5. Keep external outreach in `NOT_AUTHORIZED` until an applicable authorization/channel exists.
