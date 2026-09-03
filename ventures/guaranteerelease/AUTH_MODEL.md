# GuaranteeRelease — Controlled Prototype Authentication & Separation of Duties

Date: 2026-08-29
Status: HARDENED CONTROLLED PROTOTYPE — NOT PRODUCTION IAM

## v5 authentication

The server accepts a bearer token only when its SHA-256 digest matches an entry in `GR_AUTH_PRINCIPALS_JSON`. Each entry contains `principalId`, `tenantId`, role (`operator` or `reviewer`) and `tokenSha256`. Plaintext legacy `GR_API_KEYS_JSON` is ignored. The datastore does not persist configured bearer tokens or their hashes.

## Fail closed

Authentication configuration fails closed when malformed, when role/hash is invalid, or when a `principalId` or token hash is duplicated. This prevents ambiguous identity/role selection based on JSON order.

## Separation of duties

Operator may create/update instruments and submit `PENDING` evidence. Reviewer may approve/reject eligible evidence but cannot create/update instruments or submit evidence. Operator cannot review evidence.

Approval also requires distinct operator provenance (`submittedByRole=operator` plus `submittedByPrincipalId`). Evidence without valid distinct operator provenance must not be promoted to approved truth.

## Token requirements for controlled pilots

Bearer tokens remain secrets even though only hashes are configured. Use high-entropy random tokens, never commit raw tokens, transmit only over TLS outside isolated local testing, rotate on personnel/scope change or suspected compromise, and assign one token per principal. SHA-256 configuration does not make weak human-chosen tokens safe from offline guessing.

## Not claimed by v5

v5 is not production IAM. It does not yet provide enterprise SSO/OIDC/SAML, MFA enforcement, centralized revocation/session management, short-lived credentials, managed vault integration, production rate limiting/WAF, device/risk controls or formal user lifecycle/SCIM.

Before external production use, replace or front static bearer tokens with an approved identity layer while preserving tenant binding, role separation and principal-attributed audit history.
