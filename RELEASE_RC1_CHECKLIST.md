# ObraSignal RC1 — real-device validation

Automated CI proves that the Python suite passes, Expo Doctor passes, and the Expo mobile bundle can be produced. It does **not** prove a real device can authenticate against production services, complete account-recovery/privacy journeys, receive a real push, or complete a Play Billing purchase.

## Device acceptance gate

Run this checklist against an EAS development/preview build installed on a physical Android device.

1. Launch app with production-like environment variables.
2. Create a fresh Supabase user.
3. If email confirmation is required, confirm the account and return successfully to the app.
4. Confirm authenticated session survives app restart.
5. Exercise `Esqueci-me da palavra-passe`, follow the recovery link and set a new password.
6. Confirm the recovered account can sign in with the new password and the normal product shell is restored.
7. Complete company onboarding.
8. Save and reload the company profile.
9. Load Radar and confirm opportunities are returned.
10. Open an opportunity and confirm account-specific score, decision and explanation.
11. Change workflow through `NEW → REVIEWING → PREPARING → SUBMITTED` and verify persistence after reload.
12. Verify `WON` and `LOST` are mutually exclusive terminal states.
13. Force or observe an expired access-token condition and confirm one protected write can recover through session refresh without duplicate mutation.
14. Verify another account cannot read or mutate the first account's opportunity workflow/decisions.
15. Verify unauthenticated API calls are rejected.
16. Open `Conta e privacidade` while authenticated and confirm account export can be prepared without claiming a device file was created.
17. Confirm exported server-owned account data contains only the authenticated tenant and does not include shared public procurement data as private account data.
18. Confirm destructive deletion cannot be submitted without the exact phrase `DELETE_MY_OBRASIGNAL_DATA`.
19. On a disposable test account, submit deletion and verify the UI reports `PENDING` while external identity/session/device/billing revocation is not proven; do not classify the account as fully deleted from product evidence alone.
20. Verify privacy controls remain reachable even when normal paid product access is billing-gated.
21. Verify pilot entitlement is present for a new account where the controlled pilot policy requires it.
22. In Google Play Internal Testing, purchase `obrasignal_pro_monthly` using only a designated test instrument/account.
23. Verify RevenueCat reports the `pro` entitlement.
24. Verify ObraSignal backend reflects `pro` and unlocks paid functionality.
25. Restore purchases and confirm access remains.
26. Cancel the subscription and confirm access remains until the paid period ends.
27. Verify expiration removes paid access without deleting company/opportunity data or hiding account/privacy rights.
28. Verify push notification permission and one real opportunity alert.
29. Terminate the session and confirm tenant-private local state is no longer readable before another account is allowed to hydrate.

## Evidence record

For each applicable item record:
- build/version and exact source SHA;
- device model / Android version;
- date and operator;
- observed result (`PASS`, `FAIL`, or `NOT_APPLICABLE`);
- minimal evidence reference (screenshot, screen recording, server log reference, or test transaction identifier where appropriate);
- any incident/support record opened from a failure.

Never copy real customer secrets, payment credentials, raw provider tokens or unnecessary personal data into release evidence.

## Release rule

The app is **not production-ready** until every applicable item above is observed on a real device and recorded against the exact build/version. Automated green CI is necessary but not sufficient for release. Synthetic or operator-run test evidence must not be promoted into real customer first-value, repeat-value, willingness-to-pay or retention evidence.
