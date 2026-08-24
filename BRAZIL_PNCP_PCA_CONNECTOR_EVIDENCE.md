# Brazil PNCP PCA connector — production evidence

Source: `BR_PNCP_PCA`
Signal: `PROCUREMENT_PLAN`
Jurisdiction: Brazil (national)

## Officiality and public access

The Portal Nacional de Contratações Públicas (PNCP) is Brazil's official national public-procurement publication portal under Lei 14.133/2021.

Official PNCP open-data guidance states that public-procurement data can be queried through APIs without registration or login and downloaded/manipulated in applications. PNCP FAQ states access is free/universal and that PNCP adopts an open-data format.

Primary official references:
- https://www.gov.br/pncp/pt-br/
- https://www.gov.br/pncp/pt-br/acesso-a-informacao/copy_of_dados-abertos
- https://www.gov.br/pncp/pt-br/pncp/perguntas-e-respostas
- https://pncp.gov.br/manual/pt-br/latest/singlehtml/

Registry reuse status is GREEN for read/reuse of these public open-data consultation outputs. ObraSignal does not use PNCP authenticated maintenance/write APIs.

## National discovery contract

PNCP's own public PCA frontend uses the publisher-owned search service:

`GET https://pncp.gov.br/api/search/`

with:
- `q=`
- `tipos_documento=pcaorgao`
- `ordenacao=-data` (`Mais recente` in the official frontend)
- `pagina`
- `tam_pagina`

Live validation on 2026-08-24 proved:
- HTTP 200 JSON envelope `{items,total}`;
- `total = 10,854` PCA organisation/year aggregates at probe time;
- bounded page sizes 10, 50 and 100;
- recent-first update ordering;
- stable row `id`;
- `orgao_cnpj`, `ano`, `data_atualizacao_pncp`, `data_publicacao_pncp`, `orgao_nome`, `valor_global`, `item_url`;
- distinct bounded pages in prior Q010 probes.

This search endpoint is a public publisher-owned frontend service, not represented as a documented PNCP integration-manual endpoint. Production therefore treats its shape conservatively and fail-closes on drift.

## Official PCA identity and hydration

The current PNCP Integration Manual documents:

`GET /v1/orgaos/{cnpj}/pca/{ano}/consolidado/unidades`

Live validation returned a list with:
- `cnpj`
- `codigoUnidade`
- `nomeUnidade`
- `anoPca`
- `sequencialPca`
- `numeroControlePNCP`
- `dataPublicacaoPncp`
- `dataAtualizacao`
- `dataAtualizacaoGlobalPCA`
- `razaoSocial`
- quantity/value fields.

Live control on 2026-08-24:
- CNPJ `10648539000105`
- PCA year `2026`
- `sequencialPca=1`
- `numeroControlePNCP=10648539000105-0-000001/2026`
- `codigoUnidade=158137`
- `dataAtualizacao=2026-08-24T18:41:08`
- `valorTotal=132363750.338`

The manual also documents:

`GET /v1/orgaos/{cnpj}/pca/{ano}/{sequencial}/itens`

with optional `categoria`, `pagina`, `tamanhoPagina`.

Live response fields include:
- `cnpj`, `anoPca`, `sequencialPca`, `numeroItem`;
- `categoriaItemPcaid`, `categoriaItemPcaNome`;
- catalog/classification fields;
- `descricao`, quantity, unit and value fields;
- `dataDesejada`;
- procurement group and requesting unit;
- `dataPublicacaoPncp`, `dataInclusao`, `dataAtualizacao`.

## Construction classification

Only publisher-native PCA category IDs are allowed:
- `3` — Obra
- `4` — Serviços de Engenharia
- `8` — Obras e Serviços de Engenharia

No title/description keyword can promote category 1/2 or another category into a construction signal. No CPV is invented.

A prior live control `08241804000194 / 2026 / 1` contained 930 items, including 22 category-8 works/engineering items with structured classification, values and `dataDesejada`. One observed structured example had value around R$17.7m and desired date 2026-12-23.

## Commercial identity

Normalized item identity:

`{numeroControlePNCP}:{numeroItem}`

This preserves the publisher-native PCA identity plus publisher-native item number. `sequencialPca`, unit and classification identifiers remain provenance fields.

## Incremental-safety strategy

The documented `/api/consulta/v1/pca/atualizacao` route was previously tested with bounded date windows but returned HTTP 200 with zero-byte/non-JSON bodies while fresh PCAs were visibly updating. It is not used as the production discovery dependency.

Production uses bounded recent-first search with:
- publisher timestamp cursor;
- overlap window;
- recent-only initial bootstrap;
- hard page bounds;
- required identity/update fields;
- descending-order validation;
- duplicate detection;
- consistent `total` within each scan;
- two independent scans compared before hydration;
- fail-closed behavior if the index drifts or the cutoff is not reached before hard bounds.

PNCP intermittently closed reused HTTP connections during live probing. Production uses fresh/closed connections plus bounded retries for transport errors, 429 and 5xx conditions. Persistent failure aborts the source sync and prevents cursor advancement.

## Signal semantics

The connector emits `PROCUREMENT_PLAN`, not TENDER.

`dataDesejada` maps to `target_date`. It is never disguised as a tender submission deadline.

The connector does not claim lifecycle/tombstone completeness in v1. Aggregate cancellation state may be retained as source metadata, but no lifecycle capability is registered until item-level closure semantics are proven safely.

## Coverage limitation

Initial ingestion is intentionally recent and bounded. The source registry must not claim historical completeness. If the recent backlog exceeds hard bounds, the connector fails closed instead of moving the cursor past unobserved data.

## Production gate

Promotion requires all of the following in the same PR:
- connector and adversarial tests;
- generic Signal persistence (already merged as Q020);
- source registry entry with only proven capabilities;
- explicit runtime opt-in wiring;
- removal of temporary CI live probes;
- exact-head Python and Mobile CI;
- no automatic source activation.