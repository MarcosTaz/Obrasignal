# ObraSignal Mobile

Native iOS/Android client for ObraSignal. The app does **not** wrap the dashboard in a browser. It consumes the ObraSignal JSON API and renders opportunities with native React Native UI.

## Architecture

- `App.js` — presentation and navigation shell.
- `src/api.js` — single network boundary for the backend API.
- `src/storage.js` — local persistence and offline cache.
- `src/notifications.js` — native notification boundary.
- `/api/v1` — stable JSON contract served by the backend.

The dashboard can evolve independently from the mobile client. The mobile client only depends on the API contract.

## Product foundations

- Native opportunity feed and detail view.
- Server-side search, score and open-deadline filtering.
- Local favourites.
- Offline-first cache fallback.
- User preference storage.
- Native notification permission/channel setup.
- iPhone, iPad and Android responsive layout.
- EAS-ready project metadata.
- Backend/mobile quality checks in GitHub Actions.

## Local development

```bash
cd mobile
npm install
npx expo start
```

For native notification testing, use an EAS development build rather than relying on Expo Go for Android remote push notifications.

## Production roadmap

1. Account/authentication and server-side favourites.
2. Device push-token registration.
3. Company profile and personalised scoring rules.
4. Saved searches and alert rules.
5. Documents/attachments and contact extraction.
6. Subscription and entitlement service.
7. Store assets, privacy/terms and full device QA.

Expo SDK 57 is the current project baseline. EAS Build produces standalone iOS and Android binaries from this project.
