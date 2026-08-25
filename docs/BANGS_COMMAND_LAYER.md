# ObraSignal Bangs / Command Shortcut Layer v0

## Purpose
A transport-independent control surface for explicit `!commands`. It parses, validates, authorizes, gates, dispatches through injected public providers, and returns a canonical result. It is not a search, economics, requirements, country, watchlist, decision, buyer, submission, or LLM engine.

## Grammar
`!<command> [arguments...]` with a 2 KiB command limit, 32 arguments, and 512 characters per argument. Names are lowercase-normalized ASCII `[a-z][a-z0-9-]{0,31}`. Quoting is supported only for grouping text. Control characters are rejected. v0 does not accept flags.

No `eval`, `exec`, shell execution, SQL execution, dynamic imports, or user-directed Python evaluation exists in the core.

## Registry and command classes
The registry owns canonical names, aliases, descriptions, required capabilities, permissions, argument validators, and side-effect classes. `!help`/`!commands` are built in. Candidate domain commands are registered as contracts but are omitted from help and return `UNAVAILABLE` with `NOT_INTEGRATED` unless a runtime provider is explicitly registered and enabled.

Commands defined: help/commands, search/hunt, watch, compare, requirements, readiness, economics, workspace, buyer, documents, history, country/coverage, source/sources.

## Auth and tenant rules
The module never parses `tenant_id`, `account_id`, admin state, or permissions as authority. A trusted `BangExecutionContext` is supplied by the host transport after canonical authentication. Providers receive that context and must perform domain-level tenant checks on referenced entities. Fixed arity prevents an extra account/tenant argument being smuggled into write commands such as `!watch`.

## Capability gating
A provider is injected under a capability name. Missing provider => `UNAVAILABLE` / `NOT_INTEGRATED`. Present but disabled/gated => `GATED`. Provider exceptions => `FAILED`, never empty-success. Provider availability failures during help discovery are isolated and do not break the registry.

## Error/status model
`SUCCESS`, `PARTIAL`, `UNAVAILABLE`, `GATED`, `INVALID`, `NOT_FOUND`, `FORBIDDEN`, `FAILED`.

## Output contract
`BangResult` preserves command, status, message, data, warnings, evidence refs, capability, execution id, and generated-at timestamp. Evidence refs supplied by procurement providers are passed through unchanged.

## Observability
A pluggable observer receives command, status, capability, provider name, and latency. Raw arguments and private result data are deliberately not logged by the core.

## Idempotency
Bangs forwards the transport/domain idempotency key in `BangExecutionContext`; it does not invent persistence or duplicate domain write rules. A watchlist provider remains responsible for canonical duplicate prevention.

## Integration
1. Authenticate through existing ObraSignal auth and construct `BangPrincipal` from trusted identity/permissions.
2. Register only merged public providers with `ProviderRegistry`.
3. Optionally expose `BangExecutor.execute()` through HTTP/CLI/mobile/chat transports.
4. Keep the core transport-independent; no API or UI endpoint is introduced in v0.
5. Run Bangs tests plus repository regressions before merge.

## Future natural-language layer
A future NL-to-bang adapter may propose a structured explicit invocation, but deterministic parsing/routing remains separate and does not call an LLM.

## Rollback
Remove Bangs-owned files/registration wiring. No canonical table, Master Queue, source registry, or domain engine migration is required by this branch.
