# ObraSignal billing setup

## Architecture

ObraSignal uses RevenueCat as the subscription layer. On Android, RevenueCat uses Google Play Billing; on iOS it uses StoreKit. The app never opens a Stripe or external checkout from the mobile purchase flow.

The app uses one recurring entitlement:

- entitlement: `pro`
- product: `obrasignal_pro_monthly`
- access: personalized radar, account scoring, alerts and commercial workflow

The displayed price is taken from the store product and is therefore localized by Google Play/App Store. Do not hardcode a price in the app.

## Google Play Console

1. Create a subscription product with product ID `obrasignal_pro_monthly`.
2. Create an auto-renewing monthly base plan.
3. Set the real regional price in Play Console.
4. Create a new-customer free-trial offer only if wanted. If enabled, use the exact trial duration and post-trial price shown by Play.
5. The app must not describe the trial as simply "free". It must state the trial duration, the amount charged after the trial, automatic renewal and how to cancel.
6. Keep the product's recurring value intact throughout the subscription.
7. Add the Android app `pt.obrasignal.app` to RevenueCat and connect the Google Play credentials.

Google Play's Payments policy requires Play Billing for digital app functionality and cloud services distributed through Google Play. The standard ObraSignal Android flow therefore uses Play Billing.

## RevenueCat

Create:

- entitlement: `pro`
- product: Android `obrasignal_pro_monthly`
- offering: current offering containing the monthly package

Set the App User ID to the authenticated Supabase user ID. Never use an email address.

Create public platform API keys and configure the mobile build variables:

- `EXPO_PUBLIC_REVENUECAT_ANDROID_KEY`
- `EXPO_PUBLIC_REVENUECAT_IOS_KEY`

Create a RevenueCat secret API key and set on the backend:

- `REVENUECAT_SECRET_API_KEY`

Configure a RevenueCat webhook to:

`https://obrasignal.onrender.com/api/v1/billing/webhook`

Enable HMAC signing and set the generated signing secret as:

- `REVENUECAT_WEBHOOK_SECRET`

The backend also polls RevenueCat when an account's cached billing state is stale, so entitlement state does not depend exclusively on webhook delivery.

## EAS

Real purchases require an Expo development/production native build. Expo Go is not sufficient for real store transactions.

Required public build variables must be present in the EAS environment before building.

Example development build:

`eas build --platform android --profile development`

The production release must be tested through Google Play internal testing before production submission.

## Release gate

Do not submit the production build until all of these are verified:

- Google Play product exists and is active.
- RevenueCat product is attached to `pro`.
- Current RevenueCat offering contains the monthly package.
- Test account can purchase in Play internal testing.
- Successful purchase activates `pro` in the app.
- Backend recognizes the entitlement.
- Cancellation keeps access until the entitlement expiry.
- Failed payment/grace period does not revoke access prematurely.
- Expiration removes access.
- Restore purchases restores the entitlement.
- A second device using the same authenticated user sees the same entitlement.
- Store-managed subscription cancellation/management works.
- The in-app purchase screen displays localized store pricing and complete recurring-subscription terms.


## ObraSignal Evaluation v0.1 — separate from store trials

ObraSignal's own evaluation access is not a Google Play/App Store subscription trial and must not be configured as one implicitly. New self-service accounts receive a 21-day value-aware evaluation **only after** `profile_ready + market_data_available + first_relevant_shortlist_generated`. Onboarding therefore does not consume evaluation days. Enterprise accounts may be explicitly configured for a 30-day assisted pilot. A controlled extension is capped at 7 days and is never granted merely for inactivity.

RevenueCat continues to govern paid `pro` entitlement. Active paid entitlement takes precedence over evaluation state. Existing legacy pilot accounts keep their pre-v0.1 `trial_ends_at` window unless a separate migration is explicitly approved.

Do not create a 21-day store free-trial offer merely because the ObraSignal Evaluation is 21 days. Store trials are a separate future commercial experiment and require their own price/renewal disclosures.

Trial Policy v0.1 is **VALIDATION REQUIRED** and must be reviewed after 10 paying customers and again after 25 paying customers, or earlier if evidence clearly shows the baseline is wrong.
