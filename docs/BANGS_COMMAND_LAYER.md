# ObraSignal Bangs / Command Shortcut Layer v0

## Purpose
A transport-independent control surface for explicit `!commands`. It parses, validates, authorizes, gates, dispatches through injected public providers, and returns a canonical result. It is not a search, economics, requirements, country, watchlist, decision, buyer, submission, field-cost, or LLM engine.

The product concept remains **Bangs / Command Shortcut Layer**. Its Python package is deliberately named `bang_commands` so it cannot collide with the separate contractor field-intelligence `bangs` package introduced independently by PR #195.

## Grammar
`!<command> [arguments...]` with a 2 KiB command limit, 32 arguments, and 512 characters per argument. Names are lowercase-normalized ASCII `[a-z][a-z0-9-]{0,31}`. Quoting is supported only for grouping text. Control and Unicode format characters are rejected. v0 does not accept flags.

No `eval`, `exec`, shell execution, SQL execution, dynamic imports, or user-directed Python evaluation exists in the core.

## Registry and command classes
The registry owns canonical names, aliases, descriptions, required capabilities, permissions, argument validators, and side-effect classes. `!help`/`!commands` are built in. Candidate domain commands are registered as contracts but are omitted from help and return `UNAVAILABLE` with `NOT_INTEGRATED` unless a runtime provider is explicitly registered and enabled.

Commands defined: help/commands, search/hunt, watch, compare, requirements, readiness, economics, workspace, buyer, documents, history, country/coverage, source/sources.

## Auth and tenant rules
The module never parses `tenant_id`, `account_id`, admin state, or permissions as authority. A trusted `BangExecutionContext` is supplied by the host transport after canonical authentication. Providers receive that context and must perform domain-level tenant checks on referenced entities. Fixed arity prevents an extra account/tenant argument being smuggled into write commands such as `!watch`.

## Capability gating
A provider is injected under a capability name. Missing provider => `UNAVAILABLE` / `NOT_INTEGRATED`. Present but disabled/gated => `GATED`. A provider that explicitly reports itself absent => `UNAVAILABLE`. Exceptions while checking availability or executing a provider => `FAILED`, never empty-success. Malformed availability or result contracts also => `FAILED`. Provider availability failures during help discovery are isolated and do not break the registry.

Provider availability is required to be a cheap local/runtime-state check. Bangs does not perform network capability discovery on each invocation.

## Canonical read adapters already possible on main
`bang_commands.canonical_providers` contains two opt-in adapters backed only by public contracts that already exist on canonical `main`:

- `COUNTRY_COVERAGE` -> `market_scope_registry.market_scope(...)`
- `SOURCE_REGISTRY` -> `source_registry.source_status(...)` plus `production_gate_reasons(...)`

Use `canonical_read_provider_registry()` to register exactly those two adapters. They are read-only and perform no network calls, database writes, tenant lookup, or duplicated procurement logic.

A source that is registered but not production-ready still returns a successful **registry read** containing the canonical gate reasons; the command does not pretend that ingestion is enabled.

`SEARCH` is intentionally **not** adapted yet. On the current base, opportunity search behavior is embedded in the HTTP route/database path rather than exposed as a stable public domain contract. Calling private route internals or copying its SQL into Bangs would create a second search engine and violates the module boundary. Search therefore remains `NOT_INTEGRATED` until a merged public search contract exists.

All other feature-backed providers remain unavailable until their public domain contracts are merged into canonical `main`.

## Error/status model
`SUCCESS`, `PARTIAL`, `UNAVAILABLE`, `GATED`, `INVALID`, `NOT_FOUND`, `FORBIDDEN`, `FAILED`.

## Output contract
`BangResult` preserves command, status, message, data, warnings, evidence refs, capability, execution id, and generated-at timestamp. Evidence refs supplied by providers are passed through unchanged.

## Observability
A pluggable observer receives command, command type / side-effect class, status, capability, provider name, and latency. Raw arguments and private result data are deliberately not logged by the core. Observer failures are isolated from command execution.

## Idempotency
Bangs forwards the transport/domain idempotency key in `BangExecutionContext`; it does not invent persistence or duplicate domain write rules. A future watchlist provider remains responsible for canonical duplicate prevention. This keeps idempotency ownership with the domain that knows whether a repeated mutation is semantically equivalent.

## Namespace-conflict resolution
During parallel integration review, PR #195 was found to independently own `bangs/`, including `bangs/__init__.py`, `bangs/contracts.py`, a `bangs/providers/` package, and the root file `BANGS_INTEGRATION_MANIFEST.md`. The command-layer branch previously used the same namespace and root manifest name.

The command layer therefore moved to `bang_commands/` and `BANG_COMMAND_LAYER_INTEGRATION_MANIFEST.md`. This is an integration-safety change only; bang syntax and behavior are unchanged. No change was made to PR #195. After the rename, the two modules have disjoint owned paths and can be reviewed/merged independently.

## Integration
1. Authenticate through existing ObraSignal auth and construct `BangPrincipal` from trusted identity/permissions.
2. Register only merged public providers with `ProviderRegistry`; optionally start with `canonical_read_provider_registry()` for country/source reads.
3. Keep provider `availability()` local and bounded; do not hide network discovery behind the Bangs registry.
4. Optionally expose `BangExecutor.execute()` through HTTP/CLI/mobile/chat transports.
5. Keep the core transport-independent; no API or UI endpoint is introduced in v0.
6. Run Bangs tests plus repository regressions before merge.

## Future natural-language layer
A future NL-to-bang adapter may propose a structured explicit invocation, but deterministic parsing/routing remains separate and does not call an LLM.

## Rollback
Remove command-layer-owned `bang_commands/` files and any later host registration. No canonical table, Master Queue, source registry, market-scope registry, or domain engine migration is required by this branch.
