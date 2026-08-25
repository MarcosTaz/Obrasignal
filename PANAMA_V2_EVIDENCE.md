# PanamaCompra / PanamaCompraenCifras V2 — evidence and reopen gate

## Provisional decision

**PREPARE / REOPEN HOLD — NOT YET IMPLEMENTED**

The old premise that Panama's national OCDS publication is simply stale is no longer sufficient. A current V2 PanamaCompraenCifras portal is live and explicitly advertises an OCDS API and bulk downloads using PanamaCompra V2, V2 Tienda Virtual and PanamaCompra V3 data. However, ObraSignal should not implement or promote a source until the actual public machine contract is extracted and live-tested.

## FACT — current public surfaces

- Current portal: `https://v2.panamacompraencifras.gob.pa/`.
- The portal states that its information comes from PanamaCompra V2, PanamaCompra V2 Tienda Virtual and PanamaCompra V3 datasets.
- It advertises **API OCDS** and **Descarga de datos** surfaces.
- Search-indexed process pages contain 2026 OCIDs with prefix `ocds-emvi6n-panamacompra-v3-2026-...` and expose a RecordPackage download action.
- PanamaenObras is integrated with PanamaCompra and publishes infrastructure/project information across identification, planning, procurement, execution and completion.

## FACT — historical publication / rights

The Open Contracting Data Registry records the previous Panama DGCP OCDS publication under the **Open Data Commons PDDL** and notes that the legacy publisher feed stopped updating in 2024. This historical license is positive evidence but is not automatically treated as proof that every V2 endpoint inherits identical terms.

## FACT — infrastructure value

DGCP reports that PanamaenObras was integrated with PanamaCompra and had published more than 3,700 public infrastructure projects worth more than PAB 3 billion by the end of 2023. Open-government reporting states that Panama adopted both OCDS and OC4IDS and that PanamaenObras data includes project budget, progress, companies, responsible persons, costs, funding and project scope.

## TEST PLAN

An explicit bounded live gate probes only the documented public V2 surfaces:

- `/`
- `/api`
- `/descargas`

The test does not guess undocumented API paths. It records discoverable machine-readable URLs if the pages expose them publicly.

## Promotion gate

Before any `source_registry.py` entry or connector:

1. exact API / bulk endpoint contract is publicly discoverable;
2. machine access works from the intended deployment environment;
3. pagination or bulk completeness is understood;
4. identity, timestamps and freshness are validated;
5. current V2 reuse/license/attribution terms are confirmed;
6. construction can be selected using publisher-native OCDS/OC4IDS taxonomy or structured fields.

## Engineering decision

Prefer shared OCDS/OC4IDS transport over a Panama-specific framework. PanamaenObras may justify a separate `CAPITAL_PROJECT` / implementation-depth signal slice only after the procurement transport is stable.

## Epistemic status

- RESEARCH: current V2 reopen evidence found.
- IMPLEMENTED: no production connector.
- TESTED: public-surface live gate pending on this branch.
- GATED: exact machine contract + current rights + completeness.
- MASTER QUEUE: untouched.
