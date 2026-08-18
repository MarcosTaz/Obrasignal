# ObraSignal Mobile

Native iOS/Android client for ObraSignal. The app does **not** wrap the dashboard in a browser. It consumes the ObraSignal JSON API and renders opportunities with native React Native UI.

## Stack

- Expo SDK 57
- React Native 0.86
- iOS + Android from one codebase
- ObraSignal API at `/api/v1`
- Local saved opportunities via AsyncStorage
- EAS Build for store binaries

## Local development

```bash
cd mobile
npm install
npx expo start
```

For a physical device, use a development build when native functionality is added. Expo documents SDK 57 as the current stable line, with React Native 0.86 and Android target API 36. The latter also aligns with the Google Play target API 36 requirement for new apps/updates from 31 August 2026.

## Production builds

```bash
cd mobile
npx eas login
npx eas build --platform all --profile production
```

The app store submission should happen only after on-device QA, privacy metadata, screenshots, support URL, terms/privacy pages and production backend authentication are complete.
