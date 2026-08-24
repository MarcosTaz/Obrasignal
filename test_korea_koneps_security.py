from datetime import datetime, timezone

import pytest

from korea_koneps import KONEPSConstructionConnector, KONEPSCursor


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def _page(items=None, *, page_no=1, num_rows=100, total_count=0, code="00", message="NORMAL SERVICE"):
    return {
        "response": {
            "header": {"resultCode": code, "resultMsg": message},
            "body": {
                "items": [] if items is None else items,
                "numOfRows": num_rows,
                "pageNo": page_no,
                "totalCount": total_count,
            },
        }
    }


def _item(*, changed="2026-08-24 20:55:00"):
    return {
        "bidNtceNo": "R26BK01234567",
        "bidNtceOrd": "000",
        "ntceKindNm": "등록공고",
        "chgDt": changed,
        "rgstDt": "2026-08-24 20:50:00",
        "bidNtceDt": "2026-08-24 20:50:00",
        "bidNtceNm": "공공시설 보수",
        "bidClseDt": "2026-09-01 10:00:00",
        "ntceInsttNm": "서울특별시",
        "dminsttNm": "서울특별시 시설관리본부",
        "cnstrtsiteRgnNm": "서울특별시",
        "presmptPrce": "2500000000",
        "mainCnsttyNm": "시설물유지관리공사",
        "bidNtceDtlUrl": "https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=R26BK01234567&bidPbancOrd=000",
    }


class _Response:
    status_code = 200

    def __init__(self, payload=None, *, status=200, raise_message=None):
        self.payload = _page() if payload is None else payload
        self.status_code = status
        self.raise_message = raise_message

    def raise_for_status(self):
        if self.raise_message:
            raise RuntimeError(self.raise_message)
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class _RecordingSession:
    def __init__(self, response=None, network_error=None):
        self.response = response or _Response()
        self.network_error = network_error
        self.calls = []

    def get(self, url, *, params, headers, timeout):
        self.calls.append((url, dict(params), dict(headers), timeout))
        if self.network_error:
            raise self.network_error
        return self.response


def test_percent_encoded_portal_key_is_normalized_once_before_request():
    session = _RecordingSession()
    connector = KONEPSConstructionConnector(
        service_key="abc%2Bdef%2Fghi%3D",
        session=session,
        initial_lookback_minutes=60,
        max_minutes_per_sync=60,
    )
    rows, _ = connector.fetch_incremental(now=NOW)

    assert rows == []
    assert session.calls[0][1]["serviceKey"] == "abc+def/ghi="


def test_http_error_cannot_leak_service_key_from_prepared_url_message():
    secret = "sensitive+project/key="
    leaked_url = f"https://apis.data.go.kr/example?serviceKey={secret}&pageNo=1"
    session = _RecordingSession(
        response=_Response(status=403, raise_message=f"403 Client Error for url: {leaked_url}")
    )
    connector = KONEPSConstructionConnector(service_key=secret, session=session)

    with pytest.raises(RuntimeError, match="KR_KONEPS HTTP status 403") as exc:
        connector.fetch_incremental(now=NOW)

    assert secret not in str(exc.value)
    assert "serviceKey=" not in str(exc.value)
    assert leaked_url not in str(exc.value)


def test_network_exception_cannot_leak_service_key_from_request_message():
    secret = "another-sensitive-project-key"
    session = _RecordingSession(
        network_error=RuntimeError(
            f"connection reset for https://apis.data.go.kr/example?serviceKey={secret}"
        )
    )
    connector = KONEPSConstructionConnector(service_key=secret, session=session)

    with pytest.raises(RuntimeError, match="KR_KONEPS network request failed") as exc:
        connector.fetch_incremental(now=NOW)

    assert secret not in str(exc.value)
    assert "serviceKey=" not in str(exc.value)


def test_api_error_message_cannot_echo_service_key():
    secret = "publisher-echo-secret"
    payload = _page(
        code="30",
        message=f"SERVICE KEY {secret} IS NOT REGISTERED",
    )
    session = _RecordingSession(response=_Response(payload))
    connector = KONEPSConstructionConnector(service_key=secret, session=session)

    with pytest.raises(RuntimeError, match="resultCode='30'") as exc:
        connector.fetch_incremental(now=NOW)

    assert secret not in str(exc.value)
    assert "SERVICE KEY" not in str(exc.value)


def test_change_query_requires_publisher_chgdt_even_when_registration_dates_exist():
    item = _item(changed="")
    session = _RecordingSession(
        response=_Response(_page([item], total_count=1))
    )
    connector = KONEPSConstructionConnector(service_key="key", session=session)

    with pytest.raises(RuntimeError, match="chgDt"):
        connector.fetch_incremental(now=NOW)


def test_partial_catchup_queries_exact_bounded_change_time_window():
    session = _RecordingSession()
    connector = KONEPSConstructionConnector(
        service_key="key",
        session=session,
        initial_lookback_minutes=180,
        max_minutes_per_sync=60,
        overlap_minutes=5,
    )

    rows, cursor = connector.fetch_incremental(now=NOW)
    params = session.calls[0][1]

    assert rows == []
    assert params["inqryDiv"] == "3"
    assert params["inqryBgnDt"] == "202608241800"
    assert params["inqryEndDt"] == "202608241900"
    assert KONEPSCursor.decode(cursor).completed_through == "2026-08-24T10:00Z"


def test_existing_cursor_uses_overlap_but_never_advances_beyond_now():
    session = _RecordingSession()
    connector = KONEPSConstructionConnector(
        service_key="key",
        session=session,
        overlap_minutes=5,
        max_minutes_per_sync=60,
    )
    watermark = KONEPSCursor("2026-08-24T11:45Z", {}, {}).encode()

    rows, cursor = connector.fetch_incremental(watermark=watermark, now=NOW)
    params = session.calls[0][1]

    assert rows == []
    assert params["inqryBgnDt"] == "202608242040"
    assert params["inqryEndDt"] == "202608242100"
    assert KONEPSCursor.decode(cursor).completed_through == "2026-08-24T12:00Z"
