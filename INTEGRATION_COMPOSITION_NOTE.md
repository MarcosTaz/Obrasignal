# Integration Lab — Customer Journey current composition

NOT CANONICAL / DO NOT MERGE / NO DEPLOY.

Exact semantic inputs:
- Supply Chain #482: `f000afb50cdbea17303dc1900090f7454f9db214`
- Persistence #238: `f34d0eab23ea627c95f0d6c7fd1e0339d5533c37`
- E2E fixture #335: `8a0870f667ff465f1588e6868030fe0984a175ec`
- Customer Journey #701: `5b40013527ff7af109d189a68ce1bedaac759a42`

Composition rule: use Persistence tree as storage/startup authority; overlay Supply Chain dependency/build-owned files; overlay #335 fixture-owned files; overlay #701 customer-journey-owned files. `cors_app.py` must preserve #238 `run_serialized_schema_init` and #335 `install_e2e_fixture_api(APP)` in one file.
