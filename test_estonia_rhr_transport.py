from datetime import datetime, timezone

import pytest

from estonia_rhr import EERHRCursor, EstoniaRHRConnector


NOW = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


class Response:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200
        self.headers = {"content-length": str(len(payload))}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=131072):
        for index in range(0, len(self.payload), chunk_size):
            yield self.payload[index:index + chunk_size]

    def close(self):
        return None


class Session:
    def __init__(self, payload):
        self.payload = payload

    def get(self, url, **kwargs):
        return Response(self.payload)


def test_valid_empty_open_data_month_is_not_an_error():
    connector = EstoniaRHRConnector(
        session=Session(b"<OPEN-DATA></OPEN-DATA>"),
        initial_months=1,
        overlap_months=0,
    )
    rows, cursor = connector.fetch_incremental(now=NOW)
    assert rows == []
    assert EERHRCursor.decode(cursor).tracked == {}


def test_truncated_xml_fails_closed_before_cursor_return():
    connector = EstoniaRHRConnector(
        session=Session(b"<OPEN-DATA><ContractNotice>"),
        initial_months=1,
        overlap_months=0,
    )
    with pytest.raises(RuntimeError, match="XML parse failure.*cursor not advanced"):
        connector.fetch_incremental(now=NOW)


def test_unexpected_non_rhr_xml_root_fails_closed():
    connector = EstoniaRHRConnector(
        session=Session(b"<html><body>blocked</body></html>"),
        initial_months=1,
        overlap_months=0,
    )
    with pytest.raises(RuntimeError, match="unexpected root html.*cursor not advanced"):
        connector.fetch_incremental(now=NOW)
