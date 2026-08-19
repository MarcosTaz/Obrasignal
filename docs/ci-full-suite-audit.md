# Full-suite audit — 2026-08-19

Issue: #77

## Scope

This audit covers the expanded Python regression suite. Mobile implementation is explicitly out of scope.

## Current result

The expanded suite executed 139 tests: 130 passed and 9 failed.

## Classification

### Runtime/API defects to fix

- Opportunity detail must handle an uninitialized database safely instead of leaking `sqlite3.OperationalError`.
- Radar decision summaries must expose a stable `score` field when there is no decision (`null`, not an omitted key).
- The legacy sync-pipeline entry point `_apply_profile_scores` must either be removed from all active consumers or replaced by the canonical pipeline entry point; do not restore obsolete scoring semantics merely to satisfy a test.

### Contract tests to update after verification

- Detail-page copy asserting the historical `DECISÃO COMERCIAL` label.
- Funnel assertions expecting historical `RELEVANT` / `REJECTED` states where the canonical commercial-v2 contract uses `QUALIFIED` / `REVIEW` / `REJECT`.
- Profile-score assertion that assumes an input `profile_score` is authoritative when the canonical evaluator derives the score from the account profile.
- Radar copy assertion for superseded descriptive text.

## Rule

Do not weaken tests to make CI green. Runtime behavior is fixed first; only expectations proven to represent the superseded contract are updated.
