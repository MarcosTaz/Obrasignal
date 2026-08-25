# UK Commercial Intelligence — Forensic Evidence & Product Gap

Decision date: 2026-08-25

## Repository facts

- UK is canonical BUILD priority #7 and is assigned a dedicated UK procurement connector.
- `UK_PROCUREMENT` is registered READY with legal reuse GREEN and machine access VERIFIED.
- `uk_find_tender.py` exists and hydrates Find a Tender OCDS record packages by OCID, emits construction lots, CPV evidence, SME suitability, values, geography and lifecycle actionability.
- `test_uk_find_tender.py` covers active/closed lots, elapsed deadlines, construction filtering, unstable lot identity, cursor semantics, London DST boundary conversion and fail-closed hydration limits.
- Current connector emits only `signal_type=TENDER`. The registry similarly declares only TENDER and omits lifecycle capability despite the connector already producing lifecycle state.

## Material gap

The commercial research established that UK differentiation depends on more than live tenders: pipeline/pre-market signals, awards/suppliers, commercial tools/routes, payment notices and buyer account intelligence. None of those should be claimed as implemented merely because the source can publish them in OCDS.

The current connector deliberately hydrates the compiled procurement state and normalizes the tender object. It does **not** yet normalize awards, contracts, pipeline/pre-market notice semantics, dynamic markets/framework economics, UK8 payments or UK17 payment-compliance metrics.

## Product decision

Do not replace the existing safe tender connector with an over-broad parser. Extend UK lifecycle coverage incrementally behind source-native normalization tests. Preserve OCID as procurement identity but allow successor/restart linkage above the connector because a restarted commercial opportunity can receive a new OCID.

Required next capability sequence:

1. pipeline / planned procurement / preliminary market engagement signal normalization;
2. award + supplier normalization with PPON/Companies House identifiers when source-provided;
3. commercial-tool relationship resolution (framework / dynamic market / DPS); 
4. UK8 supplier payment events and UK17 buyer payment-quality metrics;
5. local-authority non-FTS pre-procurement sources only after the national lifecycle is represented correctly.

## Market sizing discipline

Do not use the broad ~885k construction-SME population as SAM. The official ONS IDBR source is the correct denominator family because it provides VAT/PAYE enterprises by industry and employment size band. Roofing research indicates the premium ICP is a small subset; other priority trades remain UNKNOWN until their source cells are extracted and verified. Procurement-active supplier identity should form a second, behavioural SAM-P filter rather than an assumed adoption percentage.

## Commercial thesis

The UK paid wedge is Commercial Decision Intelligence, not tender alerts. The product must rank buyer accounts/routes and recommended actions using fit, access, timing, competition, payment quality and readiness. Cheap/free tender discovery makes a premium alert-only product strategically weak.

## Evidence status

FACT: UK connector and tests exist in repository.
FACT: current normalized signal type is tender-only.
FACT: source registry currently understates lifecycle capability.
UNKNOWN: complete trade-by-size structural SAM outside already researched roofing.
UNKNOWN: procurement-active SAM-P.
UNKNOWN: willingness-to-pay at £249/£499 until paid pilots.

No revenue forecast should promote any UNKNOWN into a fact.
