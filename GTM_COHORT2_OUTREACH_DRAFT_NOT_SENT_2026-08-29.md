# ObraSignal GTM — Cohort 2 outreach experiment — NOT SENT — 2026-08-29

## Status

`PREPARED / NOT_SENT / OWNER-COMMUNICATION_BOUNDARY / NO_DEMAND_CLAIM`

This copy is deliberately designed to test the two risks exposed by Cohort 1: whether the prospect actually performs recurring tender discovery/triage, and whether the ObraSignal proposition is immediately understandable.

## Default Portuguese message

**Assunto:** Como fazem hoje a triagem de concursos de obra?

Olá,

Vi que a vossa empresa participa em contratos/concursos públicos na área de instalações e obra técnica.

Estou a testar a ObraSignal para uma tarefa muito específica: reduzir o tempo gasto a encontrar e filtrar concursos antes de decidir quais merecem análise para proposta.

Em vez de mostrar uma lista genérica, configuramos o perfil real da empresa e entregamos uma shortlist pequena, com a razão de cada oportunidade poder — ou não — encaixar no vosso trabalho.

Queria validar primeiro uma coisa simples: **a vossa equipa perde tempo de forma recorrente a procurar e fazer a primeira triagem de concursos, ou esse processo já está resolvido de outra forma?**

Se for um problema real, posso preparar uma amostra curta com oportunidades atuais para avaliarem sem compromisso.

Cumprimentos,
Marcos
ObraSignal

## Why this version differs from Cohort 1

- It begins from observed procurement participation rather than broad sector fit.
- It names one workflow: finding and first-triaging tenders before proposal work.
- It asks the prospect to confirm or reject the problem before selling a pilot.
- It explains what the product does in operational terms: company profile → small shortlist → explanation of fit.
- It makes “our process is already solved” a useful answer rather than treating every non-positive response as noise.
- It avoids unverified ROI, savings, win-rate, revenue or automation claims.

## Experiment coding

Each eventual response should be classified without optimism:

- `PAIN_CONFIRMED`
- `PAIN_DENIED`
- `PROCESS_OUTSOURCED`
- `PROCESS_RELATIONSHIP_LED`
- `PROCESS_PORTAL_LED_ALREADY_SOLVED`
- `MESSAGE_UNCLEAR`
- `WRONG_RECIPIENT`
- `WILL_TEST`
- `NOT_INTERESTED`
- `NO_RESPONSE`

A positive reply is not a pilot. A sample request is not willingness to pay. A useful shortlist is not revenue won.

## First-value experiment if prospect agrees

1. Capture the company's actual categories, geography, contract-size range and exclusions.
2. Produce a bounded shortlist of current opportunities from traceable sources.
3. Show why each item was included and any uncertainty.
4. Ask the prospect to classify each item: irrelevant / worth opening / worth investigating / likely bid.
5. Record time required and whether the shortlist changed a real work decision.
6. Ask whether they would want the same outcome repeatedly and under what commercial model.

The candidate first-value event is: **the prospect judges at least one previously untriaged surfaced opportunity useful enough to investigate or assign, with traceable source evidence.** This remains a hypothesis until observed with a real user.
