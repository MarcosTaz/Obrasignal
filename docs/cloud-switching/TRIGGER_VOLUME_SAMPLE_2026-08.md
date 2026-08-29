# EU Cloud Switching — Public Trigger Volume Sample — August 2026

Snapshot date: 2026-08-29
Purpose: test whether public procurement/market-dialogue events can plausibly supply ~10 **challengeable decision events/month** for customer acquisition.

This is a directional public-source sample, not an exhaustive TED/HILMA/national-portal census. The counting unit is one buyer decision event, not one notice/revision/source. A VMware renewal is **not** automatically counted as a switching decision.

## Conservative event sample

| # | Buyer / event | Publication | Deadline / dialogue close | Public evidence | Decision-event classification | Counts as clearly challengeable? |
|---|---|---|---|---|---|---|
| 1 | Alcaldía de Torre Pacheco — supply/install/commission server virtualization platform | 2026-08-17 | 2026-09-21 | EU Publications Office procurement `90c11215-946e-49c9-9313-d5dc76059f08` | virtualization-platform procurement; migration/replacement possibility not explicit in summary | NO — insufficient switching evidence |
| 2 | Landratsamt Weilheim-Schongau — Broadcom + Omnissa software licences | 2026-08-04 | 2026-09-03 | EU Publications Office procurement `7b19075c-291c-49b9-9298-dc13e6ed0f96` | existing Broadcom/Omnissa environment; licence procurement | NO — incumbent procurement |
| 3 | Malta Information Technology Agency — VMware subscription licences T074/26 | 2026-08 | live at snapshot | Malta eTenders CfT `T074/26` | three-year VMware subscription, direct Broadcom support | NO — incumbent VMware procurement |
| 4 | Autoridade Tributária e Aduaneira (Portugal) — infrastructure supporting VMware and other systems | 2026-08-17 | 2026-09-12 | DR announcement 20873/2026; EU procurement `5b85c611-b628-4a33-959b-845d7ef3c471` | infrastructure procurement around existing VMware solution | NO — switching not explicit |
| 5 | VTT Finland — VMware licences + Red Hat support | 2026-08-11 | 2026-09-09 | EU Publications Office procurement `e1182426-d523-4700-ac11-fa5b85b4f7b8` | licence/support purchase | NO — switching not explicit |
| 6 | Landkreis Coburg — renewal of virtualization platform/storage, hardware + migration | 2026-08-13 | 2026-08-31 | EU Publications Office procurement `78ff297d-8f8f-40b7-8818-e9f9742a8955` | platform renewal plus migration services | YES — replacement/migration decision observable |
| 7 | IEFP Portugal — 12-month VMware licensing | 2026-08-06 | per procedure | Diário da República announcement 20182/2026 | VMware licence procurement | NO — incumbent renewal |
| 8 | Município de Oeiras — VMware vSphere Foundation licences | 2026-08-04 | per procedure | Diário da República announcement 19964/2026 | VMware licence rental | NO — incumbent procurement |
| 9 | Central IT Center, Poland — VMware **or equivalent** subscriptions + support | 2026-08-19 | 2026-08-26 | notice 2026/S 159-573563; public procurement summary | equivalent explicitly admissible | YES — competing platform decision can be challenged |
| 10 | LapIT Oy, Finland — market dialogue / RFI for VMware by Broadcom **or similar licences** | 2026-08-22 | 2026-08-28 | HILMA market-survey notice 2026-055290 | pre-tender market dialogue and alternatives explicit | YES — early dialogue / alternative decision |
| 11 | Universitätsklinikum Heidelberg — VMware Cloud Foundation licences + implementation | 2026-08-14 | 2026-09-14 | German public-procurement listing | VCF purchase with licence option comparison; alternatives to VMware not established | NO — switching not proven |
| 12 | Poland — framework agreement for VMware **or equivalent** software for common courts | 2026-08-26 | 2026-09-24 | public tender index snapshot 2026-08-26 | equivalent software explicitly admitted | YES — platform competition observable |
| 13 | Germany — procurement described as virtualization platform replacing existing VMware licence infrastructure | 2026-08-13 | 2026-09-02 | public tender index snapshot 2026-08-13 | replacement of VMware explicitly stated | YES — direct switching decision |

## De-duplication / classification result

- Distinct buyer decision events sampled: **13**.
- Clearly challengeable under a conservative text-only rule: **5**.
- Incumbent/renewal/infrastructure events not counted as challengeable without stronger evidence: **8**.
- Raw-event volume must therefore **not** be represented as switching-opportunity volume.

The 5 challengeable events are:

1. Landkreis Coburg — platform renewal + migration;
2. Central IT Center Poland — VMware or equivalent;
3. LapIT Oy — pre-tender market dialogue for VMware or similar;
4. Polish common-courts framework — VMware or equivalent;
5. German replacement of existing VMware licence infrastructure.

## Interpretation

The current sample **does not yet prove** the working target of ~10 challengeable public trigger-events per month.

It does prove that:

- public procurement produces frequent VMware/virtualization events;
- naive keyword counting would materially overstate acquisition volume;
- replacement, migration, `or equivalent`, and pre-tender market-dialogue language are materially stronger acquisition triggers than ordinary renewals;
- at least five distinct August decision events in this non-exhaustive sample have text supporting a real competitive/replacement decision.

Because this was not a near-exhaustive EU census, `5` is neither a monthly market-size estimate nor a hard upper bound. The correct next test is broader rolling collection with the same decision-event de-duplication rule across TED + national portals, followed by detection-latency measurement from actual collection timestamps.

## Fail-closed acquisition rule

Count an event toward the ~10/month hypothesis only when public evidence supports at least one of:

- explicit replacement of an incumbent platform;
- explicit migration/renewal of the virtualization platform rather than only licence renewal;
- explicit `or equivalent` / alternative platform admissibility;
- pre-tender market dialogue/RFI where alternatives are still open;
- another documented decision state demonstrating the platform choice is not already locked.

Do not count:

- simple VMware/Broadcom licence renewal;
- support renewal;
- hardware procurement merely mentioning VMware;
- multiple revisions/sources of the same buyer decision;
- an event after its practical decision window has already closed;
- aggregator duplicates without a separable decision-event identity.

## Source URLs used for this snapshot

- https://op.europa.eu/en/web/public-procurement/procurement-details/-/procurement/90c11215-946e-49c9-9313-d5dc76059f08
- https://op.europa.eu/en/web/public-procurement/procurement-details/-/procurement/7b19075c-291c-49b9-9298-dc13e6ed0f96
- https://www.etenders.gov.mt/epps/cft/prepareViewCfTWS.do?resourceId=14016205
- https://op.europa.eu/en/web/public-procurement/procurement-details/-/procurement/5b85c611-b628-4a33-959b-845d7ef3c471
- https://diariodarepublica.pt/dr/detalhe/anuncio-procedimento/20873-2026-1159106526
- https://op.europa.eu/en/web/public-procurement/procurement-details/-/procurement/e1182426-d523-4700-ac11-fa5b85b4f7b8
- https://op.europa.eu/en/web/public-procurement/procurement-details/-/procurement/78ff297d-8f8f-40b7-8818-e9f9742a8955
- https://diariodarepublica.pt/dr/detalhe/anuncio-procedimento/20182-2026-1154789331
- https://diariodarepublica.pt/dr/detalhe/anuncio-procedimento/19964-2026-1154497980
- public notice 2026/S 159-573563 (Central IT Center, Poland)
- HILMA-derived market-survey notice 2026-055290 (LapIT Oy)
- German public-procurement listing for Universitätsklinikum Heidelberg, deadline 2026-09-14
- public tender index snapshot for Polish common-courts VMware-or-equivalent framework, published 2026-08-26
- public tender index snapshot for German replacement of existing VMware licence infrastructure, published 2026-08-13
