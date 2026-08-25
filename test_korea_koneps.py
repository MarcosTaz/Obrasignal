from datetime import datetime, timezone
import json

import pytest

from korea_koneps import (
    KONEPS_CONSTRUCTION_ENDPOINT,
    KONEPSConstructionConnector,
    KONEPSCursor,
)


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def _item(
    notice_no="R26BK01234567",
    *,
    order="000",
    kind="등록공고",
    changed="2026-08-24 20:55:00",
    published="2026-08-24 20:50:00",
    deadline="2026-09-01 10:00:00",
    title="서울시 공공시설 보수공사",
):
    return {
        "bidNtceNo": notice_no,
        "bidNtceOrd": order,
        "ntceKindNm": kind,
        "chgDt": changed,
        "rgstDt": published,
        "bidNtceDt": published,
        "bidNtceNm": title,
        "bidClseDt": deadline,
        "ntceInsttNm": "서울특별시",
        "dminsttNm": "서울특별시 시설관리본부",
        "cnstrtsiteRgnNm": "서울특별시",
        "presmptPrce": "2500000000",
        "bdgtAmt": "2750000000",
        "mainCnsttyNm": "시설물유지관리공사",
        "cntrctCnclsMthdNm": "일반경쟁",
        "bidMethdNm": "전자입찰",
        "sucsfbidMthdNm": "적격심사",
        "untyNtceNo": "UNIFIED-1",
        "refNo": "REF-1",
        "intrbidYn": "N",
        "reNtceYn": "N",
        "bidNtceDtlUrl": "https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=R26BK01234567&bidPbancOrd=000",
        "ntceSpecDocUrl1": "https://www.g2b.go.kr/doc/1",
        "ntceSpecFileNm1": "공고문.hwp",
    }


class _Response:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class _Session:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, *, params, headers, timeout):
        self.calls.append((url, dict(params), dict(headers), timeout))
        page_no = int(params["pageNo"])
        return _Response(self.pages[page_no])


def _page(items, *, page_no=1, num_rows=100, total_count=None, code="00", message="NORMAL SERVICE"):
    return {
        "response": {
            "header": {"resultCode": code, "resultMsg": message},
            "body": {
                "items": items,
                "numOfRows": num_rows,
                "pageNo": page_no,
                "totalCount": len(items) if total_count is None else total_count,
            },
        }
    }


def _connector(items, **kwargs):
    session = _Session({1: _page(items)})
    connector = KONEPSConstructionConnector(
        service_key="authorized-test-key",
        session=session,
        initial_lookback_minutes=60,
        max_minutes_per_sync=60,
        overlap_minutes=5,
        **kwargs,
    )
    return connector, session


def test_missing_authorized_service_key_fails_before_network(monkeypatch):
    monkeypatch.delenv("KONEPS_SERVICE_KEY", raising=False)
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY", raising=False)
    session = _Session({})
    connector = KONEPSConstructionConnector(service_key="", session=session)
    with pytest.raises(RuntimeError, match="authorized Public Data Portal service key"):
        connector.fetch_incremental(now=NOW)
    assert session.calls == []


def test_official_construction_operation_emits_actionable_works_without_keyword_inference():
    connector, session = _connector([_item(title="제목에 건설이라는 단어가 없음")])
    rows, cursor = connector.fetch_incremental(now=NOW)

    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "KR_KONEPS"
    assert row["external_id"] == "R26BK01234567:000"
    assert row["contract_type"] == "works"
    assert row["signal_type"] == "TENDER"
    assert row["is_actionable"] is True
    assert row["currency"] == "KRW"
    assert row["value"] == "2500000000"
    assert row["deadline"] == "2026-09-01T01:00:00Z"
    assert row["place"] == "서울특별시"
    assert row["koneps_main_work_type"] == "시설물유지관리공사"
    assert row["cpv"] == "" and row["cpv_codes"] == []
    assert row["url"].startswith("https://www.g2b.go.kr/")
    assert KONEPSCursor.decode(cursor).completed_through == "2026-08-24T12:00Z"

    url, params, headers, timeout = session.calls[0]
    assert url == KONEPS_CONSTRUCTION_ENDPOINT
    assert params["serviceKey"] == "authorized-test-key"
    assert params["inqryDiv"] == "3"
    assert params["inqryBgnDt"] == "202608242000"
    assert params["inqryEndDt"] == "202608242100"
    assert params["type"] == "json"
    assert params["pageNo"] == 1
    assert "Authorization" not in headers
    assert timeout == 45


def test_change_notice_updates_same_publisher_identity_not_duplicate():
    first_connector, _ = _connector([_item()])
    first_rows, watermark = first_connector.fetch_incremental(now=NOW)
    assert len(first_rows) == 1

    changed = _item(
        kind="변경공고",
        changed="2026-08-24 21:03:00",
        deadline="2026-09-05 10:00:00",
    )
    session = _Session({1: _page([changed])})
    connector = KONEPSConstructionConnector(
        service_key="authorized-test-key",
        session=session,
        overlap_minutes=5,
        max_minutes_per_sync=60,
    )
    rows, _ = connector.fetch_incremental(
        watermark=watermark,
        now=datetime(2026, 8, 24, 12, 10, tzinfo=timezone.utc),
    )
    assert len(rows) == 1
    assert rows[0]["external_id"] == "R26BK01234567:000"
    assert rows[0]["source_status"] == "변경공고"
    assert rows[0]["deadline"] == "2026-09-05T01:00:00Z"
    assert rows[0]["published_at"] == "2026-08-24T11:50:00Z"


def test_cancellation_emits_tombstone_only_for_previously_visible_bid():
    first_connector, _ = _connector([_item()])
    _, watermark = first_connector.fetch_incremental(now=NOW)

    cancelled = _item(
        kind="취소공고",
        changed="2026-08-24 21:03:00",
        deadline="2026-09-01 10:00:00",
    )
    cancelled["chgNtceRsn"] = "예산 변경으로 취소"
    session = _Session({1: _page([cancelled])})
    connector = KONEPSConstructionConnector(service_key="authorized-test-key", session=session)
    rows, _ = connector.fetch_incremental(
        watermark=watermark,
        now=datetime(2026, 8, 24, 12, 10, tzinfo=timezone.utc),
    )
    assert len(rows) == 1
    assert rows[0]["is_actionable"] is False
    assert rows[0]["_lifecycle_only"] is True
    assert rows[0]["lifecycle_status"] == "cancelled"
    assert "예산 변경" in rows[0]["lifecycle_reason"]

    isolated, _ = _connector([cancelled])
    isolated_rows, _ = isolated.fetch_incremental(now=NOW)
    assert isolated_rows == []


def test_reannouncement_order_is_a_distinct_publisher_commercial_identity():
    connector, _ = _connector([
        _item(notice_no="R26BK01234567", order="000"),
        _item(notice_no="R26BK01234567", order="001", kind="재공고", changed="2026-08-24 20:56:00"),
    ])
    rows, _ = connector.fetch_incremental(now=NOW)
    assert {row["external_id"] for row in rows} == {
        "R26BK01234567:000",
        "R26BK01234567:001",
    }


def test_expired_or_missing_deadline_is_not_exposed_as_actionable():
    expired, _ = _connector([_item(deadline="2026-08-24 20:00:00")])
    rows, cursor = expired.fetch_incremental(now=NOW)
    assert rows == []
    assert KONEPSCursor.decode(cursor).tracked == {}

    missing_item = _item()
    missing_item["bidClseDt"] = ""
    missing, _ = _connector([missing_item])
    rows, cursor = missing.fetch_incremental(now=NOW)
    assert rows == []
    assert "R26BK01234567:000" in KONEPSCursor.decode(cursor).tracked


def test_api_error_envelope_fails_closed_without_exposing_key():
    session = _Session({1: _page([], code="30", message="SERVICE KEY IS NOT REGISTERED")})
    connector = KONEPSConstructionConnector(service_key="super-secret", session=session)
    with pytest.raises(RuntimeError, match="resultCode='30'") as exc:
        connector.fetch_incremental(now=NOW)
    assert "super-secret" not in str(exc.value)


def test_malformed_envelope_and_unknown_notice_kind_fail_closed():
    session = _Session({1: {"not_response": {}}})
    connector = KONEPSConstructionConnector(service_key="key", session=session)
    with pytest.raises(RuntimeError, match="unsupported envelope"):
        connector.fetch_incremental(now=NOW)

    unknown, _ = _connector([_item(kind="새로운공고유형")])
    with pytest.raises(RuntimeError, match="unsupported ntceKindNm"):
        unknown.fetch_incremental(now=NOW)


def test_missing_publisher_identity_or_change_timestamp_fails_closed():
    no_identity = _item()
    no_identity["bidNtceOrd"] = ""
    connector, _ = _connector([no_identity])
    with pytest.raises(RuntimeError, match="missing publisher identity"):
        connector.fetch_incremental(now=NOW)

    no_time = _item()
    no_time["chgDt"] = ""
    no_time["rgstDt"] = ""
    no_time["bidNtceDt"] = ""
    connector, _ = _connector([no_time])
    with pytest.raises(RuntimeError, match="change timestamp"):
        connector.fetch_incremental(now=NOW)


def test_pagination_is_complete_bounded_and_rejects_duplicates_or_drift():
    first = _item(notice_no="R26BK00000001")
    second = _item(notice_no="R26BK00000002", changed="2026-08-24 20:56:00")
    session = _Session({
        1: _page([first], page_no=1, num_rows=1, total_count=2),
        2: _page([second], page_no=2, num_rows=1, total_count=2),
    })
    connector = KONEPSConstructionConnector(service_key="key", session=session, page_size=1)
    rows, _ = connector.fetch_incremental(now=NOW)
    assert len(rows) == 2
    assert [call[1]["pageNo"] for call in session.calls] == [1, 2]

    duplicate_session = _Session({
        1: _page([first], page_no=1, num_rows=1, total_count=2),
        2: _page([first], page_no=2, num_rows=1, total_count=2),
    })
    duplicate = KONEPSConstructionConnector(service_key="key", session=duplicate_session, page_size=1)
    with pytest.raises(RuntimeError, match="duplicate bid identity"):
        duplicate.fetch_incremental(now=NOW)

    drift_session = _Session({
        1: _page([first], page_no=1, num_rows=1, total_count=2),
        2: _page([second], page_no=2, num_rows=1, total_count=3),
    })
    drift = KONEPSConstructionConnector(service_key="key", session=drift_session, page_size=1)
    with pytest.raises(RuntimeError, match="pagination changed"):
        drift.fetch_incremental(now=NOW)


def test_page_item_and_cursor_state_hard_limits_fail_closed():
    session = _Session({1: _page([], num_rows=100, total_count=10001)})
    connector = KONEPSConstructionConnector(service_key="key", session=session, max_items=10000)
    with pytest.raises(RuntimeError, match="item hard limit"):
        connector.fetch_incremental(now=NOW)

    session = _Session({1: _page([], num_rows=1, total_count=101)})
    connector = KONEPSConstructionConnector(service_key="key", session=session, page_size=1, max_pages=100)
    with pytest.raises(RuntimeError, match="page hard limit"):
        connector.fetch_incremental(now=NOW)

    connector, _ = _connector([_item()], max_state_items=1)
    rows, _ = connector.fetch_incremental(now=NOW)
    assert len(rows) == 1


def test_corrupt_or_future_cursor_is_rejected_before_query_progress():
    connector, _ = _connector([])
    with pytest.raises(RuntimeError, match="cursor JSON"):
        connector.fetch_incremental(watermark="not-json", now=NOW)

    future = KONEPSCursor("2026-08-24T12:01Z", {}, {}).encode()
    with pytest.raises(RuntimeError, match="ahead"):
        connector.fetch_incremental(watermark=future, now=NOW)


def test_long_catchup_keeps_intermediate_state_private_until_current():
    first = _item(changed="2026-08-24 19:30:00", published="2026-08-24 19:25:00")
    session = _Session({1: _page([first])})
    connector = KONEPSConstructionConnector(
        service_key="key",
        session=session,
        initial_lookback_minutes=180,
        max_minutes_per_sync=60,
        overlap_minutes=5,
    )
    rows, cursor = connector.fetch_incremental(now=NOW)
    decoded = KONEPSCursor.decode(cursor)
    assert rows == []
    assert decoded.completed_through == "2026-08-24T10:00Z"
    assert "R26BK01234567:000" in decoded.tracked


def test_items_wrapper_shape_is_supported_but_count_mismatch_fails():
    wrapped = _page([], total_count=1)
    wrapped["response"]["body"]["items"] = {"item": _item()}
    session = _Session({1: wrapped})
    connector = KONEPSConstructionConnector(service_key="key", session=session)
    rows, _ = connector.fetch_incremental(now=NOW)
    assert len(rows) == 1

    mismatch = _Session({1: _page([_item()], total_count=2)})
    connector = KONEPSConstructionConnector(service_key="key", session=mismatch)
    with pytest.raises(RuntimeError, match="count mismatch"):
        connector.fetch_incremental(now=NOW)
