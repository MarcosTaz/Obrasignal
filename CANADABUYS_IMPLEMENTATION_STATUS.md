# CanadaBuys implementation status

Q040_CANADA_BUYS is complete and the canonical queue has advanced to `Q050_US_SAM`.

Validated implementation on `codex/canadabuys-production`:

- official New/Open/Complete CanadaBuys CSV lifecycle path;
- strict publisher-native CNST construction gate;
- solicitation-number durable identity;
- amendment/version preservation without identity churn;
- fixed UTC-05 closing-time semantics;
- conditional ETag/Last-Modified transport;
- Open snapshot lifecycle reconciliation with conservative Complete-file terminal proof;
- fail-closed exact 67-column schema contract;
- no fabricated tender value/currency;
- source registry status `ready`, legal reuse GREEN and machine access VERIFIED;
- explicit opt-in runtime gate through `OBRASIGNAL_GLOBAL_SOURCES` rather than default activation;
- production WSGI composition wiring;
- deterministic contract/runtime/registry tests;
- successful live production-path test against the official CanadaBuys publisher;
- exact-head repository Quality gate passed before queue promotion.

Operational note: `ready` does not mean the production environment variable is currently set. Repository promotion is complete; actual live ingestion remains intentionally controlled by the deployment environment's explicit source opt-in.