# ObraSignal Company Truth V8 — 2026-08-31

Composition base: `integration/company-truth-composition-v7-20260830`

Material delta integrated:
- mobile customer settings are tenant-private;
- legacy global settings are purged on tenant bind;
- unauthenticated private-setting writes fail closed;
- A → B → sign-out isolation is covered by deterministic Python and dynamic mobile regression tests.

Pre-composition repair SHA: `2650c189888108a635372d74c886ed0b73749037`.

This marker exists to force a fresh full PR CI run on the final V8 composition head. It is not a production-readiness claim and does not authorize deployment by itself.
