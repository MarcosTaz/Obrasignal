# ObraSignal — Pilot Incident / Support Record Template

Use one record per customer-impacting issue. Preserve facts; do not upgrade assumptions.

## Identity

- Incident ID:
- Reported at:
- Reported by:
- Account/company:
- Environment/build SHA:
- Journey stage:
- Severity: P0 / P1 / P2 / P3
- Status: OPEN / CONTAINED / DIAGNOSING / REPAIRING / VERIFYING / RESOLVED / CLOSED

## Customer-visible truth

- What the customer attempted:
- What they observed:
- What they expected:
- Is first value blocked? YES / NO / UNKNOWN
- Is repeat value blocked? YES / NO / UNKNOWN
- Is authentication/recovery blocked? YES / NO / UNKNOWN
- Is payment/billing blocked? YES / NO / UNKNOWN
- Is account export/deletion affected? YES / NO / UNKNOWN
- Deletion state if relevant: NONE / PENDING / FAILED / UNKNOWN / NOT_APPLICABLE
- Is another tenant's data implicated? YES / NO / UNKNOWN
- Is customer-facing truth potentially false? YES / NO / UNKNOWN

## Evidence

- Source URLs / identifiers:
- Request or correlation IDs:
- Relevant timestamps:
- Screenshots/log extracts:
- Reproduction status: REPRODUCED / NOT_REPRODUCED / UNKNOWN
- Exact source SHA/build under test:

Never paste passwords, recovery links/tokens, raw access tokens, credentials, full payment data, provider secrets, exported private-account payloads, or unrelated personal data into the incident record.

## Containment

- Unsafe capability disabled/avoided:
- Safe workaround:
- Customer impact while contained:
- If privacy/tenant issue: affected path blocked from further customer exploration? YES / NO / NOT_APPLICABLE

## Diagnosis

- Root cause: CONFIRMED / HYPOTHESIS / UNKNOWN
- Root cause detail:
- Owning component:
- Regression origin if known:
- Identity-provider vs app-auth boundary distinguished? YES / NO / NOT_APPLICABLE
- Tenant/account identity verified without collecting secrets? YES / NO / NOT_APPLICABLE
- For protected-write 401: one refresh observed? YES / NO / UNKNOWN / NOT_APPLICABLE
- Duplicate mutation observed? YES / NO / UNKNOWN / NOT_APPLICABLE

## Privacy / deletion truth

Complete only when relevant:
- Export scope verified as current canonical server-owned account data only? YES / NO / UNKNOWN
- Shared public procurement data incorrectly treated as tenant-private? YES / NO / UNKNOWN
- Cross-tenant export suspected? YES / NO / UNKNOWN
- Destructive confirmation contract used exactly? YES / NO / UNKNOWN
- Product-private cleanup proven? YES / NO / UNKNOWN
- External identity/session/device/billing revocation proven? YES / NO / UNKNOWN
- Has any `PENDING`, `FAILED`, or `UNKNOWN` state been incorrectly communicated as completed? YES / NO / UNKNOWN

Any suspected cross-tenant export/deletion or wrong-tenant destructive action is provisionally P0 until disproved.

## Repair

- Change/PR/commit:
- Targeted test:
- Regression test:
- Exact-head CI:
- Rollback path:

## Verification

- Customer path retested:
- Tenant/security boundary retested:
- Authentication/recovery retested if relevant:
- Persistence/data truth retested:
- Privacy/export/deletion state retested if relevant:
- Observability confirms healthy state:
- Remaining uncertainty:

## Customer communication

- Acknowledgement sent:
- Workaround communicated:
- Resolution communicated:
- Pending external boundary disclosed if relevant:
- Follow-up required:

## Closure rule

Close only when the customer-relevant path is verified or a durable, explicitly communicated workaround safely resolves the pilot need. Code completion alone is not closure. Never close an account-deletion incident as completed while required external revocation remains unproved.
