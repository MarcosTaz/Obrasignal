# ObraSignal RC1 — real-device validation

Automated CI proves that the Python suite passes, Expo Doctor passes, and the Expo mobile bundle can be produced. It does **not** prove a real device can authenticate against production services or complete a Play Billing purchase.

## Device acceptance gate

Run this checklist against an EAS development/preview build installed on a physical Android device.

1. Launch app with production-like environment variables.
2. Create a fresh Supabase user.
3. Confirm authenticated session survives app restart.
4. Complete company onboarding.
5. Save and reload the company profile.
6. Load Radar and confirm opportunities are returned.
7. Open an opportunity and confirm account-specific score, decision and explanation.
8. Change workflow through `NEW → REVIEWING → PREPARING → SUBMITTED` and verify persistence after reload.
9. Verify `WON` and `LOST` are mutually exclusive terminal states.
10. Verify another account cannot read or mutate the first account's opportunity workflow/decisions.
11. Verify unauthenticated API calls are rejected.
12. Verify pilot entitlement is present for a new account.
13. In Google Play Internal Testing, purchase `obrasignal_pro_monthly`.
14. Verify RevenueCat reports the `pro` entitlement.
15. Verify ObraSignal backend reflects `pro` and unlocks paid functionality.
16. Restore purchases and confirm access remains.
17. Cancel the subscription and confirm access remains until the paid period ends.
18. Verify expiration removes paid access without deleting company/opportunity data.
19. Verify push notification permission and one real opportunity alert.

## Release rule

The app is **not production-ready** until every applicable item above is observed on a real device and recorded with date/build/version. Automated green CI is necessary but not sufficient for release.
