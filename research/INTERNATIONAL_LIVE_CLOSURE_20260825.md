# International live closure probe — 2026-08-25

Research-only evidence branch based on `main@fa08420b73d96bf2a3a81a59fc3bf3c3df57651d`.

Purpose: re-test the smallest high-value external gates for Brazil PNCP PCA discovery, Honduras public OCDS access/paging/bulk, and Peru OECE machine access from a normal GitHub-hosted runner with ordinary TLS verification.

Safety: no login, credentials, CAPTCHA, WAF bypass, TLS weakening, private endpoint guessing, source registration, runtime wiring, production activation, Master Queue mutation or merge authorization.

## Exact-head evidence

Probe HEAD: `f77d361fa1bd4d9d4dc32cf47ea4b792f99d695d`.

- `ObraSignal Quality` run `32867384306` / #1628: SUCCESS.
- `International Closure Live Probes` run `32867384446` / #1: SUCCESS as an evidence collector.
- Exact revision assertion passed before network I/O.

A green evidence-collector workflow does not mean the probed sources were green. Each source result below is classified independently.

## Brazil — PNCP PCA

Official public/open-data rights and no-login access are already independently documented. This run tested the current official PCA update discovery route with ordinary TLS and no retries/bypass:

- 1-day window, ISO dates: read timeout;
- 1-day window, compact `YYYYMMDD`: read timeout;
- 7-day window, ISO dates: read timeout;
- 7-day window, compact `YYYYMMDD`: read timeout;
- current official OpenAPI `/api/consulta/v3/api-docs`: read timeout from the same hosted runner.

Decision: `GATE_CONFIRMED / NEEDS_ENDPOINT_CONTRACT_OR_SOURCE_RELIABILITY`. The result does not support implementing a production PCA discovery connector from this runner yet. Because even OpenAPI timed out, this run cannot distinguish PCA-query cost from broader PNCP reachability/latency in the hosted environment. No access-control bypass is justified.

Exact next proof: one successful bounded response from the official PNCP OpenAPI plus one compact-date `/v1/pca/atualizacao` page with the documented pagination envelope, under ordinary TLS, before implementation handoff.

## Honduras — ONCAE/SEFIN OCDS

Official documentation already closes the REST/OCDS route, page-number pagination, OCID identity, lifecycle model, bulk-download surface and CC BY 4.0 reuse. This hosted-runner check tested the documented HTTPS routes:

- `/api/v1/record/?page=1`: timeout;
- `/api/v1/record/?page=2`: timeout;
- `/api/v1/descargas/`: timeout.

Decision: `GATE_NARROWED / NEEDS_ENDPOINT_CONTRACT_OR_MACHINE_REACHABILITY`. Rights/schema/paging design are not the blocker; current ordinary HTTPS source responsiveness from the target class of hosted environment is.

Exact next proof: page 1 + page 2 + bulk metadata all return successfully in one bounded run, then validate current-year freshness and publisher-native construction classification before implementation.

## Peru — OECE OCDS

The exact machine-access gate from prior research was re-tested without circumvention:

- `/api/v1/files`: HTTP 403;
- portal root: HTTP 403.

Decision: `GATE_CONFIRMED / NEEDS_MACHINE_ACCESS`. This is a source/environment access gate, not a connector bug. Current official rights/open-contracting evidence does not authorize bypassing the 403.

Exact reopen condition: the actual deployment/hosted environment receives stable permitted 2xx responses from the official route under ordinary TLS, after which shared OCDS pagination/completeness/identity/taxonomy validation may proceed.

## Handoffs / non-duplication

- Chile is already canonically implemented via merged PR #154 and remains credential-gated; do not duplicate it here.
- Peru remains owned by the existing external-gate evidence path (#179); do not create a connector while 403 persists.
- Brazil has no newly authorized connector from this evidence; preserve PNCP as the strategic source identity/path.
- Honduras should reuse canonical shared OCDS infrastructure if the endpoint gate clears; do not create a second OCDS framework.

This file is an operational research record only and is not a canonical source registry, market registry, Master Queue or production activation record.