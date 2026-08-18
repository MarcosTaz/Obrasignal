# ObraSignal — Perfil da Empresa

## Objetivo
Permitir que uma empresa descreva o que faz em linguagem normal e transformar essa descrição num radar comercial europeu sem exigir conhecimento de CPV.

## Fluxo
1. Utilizador escreve a atividade.
2. ObraSignal deriva sinais de procura e famílias CPV.
3. Utilizador confirma/edita mercados, valores e exclusões.
4. Guardar através de `POST /api/v1/profile`.
5. Nova sincronização aplica o perfil ao scoring.
6. Oportunidades são classificadas por relevância individual.

## UX
- Campo principal: “O que faz a sua empresa?”
- Mercados: Portugal, Espanha, França, Bélgica, Luxemburgo, Europa.
- Valor mínimo e máximo opcionais.
- Exclusões em linguagem normal.
- Pré-visualização antes de guardar.
- Mostrar “sinais de pesquisa” e “famílias CPV” como informação, não como obrigação.
- Nunca pedir ao utilizador que introduza CPV manualmente para o caso normal.

## Estados de score
- 90–100: ALERTA MÁXIMO
- 75–89: ALERTA
- 60–74: NO RADAR
- 0–59: BAIXA PRIORIDADE

## Princípios
- O score global nunca é destruído pelo perfil.
- O score personalizado deve explicar os principais fatores positivos e negativos.
- O mesmo procedimento publicado em várias fontes deve ser deduplicado antes do alerta.
- A interface deve abrir a fonte oficial original.
- “Quase em tempo real” significa o mais rapidamente possível depois de a fonte disponibilizar o anúncio; não prometer instantaneidade quando a fonte não a oferece.

## Contrato API
`GET /api/v1/profile` devolve o perfil atual.
`POST /api/v1/profile` aceita `name`, `activity`, `keywords`, `countries`, `cpv_prefixes`, `min_value`, `max_value` e `exclude_keywords`.
