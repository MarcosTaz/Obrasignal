# Production security gates — not yet satisfied
Public/multi-user customer-data deployment is blocked until all are independently verified:
1. AuthN with secure session lifecycle and MFA policy where appropriate.
2. Server-enforced tenant AuthZ on every read/write path.
3. Encrypted durable persistence with migration/backup/restore tests.
4. Secret management and key rotation; no secrets in source/client bundles.
5. Immutable/auditable event history for material economic changes.
6. Data retention/export/deletion workflows and tenant-scoped verification.
7. Upload/content validation, malware/document handling policy where applicable.
8. Rate/resource limits, observability, alerting and incident response.
9. Deployment identity, rollback and environment separation.
10. Independent cross-tenant/adversarial security test before real shared runtime.

Until then, real pilot delivery stays assisted-local with authorized transfer and human review.
