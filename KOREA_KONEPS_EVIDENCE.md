# South Korea KONEPS — implementation evidence

This file records the source contract and unresolved production gate for `KR_KONEPS`.

## Official supported source

- Publisher: Public Procurement Service (PPS / 조달청).
- System: KONEPS / 나라장터.
- Public Data Portal dataset: `조달청_나라장터 입찰공고정보서비스`.
- API base: `https://apis.data.go.kr/1230000/ad/BidPublicInfoService`.
- Construction-list operation: `getBidPblancListInfoCnstwk`.
- Coverage declared by the official portal: nationwide.
- Refresh declared by the official portal: real-time.
- Cost: free.
- Reuse: unrestricted.
- Access: an approved Public Data Portal `serviceKey` is required.

## Documented machine contract

The construction operation supports:

- `inqryDiv=1` — query by registration datetime.
- `inqryDiv=2` — query by bid notice number.
- `inqryDiv=3` — query by change datetime.
- `inqryBgnDt` / `inqryEndDt` — `YYYYMMDDHHMM`.
- `pageNo`, `numOfRows`, `type=json`.
- response header `resultCode` / `resultMsg`.
- response body `items`, `pageNo`, `numOfRows`, `totalCount`.

Relevant construction notice fields include:

- `bidNtceNo` — bid notice identity.
- `bidNtceOrd` — notice/reannouncement order.
- `ntceKindNm` — registration/change/cancellation/reannouncement notice kind.
- `bidNtceDt`, `rgstDt`, `chgDt` — publisher timestamps.
- `bidClseDt` — structured bid deadline.
- `bidNtceNm` — notice title.
- `ntceInsttNm` / `dminsttNm` — notice and demand organizations.
- `presmptPrce`, `bdgtAmt` — estimated/budget amounts.
- `cnstrtsiteRgnNm` — construction site region.
- `bidNtceDtlUrl` — publisher detail URL.
- `ntceSpecDocUrl1..10`, `stdNtceDocUrl` — publisher document URLs.

## Credential-free alternatives tested and rejected

A temporary evidence-only PR (#127) tested whether the current G2B website could provide production discovery without a service key.

Findings:

1. `https://www.g2b.go.kr/` was reachable anonymously, but the older WebSquare bid-search controls used by a May-2026 public crawler were no longer present in the live headless-browser probe.
2. The old `/pn/pnp/pnpd/searchBidNtce.do` route returned G2B's `시스템 접근 안내` page saying the requested page could not be found / the URL may be invalid.
3. No anonymous `srchBidPbanc.do` discovery call was observed.
4. The official D-1 `조달청_입찰공고 내역` report is unrestricted-use, but its `data.g2b.go.kr` report URL redirects to G2B OIDC SSO. It is not an anonymous ingestion substitute.
5. Public detail pages and attachments exist, but detail access without a complete list is not sufficient for national discovery/completeness.

Therefore no credential-free source passed the project's machine-access/completeness gate.

## Implemented semantics pending live validation

The connector is prebuilt but **must remain non-production** until a real key is supplied and a live smoke passes.

- Construction classification comes from the construction-specific publisher operation; no title/keyword classification is used.
- Stable commercial identity is `bidNtceNo`.
- `bidNtceOrd` and publisher change timestamp form version ordering.
- Each day is read through both registration-time and change-time queries so later changes/cancellations are not missed.
- Exact duplicate versions across the two query modes are deduplicated; conflicting same-version payloads fail closed.
- Pagination is bounded and validated against `totalCount`.
- Cancellation notices close a previously visible notice.
- A valid future `bidClseDt` is required before exposure as actionable.
- Currency is KRW.
- Cursor advancement is atomic with staged source observations through the existing incremental runtime plugin.

## Registry state

`KR_KONEPS` remains:

- `status=planned`
- `machine_access=CREDENTIAL_REQUIRED`
- `legal_reuse=GREEN`
- `capabilities=()`
- `adapter=KONEPSConstructionBidConnector`

The empty production capability tuple is deliberate: implementation exists, but no capability is promoted as production-verified until the authenticated live contract is exercised.

## Required final gate

1. Obtain/approve a Public Data Portal key for `조달청_나라장터 입찰공고정보서비스`.
2. Supply it as `OBRASIGNAL_KR_KONEPS_SERVICE_KEY` in a controlled validation environment.
3. Run a bounded live smoke for registration and change queries.
4. Verify pagination, construction records, stable identities, future deadlines, change/cancellation behavior and rate/traffic limits.
5. Only then change `machine_access` to `VERIFIED`, assign proven capabilities, set `status=ready`, and allow explicit source opt-in.
