# CanadaBuys implementation status

Q040_CANADA_BUYS remains ACTIVE until exact-head CI and live production-path validation pass.

Implemented on `codex/canadabuys-production`:

- official New/Open CSV connector;
- strict publisher-native CNST construction gate;
- solicitation-number durable identity;
- amendment/version preservation;
- fixed UTC-05 closing-time semantics;
- conditional ETag/Last-Modified transport;
- Open snapshot lifecycle reconciliation;
- fail-closed 67-column schema contract;
- no fabricated tender value/currency;
- generic incremental runtime wrapper;
- deterministic contract/runtime tests;
- opt-in live production-path test.

Not yet promoted at the time this file is written:

- source registry entry;
- default runtime activation;
- master queue Q040 -> DONE.

Those require exact-head CI plus a successful live production-path gate.