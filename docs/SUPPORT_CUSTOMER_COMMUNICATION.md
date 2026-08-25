# ObraSignal Support — Customer Incident Communication

Status: **support-owned templates / evidence-gated / no automatic send**

These templates are preparation only. They do not authorize customer contact, production mutation, rollback, provider changes or any claim that an incident is resolved.

## Evidence gates

Every customer-facing incident update must be anchored to the affected journey and observed evidence. Before sending, support must know which of these states is justified:

- `INVESTIGATING`: a customer-visible symptom is reported or detected, but cause/recovery is not yet verified.
- `DEGRADED`: evidence proves the service remains available with materially reduced capability.
- `UNAVAILABLE`: evidence proves the required service/dependency is unavailable.
- `DATA_DELAYED`: current data cannot be represented as fresh; stale/unknown remains explicit.
- `BILLING_VERIFICATION_UNAVAILABLE`: authoritative billing/access state cannot currently be verified.
- `SERVICE_RESTORED`: the service path is functioning again, but end-to-end customer recovery or root cause may still be open.
- `RESOLUTION_VERIFIED`: the relevant customer journey has been re-verified after recovery. This is the earliest state that may be described as resolved for that verified scope.

`SERVICE_RESTORED` is never silently rewritten as `RESOLUTION_VERIFIED`.

## Required internal fields before send

Use only bounded support evidence:

- customer-visible affected capability;
- failure class;
- opaque correlation/reference identifier when available;
- first/last observed timestamp with timezone;
- current communication state;
- affected build/version when proven relevant;
- workaround only if tested and safe;
- next customer action only when it is actually useful;
- verification scope for any recovery claim.

Never copy raw logs, credentials, authorization headers, customer payloads, unrelated account identifiers or another tenant's data into a customer communication.

## Template — degradation

**Subject:** ObraSignal service degradation

We are seeing degraded behavior affecting **{capability}**. The service is still available, but **{bounded_impact}** may be incomplete or delayed.

Current status: **DEGRADED**. Reference: **{correlation_id_or_case_reference}**. Last observed: **{timestamp_with_timezone}**.

{safe_workaround_if_proven}

We will only mark this resolved after the affected journey has been verified again.

## Template — outage

**Subject:** ObraSignal service unavailable

**{capability}** is currently unavailable. We have not treated missing or unavailable results as successful/empty data.

Current status: **UNAVAILABLE**. Reference: **{correlation_id_or_case_reference}**. Last observed: **{timestamp_with_timezone}**.

{safe_customer_action_if_any}

Recovery work is being handled by the owning service team. We will distinguish service restoration from verified resolution in subsequent updates.

## Template — billing verification issue

**Subject:** ObraSignal billing verification unavailable

We cannot currently verify the authoritative billing/access state for **{affected_access_scope}**.

Current status: **BILLING_VERIFICATION_UNAVAILABLE**. We are not treating an unavailable verification as an active subscription, Evaluation state or entitlement change.

Reference: **{correlation_id_or_case_reference}**. Last observed: **{timestamp_with_timezone}**.

{safe_customer_action_if_any}

We will confirm access only after the authoritative billing state can be verified again.

## Template — data delay / stale market data

**Subject:** ObraSignal data update delayed

Current data for **{source_or_market_scope}** is delayed or cannot yet be verified as fresh.

Current status: **DATA_DELAYED**. Existing historical opportunities remain available where the product contract permits, but this delay must not be interpreted as evidence that there are no current opportunities.

Reference: **{correlation_id_or_case_reference}**. Last verified fresh data: **{freshness_timestamp_or_unknown}**.

We will report current coverage only after the owning source-health contract proves it.

## Template — service restored, verification still open

**Subject:** ObraSignal service restored — verification in progress

Service for **{capability}** is responding again as of **{timestamp_with_timezone}**.

Current status: **SERVICE_RESTORED**. This is not yet a full resolution claim: **{verification_scope_remaining}** still needs end-to-end verification.

Reference: **{correlation_id_or_case_reference}**.

{safe_customer_action_if_any}

## Template — verified resolution

**Subject:** ObraSignal incident resolved for {verified_scope}

The affected **{verified_scope}** journey has been re-verified after recovery as of **{timestamp_with_timezone}**.

Current status: **RESOLUTION_VERIFIED**. Verification performed: **{bounded_verification_description}**.

Reference: **{correlation_id_or_case_reference}**.

{customer_follow_up_if_any}

Root-cause/prevention work may remain open unless it is separately confirmed closed. If that work is still open, do not imply otherwise.

## Template — investigation / unknown cause

**Subject:** ObraSignal issue under investigation

We have confirmed a problem affecting **{capability}**, but the available evidence is not sufficient to state a root cause yet.

Current failure class: **UNKNOWN**. Reference: **{correlation_id_or_case_reference}**. Last observed: **{timestamp_with_timezone}**.

We will not ask you to delete data, recreate an account or repeat destructive steps unless a verified recovery procedure specifically requires it.

## Pre-send truth checklist

1. Does every factual claim have current evidence for the affected scope?
2. Is `UNKNOWN` still represented as unknown rather than zero/success/customer error?
3. Is any workaround clearly labelled as a workaround rather than a fix?
4. Does the message avoid raw logs, secrets, tenant selectors and unrelated private data?
5. If the message says `SERVICE_RESTORED`, is end-to-end verification still described accurately?
6. If the message says resolved, is the customer journey actually `RESOLUTION_VERIFIED` for the named scope?
7. If root cause remains open, does the message avoid claiming it is closed?
8. Are billing, source freshness, Auth, recovery and deployment claims delegated to their authoritative owner evidence?
9. Does the message avoid asking the customer to destroy or recreate data unnecessarily?
10. Is the reference identifier opaque and support-safe?
