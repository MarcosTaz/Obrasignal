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
- Is payment/billing blocked? YES / NO / UNKNOWN
- Is another tenant's data implicated? YES / NO / UNKNOWN
- Is customer-facing truth potentially false? YES / NO / UNKNOWN

## Evidence

- Source URLs / identifiers:
- Request or correlation IDs:
- Relevant timestamps:
- Screenshots/log extracts:
- Reproduction status: REPRODUCED / NOT_REPRODUCED / UNKNOWN

Never paste credentials, tokens, full payment data or unrelated personal data.

## Containment

- Unsafe capability disabled/avoided:
- Safe workaround:
- Customer impact while contained:

## Diagnosis

- Root cause: CONFIRMED / HYPOTHESIS / UNKNOWN
- Root cause detail:
- Owning component:
- Regression origin if known:

## Repair

- Change/PR/commit:
- Targeted test:
- Regression test:
- Exact-head CI:
- Rollback path:

## Verification

- Customer path retested:
- Tenant/security boundary retested:
- Persistence/data truth retested:
- Observability confirms healthy state:
- Remaining uncertainty:

## Customer communication

- Acknowledgement sent:
- Workaround communicated:
- Resolution communicated:
- Follow-up required:

## Closure rule

Close only when the customer-relevant path is verified or a durable, explicitly communicated workaround safely resolves the pilot need. Code completion alone is not closure.
