"""Canonical international product-scope decision for ObraSignal.

This registry is strategic, not a source-health registry.  Source readiness remains
in source_registry.py.  A technically ready source does not force a market into
active product scope, and sunk implementation cost is deliberately ignored.

Last decision: 2026-08-24
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ScopeStatus = Literal["BUILD", "SHARED", "HOLD", "REMOVE"]


@dataclass(frozen=True)
class MarketScope:
    status: ScopeStatus
    reason: str
    infrastructure: str = ""
    reopen_condition: str = ""
    priority: int | None = None


LEGACY_RESEARCH_MARKETS = 108
LEGACY_CONNECTOR_CANDIDATES = 45
DECISION_UNIVERSE = 135
OFFICIAL_ACTIVE_MARKETS = 45
TARGET_DEDICATED_CONNECTORS = 13

BUILD_ORDER = ['Portugal',
 'Spain',
 'Italy',
 'France',
 'Germany',
 'Switzerland',
 'United Kingdom',
 'Netherlands',
 'Poland',
 'Brazil',
 'Canada',
 'United States',
 'Colombia',
 'Chile']

DEDICATED_CONNECTORS = {'Brazil': 'PNCPConnector',
 'Canada': 'CanadaBuysConnector',
 'Chile': 'MercadoPublicoChileConnector',
 'France': 'BOAMP/DECP',
 'Germany': 'SERVICE_BUND_DE',
 'Italy': 'ANACPVLConnector',
 'Netherlands': 'TenderNedConnector',
 'Poland': 'BZPConnector',
 'Portugal': 'BASEConnector',
 'Spain': 'PLACSPConnector',
 'Switzerland': 'SIMAPConnector',
 'United Kingdom': 'UKProcurementConnector',
 'United States': 'SAMConnector'}

SHARED_FAMILIES = {
    "TED_EFORMS": ('Austria',
 'Belgium',
 'Bulgaria',
 'Croatia',
 'Cyprus',
 'Czech Republic',
 'Denmark',
 'Estonia',
 'Finland',
 'Greece',
 'Hungary',
 'Iceland',
 'Ireland',
 'Latvia',
 'Liechtenstein',
 'Lithuania',
 'Luxembourg',
 'Malta',
 'Norway',
 'Romania',
 'Slovakia',
 'Slovenia',
 'Sweden'),
    "OCDS_API_BULK": ('Dominican Republic',
 'Ecuador',
 'Guatemala',
 'Honduras',
 'Paraguay',
 'Peru',
 'South Africa',
 'Uruguay'),
}

_BUILD = {
    'Portugal': MarketScope("BUILD", 'Elevada relevância local, excelente histórico BASE e mercado já validado; preservar o core é obrigatório.', infrastructure='BASEConnector', priority=1),
    'Spain': MarketScope("BUILD", 'Mercado de obras grande, enorme peso local/sub-threshold e dados nacionais fortes; justifica inteligência específica apesar da competição.', infrastructure='PLACSPConnector', priority=2),
    'Italy': MarketScope("BUILD", 'Decision Index 85, >€54bn/ano de obras públicas e BDNCP/ANAC com lifecycle rico; alto valor por conta.', infrastructure='ANACPVLConnector', priority=3),
    'France': MarketScope("BUILD", 'Grande mercado de construção e combinação BOAMP+DECP com descoberta e histórico fortes.', infrastructure='BOAMP/DECP connector family', priority=4),
    'Germany': MarketScope("BUILD", 'Grande procurement de construção, dados nacionais eForms/OCDS fortes e ARPU elevado.', infrastructure='DÖE/Bekanntmachungsservice connector', priority=5),
    'Switzerland': MarketScope("BUILD", 'SIMAP tem API comercialmente reutilizável, elevada qualidade e ARPU potencial muito alto.', infrastructure='SIMAPConnector', priority=6),
    'United Kingdom': MarketScope("BUILD", 'Dados OCDS de classe mundial, planning notices e ARPU alto justificam competir apesar de incumbentes fortes.', infrastructure='Find a Tender + Contracts Finder connector', priority=7),
    'Netherlands': MarketScope("BUILD", 'TenderNed oferece API oficial forte e mercado suficiente para below-threshold/intelligence dedicado.', infrastructure='TenderNedConnector', priority=8),
    'Poland': MarketScope("BUILD", 'Mercado grande, forte visibilidade below-threshold e webservice oficial; bom equilíbrio escala/dados.', infrastructure='BZPConnector', priority=9),
    'Brazil': MarketScope("BUILD", 'Mercado enorme e PNCP/PCA pode acrescentar pipeline pré-edital nacional; complexidade é justificada pelo upside.', infrastructure='PNCPConnector', priority=10),
    'Canada': MarketScope("BUILD", 'Alto poder de compra, excelente CanadaBuys federal e ARPU elevado; federal-first é economicamente racional.', infrastructure='CanadaBuysConnector', priority=11),
    'United States': MarketScope("BUILD", 'Maior upside absoluto e ARPU elevado; começar SAM federal e não tentar SLED de uma vez.', infrastructure='SAMConnector', priority=12),
    'Colombia': MarketScope("BUILD", 'SECOP/PAA tem dados nacionais excecionalmente ricos; escala suficiente e reutilização via Socrata reduz custo técnico.', infrastructure='SocrataProcurementAdapter + SECOP market config', priority=13),
    'Chile': MarketScope("BUILD", 'API oficial quase real-time e mercado comercial significativo; implementação é relativamente barata para o valor obtido.', infrastructure='MercadoPublicoChileConnector', priority=14),
}

_SHARED = {
    'Austria': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Belgium': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Bulgaria': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Croatia': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Cyprus': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Czech Republic': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Denmark': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Dominican Republic': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='OCDSAPIConnector/OCDSBulkConnector'),
    'Ecuador': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='OCDSAPIConnector/OCDSBulkConnector'),
    'Estonia': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Finland': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Greece': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Guatemala': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='OCDSAPIConnector/OCDSBulkConnector'),
    'Honduras': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='OCDSAPIConnector/OCDSBulkConnector'),
    'Hungary': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Iceland': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Ireland': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Latvia': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Liechtenstein': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Lithuania': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Luxembourg': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Malta': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Norway': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Paraguay': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='OCDSAPIConnector/OCDSBulkConnector'),
    'Peru': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='OCDSAPIConnector/OCDSBulkConnector'),
    'Romania': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Slovakia': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Slovenia': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'South Africa': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='OCDSAPIConnector/OCDSBulkConnector'),
    'Sweden': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='TED/eForms'),
    'Uruguay': MarketScope("SHARED", 'Keep supported without country-specific roadmap work; the common publication/data family carries the market.', infrastructure='OCDSAPIConnector/OCDSBulkConnector'),
}

_HOLD = {
    'Algeria': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando existir uma fonte nacional oficial, automatizável e comercialmente reutilizável com cobertura material.'),
    'Angola': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando existir feed/API oficial reutilizável e cobertura nacional suficiente para justificar localização e GTM.'),
    'Argentina': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando os dados oficiais de CONTRAT.AR forem atuais, completos e machine-readable o suficiente para descoberta em produção.'),
    'Australia': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando a rota machine-readable atual para live ATMs e os direitos de reutilização estiverem formalmente validados.'),
    'Côte d’Ivoire': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando a digitalização nacional produzir uma API/feed oficial reutilizável com cobertura suficiente para não depender de trabalho manual.'),
    'DRC': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando existir procurement nacional digital estável, machine-readable e legalmente reutilizável em escala.'),
    'Egypt': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando houver feed/API nacional oficial e reutilizável para procurement de construção, com cobertura/frescura verificáveis.'),
    'Ethiopia': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando o e-GP expuser dados nacionais machine-readable com direitos de reutilização comercial claros.'),
    'India': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando existir uma API/feed oficial ampla que dispense CAPTCHA/fluxos manuais e permita automação/reutilização comercial.'),
    'Indonesia': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando LKPP oferecer uma rota live de tenders oficialmente suportada e a licença comercial estiver fechada.'),
    'Japan': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando houver cobertura machine-readable suficientemente unificada e uma estratégia de localização/GTM que feche o custo de entrada.'),
    'Kenya': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando a licença comercial estiver GREEN e o OCDS/e-GP tiver completude de itens/documentos próxima do portal humano.'),
    'Mexico': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando ComprasMX tiver uma rota oficial live/incremental estável e o valor federal puder ser entregue sem uma estratégia estatal fragmentada desde o primeiro dia.'),
    'Morocco': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando o Portail Marocain publicar uma API/feed suportado e os direitos de reutilização comercial estiverem fechados.'),
    'New Zealand': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando live procurement machine access e diferenciação comercial forem suficientemente fortes para competir pelas mesmas horas de engenharia dos mercados premium.'),
    'Nigeria': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando NOCOPO provar frescura/completude sustentadas e houver evidência de willingness-to-pay que compense risco de suporte/cobrança.'),
    'Panama': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando a rota canónica de ingestão automatizada estiver fechada e houver evidência de WTP acima do custo de um mercado pequeno/médio.'),
    'Philippines': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando mPhilGEPS/OCDS tiver uma interface pública de produção estável e documentada.'),
    'Rwanda': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir apenas com autorização comercial escrita ou licença que deixe de impor NonCommercial ao feed OCDS.'),
    'Saudi Arabia': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando Etimad oferecer API autorizada de descoberta ampla de tenders, não apenas produtos de contract intelligence.'),
    'Singapore': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando houver uma rota reutilizável para live tenders; awards abertos sozinhos não justificam um mercado de discovery.'),
    'South Korea': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir imediatamente quando existir `KONEPS_SERVICE_KEY` do projeto e o live probe validar paginação, `chgDt`, identity e lifecycle.'),
    'Taiwan': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando a interface nacional de tenders estiver oficialmente documentada para ingestão e reutilização comercial.'),
    'Tanzania': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando houver prova de ARPU/WTP regional suficiente; tecnicamente o OCDS é forte, comercialmente ainda não vence o teste das próximas 100 horas.'),
    'Uganda': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando API/feed e reutilização comercial estiverem ambos provados e houver tração regional paga.'),
    'Ukraine': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir desenvolvimento comercial normal quando risco de guerra/seguro/execução deixar de dominar a capacidade real de contractors estrangeiros entregarem obras.'),
    'United Arab Emirates': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando existir feed/API pública suportada para tender discovery e termos de redistribuição claros.'),
    'Zambia': MarketScope("HOLD", 'Commercial option retained, but zero development is authorized while the reopening condition is false.', reopen_condition='Reabrir quando o endpoint OCDS publicado estiver live/estável e houver evidência de clientes pagantes suficiente para justificar suporte dedicado.'),
}

_REMOVE = {
    'Antigua and Barbuda': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Bahamas': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Barbados': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Belize': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Benin': MarketScope("REMOVE", 'Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.'),
    'Bolivia': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Botswana': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Burkina Faso': MarketScope("REMOVE", 'Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.'),
    'Burundi': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Cabo Verde': MarketScope("REMOVE", 'Não justifica desenvolvimento porque o TAM é muito pequeno, o ARPU provável é baixo e não existe uma rota machine-readable/reutilizável forte que compense suporte local.'),
    'Cameroon': MarketScope("REMOVE", 'Não justifica desenvolvimento porque a fonte disponível exige automação limitada/exports frágeis e o retorno esperado é inferior ao de mercados com APIs robustas.'),
    'Central African Republic': MarketScope("REMOVE", 'Não justifica desenvolvimento porque a capacidade pagante, infraestrutura digital e cobertura procurement são demasiado fracas para competir por recursos de engenharia.'),
    'Chad': MarketScope("REMOVE", 'Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.'),
    'Comoros': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Costa Rica': MarketScope("REMOVE", 'Não justifica desenvolvimento porque o mercado é pequeno, a concorrência local já comprime o preço e uma integração própria perde no teste das próximas 100 horas.'),
    'Cuba': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não há fonte procurement buildable provada e as restrições operacionais/comerciais tornam o retorno incompatível com o roadmap.'),
    'Djibouti': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Dominica': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'El Salvador': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Equatorial Guinea': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Eritrea': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe infraestrutura procurement digital buildable e o retorno comercial plausível é insuficiente.'),
    'Eswatini': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Faroe Islands': MarketScope("REMOVE", 'Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.'),
    'Gabon': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Gambia': MarketScope("REMOVE", 'Não justifica desenvolvimento porque a fonte disponível exige automação limitada/exports frágeis e o retorno esperado é inferior ao de mercados com APIs robustas.'),
    'Ghana': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não foi provada API/feed autorizado nem reutilização comercial, enquanto ARPU e GTM não compensam essa fricção.'),
    'Greenland': MarketScope("REMOVE", 'Não justifica desenvolvimento porque a fonte disponível exige automação limitada/exports frágeis e o retorno esperado é inferior ao de mercados com APIs robustas.'),
    'Grenada': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Guinea': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Guinea-Bissau': MarketScope("REMOVE", 'Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.'),
    'Guyana': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Haiti': MarketScope("REMOVE", 'Não justifica desenvolvimento porque risco operacional extremo, baixa capacidade pagante e ausência de fonte machine-readable tornam o mercado inadequado ao produto agora.'),
    'Jamaica': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Lesotho': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Liberia': MarketScope("REMOVE", 'Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.'),
    'Libya': MarketScope("REMOVE", 'Não justifica desenvolvimento porque risco institucional, cobertura digital insuficiente e baixa previsibilidade comercial anulam o benefício de engenharia.'),
    'Madagascar': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Malawi': MarketScope("REMOVE", 'Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.'),
    'Mali': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Mauritania': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Mauritius': MarketScope("REMOVE", 'Não justifica desenvolvimento porque a escala é pequena e o portal não oferece API/feed público suportado; localização e QA excedem o retorno provável.'),
    'Mozambique': MarketScope("REMOVE", 'Não justifica desenvolvimento porque a escala pagante provável é baixa, a automação oficial é fraca e o custo de manutenção/localização não compete com mercados superiores.'),
    'Namibia': MarketScope("REMOVE", 'Não justifica desenvolvimento porque TAM e número de clientes plausíveis são baixos e a API/reutilização continuam por provar.'),
    'Nicaragua': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Niger': MarketScope("REMOVE", 'Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.'),
    'Republic of Congo': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Saint Kitts and Nevis': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Saint Lucia': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Saint Vincent and the Grenadines': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'São Tomé and Príncipe': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Senegal': MarketScope("REMOVE", 'Não justifica desenvolvimento porque o mercado e ARPU previstos não compensam ausência de uma rota automatizada/reutilizável suficientemente forte.'),
    'Seychelles': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Sierra Leone': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Somalia': MarketScope("REMOVE", 'Não justifica desenvolvimento porque risco operacional, baixa digitalização verificável e ausência de fonte buildable superam largamente o potencial comercial.'),
    'South Sudan': MarketScope("REMOVE", 'Não justifica desenvolvimento porque risco operacional extremo e ausência de infraestrutura procurement machine-readable impedem um produto comercial sustentável.'),
    'Sudan': MarketScope("REMOVE", 'Não justifica desenvolvimento porque conflito/risco operacional e inexistência de fonte buildable tornam qualquer investimento de produto irracional agora.'),
    'Suriname': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Togo': MarketScope("REMOVE", 'Não justifica desenvolvimento porque a reutilização comercial ou automação continua incerta e o potencial económico não é suficiente para pagar essa complexidade.'),
    'Trinidad and Tobago': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
    'Tunisia': MarketScope("REMOVE", 'Não justifica desenvolvimento porque TUNEPS é operacional mas não há API/feed comercialmente reutilizável provado e o poder de compra/ARPU não justifica contornar essa limitação.'),
    'Venezuela': MarketScope("REMOVE", 'Não justifica desenvolvimento porque risco económico/institucional, acesso a dados e capacidade comercial tornam o retorno ajustado ao esforço claramente inferior aos mercados prioritários.'),
    'Zimbabwe': MarketScope("REMOVE", 'Não justifica desenvolvimento porque não existe uma fonte oficial buildable provada e a dimensão/ARPU provável não justifica investigação e manutenção adicionais face aos mercados prioritários.'),
}

MARKET_SCOPE = {**_BUILD, **_SHARED, **_HOLD, **_REMOVE}


def market_scope(country: str) -> MarketScope:
    """Return the canonical scope decision; unknown markets are not active by default."""
    try:
        return MARKET_SCOPE[country]
    except KeyError as exc:
        raise KeyError(f"market is not in the canonical scope registry: {country}") from exc


def active_markets() -> tuple[str, ...]:
    return tuple(sorted(k for k, v in MARKET_SCOPE.items() if v.status in {"BUILD", "SHARED"}))


def development_allowed(country: str) -> bool:
    """Only BUILD markets may receive country-specific connector engineering."""
    return market_scope(country).status == "BUILD"


def scope_counts() -> dict[str, int]:
    return {
        status: sum(1 for value in MARKET_SCOPE.values() if value.status == status)
        for status in ("BUILD", "SHARED", "HOLD", "REMOVE")
    }
