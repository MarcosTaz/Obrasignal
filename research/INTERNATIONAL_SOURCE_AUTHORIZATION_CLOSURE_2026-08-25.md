# ObraSignal — International Source Authorization Closure

**Operational research snapshot only. This is NOT a Master Queue, NOT a source registry, NOT a production activation document.**

## Provenance and safety boundary

- Repository: `MarcosTaz/Obrasignal`
- Exact canonical `main` inspected: `fce51d5b5524e09691f9187f7619ea0166217487`
- Canonical tree: `eac97dee4390ffba831241b7465df9e1e04f2fcc`
- Verified: `2026-08-25`
- Canonical scope remains `market_scope_registry.py`.
- Canonical source readiness remains `source_registry.py`.
- Runtime composition remains `preload.py` + `cors_app.py`.
- No Master Queue mutation.
- No source promotion.
- No production activation.
- No WAF/CAPTCHA/authentication bypass.
- No TLS verification weakening.
- No automatic merge.

## Canonical 135-country primary-state closure

The mutually exclusive current primary states are:

| PRIMARY STATE | COUNT | DECISION |
|---|---:|---|
| `PRODUCTION_ACTIVE` | 26 | Canonical baseline exists and is active; research is not the blocker. |
| `PRODUCTIZABLE_NOW` | 13 | Source is implemented, GREEN/VERIFIED and has a canonical runtime composition path; controlled deployment/activation belongs elsewhere. |
| `IMPLEMENTED_NEEDS_INTEGRATION` | 1 | Dominican Republic; implementation already belongs to PR #197/#225. |
| `NEEDS_MACHINE_ACCESS` | 2 | Peru and Guatemala. |
| `NEEDS_ENDPOINT_CONTRACT` | 2 | Brazil and Honduras. |
| `NEEDS_CREDENTIAL` | 1 | Chile canonical Mercado Público API path. |
| `HOLD` | 28 | Strategic scope remains canonical even where technical code exists. |
| `REMOVE` | 62 | No engineering/research authorization until a later canonical scope reversal. |
| **TOTAL** | **135** | |

### BUILD markets

| COUNTRY | PRIMARY STATE | SOURCE / ID | EXACT REMAINING PROOF OR ACTION |
|---|---|---|---|
| Portugal | `PRODUCTION_ACTIVE` | BASE / `BASE` | None in this cell. |
| Spain | `PRODUCTION_ACTIVE` | PLACSP / `PLACSP` | None in this cell. |
| France | `PRODUCTION_ACTIVE` | BOAMP / `BOAMP` | BOAMP baseline remains active. DECP contract enrichment belongs to PR #230. |
| Italy | `PRODUCTIZABLE_NOW` | ANAC / `IT_ANAC` | Controlled integration/deployment decision only. |
| Germany | `PRODUCTIZABLE_NOW` | DÖE / `SERVICE_BUND_DE` | Controlled integration/deployment decision only. |
| Switzerland | `PRODUCTIZABLE_NOW` | SIMAP / `CH_SIMAP` | Controlled integration/deployment decision only. |
| United Kingdom | `PRODUCTIZABLE_NOW` | Find a Tender + Contracts Finder / `UK_PROCUREMENT` | Controlled integration/deployment decision only. |
| Netherlands | `PRODUCTIZABLE_NOW` | TenderNed / `NL_TENDERNED` | Controlled integration/deployment decision only. |
| Poland | `PRODUCTIZABLE_NOW` | BZP / `PL_BZP` | Controlled integration/deployment decision only. |
| Canada | `PRODUCTIZABLE_NOW` | CanadaBuys / `CA_CANADABUYS` | Controlled integration/deployment decision only. |
| United States | `PRODUCTIZABLE_NOW` | SAM.gov / `US_SAM` | Controlled integration/deployment decision only. |
| Colombia | `PRODUCTIZABLE_NOW` | SECOP / `CO_SECOP` | Controlled integration/deployment decision only. |
| Brazil | `NEEDS_ENDPOINT_CONTRACT` | PNCP/PCA / unregistered candidate | #135 proved `/v1/pca/atualizacao` was not production-usable in its bounded 2026-08-24 probe. Re-run a small official window only when the endpoint returns stable JSON/204 semantics, current data and paging. |
| Chile | `NEEDS_CREDENTIAL` | Mercado Público / `CL_MERCADOPUBLICO` | Obtain a legitimate API ticket, then live-validate paging, identity, update semantics and complete-detail hydration before wiring. |

### SHARED markets

The 23 TED/eForms shared markets — Austria, Belgium, Bulgaria, Croatia, Cyprus, Czech Republic, Denmark, Estonia, Finland, Greece, Hungary, Iceland, Ireland, Latvia, Liechtenstein, Lithuania, Luxembourg, Malta, Norway, Romania, Slovakia, Slovenia and Sweden — are `PRODUCTION_ACTIVE` through canonical TED baseline coverage. National enrichments do not demote that baseline. Finland HILMA remains credential-gated enrichment on PR #181; Luxembourg PMP-LU remains legal-YELLOW/opt-in enrichment.

OCDS/API-bulk shared-family decisions:

| COUNTRY | PRIMARY STATE | EXACT REMAINING PROOF OR ACTION |
|---|---|---|
| Ecuador | `PRODUCTIZABLE_NOW` | Existing `EC_SERCOP` path; no new source research. |
| Paraguay | `PRODUCTIZABLE_NOW` | Existing `PY_DNCP` path; no new source research. |
| South Africa | `PRODUCTIZABLE_NOW` | Existing `ZA_ETENDERS` path; no new source research. |
| Uruguay | `PRODUCTIZABLE_NOW` | Existing `UY_ARCE` path; PAC enrichment/integration ownership is already in #197/#225. |
| Dominican Republic | `IMPLEMENTED_NEEDS_INTEGRATION` | #197 implementation + #225 current-main composition; close sustainable OCDS discovery/detail hydration completeness/economics. |
| Peru | `NEEDS_MACHINE_ACCESS` | #179 official OECE bulk/API probe returned HTTP 403 from hosted runner. Wait for normally permitted machine access; do not bypass. |
| Guatemala | `NEEDS_MACHINE_ACCESS` | Official Guatecompras OCDS route is evidenced, but the current web environment receives HTTP 403. Normal permitted access must exist before implementation. |
| Honduras | `NEEDS_ENDPOINT_CONTRACT` | Rights/schema are strong; one bounded HTTPS Release/Record/Files call must return current 2026 data with stable paging and normal TLS. Current closure probe was not usable (timeout/cache miss). |

### HOLD / REMOVE

All 28 `HOLD` and 62 `REMOVE` entries remain exactly governed by `market_scope_registry.py`. Technical implementation cannot override strategic scope. Important existing evidence does not change that rule: South Korea remains HOLD until `KONEPS_SERVICE_KEY` plus live validation; Taiwan and Zambia remain HOLD despite successful technical evidence in PR #228; Tanzania remains HOLD on economics despite the technical spike; Panama remains HOLD with the #180 TLS gate; UAE remains HOLD; Morocco remains HOLD.

## Decision-changing investigations

### South Korea / KONEPS — `EXTERNAL_ACTION_REQUIRED`, gate narrowed

Official current PPR/data.go.kr evidence now closes the rights/API uncertainty for the registered KONEPS path:

- official REST bid-notice OpenAPI, nationwide and construction-specific;
- free;
- licence scope: no restrictions;
- development and production approval: automatic;
- development traffic: 1,000 calls; production traffic can be increased by registering a use case;
- a service key is still required.

Official path: https://www.data.go.kr/data/15129394/openapi.do

**Exact next proof:** obtain the project key and run the already-defined bounded live test for paging, `chgDt`, identity and lifecycle. Until then the canonical strategic HOLD remains correct.

### Chile / Mercado Público — `EXTERNAL_ACTION_REQUIRED`, rights gate cleared

Current ChileCompra policy states that procurement-procedure information is public and its public access/use is not restricted. Its Datos Abiertos surface explicitly exists to enable reuse for new reports or applications. Protected personal/reserved data remains excluded from this conclusion.

The canonical API path still requires a legitimate ticket. Official help directs the user through the API portal, Chilean `Clave Única`, RUT confirmation and a `Solicitud de Ticket` request.

Official evidence:
- https://www.chilecompra.cl/terminos-y-condiciones-de-uso/
- https://ayuda.mercadopublico.cl/preguntasfrecuentes/articulo/?id=KA-01967

**Exact next proof:** legitimate API ticket + live contract test. A public bulk/OCDS same-publisher transport can be evaluated as a fallback, but must not create a second source identity.

### Peru / OECE OCDS — `GATE_NARROWED`, access still blocked

OECE currently exposes OCDS downloads plus Release/Record/Files API documentation. Official OECE material states that the data are provided without restrictions to promote interoperability and innovative projects. This materially strengthens the reuse evidence, but does not erase the source-side access fact captured by #179: the hosted runner received HTTP 403.

Official evidence:
- https://www.gob.pe/52005-acceder-al-portal-de-contrataciones-abiertas-de-la-compra-publica-ocds
- https://www.gob.pe/institucion/oece/noticias/884163-osce-implementa-el-estandar-de-datos-para-las-contrataciones-abiertas-ocds

**Decision:** `NEEDS_MACHINE_ACCESS`. No connector and no bypass.

### Honduras / ONCAE-SEFIN OCDS — `GATE_NARROWED`

The official API manual documents REST GET Release, Record and bulk Files services, page-based navigation, OCDS lifecycle stages from planning through implementation, and JSON responses. The portal carries a Creative Commons Attribution 4.0 licence. This clears the legal/schema research blocker.

Official evidence:
- https://contratacionesabiertas.gob.hn/manual_api/
- https://contratacionesabiertas.gob.hn/servicio/

The documented examples are HTTP URLs while the portal itself is HTTPS. A bounded HTTPS attempt in this closure did not yield a usable data response (timeout/cache miss).

**Decision:** `NEEDS_ENDPOINT_CONTRACT`, not implementation-authorized yet. One clean secure/current live proof can move it to shared-OCDS implementation.

### Brazil / PNCP-PCA — `GATE_CONFIRMED`

The current PNCP officially exposes Dados Abertos/APIs without login for query access, explicitly including use by companies and downloading/manipulating data in applications. This removes credential/public-machine-access uncertainty from the primary blocker.

Official evidence:
- https://www.gov.br/pncp/pt-br/acesso-a-informacao/dados-abertos
- https://www.gov.br/pncp/pt-br/pncp/manuais

PR #135 already proved the exact implementation-critical problem: the global PCA update route existed, but the bounded date probes timed out or returned HTTP 200 with empty/non-JSON bodies. No production-usable date form was proven.

**Decision:** `NEEDS_ENDPOINT_CONTRACT`. Do not write/promote the PNCP adapter until that route behaves deterministically. Exact commercial redistribution wording should still be retained as a production legal check; open browser access alone is not treated as commercial authorization.

### Guatemala / Guatecompras OCDS — `GATE_NARROWED`

Official government evidence establishes the Guatecompras OCDS programme and Creative-Commons-style reuse evidence for MINFIN open datasets, but the current OCDS portal returned HTTP 403 in this environment.

**Decision:** `NEEDS_MACHINE_ACCESS`. No access-control circumvention. Exact dataset-licence linkage and current endpoint/freshness are secondary proofs after normal access exists.

### Qatar / Ashghal candidate — `IMPLEMENTATION_NOT_JUSTIFIED` without written permission

Ashghal's own Terms & Conditions protect site content and grant only a personal-use licence; they prohibit republication, distribution, sale and derivative works. This is incompatible with ObraSignal commercial storage/redistribution unless Ashghal gives written permission or a source-specific open-data licence supersedes those terms.

Official terms: https://www.ashghal.gov.qa/en/Pages/TermsConditions.aspx

**Handoff:** PR #235 owns the existing MENA implementation. Do not duplicate the adapter. Technical live success does not authorize production.

### UAE / MoF DPP candidate — `GATE_NARROWED`

The UAE Ministry of Finance has an explicit open-data policy requiring machine-readable, free and unrestricted access for datasets that the Ministry formally classifies as open data. The unresolved fact is narrower: the `Current Business Opportunities` tender listing used by the candidate has not been proven to be one of those classified open datasets.

Official policy: https://mof.gov.ae/en/open-data/open-data-policy/

**Decision:** legal remains YELLOW for that exact source until dataset classification/licence linkage or written permission is obtained. Handoff remains PR #235.

### Luxembourg / PMP-LU — `GATE_CONFIRMED`, baseline unaffected

`PMP-LU` remains `legal_reuse=YELLOW` and opt-in in the canonical source registry. No authoritative commercial storage/redistribution grant was closed in this cell. This affects only national RSS enrichment; Luxembourg's canonical TED baseline remains `PRODUCTION_ACTIVE`.

## External action queue

| COUNTRY | PROVIDER | ACTION | WHAT TO REQUEST | WHAT IT UNLOCKS | COST / RISK |
|---|---|---|---|---|---|
| South Korea | PPR / data.go.kr | `NEEDED_CREDENTIAL` | Project service key for dataset 15129394 | KONEPS live gate and possible strategic reopen | Free / low risk |
| Chile | Dirección ChileCompra | `NEEDED_CREDENTIAL` | Mercado Público API ticket for legitimate project use | Canonical adapter live validation | Fee not evidenced / medium eligibility-evolution risk |
| Finland | HILMA AVP | `NEEDED_CREDENTIAL` | AVP read subscription key | Optional national works + plan enrichment on #181 | Baseline Finland unaffected |
| Qatar | Ashghal | `NEEDED_WRITTEN_PERMISSION` | Commercial storage/republication/derivative-use permission for tender data | Only path to a lawful QA candidate under current terms | High legal risk |
| UAE | Ministry of Finance | `NEEDED_WRITTEN_PERMISSION` or dataset-classification confirmation | Confirm the exact tender listing is open data and commercially reusable/redistributable | Candidate legal YELLOW -> GREEN if confirmed | Medium risk |
| Luxembourg | Portail des marchés publics | `NEEDED_WRITTEN_PERMISSION` / terms confirmation | Explicit reuse/storage/redistribution terms for RSS content | Optional national RSS enrichment | Low product risk because TED baseline is active |

## Existing-owner handoffs / supersession

- **PR #225 / #197:** Dominican Republic + Uruguay consolidated LATAM path. Do not duplicate overlapping adapters.
- **PR #230:** France DECP contract enrichment owner.
- **PR #228:** Taiwan + Zambia technical evidence owner; strategic HOLD remains authoritative.
- **PR #235:** Qatar/Israel/Oman/UAE rights-gated MENA implementation owner. Apply legal findings there; do not fork runtime/source identities.
- **PR #181:** Finland HILMA implementation owner; only credential/live proof remains for that enrichment.
- **PR #179:** Peru access-gate evidence. Prefer shared OCDS infrastructure only after permitted access clears.
- **PR #180:** Panama TLS-gate evidence. Never use `verify=False` or custom trust bypass.
- **PR #135:** Brazil PNCP/PCA diagnostic. Its failed/empty live route is a gate, not an invitation to guess request formats.

## Ready-for-implementation queue

No newly researched unowned source is fully implementation-authorized at this exact head.

The closest is **Honduras**: one legitimate HTTPS/current-data proof can authorize the smallest shared-OCDS implementation. Brazil still lacks a stable endpoint contract; Peru and Guatemala still lack normal machine access; Chile still lacks the legitimate API credential. Dominican implementation already has an owner.

The existing current-main `ready` sources that are wired and GREEN/VERIFIED are deployment/integration work, not new research work: `SERVICE_BUND_DE`, `CH_SIMAP`, `IT_ANAC`, `UK_PROCUREMENT`, `NL_TENDERNED`, `PL_BZP`, `EC_SERCOP`, `PY_DNCP`, `ZA_ETENDERS`, `UY_ARCE`, `CO_SECOP`, `US_SAM`, `CA_CANADABUYS`.

## Justified quiescence for this closure cell

Every high-value unresolved source is now bounded by a genuine external or source-side proof:

1. legitimate credential or written permission;
2. source-side 403/TLS/access recovery;
3. bounded live endpoint-contract proof that cannot be fabricated from documentation;
4. production-volume completeness/economics inside an existing owner PR;
5. canonical strategic HOLD/REMOVE reopen decision outside this cell.

Researching lower-value `REMOVE` markets now would violate value-of-information and market-scope governance rather than advance shipping.

**NO MERGE. NO MASTER QUEUE PROMOTION. NO PRODUCTION ACTIVATION.**