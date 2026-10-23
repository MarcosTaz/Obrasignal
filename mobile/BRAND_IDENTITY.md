# ObraSignal — permanent corporate palette (2026-10-23)

## Identity versus user theme
The **corporate identity is fixed**. User-facing themes are visual preferences, not new logos, new corporate names or changes to the underlying business/authorization data. The default theme is `signature`; prior user palettes are retained in Settings.

### Approved palette
| Semantic role | Token | Value | Guidance |
|---|---|---|---|
| Dominant / rigor | `BRAND.slate` | `#2A3439` | Wordmark, headings, proposals, durable symbols |
| Secondary / structure | `BRAND.mineral` | `#5C6B73` | Subheadings, UI annotations, support text |
| Light / air | `BRAND.mistBlue` | `#9DB2BF` | Decorative highlights, icons, fills — not small text on white |
| Fog surface | `BRAND.fog` | `#DBE2EF` | Panels, reports, selected chips |
| Paper surface | `BRAND.paper` | `#F8FAFC` | App surfaces, forms and documents |
| Field signal | `BRAND.copper` | `#C87D55` | Meaningful CTA, selected emphasis and alerts |
| Reading text | `BRAND.ink` | `#0F172A` | High precision body text, dark labels on copper |

Source of truth: `mobile/src/brand-palette.mjs`. Theme tokens and defaults: `mobile/src/theme-system.mjs`.

## Legibility rules
- Use **ink on copper** for button copy; expected WCAG AA contrast >4.5:1. Do not use pale/white microtext on copper or copper microtext on white.
- Use **slate or ink on paper**, mineral for secondary text. Mist blue should not replace the semantic foreground.
- Do not tie corporate brand colours to tenant-selected `settings.theme`. The product workspace may change its surface/background through `createThemeColors`, but its name and core mark remain consistent.
- Preserve public source-verification explanations, truthful example labels, commercial billing boundaries, privacy text and native authorization flows.

## Implementation register
- Public Web auth/landing: `mobile/components/AuthScreen.tsx`
- Favicon and Web branding: `mobile/src/webBranding.js`
- Cinematic startup sequence: `mobile/components/WebIntro.js`
- Web workspace / default theme / selection: `mobile/App.web.js`, `mobile/src/theme-system.mjs`, `mobile/src/storage.js`
- Native Radar: `mobile/App.js`
- Native platform default appearance: `mobile/app.json`
- Account onboarding/access/recovery: `mobile/components/ProfileOnboarding.js`, `mobile/components/AuthGate.js`, `mobile/components/PasswordRecovery.js`
- Plans and data protection: `mobile/components/BillingGate.js`, `mobile/components/AccountPrivacyControls.js`
- Shared status and opportunity explanation: `mobile/components/SecurityTrustBar.js`, `mobile/components/OpportunityExplanation.js`, `mobile/components/WorkflowFunnel.js`
- Regression coverage: `mobile/src/theme-system.test.mjs`.

## Release boundary
The current flat-ring favicon and introductory mark are **palette adaptations of the existing symbol, not legal or creative approval of a final timeless master logo**. Before logo finalization, select an independently reviewed master vector and produce exact derivatives (favicon/PWA/native app/store/docs). No real production deployment is implied by changing these files in a draft PR.

## Official reusable logo component — October 23
- `mobile/src/logo-geometry.mjs`: exact reusable five-path flat-vector geometry (monogram metaphor: evidence/structures converging to a copper decision threshold).
- `mobile/components/BrandLogo.js`: one React Native SVG component for public/secure Web, native header, login, onboarding, recovery and animated Web intro. Layout variants horizontal/vertical/mark; high-contrast inverse mode.
- `mobile/public/obrasignal-monogram.svg` and `mobile/public/obrasignal-logo.svg`: standalone Web/download derivatives. Favicon generated from geometry, no runtime DOM surgery.
- Expo SVG dependency pinned to recommended SDK 57 compatible version `15.15.4`.
- SVG uses flat corporate slate/mineral/copper. The user's current `settings.theme` NEVER changes the official geometry or corporate logo colours.
- **No legal trademark clearance or final typographic outline approval is implied by visual acceptance.** Native store splash icons (PNG raster exports) still require dedicated EAS asset packaging, not an unsupported SVG passed as app-icon PNG.
