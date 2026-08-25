# API contract governance

This layer observes cross-owner compatibility. It is **not** a second API,
business, Auth, persistence, billing, source, or client authority.

## Current executable slice

`opportunity_workflow.v1` is the first high-risk contract enrolled because its
canonical GET response and the Authenticated E2E consumer currently disagree:
the provider returns workflow state under `workflow`, while that consumer reads
`status`/`note` at the response root.

`contract_governance.py` observes only compatibility-significant source
semantics, creates a deterministic SHA-256 fingerprint, classifies known
cross-owner findings, and compares them with
`contracts/public_contract_registry.json`.

A known defect may be acknowledged so governance CI stays useful instead of
making the baseline permanently red. A new fingerprint, new finding, or the
disappearance of an acknowledged finding is `REVIEW_REQUIRED`: the registry
must be updated only after the compatibility decision and exact-head evidence
are explicit.

## Rules

- Executable domain owners remain business truth.
- Registry entries are observation metadata, never implementation authority.
- Tenant derivation, identity, null/unknown behavior, response/error envelope,
  version, and consumer interpretation are contract-significant.
- Fixes owned by Auth, Web, Mobile, Billing, Persistence, Source, Notification,
  or another domain are routed there rather than copied here.
- A green producer does not imply a compatible consumer.
- A harmless additive change should be enrolled/classified deliberately rather
  than treated as breaking merely because files changed.
- Historical fingerprints are evidence only; recompute after relevant HEAD
  movement.

Run:

```bash
python contract_governance.py
pytest -q tests/test_contract_governance.py
```

Exit code `2` means compatibility review is required.
