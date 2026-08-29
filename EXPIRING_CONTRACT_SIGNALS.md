# Expiring Contract Signal Engine v0

## Purpose

Turn sufficiently structured canonical `CONTRACT` history into conservative `CONTRACT_EXPIRY` signals answering: which known contracts are approaching their current known end?

**Contract expiry is a signal, not a promise.** A signal never means an open tender, confirmed renewal, guaranteed reprocurement or predicted future contract value.

## Repository state and boundary

At the branch point, ObraSignal already had a provenance-first generic Signal store whose allowed types include `CONTRACT`, `AWARD` and `CONTRACT_EXPIRY`, but no first-class canonical Contract/Award domain model or contract-term persistence schema was present. The generic OCDS adapter normalized tender data only. Therefore v0 deliberately does **not** invent a parallel contract database or infer contract terms from tender/award dates.

The engine consumes a mapping representing a canonical Contract supplied by a future/current normalization boundary. A `contract_id` is mandatory. An `AWARD` external id alone is not accepted as a Contract identity.

## Contract vs Award

`AWARD_DATE`, `CONTRACT_SIGNED_AT`, `CONTRACT_START_DATE`, `CONTRACT_END_DATE`, `INITIAL_TERM_END`, `CURRENT_TERM_END`, `TERMINATED_AT`, `EXTENDED_TO` and option periods are distinct semantics. V0 uses only explicit contract fields supplied to it. It never derives an end date from an award date.

## Date semantics and duration derivation

End-date evidence is classified as:

- `OFFICIAL`: explicit `contract_end_date` / `current_term_end`;
- `OFFICIAL_EXTENSION`: an `extended_to` date with `extension_confirmed=true`;
- `DERIVED`: explicit `contract_start_date + duration_amount + duration_unit`;
- `PARTIAL`: source provides only month/year, quarter/year or year;
- `UNKNOWN`: insufficient or invalid term data.

Calendar months/years use calendar arithmetic with month-end clamping. For example, 31 January + 1 calendar month is the last day of February, not +30 days. Partial dates remain partial and do not receive a fabricated day.

## Expiry windows

`ExpiryPolicy` owns the horizon thresholds and version. Defaults are v0 product policy, not universal procurement truth: near term <=90 days, mid-near <=180, forward <=365, maximum actionable future horizon 730 days, recently expired lookback 90 days. Callers can replace these thresholds without editing evaluator logic.

## Options and extensions

An option is not an exercised extension. `option_periods`, `renewal_options` or `max_possible_end` only produce `OPTION_EXISTS_NOT_EXERCISED`; they do not move `current_known_end`.

A confirmed `extended_to` moves current known end and changes logical signal identity. The prior signal can therefore be superseded by persistence/integration logic without continuing stale urgency. Amendment history is preserved by the canonical contract owner; this engine does not build a second diff/history engine.

## Termination and completed contracts

`TERMINATED`, `CANCELLED` and `COMPLETED` contracts never appear as normal expiring signals. A past known end is `EXPIRED`, and only a configurable recent lookback is feed-eligible for context. Open-ended/insufficient terms remain `UNKNOWN`.

## Value semantics

`contract_value` / `current_contract_value` is exposed only as `prior_known_contract_value`. It is not a prediction of replacement value. Currency is preserved as supplied and no conversion occurs.

## Source and provenance

The assessment preserves `source_reference`, evidence basis, precision, derivation calculation, policy version, freshness reference and lineage reference when supplied. Source health/freshness remains owned by the existing source-health capability; v0 consumes references rather than duplicating that engine.

## Lineage compatibility

`lineage_ref` is an optional compatibility hook. V0 does not create a matching engine or hard-depend on Opportunity Lineage, Procurement Plan Intelligence, Evidence Graph or Future Demand. A later graph may represent `CONTRACT -> CONTRACT_EXPIRY -> PROCUREMENT_PLAN -> TENDER` while retaining each node's independent evidence.

## Read model and serialization

`ExpiryAssessment` is the read model. `as_signal_record()` serializes it as `signal_type=CONTRACT_EXPIRY`, sets `is_open_tender=false`, `replacement_procurement_confirmed=false`, and includes the warning `No replacement procurement has been confirmed.` There is deliberately no `BID NOW` semantics.

## Detection vs persistence

`evaluate_contract_expiry(contract, now, policy)` is pure and has no DB/network dependency. Persistence is separate. The existing `signal_store` can persist the serialized record because `CONTRACT_EXPIRY` is already an allowed canonical Signal type. V0 does not automatically persist on every request or create a scheduler.

## API / UI

No API/UI route is enabled in v0 because the repository does not yet expose a canonical Contract query model from which an authenticated endpoint could safely select contracts. Adding an endpoint over tender/award rows would violate the central Contract != Award rule. The read model is ready for a future API once canonical Contract ingestion exists.

Recommended UI wording: **CONTRACT END SIGNAL** / **Known contract approaches end of term** with the explicit no-replacement-procurement warning.

## Tests

Tests cover official/derived/partial/unknown dates, leap years/month ends, active/expired/completed/terminated/cancelled contracts, future starts, options, confirmed extensions, multiple amendments, duplicate source observations with one canonical contract identity, multiple contracts per buyer, deterministic clock/idempotency, configurable horizons, prior-value/currency/provenance semantics, malformed/extreme duration input and false-tender/false-award controls.

## Security

The pure evaluator performs no SQL, HTML rendering, external URL fetching or tenant annotation access. It requires canonical contract identity, bounds duration arithmetic, rejects malformed policy ordering and treats free text/source metadata as opaque data. Escaping remains the responsibility of the eventual UI serializer/template boundary. Tenant-specific watch/decision state is explicitly outside this shared public signal model.

## Performance

Evaluation is O(1) per candidate. Production integration should preselect canonical contracts by current known end/status using indexed fields rather than scan historical contracts on each request. No scheduler/index is added before such a canonical Contract table exists.

## Known limitations

- Canonical first-class Contract/Award models are not yet present at this branch point; v0 therefore provides the engine contract but does not manufacture contract records from tender history.
- Partial dates are evidence-preserving `UNKNOWN` assessments rather than actionable expiry calculations.
- Extension supersession is represented by changed deterministic signal identity; durable resolution/event emission belongs to the eventual canonical Contract persistence integration.
- No replacement detection, reprocurement probability, recurrence model or future-value prediction exists.

## Future Demand integration

Future Demand may consume `CONTRACT_EXPIRY` as one evidence node. It must keep expiry certainty separate from reprocurement likelihood and may not translate expiry alone into `new tender expected`.

## Rollback

The module is isolated: remove `contract_expiry.py`, its tests/documentation, and the capability-registry entry if added. No canonical queue state, existing schema, connector or production route needs rollback.
