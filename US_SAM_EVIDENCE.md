# US SAM — Q050 evidence

Status: IMPLEMENTATION IN PROGRESS.

## Official contract

- SAM.gov Contract Opportunities is the official U.S. federal opportunity source.
- Publisher-native construction classification is NAICS sector 23; ObraSignal admits only six-digit NAICS codes beginning with `23`.
- Public full extract: `ContractOpportunitiesFullCSV.csv`; live probe on 2026-08-25 returned HTTP 200, 248,581,349 bytes, 47 columns, ETag and Last-Modified metadata.
- Publisher fields include NoticeId, solicitation number, organization hierarchy, posted date, notice/base type, archive metadata, set-aside, response deadline, NAICS, classification code, place of performance, contacts, links and description.
- `NoticeId` is the connector identity. Solicitation number is preserved but is not assumed globally unique.
- `Award$` is award information and is never presented as current tender value.
- Full CSV is treated as an active daily snapshot. Disappearance does not prove cancellation and therefore fails closed.
- GSA API v2 requires an API key and only returns the latest active opportunity version; it is not required for the no-key v0.1 production path.

## Production semantics

- Source ID: `US_SAM`.
- Opt-in only through `OBRASIGNAL_GLOBAL_SOURCES=US_SAM`.
- Conditional GET uses ETag/Last-Modified.
- CSV is parsed streaming to avoid loading the ~250 MB file into memory.
- Actionable notice types in v0.1: Presolicitation, Solicitation, Combined Synopsis/Solicitation, Sources Sought.
- No keyword filtering as the primary construction gate.
- No fabricated contract value or currency.
