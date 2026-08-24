from datetime import datetime, timezone
import json

import pytest

from korea_koneps import (
    KONEPS_API,
    KONEPSConstructionBidConnector,
    KONEPSCursor,
    _event,
)


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def _row(
    notice_no="R26BK01699999",
    *,
    order="000",
    kind="등록공고",
    changed="2026-08-24 15:00:00",
    registered="2026-08-24 14:59:00",
    published="2026-08-24 14:55:00",
    deadline="2026-09-10 10:00:00",
):
    return {
        "bidNtceNo": notice_no,
        "bidNtceOrd": order,
        "reNtceYn": "N",
        "rgstTyNm": "조달청 또는 나라장터 자체 공고건",
        "ntceKindNm": kind,
        "bidNtceDt": published,
        "bidNtceNm": "도로 정비공사",
        "ntceInsttNm": "서울특별시",
        "dminsttNm": "서울특별시 도로사업소",
        "ntceInsttOfclNm": "홍길동",
        "ntceInsttOfclTelNo": "02-000-0000",
        "ntceInsttOfclEmailAdrs": "buyer@example.kr",
        "bidMethdNm": "전자입찰",
        "cntrctCnclsMthdNm": "일반경쟁",
        "bidBeginDt": "2026-08-25 10:00:00",
        "bidClseDt": deadline,
        "opengDt": "2026-09-10 11:00:00",
        "bdgtAmt": "1500000000",
        "presmptPrce": "1300000000",
        "sucsfbidMthdNm": "적격심사",
        "cnstrtsiteRgnNm": "서울특별시",
        "ntceSpecDocUrl1": "https://www.g2b.go.kr/file/1",
        "ntceSpecFileNm1": "공고문.hwp",
        "bidNtceDtlUrl": "https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=R26BK01699999&bidPbancOrd=000",
        "rgstDt": registered,
        "chgDt": changed,
        "chgNtceRsn": "",
    }


class _Response:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _Session:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, *, params, timeout):
        params = dict(params)
        self.calls.append((url, params, timeout))
        key = (params["inqryBgnDt"][:8], params["inqryDiv"], int(params["pageNo"]))
        return _Response(self.responses[key])


def _payload(items, *, page=1, size=100, total=None, code="00", message="NORMAL SERVICE"):
    if total is None:
        total = len(items)
    return {
        "response": {
            "header": {"resultCode": code, "resultMsg": message},
            "body": {
                "items": items,
                "numOfRows": size,
                "pageNo": page,
                "totalCount": total,
            },
        }
    }


def _connector_for_day(registration_rows=None, change_rows=None, **kwargs):
    registration_rows = registration_rows or []
    change_rows = change_rows or []
    responses = {
        ("20260824", "1", 1): _payload(registration_rows),
        ("20260824", "3", 1): _payload(change_rows),
    }
    session = _Session(responses)
    connector = KONEPSConstructionBidConnector(
        service_key="test-key",
        session=session,
        initial_lookback_days=1,
        overlap_days=0,
        max_days_per_sync=1,
        **kwargs,
    )
    return connector, session


def test_requires_explicit_service_key(monkeypatch):
    monkeypatch.delenv("OBRASIGNAL_KR_KONEPS_SERVICE_KEY", raising=False)
    with pytest.raises(RuntimeError, match="requires OBRASIGNAL_KR_KONEPS_SERVICE_KEY"):
        KONEPSConstructionBidConnector()


def test_construction_endpoint_row_becomes_actionable_without_keyword_inference():
    connector, _ = _connector_for_day([_row()])
    rows, cursor = connector.fetch_incremental(now=NOW)

    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "KR_KONEPS"
    assert row["external_id"] == "R26BK01699999"
    assert row["contract_type"] == "works"
    assert row["is_actionable"] is True
    assert row["deadline"] == "2026-09-10T01:00:00Z"
    assert row["value"] == "1300000000"
    assert row["currency"] == "KRW"
    assert row["buyer"] == "서울특별시"
    assert row["place"] == "서울특별시"
    assert row["koneps_bid_notice_order"] == "000"
    assert row["koneps_documents"] == [{"url": "https://www.g2b.go.kr/file/1", "name": "공고문.hwp"}]
    assert KONEPSCursor.decode(cursor).completed_through == "2026-08-24"


def test_registration_and_change_queries_dedupe_same_exact_version():
    same = _row()
    connector, _ = _connector_for_day([same], [same])
    rows, _ = connector.fetch_incremental(now=NOW)
    assert len(rows) == 1
    assert rows[0]["external_id"] == "R26BK01699999"


def test_conflicting_same_version_across_queries_fails_closed():
    a = _row()
    b = _row()
    b["bidNtceNm"] = "conflicting title"
    connector, _ = _connector_for_day([a], [b])
    with pytest.raises(RuntimeError, match="conflicting payloads"):
        connector.fetch_incremental(now=NOW)


def test_later_change_order_updates_same_bid_notice_without_duplicate():
    original = _row(changed="2026-08-24 09:00:00", deadline="2026-09-01 10:00:00")
    changed = _row(
        order="001",
        kind="변경공고",
        changed="2026-08-24 16:00:00",
        deadline="2026-09-15 10:00:00",
    )
    changed["chgNtceRsn"] = "입찰마감일 변경"
    connector, _ = _connector_for_day([original], [changed])
    rows, _ = connector.fetch_incremental(now=NOW)

    assert len(rows) == 1
    assert rows[0]["external_id"] == "R26BK01699999"
    assert rows[0]["koneps_bid_notice_order"] == "001"
    assert rows[0]["source_status"] == "변경공고"
    assert rows[0]["deadline"] == "2026-09-15T01:00:00Z"
    assert rows[0]["published_at"] == "2026-08-24T05:55:00Z"


def test_later_cancellation_closes_previously_visible_notice():
    first_connector, _ = _connector_for_day([_row()])
    first_rows, watermark = first_connector.fetch_incremental(now=NOW)
    assert first_rows[0]["is_actionable"] is True

    original = _row()
    cancelled = _row(
        order="001",
        kind="취소공고",
        changed="2026-08-25 09:00:00",
        registered="2026-08-25 08:59:00",
        deadline="",
    )
    responses = {
        ("20260824", "1", 1): _payload([original]),
        ("20260824", "3", 1): _payload([original]),
        ("20260825", "1", 1): _payload([]),
        ("20260825", "3", 1): _payload([cancelled]),
    }
    session = _Session(responses)
    connector = KONEPSConstructionBidConnector(
        service_key="test-key",
        session=session,
        overlap_days=1,
        max_days_per_sync=2,
    )
    rows, _ = connector.fetch_incremental(
        watermark=watermark,
        now=datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc),
    )
    assert len(rows) == 1
    assert rows[0]["external_id"] == "R26BK01699999"
    assert rows[0]["is_actionable"] is False
    assert rows[0]["_lifecycle_only"] is True
    assert rows[0]["lifecycle_status"] == "publisher_cancelled"


def test_expired_deadline_is_not_exposed_as_actionable():
    connector, _ = _connector_for_day([_row(deadline="2026-08-24 20:00:00")])
    rows, cursor = connector.fetch_incremental(now=NOW)
    assert rows == []
    assert KONEPSCursor.decode(cursor).tracked == {}


def test_missing_deadline_is_tracked_but_not_published():
    connector, _ = _connector_for_day([_row(deadline="")])
    rows, cursor = connector.fetch_incremental(now=NOW)
    decoded = KONEPSCursor.decode(cursor)
    assert rows == []
    assert "R26BK01699999" in decoded.tracked


def test_missing_publisher_identity_fails_closed():
    connector, _ = _connector_for_day([_row(notice_no="")])
    with pytest.raises(RuntimeError, match="missing bidNtceNo"):
        connector.fetch_incremental(now=NOW)


def test_api_error_code_fails_closed():
    responses = {
        ("20260824", "1", 1): _payload([], code="30", message="SERVICE KEY IS NOT REGISTERED ERROR"),
    }
    connector = KONEPSConstructionBidConnector(
        service_key="bad-key",
        session=_Session(responses),
        initial_lookback_days=1,
        overlap_days=0,
        max_days_per_sync=1,
    )
    with pytest.raises(RuntimeError, match="API error code=30"):
        connector.fetch_incremental(now=NOW)


def test_pagination_count_mismatch_fails_closed():
    responses = {
        ("20260824", "1", 1): _payload([_row()], total=2),
        ("20260824", "3", 1): _payload([]),
    }
    connector = KONEPSConstructionBidConnector(
        service_key="test-key",
        session=_Session(responses),
        initial_lookback_days=1,
        overlap_days=0,
        max_days_per_sync=1,
    )
    with pytest.raises(RuntimeError, match="count mismatch"):
        connector.fetch_incremental(now=NOW)


def test_pagination_change_mid_scan_fails_closed():
    responses = {
        ("20260824", "1", 1): _payload([_row("R26BK01699991")], page=1, size=1, total=2),
        ("20260824", "1", 2): _payload([_row("R26BK01699992")], page=2, size=1, total=3),
    }
    connector = KONEPSConstructionBidConnector(
        service_key="test-key",
        session=_Session(responses),
        initial_lookback_days=1,
        overlap_days=0,
        max_days_per_sync=1,
        page_size=1,
    )
    with pytest.raises(RuntimeError, match="pagination changed"):
        connector.fetch_incremental(now=NOW)


def test_hard_limit_fails_before_cursor_advance():
    responses = {
        ("20260824", "1", 1): _payload([], total=10100),
    }
    connector = KONEPSConstructionBidConnector(
        service_key="test-key",
        session=_Session(responses),
        initial_lookback_days=1,
        overlap_days=0,
        max_days_per_sync=1,
        max_items_per_query=10000,
    )
    with pytest.raises(RuntimeError, match="hard limits"):
        connector.fetch_incremental(now=NOW)


def test_corrupt_and_future_cursor_are_rejected():
    connector, _ = _connector_for_day([])
    with pytest.raises(RuntimeError, match="cursor JSON"):
        connector.fetch_incremental(watermark="not-json", now=NOW)

    future = KONEPSCursor("2026-08-25", {}, {}).encode()
    with pytest.raises(RuntimeError, match="ahead"):
        connector.fetch_incremental(watermark=future, now=NOW)


def test_partial_catchup_does_not_publish_intermediate_truth():
    responses = {
        ("20260822", "1", 1): _payload([_row(changed="2026-08-22 15:00:00", registered="2026-08-22 14:59:00", published="2026-08-22 14:55:00")]),
        ("20260822", "3", 1): _payload([]),
    }
    connector = KONEPSConstructionBidConnector(
        service_key="test-key",
        session=_Session(responses),
        initial_lookback_days=3,
        overlap_days=0,
        max_days_per_sync=1,
    )
    rows, cursor = connector.fetch_incremental(now=NOW)
    decoded = KONEPSCursor.decode(cursor)
    assert rows == []
    assert decoded.completed_through == "2026-08-22"
    assert "R26BK01699999" in decoded.tracked


def test_official_request_contract_uses_change_and_registration_windows():
    connector, session = _connector_for_day([])
    connector.fetch_incremental(now=NOW)
    assert len(session.calls) == 2
    assert {call[1]["inqryDiv"] for call in session.calls} == {"1", "3"}
    for url, params, timeout in session.calls:
        assert url == KONEPS_API
        assert params["serviceKey"] == "test-key"
        assert params["type"] == "json"
        assert params["inqryBgnDt"] == "202608240000"
        assert params["inqryEndDt"] == "202608242359"
        assert params["pageNo"] == 1
        assert params["numOfRows"] == 100
        assert timeout == 60


def test_event_maps_publisher_fields_without_creating_cpv():
    event = _event(_row(), query_day="2026-08-24", query_div=1)
    assert event["notice_no"] == "R26BK01699999"
    assert event["deadline"] == "2026-09-10T01:00:00Z"
    assert event["place"] == "서울특별시"
    assert event["cancelled"] is False
