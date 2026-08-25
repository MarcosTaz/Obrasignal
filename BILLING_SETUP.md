# ObraSignal billing setup

## Architecture and authority

ObraSignal uses RevenueCat as the subscription layer. Android uses Google Play Billing; iOS uses StoreKit. The mobile app does not introduce Stripe, external checkout, or a second billing authority.

Canonical paid contract:

- entitlement: `pro`
- product identity: `obrasignal_pro_monthly`
- Google Play base-plan form accepted by the backend/mobile contract: `obrasignal_pro_monthly:<base_plan_id>`
- backend authority: RevenueCat Subscriber API snapshot persisted into the tenant `accounts` row
- protected API access: `subscription_state()` / server-side billing guard

A client-side RevenueCat entitlement is purchase feedback only. It is not sufficient by itself to label the account Pro or unlock protected backend routes.

The displayed price comes from the selected canonical store product and must never be hardcoded. The app must not fall back to an unrelated monthly/first package if `obrasignal_pro_monthly` is absent from the current offering.

## Google Play Console

1. Create subscription product `obrasignal_pro_monthly`.
2. Create the intended auto-renewing monthly base plan.
3. Set real regional prices in Play Console.
4. Create a new-customer store trial only if separately approved as a store experiment.
5. Show the exact store trial duration, post-trial price, recurring nature and cancellation terms.
6. Add Android app `pt.obrasignal.app` to RevenueCat and connect Google Play credentials.
7. Verify the RevenueCat product/base-plan mapping grants entitlement `pro`.

Google Play Billing remains the mobile payment path for digital functionality distributed through Google Play.

## App Store Connect

1. Create the matching auto-renewable subscription product using the canonical ObraSignal product identity expected by RevenueCat.
2. Configure price, localization, subscription group and required disclosures.
3. Attach the product to RevenueCat entitlement `pro` and the current offering.
4. Test through an Apple sandbox/TestFlight path before any real-store claim.

## RevenueCat mobile configuration

Create/retain:

- entitlement: `pro`
- product: `obrasignal_pro_monthly` (plus the store-specific/base-plan identifier RevenueCat exposes)
- current offering containing only the intended Pro package for the ObraSignal purchase CTA

Set RevenueCat App User ID to the authenticated Supabase user ID. Never use email as identity and do not intentionally run the paid flow under a RevenueCat anonymous ID.

Public mobile build variables:

- `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY`
- `EXPO_PUBLIC_REVENUECAT_IOS_KEY`

Backend Subscriber API key:

- `REVENUECAT_SECRET_API_KEY`

## RevenueCat webhook authentication

Webhook URL:

`https://obrasignal.onrender.com/api/v1/billing/webhook`

Production webhook authentication requires RevenueCat's supported configurable `Authorization` header.

1. Generate a random webhook authorization secret.
2. In the RevenueCat webhook integration, configure the exact header value:

   `Bearer <random-secret>`

3. Set only the secret portion on the backend as:

   `REVENUECAT_WEBHOOK_AUTHORIZATION_SECRET`

The backend compares the complete expected Bearer value in constant time. Missing, wrong or malformed authorization fails closed.

RevenueCat also supports official HMAC webhook signing. If that optional second factor is enabled in RevenueCat, store its signing secret separately as:

- `REVENUECAT_WEBHOOK_SIGNING_SECRET`

When configured, both the Authorization header and the official `X-RevenueCat-Webhook-Signature` must validate. Do not invent or reserialize a custom body-signature format; the backend verifies RevenueCat's documented timestamp + raw-body HMAC format only.

Do not reuse one secret value for both Authorization and HMAC signing.

## Webhook state contract

A webhook event is a trigger to reconcile authoritative RevenueCat subscriber state; the event body does not directly grant Pro.

Before any tenant/account mutation the backend requires:

- supported subscription lifecycle event type;
- non-empty event id;
- authenticated non-anonymous `app_user_id`;
- canonical ObraSignal Pro product identity;
- entitlement list containing `pro`;
- structurally valid event/expiration timestamps.

Unknown event types and unrelated product/entitlement events are acknowledged without granting access and without creating an account. Malformed relevant events fail without mutation.

For a valid relevant event, the backend fetches `GET /v1/subscribers/<app_user_id>` and derives the local state from the current `pro` entitlement plus canonical product subscription. Provider failure returns a retryable webhook failure and does not mutate local paid state.

RevenueCat delivers webhooks at least once; event ids are therefore persisted for idempotency. A replay or an out-of-order event reconciles the current Subscriber API snapshot rather than overwriting newer state from stale event semantics.

## Subscription state semantics

Backend paid access is active only when all are true:

- RevenueCat entitlement `pro` exists;
- its product identifier is the canonical ObraSignal Pro product/base-plan identity;
- authoritative expiry or grace expiry is a valid future instant.

State mapping:

- `INITIAL_PURCHASE`, `RENEWAL`, `UNCANCELLATION`, `PRODUCT_CHANGE`, `SUBSCRIPTION_EXTENDED`, `TRIAL_CONVERTED`: current Subscriber API snapshot decides `active`/`trial`/`expired`.
- `TRIAL_STARTED`: paid/store trial remains Pro only until its authoritative expiry.
- `CANCELLATION`: does not revoke immediately; access remains until the authoritative entitlement expiry.
- `BILLING_ISSUE`: grace remains active only through RevenueCat's authoritative grace boundary.
- `EXPIRATION`: removes paid access once the authoritative entitlement/grace boundary has passed.
- missing/malformed expiry: never indefinite Pro.
- subscriber API disagreement: Subscriber API wins over the webhook claim.

The backend can also reconcile stale cached billing state from the Subscriber API when `/api/v1/billing/status` is read. Protected business endpoints do not trust mobile purchase claims.

## EAS / native builds

Real purchases require a native development/production build. Expo Go is not proof of a store transaction.

Required public RevenueCat build variables must be present in the EAS environment. Production release remains subject to Mobile Release Preflight plus store sandbox/internal testing.

## ObraSignal Evaluation v0.1 — separate from store trials

ObraSignal's own evaluation access is not a Google Play/App Store subscription trial. New self-service accounts receive a 21-day value-aware evaluation only after:

`profile_ready + market_data_available + first_relevant_shortlist_generated`

Onboarding does not consume evaluation days. Enterprise accounts may be explicitly configured for a 30-day assisted pilot. A controlled extension is capped at 7 days and is not granted for inactivity alone.

RevenueCat governs paid `pro`. A valid paid entitlement takes precedence over evaluation. Existing legacy pilot accounts retain their pre-v0.1 `trial_ends_at` window unless a separate migration is approved.

Do not create a 21-day store free-trial offer merely because the product evaluation is 21 days.

## Release gate

Do not claim paid commerce ready until all applicable stages are evidenced separately.

Repository/synthetic gates:

- webhook Authorization valid/wrong/missing/malformed;
- optional official HMAC when enabled;
- unrelated product/entitlement cannot create account or Pro;
- missing app user / malformed payload/timestamps cannot mutate state;
- duplicate and out-of-order events are safe;
- subscriber API disagreement wins;
- cancellation keeps access only until expiry;
- billing issue honors grace boundary;
- expiry removes backend access;
- mobile cannot purchase an unrelated offering package;
- mobile SDK entitlement alone cannot label backend Pro;
- backend guard returns subscription-required after paid expiry.

External sandbox/store gates:

- store product exists and is active;
- RevenueCat maps it to `pro` and current offering;
- purchase activates `pro` in RevenueCat;
- backend recognizes it through Subscriber API/webhook;
- app restart preserves backend-recognized Pro;
- same user on a second device sees the same entitlement;
- restore reconciles backend Pro;
- cancellation retains access to expiry;
- grace behavior matches the configured store/RevenueCat policy;
- expiration removes protected backend access;
- reactivation/restore re-enables access;
- management/cancellation opens the store-managed path;
- localized price and recurring terms are displayed.

A RevenueCat dashboard test webhook is not a store purchase. A store sandbox purchase is not a real charged production purchase. A real-store claim requires an actual configured production store transaction.
