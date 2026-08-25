# International Coverage Audit

## Purpose

This file documents the repository-state audit introduced by `international_coverage_audit.py`.

The audit answers one narrow question:

> What can the ObraSignal repository prove about international markets, sources, signals, implementation, tests, runtime wiring, production path and gaps?

It intentionally does **not** use chat memory, external market research, or manual claims.

## Canonical command

```bash
python international_coverage_audit.py --json
python international_coverage_audit.py --markdown
python international_coverage_audit.py --strict
```

`--json` is the machine-readable audit output. It is sorted and deterministic.

`--markdown` renders the same audit as a human-readable report.

`--strict` returns a non-zero exit code when contradictions are present.

## Contract

The audit output contract is:

`OBRASIGNAL_REPOSITORY_STATE_INTERNATIONAL_COVERAGE_AUDIT_V1`

Each country row includes:

- `COUNTRY`
- `ISO2`
- `ISO3`
- `MARKET_CLASSIFICATION`
- `SOURCES`
- `SOURCE_FAMILIES`
- `SIGNAL_TYPES`
- `CONSTRUCTION_COVERAGE`
- `PROCUREMENT_PLAN`
- `TENDER`
- `AWARD`
- `CONTRACT`
- `MACHINE_ACCESS`
- `RIGHTS`
- `IMPLEMENTED`
- `TESTED`
- `LIVE_VALIDATED`
- `RUNTIME_WIRED`
- `PRODUCTION_PATH`
- `GATED`
- `PR`
- `KNOWN_GAPS`
- `PROVENANCE`

## Evidence sources

The auditor reads only repository state:

- `market_scope_registry.py`
- `source_registry.py`
- `shared_source_families.py`
- repository filenames for connectors, runtimes, tests, evidence docs and live workflows

It does not perform live network probes.

## Conservative state rules

A source in `source_registry.py` is not enough to claim production.

A market in `market_scope_registry.py` is not enough to claim implementation.

A connector file is not enough to claim runtime wiring.

A test file is not enough to claim live validation.

A planned or credential-gated source remains gated even if connector code exists.

## Known limitation

The audit can prove repository state, not external truth. Live source availability and legal reuse changes still need legitimate live validation workflows.

## Rollback

Delete these files:

- `international_coverage_audit.py`
- `test_international_coverage_audit.py`
- `INTERNATIONAL_COVERAGE_AUDIT.md`
- `international_coverage_audit_manifest.json`
