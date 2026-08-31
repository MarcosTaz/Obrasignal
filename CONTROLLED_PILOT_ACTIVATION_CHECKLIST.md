# ObraSignal — Controlled Real-Pilot Activation Checklist

Status: `PREPARED / ACTIVATION_NOT_AUTHORIZED`

Use this checklist only when a real workflow-qualified prospect has explicitly agreed to a controlled pilot. It prevents “interested” from being silently promoted to “pilot” and prevents the real customer becoming a debugging environment.

## 1. Prospect / problem gate

- [ ] Prospect is workflow-qualified by real procurement/tender activity.
- [ ] Relevant user/role is identified.
- [ ] Customer explicitly confirms the discovery/triage workflow exists.
- [ ] Current workaround is recorded.
- [ ] Pain frequency/severity is recorded without embellishment.
- [ ] Customer explicitly agrees to test.

## 2. Pilot definition

- [ ] Pilot ID assigned.
- [ ] Start date agreed.
- [ ] Review date agreed.
- [ ] Free/paid/quoted state explicit.
- [ ] Required customer inputs defined.
- [ ] First Value Event definition disclosed internally.
- [ ] Repeat-value measurement plan active.
- [ ] Success/failure criteria recorded.
- [ ] Known limitations disclosed.

## 3. Build / environment gate

- [ ] Exact candidate build SHA frozen.
- [ ] Exact-head CI green.
- [ ] No known P0.
- [ ] No falsely closed customer-blocking P1.
- [ ] Database/startup/migration path verified for candidate.
- [ ] Backup/restore procedure verified for candidate data model.
- [ ] Production or controlled pilot environment is serving the intended SHA before customer access.
- [ ] Protected-route/auth smoke passes.
- [ ] Source-health/currentness is acceptable for sources used by this customer.

No auto-merge/deploy is authorized by this checklist.

## 4. Customer journey gate

Before invitation:
- [ ] signup/auth path known working for intended environment;
- [ ] email-confirmation return path works where confirmation is enabled;
- [ ] password-recovery link and new-password path are verified on the intended build;
- [ ] profile/setup works;
- [ ] Radar/opportunity path works;
- [ ] source/relevance explanation is present;
- [ ] save/workflow state persists;
- [ ] logout/login/return preserves tenant-private truth;
- [ ] an expired authenticated session can recover one protected write without duplicate mutation, or the pilot is explicitly blocked until re-authentication behavior is verified;
- [ ] notification path, if enabled, is clearly classified as provider-accepted/scheduled rather than falsely “delivered”;
- [ ] account/privacy controls are reachable independently of paid product entitlement;
- [ ] error/degraded states are truthful;
- [ ] no test-only fixture path is exposed in production.

## 5. Tenant / security gate

- [ ] Cross-tenant reads fail.
- [ ] Cross-tenant private updates fail.
- [ ] Guessed/copy-pasted IDs cannot expose another tenant's private workflow/profile.
- [ ] Stale/invalid auth fails closed.
- [ ] Export/deletion privacy boundaries remain scoped to authenticated tenant.
- [ ] Account export is not presented as a complete device/provider export when only current canonical server-owned account data is included.
- [ ] Destructive deletion requires the exact explicit confirmation expected by the backend.
- [ ] Product-private deletion is not presented as fully completed while external identity/session/device/billing revocation is unproved.
- [ ] No secrets appear in client-visible configuration/logging.

## 6. Support gate

- [ ] Actual monitored support contact is provided to customer.
- [ ] P0/P1 escalation owner is known.
- [ ] Incident record template is available.
- [ ] Data-correction process is ready.
- [ ] Pilot operating review cadence is defined.
- [ ] No 24/7 promise is made unless operationally true.

## 7. Privacy / legal gate

- [ ] Pilot nature/limitations are communicated.
- [ ] Only necessary customer data is requested.
- [ ] No unnecessary secrets/payment details are requested.
- [ ] Applicable privacy/terms owner/legal requirements are resolved enough for the specific pilot or explicitly gated.
- [ ] Account export/deletion wording shown to the pilot is consistent with the actual implemented data boundaries.
- [ ] Any external deletion/revocation obligation that cannot yet be executed is explicitly tracked rather than silently marked complete.
- [ ] No unverified legal-compliance statement is made.

## 8. Billing gate

If pilot is not charging:
- [ ] no real payment instrument is requested or charged;
- [ ] free/pilot entitlement state is explicit.

If a paid continuation is authorized later:
- [ ] price/terms explicitly accepted;
- [ ] production payment/provider configuration owner-approved;
- [ ] checkout/provider flow tested safely;
- [ ] entitlement derives from provider authority;
- [ ] duplicate/out-of-order provider events remain idempotent;
- [ ] cancellation/failure/reconciliation path is understood.

## 9. Measurement gate

- [ ] Baseline workflow captured.
- [ ] Signup/pilot-start timestamp captured.
- [ ] FVE evidence collector ready.
- [ ] Human-assisted minutes captured.
- [ ] Separate repeat-value cycle tracking ready.
- [ ] Support burden captured.
- [ ] Price/WTP outcome captured distinctly from usage.

## 10. Activation decision

Only classify `PILOT_ACTIVE` when:
- the customer explicitly agreed;
- exact environment/build is safe enough for controlled use;
- support route is live;
- measurement is ready;
- no unresolved P0 exists;
- applicable owner/legal boundaries for that pilot are satisfied.

Otherwise remain `PILOT_PREPARED` or `BLOCKED_OWNER_ONLY` and continue independent work.
