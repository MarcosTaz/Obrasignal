# ObraSignal Mobile

Native iOS/Android client for ObraSignal. The app does **not** wrap the dashboard in a browser. It consumes the ObraSignal JSON API and renders opportunities with native React Native UI.

## Architecture

- `App.js` — presentation and navigation shell.
- `src/api.js` — single network boundary for the backend API.
- `src/billing.js` — RevenueCat purchase/entitlement boundary.
- `src/storage.js` — local persistence and offline cache.
- `src/notifications.js` — native notification boundary.
- `../lib/supabase.ts` — Supabase authentication/session client.
- `/api/v1` — stable JSON contract served by the backend.

The dashboard can evolve independently from the mobile client. The mobile client only depends on the API contract.

## Implemented product foundations

- Native opportunity feed and detail view.
- Server-side search, personalised score and open-deadline filtering.
- Company profile onboarding and account-scoped profile persistence.
- Commercial workflow and workflow statistics.
- Supabase authentication with persistent sessions.
- RevenueCat integration for `obrasignal_pro_monthly` and entitlement `pro`.
- Purchase and restore flows in the native billing boundary.
- Local favourites and offline cache fallback.
- Native notification permission/channel setup.
- iPhone, iPad and Android responsive layout.
- EAS-ready project metadata.
- Backend/mobile quality checks in GitHub Actions.

## External production gates still required

The code above is not by itself proof of a production release. Before RC1 is considered closed, the following external checks must pass:

1. Render production environment configured with `OBRASIGNAL_AUTH_MODE=provider`, valid JWT issuer/audience/JWKS values, and a successful real authenticated request to `/api/v1/profile`.
2. Supabase production project configured and a real login/session persistence test completed.
3. EAS production environment contains the required Supabase and RevenueCat public client variables.
4. RevenueCat is connected to Google Play/App Store with product `obrasignal_pro_monthly` and entitlement `pro`.
5. Real sandbox purchase, entitlement activation, restore, cancellation and expiry tests pass on a native build.
6. Device push-token registration and real notification delivery are validated.
7. Store privacy/terms/assets and final device QA are complete.

## Local development

```bash
cd mobile
npm install
npx expo start
```

For native notification testing, use an EAS development build rather than relying on Expo Go for Android remote push notifications.

## Release profiles

`mobile/eas.json` defines `development`, `preview` and `production` build profiles. The Android package and iOS bundle identifier are both `pt.obrasignal.app`.

Expo SDK 57 is the current project baseline. EAS Build produces standalone iOS and Android binaries from this project.
