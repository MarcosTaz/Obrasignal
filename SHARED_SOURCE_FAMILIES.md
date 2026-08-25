# ObraSignal Shared Source Families

Status: Q070 implementation contract.

## Purpose

A source family exists to reduce maintained connector surface **only where the
publisher contract is actually shared**. It is not permission to force different
APIs into one abstraction.

`shared_source_families.py` is the canonical fitness registry. Normal CI must
fail if a source that claims a generic adapter is no longer registered in the
matching family, if a family member disappears from the source registry, or if
an incremental member loses its incremental capability.

## Current families

| Family | Standard | Members | Shared boundary |
| --- | --- | --- | --- |
| `TED_SEARCH` | TED/eForms | `TED` | central TED Search API contract |
| `EFORMS_XML` | eForms | `SERVICE_BUND_DE`, `EE_RHR` | semantic eForms contract; publisher transport/lifecycle parsing remains local |
| `OCDS_PAGE_API` | OCDS | `PY_DNCP`, `ZA_ETENDERS` | bounded temporal windows + page-number completeness; `ocds_adapter.py` |
| `OCDS_OPAQUE_CURSOR` | OCDS | `UK_PROCUREMENT` | bounded windows + publisher opaque cursor; `ocds_cursor_adapter.py` |
| `OCDS_MONTHLY_BULK` | OCDS | `EC_SERCOP` | monthly bulk discovery + bounded record hydration; `ocds_bulk_adapter.py` |

## Runtime composition

`shared_family_runtime.py` owns the repeated opt-in runtime installation glue for
family members and delegates source health, staged cursor persistence, legacy
TENDER projection and failure isolation to `incremental_runtime_plugin.py`.

Germany, Estonia, Ecuador and UK runtime modules use this common installation
boundary. Their country modules still own only what is genuinely publisher
specific: URLs, authentication, taxonomy, pagination parameters, local fields,
identity and lifecycle interpretation.

## Deliberate non-merges

The three OCDS transports are not merged. Page-number pagination, opaque cursors
and bulk+record hydration have different completeness and security failure modes.
A single configurable mega-adapter would make those guarantees weaker and harder
to test.

Germany and Estonia are both eForms publishers, but their export partitioning,
identity/version and lifecycle behaviour differ materially. `EFORMS_XML` is
therefore a semantic/fitness family, not a claim that their parsers are identical.

Uruguay ARCE remains outside these generic OCDS transport families because its
validated contract is RSS discovery plus Record/Release APIs. It should join a
new shared family only when a second source proves the same transport contract;
creating a one-off abstraction would not reduce maintenance.

## Onboarding rule

Before adding a new country connector:

1. Check `shared_source_families.py` for an existing compatible family.
2. Reuse that family when pagination, completeness and lifecycle guarantees fit.
3. Keep source-specific normalization/configuration in the country module.
4. Use `shared_family_runtime.install_shared_family_source` for opt-in runtime
   composition when the source is an incremental family member.
5. If no family fits, use a source-specific connector rather than weakening an
   existing family contract.
6. Add a new family only after it represents a genuinely reusable contract, not
   merely because two sources both emit JSON/XML/OCDS.

## Safety / rollback

This change has no schema migration and no credential changes. Family runtime
composition remains behind the existing `OBRASIGNAL_GLOBAL_SOURCES` and source
production gates. Rollback is code-only: restore the previous country runtime
wrappers; persisted source cursors and Signal observations are unchanged.
