# ObraSignal billing setup

## Architecture

ObraSignal uses RevenueCat as the subscription/entitlement layer. The authenticated Supabase user ID is the canonical RevenueCat App User ID across channels. Never use an email address as the RevenueCat identity.

The product uses one recurring entitlement:

- entitlement: `pro`
- product: `obrasignal_pro_monthly`
- access: personalized radar, account scoring, alerts and commercial workflow

The backend projection remains the only access authority. Client/store state may drive purchase UX, but never grants private product access by itself.

## Commercial priority — Web first

The current release priority is Web until the first paying subscriptions are proven. Android may be prepared in parallel when the EAS quota permits, but must not delay Web revenue. iOS is intentionally deferred until the Apple Developer membership is justified by real revenue.

ObraSignal is sold to businesses. RevenueCat's own RevenueCat Billing engine is not the selected B2B Web engine. The preferred Web path is **Stripe Billing connected to RevenueCat**, surfaced through a RevenueCat production Web Purchase Link (or the RevenueCat Web SDK once configured). This keeps Web payment processing in Stripe while maintaining the same RevenueCat `pro` entitlement used by other channels.

Do not silently reuse an unrelated Stripe merchant account. The intended ObraSignal merchant account/legal identity must be explicit before creating live products, prices or payment links.

### Web production setup

1. Use/create the intended ObraSignal Stripe merchant account and complete its required business/merchant verification.
2. Connect Stripe Billing to the ObraSignal RevenueCat project.
3. Create/import the monthly product corresponding to `obrasignal_pro_monthly` and attach it to entitlement `pro` / the current offering as required by the selected RevenueCat Web configuration.
4. Create a **production** RevenueCat Web Purchase Link. Sandbox purchase links are never valid in the production bundle.
5. Set one or both client-side production options in GitHub Actions:
   - `EXPO_PUBLIC_REVENUECAT_PURCHASE_LINK` — production `https://pay.rev.cat/<token>` link; the client appends the URL-encoded authenticated App User ID as a path segment.
   - `EXPO_PUBLIC_REVENUECAT_WEB_KEY` — RevenueCat Web SDK public key if the embedded Web SDK flow is enabled.
6. Set backend reconciliation credentials on Render:
   - `REVENUECAT_SECRET_API_KEY`
   - `REVENUECAT_WEBHOOK_SECRET`
7. Configure the signed RevenueCat webhook endpoint:
   - `https://obrasignal.onrender.com/api/v1/billing/webhook`
8. Keep `obrasignal.com` as the canonical customer domain and do not mark the commercial release ready until that domain serves the exact released build.

The authenticated `/api/v1/billing/status` response publishes only Boolean provider-readiness flags. The Web client will not expose automatic checkout unless both backend subscriber sync and signed-webhook reconciliation are configured. Secrets are never returned to the client.

### Web acceptance sequence

Run sandbox/staging proof separately from production. Before broad acquisition, prove all of the following with the same authenticated App User ID:

- checkout opens only for an authenticated customer;
- checkout identity uses the Supabase user ID, not email;
- successful test purchase yields RevenueCat entitlement `pro`;
- signed webhook updates the backend account idempotently;
- `/api/v1/billing/status` reports `pro` after purchase;
- refreshed Web session obtains access from server authority;
- cancellation preserves access until entitlement expiry;
- expiration removes paid access;
- subscriber API reconciliation recovers from a missed/delayed webhook;
- a second authenticated session sees the same server entitlement;
- management/cancellation route is usable;
- one controlled live payment is completed and reconciled before mass advertising.

## Android / Google Play

1. Create a subscription product with product ID `obrasignal_pro_monthly`.
2. Create an auto-renewing monthly base plan.
3. Set the real regional price in Play Console.
4. Create a new-customer free-trial offer only if wanted. If enabled, use the exact trial duration and post-trial price shown by Play.
5. The app must not describe the trial as simply "free". It must state the trial duration, the amount charged after the trial, automatic renewal and how to cancel.
6. Keep the product's recurring value intact throughout the subscription.
7. Add the Android app `pt.obrasignal.app` to RevenueCat and connect the Google Play credentials.

Google Play's Payments policy requires Play Billing for digital app functionality and cloud services distributed through Google Play. The standard ObraSignal Android flow therefore uses Play Billing; it never diverts an in-app Android purchase to the Web checkout.

## iOS / App Store

iOS uses StoreKit through RevenueCat and is not part of the current first-revenue critical path. A real App Store/TestFlight release requires the Apple Developer membership and valid Apple distribution credentials. When iOS is activated, create the matching subscription product, attach it to `pro`, and validate purchase/restore/cancel/expiry through Apple's sandbox/TestFlight before production.

## RevenueCat shared configuration

Create/maintain:

- entitlement: `pro`
- product identity: `obrasignal_pro_monthly`
- current offering containing the monthly package where an offering-based channel is used

Public client variables:

- `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY`
- `EXPO_PUBLIC_REVENUECAT_IOS_KEY`
- `EXPO_PUBLIC_REVENUECAT_WEB_KEY` (optional when a production hosted purchase link is used)
- `EXPO_PUBLIC_REVENUECAT_PURCHASE_LINK` (Web production hosted checkout option)

Backend-only variables:

- `REVENUECAT_SECRET_API_KEY`
- `REVENUECAT_WEBHOOK_SECRET`

The backend polls RevenueCat when an account's cached billing state is stale, so entitlement state does not depend exclusively on webhook delivery. HMAC-signed webhook delivery provides the near-real-time path; subscriber API sync is the recovery/reconciliation path.

## EAS

Real native purchases require an Expo development/production native build. Expo Go is not sufficient for real store transactions.

Required public native build variables must be present in the EAS environment before building. Example development build:

`eas build --platform android --profile development`

Android production must be tested through Google Play internal testing before production submission. iOS follows the equivalent TestFlight/App Store path when that channel is activated.

## Release gates

### Web commercial readiness

`ObraSignal Commercial Readiness` is intentionally stricter than ordinary Web deploy health. It must remain RED until:

- automatic production Web checkout configuration exists;
- `obrasignal.com` resolves and serves the exact release SHA;
- the released page self-reports checkout configured;
- the production API is reachable;
- backend RevenueCat subscriber sync + signed webhook reconciliation are configured and the authenticated billing endpoint reports provider readiness;
- a controlled purchase proves checkout → RevenueCat → backend → `pro` end to end.

A green GitHub Pages deployment alone does **not** mean ObraSignal can charge customers.

### Native store readiness

Do not submit a native production build until all applicable channel requirements are verified:

- store product exists and is active;
- RevenueCat product is attached to `pro`;
- current offering contains the monthly package where required;
- test account can purchase in the store's test channel;
- successful purchase activates `pro` in the app and backend;
- cancellation keeps access until entitlement expiry;
- failed payment/grace period does not revoke access prematurely;
- expiration removes access;
- restore purchases restores the entitlement;
- a second device using the same authenticated user sees the same entitlement;
- store-managed subscription cancellation/management works;
- purchase screen displays localized store pricing and complete recurring-subscription terms.

## ObraSignal Evaluation v0.1 — separate from paid subscription trials

ObraSignal's own evaluation access is not a Google Play/App Store/Stripe subscription trial and must not be configured as one implicitly. New self-service accounts receive a 21-day value-aware evaluation **only after** `profile_ready + market_data_available + first_relevant_shortlist_generated`. Onboarding therefore does not consume evaluation days. Enterprise accounts may be explicitly configured for a 30-day assisted pilot. A controlled extension is capped at 7 days and is never granted merely for inactivity.

RevenueCat continues to govern paid `pro` entitlement. Active paid entitlement takes precedence over evaluation state. Existing legacy pilot accounts keep their pre-v0.1 `trial_ends_at` window unless a separate migration is explicitly approved.

Do not create a 21-day paid-channel free-trial offer merely because the ObraSignal Evaluation is 21 days. Paid-channel trials are a separate future commercial experiment and require their own price/renewal disclosures.

Trial Policy v0.1 is **VALIDATION REQUIRED** and must be reviewed after 10 paying customers and again after 25 paying customers, or earlier if evidence clearly shows the baseline is wrong.
