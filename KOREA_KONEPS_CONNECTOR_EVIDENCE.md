# Korea PPS / KONEPS — connector evidence and production block

This note records the source contract used by `korea_koneps.py` and, equally importantly, why the source is **not** production-ready yet.

## Official source

- Publisher: Public Procurement Service (PPS), Republic of Korea.
- System: KONEPS / 나라장터.
- Official Public Data Portal dataset: `조달청_나라장터 입찰공고정보서비스`.
- Official service base: `https://apis.data.go.kr/1230000/ad/BidPublicInfoService`.
- Construction list operation: `GET /getBidPblancListInfoCnstwk` (`공사`).
- The portal describes the dataset as nationwide, real-time, free, and `이용허락범위 제한 없음` (no limitation on scope of use).
- Public Data Portal application/approval is still required and requests require a `serviceKey`.

## Documented incremental contract

The construction operation supports:

- `inqryDiv=1` — registration datetime.
- `inqryDiv=2` — bid notice number.
- `inqryDiv=3` — change datetime.
- `inqryBgnDt` / `inqryEndDt` in `YYYYMMDDHHMM` for datetime queries.
- `pageNo`, `numOfRows`, and JSON response type.

The JSON response envelope contains `response.header` and `response.body`, with `resultCode=00` for success and body pagination metadata `pageNo`, `numOfRows`, `totalCount`, plus bid items.

Documented construction fields used by the connector include:

- `bidNtceNo` and `bidNtceOrd` — publisher bid notice identity/order.
- `ntceKindNm` — documented values include `등록공고`, `변경공고`, `취소공고`, `재공고`.
- `bidNtceDt`, `rgstDt`, `chgDt`.
- `bidNtceNm`.
- `bidClseDt` — structured bid closing datetime.
- `ntceInsttNm`, `dminsttNm`.
- `cnstrtsiteRgnNm` — construction-site region.
- `presmptPrce`, `bdgtAmt`.
- `mainCnsttyNm` — main construction type.
- `cntrctCnclsMthdNm`, `bidMethdNm`, `sucsfbidMthdNm`.
- `chgNtceRsn`.
- `bidNtceDtlUrl` / `bidNtceUrl`.
- notice-document URL/file-name fields.

## ObraSignal semantics chosen

- Construction classification is publisher-native because the source operation itself is `Cnstwk/공사`; no title, CPV, or keyword inference is used.
- Commercial identity is `bidNtceNo + bidNtceOrd`, matching the publisher's detail-link identity.
- `변경공고` updates the same publisher identity.
- `취소공고` closes a previously visible identity; an isolated cancellation does not invent a prior opportunity.
- `재공고` with a new order is treated as a distinct publisher commercial identity.
- A valid future `bidClseDt` is required before a row is actionable.
- No CPV code is manufactured from Korean work-type labels.
- Incremental discovery uses `inqryDiv=3` with bounded overlap and fail-closed pagination/count validation.
- Long catch-up preserves intermediate state privately until the connector reaches current time, so a later amendment/cancellation in the remaining window cannot be missed before publication.

## Production gate remains closed

The connector is intentionally **not runtime-wired** and this branch does **not** alter `source_registry.py`.

`KR_KONEPS` must remain:

- `status=planned`
- `machine_access=CREDENTIAL_REQUIRED`
- `adapter=None`
- `capabilities=()`

until all of the following are true:

1. an authorized project-owned Public Data Portal service key is configured;
2. live calls to `getBidPblancListInfoCnstwk` validate the request/response contract and pagination;
3. current Works notices with publisher identities and structured future deadlines are observed;
4. change/cancellation behaviour is validated against live publisher data;
5. exact-head CI passes after runtime wiring and registry promotion.

No third-party or leaked service key may be used to satisfy this gate.
