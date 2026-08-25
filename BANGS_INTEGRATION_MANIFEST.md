# Integration Manifest — BANGS COMMAND LAYER

MODULE: BANGS COMMAND LAYER v0

BRANCH: feature/bangs-command-layer-v0

BASE HEAD: 52e011083545a2e69526cd8e0a294cfb61682884

PR: #193 — https://github.com/MarcosTaz/Obrasignal/pull/193 — open against `main`; no auto-merge.

OWNED FILES:
- `bangs/__init__.py`
- `bangs/contracts.py`
- `bangs/parser.py`
- `bangs/registry.py`
- `bangs/providers.py`
- `bangs/executor.py`
- `tests/test_bangs.py`
- `docs/BANGS_COMMAND_LAYER.md`
- `BANGS_INTEGRATION_MANIFEST.md`

CANONICAL FILES TOUCHED: none.

PUBLIC CONTRACTS USED: host-supplied trusted auth identity; provider protocol defined by this module. No private tables or feature-branch implementation imports.

OPTIONAL PROVIDERS: SEARCH, WATCHLIST, OPPORTUNITY_COMPARE, OPPORTUNITY_REQUIREMENTS, OPPORTUNITY_READINESS, BID_ECONOMICS, PURSUIT_WORKSPACE, BUYER_PROFILE, OPPORTUNITY_DOCUMENTS, OPPORTUNITY_HISTORY, COUNTRY_COVERAGE, SOURCE_REGISTRY.

DEPENDENCIES: Python standard library only inside Bangs core. Host supplies canonical provider implementations and trusted identity.

CONFLICT RISKS: low. New package/docs/tests only. Integration conflicts can arise only later if host wiring chooses names already claimed by another control surface.

MERGE ORDER: domain capability branches may merge first or independently; Bangs may merge without them because missing providers fail closed. Provider wiring should happen only after each domain public contract is merged.

TEST STATUS: 50 tests from the initial module version passed locally before publication. The hardened PR head defines 68 Bangs test cases; the repository-wide GitHub Actions run on the exact PR head is the authoritative quality gate and must be green before integration.

PRODUCTION STATUS: NOT CLAIMED.

ROLLBACK: revert this PR or remove Bangs-owned files and any later host registration. No data migration and no Master Queue rollback is required.
