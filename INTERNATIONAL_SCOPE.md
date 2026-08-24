# ObraSignal — International Product Scope

**Canonical decision date:** 2026-08-24  
**Policy:** commercial return beats geographic coverage. Sunk connector work does not protect a market.

## Executive decision

- Legacy research universe: **108 markets**.
- Legacy connector backlog: **45 connector candidates**.
- Corrected decision universe: **135 reviewed jurisdictions** because the legacy 108 omitted several core/strategic markets and some zero-connector TED/EEA coverage.
- Official active product coverage: **45 markets = 14 BUILD + 31 SHARED**.
- Frozen option set: **28 HOLD**.
- Removed from active product scope: **62 REMOVE**.
- Target country-specific dedicated connectors: **13**; Colombia remains BUILD through the common Socrata family.
- Legacy connector candidates retired from dedicated active development: **32 / 45 (71.1%)**.
- Estimated engineering/maintenance load reduction: **55–65%**. This is an effort range, not a count identity, because the retained US/Brazil/Canada connectors are heavier than an average retired connector.
- Evidence-weighted commercial proxy retained as BUILD+SHARED+HOLD across the 64 commercially scored markets: **96.6%**.
- Among scored markets not frozen by a HOLD gate, BUILD+SHARED captures **95.2%** of the proxy left after removals.

Commercial proxy used only for scope comparison: `Decision Index × Construction Opportunity × ARPU Potential × GTM Feasibility`. It is not TAM and must never be marketed as revenue forecast.

## Engineering rule

Country-specific connector engineering is allowed **only** for `BUILD`. `SHARED` may receive common-family work and market configuration, never a bespoke connector roadmap. `HOLD` receives zero development until its explicit reopen condition is true. `REMOVE` receives no research or engineering unless an objective market/source change creates a new case.

## BUILD NOW

| Priority | Market | Commercial potential | Data | Connector / family | Decision |
|---:|---|---|---|---|---|
| 1 | Portugal | DI 75; construction 3/5; ARPU 3/5 | readiness 5/5 | BASEConnector | Elevada relevância local, excelente histórico BASE e mercado já validado; preservar o core é obrigatório. |
| 2 | Spain | DI 75; construction 4/5; ARPU 3/5 | readiness 5/5 | PLACSPConnector | Mercado de obras grande, enorme peso local/sub-threshold e dados nacionais fortes; justifica inteligência específica apesar da competição. |
| 3 | Italy | DI 85; construction 5/5; ARPU 4/5 | readiness 5/5 | ANACPVLConnector | Decision Index 85, >€54bn/ano de obras públicas e BDNCP/ANAC com lifecycle rico; alto valor por conta. |
| 4 | France | DI 80; construction 5/5; ARPU 4/5 | readiness 5/5 | BOAMP/DECP connector family | Grande mercado de construção e combinação BOAMP+DECP com descoberta e histórico fortes. |
| 5 | Germany | DI 80; construction 5/5; ARPU 5/5 | readiness 5/5 | DÖE/Bekanntmachungsservice connector | Grande procurement de construção, dados nacionais eForms/OCDS fortes e ARPU elevado. |
| 6 | Switzerland | DI 75; construction 4/5; ARPU 5/5 | readiness 5/5 | SIMAPConnector | SIMAP tem API comercialmente reutilizável, elevada qualidade e ARPU potencial muito alto. |
| 7 | United Kingdom | DI 85; construction 5/5; ARPU 5/5 | readiness 5/5 | Find a Tender + Contracts Finder connector | Dados OCDS de classe mundial, planning notices e ARPU alto justificam competir apesar de incumbentes fortes. |
| 8 | Netherlands | DI 75; construction 4/5; ARPU 4/5 | readiness 5/5 | TenderNedConnector | TenderNed oferece API oficial forte e mercado suficiente para below-threshold/intelligence dedicado. |
| 9 | Poland | DI 80; construction 5/5; ARPU 4/5 | readiness 5/5 | BZPConnector | Mercado grande, forte visibilidade below-threshold e webservice oficial; bom equilíbrio escala/dados. |
| 10 | Brazil | DI 80; construction 5/5; ARPU 4/5 | readiness 4/5 | PNCPConnector | Mercado enorme e PNCP/PCA pode acrescentar pipeline pré-edital nacional; complexidade é justificada pelo upside. |
| 11 | Canada | DI 80; construction 5/5; ARPU 5/5 | readiness 4/5 | CanadaBuysConnector | Alto poder de compra, excelente CanadaBuys federal e ARPU elevado; federal-first é economicamente racional. |
| 12 | United States | DI 75; construction 5/5; ARPU 5/5 | readiness 4/5 | SAMConnector | Maior upside absoluto e ARPU elevado; começar SAM federal e não tentar SLED de uma vez. |
| 13 | Colombia | DI 80; construction 4/5; ARPU 3/5 | readiness 5/5 | SocrataProcurementAdapter + SECOP market config | SECOP/PAA tem dados nacionais excecionalmente ricos; escala suficiente e reutilização via Socrata reduz custo técnico. |
| 14 | Chile | DI 75; construction 4/5; ARPU 3/5 | readiness 5/5 | MercadoPublicoChileConnector | API oficial quase real-time e mercado comercial significativo; implementação é relativamente barata para o valor obtido. |

### Remaining BUILD implementation order

Most European BUILD connectors already exist in the production registry. The next missing/unfinished market implementations are:

1. **Brazil — PNCP**: resume with tiny global-PCA update windows and fail-closed health logic; do not trust the global update route until JSON/date semantics are proven live.
2. **Canada — CanadaBuys**: federal-first; do not expand into provincial fragmentation until federal product value is proven.
3. **United States — SAM.gov**: federal opportunities first; awards enrichment second; SLED is a later source family, not part of the initial connector.
4. **Chile — Mercado Público**: official API/ticket flow; preserve native taxonomy and lifecycle, avoid creating a country-specific architecture where a generic REST layer suffices.

South Korea is intentionally **not** in this list while the project service key is absent; it is HOLD even though its connector code has been prebuilt.

## SHARED COVERAGE

These markets remain supported, but a bespoke country connector is not justified.

### TED / eForms family

`TEDConnector + EFormsNoticeNormalizer`; supported scope is the procurement published through TED/eForms. Existing country-specific adapters for some of these markets are optional enrichment and must not create a new feature roadmap merely because the code already exists.

Austria, Belgium, Bulgaria, Croatia, Cyprus, Czech Republic, Denmark, Estonia, Finland, Greece, Hungary, Iceland, Ireland, Latvia, Liechtenstein, Lithuania, Luxembourg, Malta, Norway, Romania, Slovakia, Slovenia, Sweden.

### OCDS API / bulk family

`OCDSAPIConnector + OCDSBulkConnector + market config`; no bespoke connector unless a later paid-demand case proves that the common family cannot deliver the required product depth.

Dominican Republic, Ecuador, Guatemala, Honduras, Paraguay, Peru, South Africa, Uruguay.

## HOLD — zero development now

- **Algeria:** Reabrir quando existir uma fonte nacional oficial, automatizável e comercialmente reutilizável com cobertura material.
- **Angola:** Reabrir quando existir feed/API oficial reutilizável e cobertura nacional suficiente para justificar localização e GTM.
- **Argentina:** Reabrir quando os dados oficiais de CONTRAT.AR forem atuais, completos e machine-readable o suficiente para descoberta em produção.
- **Australia:** Reabrir quando a rota machine-readable atual para live ATMs e os direitos de reutilização estiverem formalmente validados.
- **Côte d’Ivoire:** Reabrir quando a digitalização nacional produzir uma API/feed oficial reutilizável com cobertura suficiente para não depender de trabalho manual.
- **DRC:** Reabrir quando existir procurement nacional digital estável, machine-readable e legalmente reutilizável em escala.
- **Egypt:** Reabrir quando houver feed/API nacional oficial e reutilizável para procurement de construção, com cobertura/frescura verificáveis.
- **Ethiopia:** Reabrir quando o e-GP expuser dados nacionais machine-readable com direitos de reutilização comercial claros.
- **India:** Reabrir quando existir uma API/feed oficial ampla que dispense CAPTCHA/fluxos manuais e permita automação/reutilização comercial.
- **Indonesia:** Reabrir quando LKPP oferecer uma rota live de tenders oficialmente suportada e a licença comercial estiver fechada.
- **Japan:** Reabrir quando houver cobertura machine-readable suficientemente unificada e uma estratégia de localização/GTM que feche o custo de entrada.
- **Kenya:** Reabrir quando a licença comercial estiver GREEN e o OCDS/e-GP tiver completude de itens/documentos próxima do portal humano.
- **Mexico:** Reabrir quando ComprasMX tiver uma rota oficial live/incremental estável e o valor federal puder ser entregue sem uma estratégia estatal fragmentada desde o primeiro dia.
- **Morocco:** Reabrir quando o Portail Marocain publicar uma API/feed suportado e os direitos de reutilização comercial estiverem fechados.
- **New Zealand:** Reabrir quando live procurement machine access e diferenciação comercial forem suficientemente fortes para competir pelas mesmas horas de engenharia dos mercados premium.
- **Nigeria:** Reabrir quando NOCOPO provar frescura/completude sustentadas e houver evidência de willingness-to-pay que compense risco de suporte/cobrança.
- **Panama:** Reabrir quando a rota canónica de ingestão automatizada estiver fechada e houver evidência de WTP acima do custo de um mercado pequeno/médio.
- **Philippines:** Reabrir quando mPhilGEPS/OCDS tiver uma interface pública de produção estável e documentada.
- **Rwanda:** Reabrir apenas com autorização comercial escrita ou licença que deixe de impor NonCommercial ao feed OCDS.
- **Saudi Arabia:** Reabrir quando Etimad oferecer API autorizada de descoberta ampla de tenders, não apenas produtos de contract intelligence.
- **Singapore:** Reabrir quando houver uma rota reutilizável para live tenders; awards abertos sozinhos não justificam um mercado de discovery.
- **South Korea:** Reabrir imediatamente quando existir `KONEPS_SERVICE_KEY` do projeto e o live probe validar paginação, `chgDt`, identity e lifecycle.
- **Taiwan:** Reabrir quando a interface nacional de tenders estiver oficialmente documentada para ingestão e reutilização comercial.
- **Tanzania:** Reabrir quando houver prova de ARPU/WTP regional suficiente; tecnicamente o OCDS é forte, comercialmente ainda não vence o teste das próximas 100 horas.
- **Uganda:** Reabrir quando API/feed e reutilização comercial estiverem ambos provados e houver tração regional paga.
- **Ukraine:** Reabrir desenvolvimento comercial normal quando risco de guerra/seguro/execução deixar de dominar a capacidade real de contractors estrangeiros entregarem obras.
- **United Arab Emirates:** Reabrir quando existir feed/API pública suportada para tender discovery e termos de redistribuição claros.
- **Zambia:** Reabrir quando o endpoint OCDS publicado estiver live/estável e houver evidência de clientes pagantes suficiente para justificar suporte dedicado.

## REMOVE FROM ACTIVE PRODUCT SCOPE

- **Antigua and Barbuda:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Bahamas:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Barbados:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Belize:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Benin:** Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.
- **Bolivia:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Botswana:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Burkina Faso:** Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.
- **Burundi:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Cabo Verde:** Não justifica desenvolvimento porque o TAM é muito pequeno, o ARPU provável é baixo e não existe uma rota machine-readable/reutilizável forte que compense suporte local.
- **Cameroon:** Não justifica desenvolvimento porque a fonte disponível exige automação limitada/exports frágeis e o retorno esperado é inferior ao de mercados com APIs robustas.
- **Central African Republic:** Não justifica desenvolvimento porque a capacidade pagante, infraestrutura digital e cobertura procurement são demasiado fracas para competir por recursos de engenharia.
- **Chad:** Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.
- **Comoros:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Costa Rica:** Não justifica desenvolvimento porque o mercado é pequeno, a concorrência local já comprime o preço e uma integração própria perde no teste das próximas 100 horas.
- **Cuba:** Não justifica desenvolvimento porque não há fonte procurement buildable provada e as restrições operacionais/comerciais tornam o retorno incompatível com o roadmap.
- **Djibouti:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Dominica:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **El Salvador:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Equatorial Guinea:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Eritrea:** Não justifica desenvolvimento porque não existe infraestrutura procurement digital buildable e o retorno comercial plausível é insuficiente.
- **Eswatini:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Faroe Islands:** Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.
- **Gabon:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Gambia:** Não justifica desenvolvimento porque a fonte disponível exige automação limitada/exports frágeis e o retorno esperado é inferior ao de mercados com APIs robustas.
- **Ghana:** Não justifica desenvolvimento porque não foi provada API/feed autorizado nem reutilização comercial, enquanto ARPU e GTM não compensam essa fricção.
- **Greenland:** Não justifica desenvolvimento porque a fonte disponível exige automação limitada/exports frágeis e o retorno esperado é inferior ao de mercados com APIs robustas.
- **Grenada:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Guinea:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Guinea-Bissau:** Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.
- **Guyana:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Haiti:** Não justifica desenvolvimento porque risco operacional extremo, baixa capacidade pagante e ausência de fonte machine-readable tornam o mercado inadequado ao produto agora.
- **Jamaica:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Lesotho:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Liberia:** Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.
- **Libya:** Não justifica desenvolvimento porque risco institucional, cobertura digital insuficiente e baixa previsibilidade comercial anulam o benefício de engenharia.
- **Madagascar:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Malawi:** Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.
- **Mali:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Mauritania:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Mauritius:** Não justifica desenvolvimento porque a escala é pequena e o portal não oferece API/feed público suportado; localização e QA excedem o retorno provável.
- **Mozambique:** Não justifica desenvolvimento porque a escala pagante provável é baixa, a automação oficial é fraca e o custo de manutenção/localização não compete com mercados superiores.
- **Namibia:** Não justifica desenvolvimento porque TAM e número de clientes plausíveis são baixos e a API/reutilização continuam por provar.
- **Nicaragua:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Niger:** Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.
- **Republic of Congo:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Saint Kitts and Nevis:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Saint Lucia:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Saint Vincent and the Grenadines:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **São Tomé and Príncipe:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Senegal:** Não justifica desenvolvimento porque o mercado e ARPU previstos não compensam ausência de uma rota automatizada/reutilizável suficientemente forte.
- **Seychelles:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Sierra Leone:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Somalia:** Não justifica desenvolvimento porque risco operacional, baixa digitalização verificável e ausência de fonte buildable superam largamente o potencial comercial.
- **South Sudan:** Não justifica desenvolvimento porque risco operacional extremo e ausência de infraestrutura procurement machine-readable impedem um produto comercial sustentável.
- **Sudan:** Não justifica desenvolvimento porque conflito/risco operacional e inexistência de fonte buildable tornam qualquer investimento de produto irracional agora.
- **Suriname:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Togo:** Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.
- **Trinidad and Tobago:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.
- **Tunisia:** Não justifica desenvolvimento porque TUNEPS é operacional mas não há API/feed comercialmente reutilizável provado e o poder de compra/ARPU não justifica contornar essa limitação.
- **Venezuela:** Não justifica desenvolvimento porque risco económico/institucional, acesso a dados e capacidade comercial tornam o retorno ajustado ao esforço claramente inferior aos mercados prioritários.
- **Zimbabwe:** Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.

## Quantification

### BEFORE

- 108 legacy research markets.
- 45 connector candidates.
- Complexity: country-by-country expansion with many markets that were only WATCH/PREPARE and no credible commercial justification.

### AFTER

- 14 BUILD.
- 31 SHARED.
- 28 HOLD.
- 62 REMOVE.
- **45 official active markets (BUILD + SHARED).**
- 13 target dedicated country connectors.
- 32 of 45 legacy connector candidates removed from dedicated active development (**71.1%**).
- Estimated ongoing engineering/maintenance reduction: **55–65%**, medium confidence.
- Evidence-weighted strategic commercial option retained: **96.6%** across the 64 scored markets; active scope captures **95.2%** of the comparable proxy among markets not blocked in HOLD.

## Rebase outcome

**Official ObraSignal active international coverage is now 45 markets.**

The number 108 is retained only as a historical research-universe baseline. It must not be used as a product target or KPI.

Future market additions require evidence strong enough to displace work in an existing BUILD market under the 100-hour substitution test.
