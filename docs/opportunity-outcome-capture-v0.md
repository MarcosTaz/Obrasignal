# Opportunity Outcome Capture v0

**Capability state:** PILOT / parallel implementation  
**Contract:** `opportunity-outcome.v0`  
**Branch:** `feature/opportunity-outcome-v0`

## PURPOSE

Opportunity Outcome Capture records what actually happened after an account encountered and/or made a pursuit decision about an opportunity. It closes the data loop without turning intent, workflow state, or missing evidence into a fabricated result.

The core rule is:

> **DECISION != OUTCOME. PURSUE != BID_SUBMITTED. BID_SUBMITTED != WON. ABSENCE OF AN AWARD != LOST.**

`UNKNOWN` or no outcome is preferable to a false conclusion.

## NON-GOALS

This version does **not** implement Outcome Graph, Contractor DNA, win probability, regret analysis, decision-quality scoring, ROI/value-created calculations, benchmarking, fuzzy bidder identification, new award scraping, portfolio learning, or COMMAND. It does not modify `master_execution_queue.py` or the canonical Opportunity record.

## REPOSITORY FIT

The repository currently identifies procurement opportunities by `source + external_id`; the legacy `tenders.id` remains the integer product projection. Outcome Capture therefore stores `source + external_id` and validates that the opportunity already exists. It does not invent a competing global opportunity identifier.

The canonical Signal store supports `TENDER`, `AWARD`, and `CONTRACT` signal types, but the current OCDS adapter normalizes tender data only. Outcome Capture does not rewrite that ingestion pipeline.

A richer Pursuit Decision Journal exists on a separate parallel branch at the time of this implementation. Consequently `decision_id` is optional. If the `opportunity_pursuit_decisions` table exists, a supplied reference is verified against the authenticated account and the same legacy opportunity id; if that table is absent, Outcome Capture fails closed rather than accepting an unverifiable reference.

## OUTCOME TYPES

- `BID_SUBMITTED` — a bid/application was actually submitted. It does not imply selection or award.
- `WON` — sufficient official evidence identifies this company, or the company explicitly confirms the win.
- `LOST` — an official result or the company explicitly confirms loss. A winner need not be known, but missing award data is never enough.
- `WITHDRAWN` — participation was abandoned/withdrawn after meaningful participation. It is not automatically equivalent to `NO_SUBMISSION`.
- `NO_SUBMISSION` — the account did not submit. A prior `PURSUE` decision may still have existed.
- `CANCELLED` — the procurement/procedure was cancelled. It is not a contractor loss.
- `UNKNOWN` — outcome is explicitly unknown.

No `PARTIAL_WIN` type is introduced. Optional `lot_id` preserves lot-level outcomes when a source provides a stable lot identifier.

## DECISION VS OUTCOME

Outcome Capture never reads a pursuit decision and manufactures a result. A `PURSUE`, `NO_BID`, readiness score, watchlist state, or workflow status is not outcome evidence.

An outcome can exist with no decision reference, supporting imported/legacy histories. A decision reference, when present, is a reference only; Decision data is not copied into the Outcome row.

## SOURCE TYPES

- `OFFICIAL_SOURCE` — supported by an official publication/record and provenance.
- `USER_CONFIRMED` — explicitly asserted by the authenticated company/account.
- `SYSTEM_DERIVED` — deterministic derivation from sufficiently strong source semantics, used sparingly (for example, a formally cancelled procedure).
- `IMPORTED` — imported historical data whose import process owns provenance quality.
- `UNKNOWN` — origin is not known.

The public HTTP API intentionally creates **only `USER_CONFIRMED`** records. A client cannot label its own claim `OFFICIAL_SOURCE`. Trusted in-process adapters are the path for official/derived facts.

## OFFICIAL VS USER CONFIRMED

Official/derived records require at least one provenance anchor: `source_ref`, `source_native_id`, or `evidence_refs`. They may also retain `source_publication` and `occurred_at`.

A user saying “we won”, “we lost” or “we did not submit” is valid company-specific evidence, but remains `USER_CONFIRMED` and is not promoted into a global procurement fact.

## IDENTITY MATCHING

`official_award_candidate()` is intentionally skeptical:

1. it accepts exact canonical organization identifiers, preferably scheme-qualified (`scheme:id`);
2. exact intersection between verified account identifiers and winner identifiers can yield a `WON` candidate;
3. it does **not** accept organization names, so fuzzy/similar-name matching cannot create a win;
4. the same local number under different jurisdiction/scheme prefixes is not a match;
5. no award record, an empty winner list, or a different winner returns no outcome candidate — never `LOST`.

This intentionally leaves consortium membership unresolved unless a canonical verified identifier relationship is available elsewhere. A consortium name resemblance is not sufficient.

## HISTORY / CORRECTIONS

`opportunity_outcomes` is append-only for material outcome records. A correction creates a new row with `supersedes_outcome_id`. The superseded row remains in history.

The current read model selects an outcome that has not been superseded. History marks rows as `CURRENT` or `SUPERSEDED` without physically deleting prior claims.

A row can be superseded only once and only within the same authenticated account, opportunity, and lot scope.

## IDEMPOTENCY / DEDUPLICATION

Client retries can provide an `idempotency_key`. Reusing the key with the same normalized request returns the prior outcome; reusing it with a different request returns a conflict.

Official/derived records additionally compute an account-scoped dedupe key from opportunity, lot, outcome type, source type, and official native/reference identifier. Repeated ingestion of the same official event therefore does not duplicate an outcome.

## AWARD VALUE

`award_value` is independent from the published opportunity/tender `value`. Outcome Capture never copies one into the other.

Award money:

- is stored as an exact decimal string, not binary float;
- must be finite and non-negative;
- requires an explicit three-letter currency code;
- is currently valid only for `WON`;
- is never converted or summed across currencies by this capability.

Zero is accepted because some official award structures may legitimately publish zero/nominal values; Outcome Capture preserves the source assertion rather than inventing value semantics.

## TENANT BOUNDARY

All company-specific outcome reads/writes are scoped by the account resolved from authentication/session. The public API rejects client-supplied `account_id` and does not expose another tenant's rows.

Correction lookups include `account_id`; a foreign outcome id returns `404`, preventing cross-tenant mutation/IDOR disclosure.

Official public procurement facts may be shared in the canonical Signal layer. The assertion “this official result is our company outcome” remains account-scoped.

## API

Authenticated v1 endpoints:

- `POST /api/v1/opportunities/<id>/outcomes` — append a `USER_CONFIRMED` outcome.
- `GET /api/v1/opportunities/<id>/outcome?lot_id=...` — current account outcome.
- `GET /api/v1/opportunities/<id>/outcomes?lot_id=...` — account history.
- `PATCH /api/v1/opportunities/<id>/outcomes/<outcome_id>` — append a correction version for a user-confirmed row.

The client cannot set `account_id`, timestamps owned by recording, status, or `supersedes_outcome_id` directly. Client PATCH is denied for official records.

## VALIDATION / SECURITY

The module validates enumerations, ISO-8601 timezone-aware occurrence timestamps, five-minute clock skew for future-date rejection, monetary values, currencies, confidence, decision references, text sizes, and evidence list sizes.

SQL statements are parameterized. Control characters and oversized notes are rejected. Notes are returned only as JSON data; the module does not render HTML. Opportunity rows are read for identity validation and never updated by Outcome Capture.

## PERSISTENCE / MIGRATION

`ensure_outcome_table()` creates one additive SQLite table plus indexes. It is idempotent and does not alter the `tenders` schema. The production WSGI startup boundary calls it after the existing `init_db()` and before serving traffic.

No separate database, distributed infrastructure, analytics engine, or ML component is introduced.

## EVENT BOUNDARY

The repository currently has `opportunity_events`, but it is a notification-specific store for events such as `new_high_match`, not a generic capability event bus. Outcome Capture therefore does **not** misuse it for `opportunity.outcome_recorded`.

A future generic versioned event contract may publish a payload containing `account_id`, opportunity identity, `outcome_id`, `outcome_type`, and `source_type` without changing this append-only persistence contract.

## TESTS

The v0 test set covers:

- every outcome type;
- official and user-confirmed win/loss provenance;
- outcome with and without decision reference;
- current outcome and complete correction history;
- correction/tenant boundaries;
- idempotent retries and conflicting retry keys;
- repeated official-event deduplication;
- missing opportunity and invalid outcome failures;
- occurred vs recorded date semantics and impossible future dates;
- exact award decimal/currency semantics and malformed money;
- lot-level win/loss and multi-currency preservation;
- exact canonical identifier match;
- false-win prevention for similar companies/different identifiers;
- jurisdiction-qualified identity mismatch;
- false-loss prevention when award evidence is absent or another winner exists;
- `PURSUE` without evidence producing no outcome;
- cancelled procedure not becoming `LOST`;
- official provenance requirements;
- SQL-injection-shaped identity strings, XSS-shaped notes, payload bounds;
- migration idempotency and non-mutation of Opportunity;
- HTTP auth-derived tenant, cross-tenant read/write isolation, source spoof rejection, corrections, malformed values and missing opportunities.

## KNOWN LIMITATIONS

- No canonical Organization/consortium identity-resolution service is integrated here; official win automation therefore requires exact verified identifiers supplied by a trusted caller.
- The current core has lot scoring but no canonical persisted lot entity. `lot_id` is consequently an optional stable source/canonical reference, not a foreign key.
- The current generic OCDS adapter normalizes tender data and does not expose an award/contract normalization contract suitable for automatic outcome ingestion. This module does not expand that pipeline.
- Decision Journal is not on `main` at the implementation base commit; decision references fail closed unless its table is actually present.
- No generic domain event bus exists, so outcome events are not emitted in v0.
- No UI surface is added in this branch. The API contract is deliberately completed first; a contextual UI can consume it later without changing persistence semantics.

## FUTURE OUTCOME GRAPH / DNA INTEGRATION

Future Outcome Graph/DNA consumers should consume account-scoped current/history contracts or a future versioned outcome event. They must not reinterpret `WON` as “good decision” or `LOST` as “bad decision”, and must preserve source/provenance distinctions when calculating learning signals.

This branch does not mark Outcome Graph or DNA as implemented, integrated, enabled, or production-ready.

## ROLLBACK

Runtime rollback is additive: stop importing the outcome API blueprint/startup initializer and leave the table in place so historical audit data is not destroyed. A destructive table drop is intentionally not part of application rollback.

## STATUS DISCIPLINE

Prepared in parallel. Does not promote Outcome Graph/DNA, modify the canonical Master Execution Queue, or claim production integration.
