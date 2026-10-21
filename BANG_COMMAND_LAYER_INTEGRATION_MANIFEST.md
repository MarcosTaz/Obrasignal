# Integration Manifest — BANG COMMAND LAYER

MODULE: BANGS / COMMAND SHORTCUT LAYER v0

TECHNICAL PACKAGE: `bang_commands`

BRANCH: `feature/bangs-command-layer-v0`

BASE HEAD: `52e011083545a2e69526cd8e0a294cfb61682884`

PR: #193, opened from branch to `main`; no auto-merge.

## OWNED FILES
- `bang_commands/__init__.py`
- `bang_commands/contracts.py`
- `bang_commands/parser.py`
- `bang_commands/registry.py`
- `bang_commands/providers.py`
- `bang_commands/executor.py`
- `bang_commands/canonical_providers.py`
- `tests/test_bangs.py`
- `docs/BANGS_COMMAND_LAYER.md`
- `BANG_COMMAND_LAYER_INTEGRATION_MANIFEST.md`

CANONICAL FILES TOUCHED: none.

## PUBLIC CONTRACTS USED
- trusted host-supplied Bang principal/context boundary;
- provider protocol defined by this module;
- `market_scope_registry.market_scope(...)` for canonical country/scope reads;
- `source_registry.source_status(...)` and `source_registry.production_gate_reasons(...)` for canonical source-registry reads.

No private database tables, HTTP-route internals, feature-branch implementation imports, or duplicated domain engines are used.

## CANONICAL PROVIDERS AVAILABLE ON THIS BRANCH
Opt-in, read-only adapters:
- `COUNTRY_COVERAGE` -> canonical market scope registry;
- `SOURCE_REGISTRY` -> canonical source registry.

`canonical_read_provider_registry()` registers only these two providers.

## PROVIDERS DELIBERATELY NOT WIRED
- `SEARCH`
- `WATCHLIST`
- `OPPORTUNITY_COMPARE`
- `OPPORTUNITY_REQUIREMENTS`
- `OPPORTUNITY_READINESS`
- `BID_ECONOMICS`
- `PURSUIT_WORKSPACE`
- `BUYER_PROFILE`
- `OPPORTUNITY_DOCUMENTS`
- `OPPORTUNITY_HISTORY`

Reason: their stable public domain contracts are not all present on this base `main`. In particular, current direct opportunity search is implemented in the API/database route rather than a clean public domain query contract, so Bangs does not copy/reach through that implementation.

## PARALLEL-NAMESPACE CONFLICT FOUND AND RESOLVED
PR #195 independently owns a different contractor field-intelligence engine under `bangs/`, including paths that directly overlapped this command-layer branch (`bangs/__init__.py`, `bangs/contracts.py`, a `bangs/providers/` package and root `BANGS_INTEGRATION_MANIFEST.md`).

Resolution in this branch:
- command shortcut implementation moved from `bangs/` to `bang_commands/`;
- command-layer manifest moved from `BANGS_INTEGRATION_MANIFEST.md` to `BANG_COMMAND_LAYER_INTEGRATION_MANIFEST.md`;
- functional bang syntax is unchanged;
- PR #195 is not modified.

After this rename, command-layer and field-intelligence owned paths are disjoint.

## DEPENDENCIES
Python standard library plus canonical repository modules already present on base `main` for the optional country/source read adapters. Host supplies trusted identity and any later domain providers.

## CONFLICT RISK
LOW after namespace separation. The previously confirmed direct path conflict with PR #195 is removed in the final diff. Future runtime registration still requires deliberate host integration review.

## MERGE ORDER
- PR #193 and PR #195 can be reviewed independently once exact-head quality gates are green because they no longer share technical package/manifest paths.
- domain feature branches may merge before or after the command layer; missing providers fail closed.
- provider wiring for tenant-private or domain-heavy commands must happen only after the relevant public contract is canonical.

## TEST STATUS
Parser/registry/executor/security/provider-contract tests plus canonical country/source adapter tests are included. Repository-wide PR CI on the exact final branch head is the authoritative acceptance gate.

## PRODUCTION STATUS
NOT CLAIMED. No API/UI/CLI runtime transport is added and no production capability is promoted by this branch.

## MASTER QUEUE
Untouched.

## ROLLBACK
Revert PR #193 or remove `bang_commands/`, its tests/docs/manifest, and any later host registration. No schema migration, canonical data change, source activation, market-scope mutation, or Master Queue rollback is required.
