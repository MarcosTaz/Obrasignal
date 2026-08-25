from dataclasses import replace
from datetime import date

import pytest

from dominican_republic_dgcp import DGCP_CONFIG
from dominican_republic_dgcp_discovery import DGCPProcessDiscoveryConnector


class Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class Session:
    def __init__(self, payload):
        self.payload = payload

    def get(self, *args, **kwargs):
        return Response(self.payload)


def _config():
    return replace(DGCP_CONFIG, page_size=1000, max_pages_per_window=5)


def test_null_content_is_valid_only_for_publisher_declared_empty_page():
    payload = {"code": 200, "hasError": False, "page": 1, "pages": 0, "limit": 1000, "totalResults": 0, "payload": {"content": None}}
    connector = DGCPProcessDiscoveryConnector(_config(), session=Session(payload))
    rows, meta = connector._process_page(date(2026, 8, 25), date(2026, 8, 25), 1)
    assert rows == []
    assert meta["total"] == 0


def test_null_content_with_positive_total_fails_closed():
    payload = {"code": 200, "hasError": False, "page": 1, "pages": 1, "limit": 1000, "totalResults": 1, "payload": {"content": None}}
    connector = DGCPProcessDiscoveryConnector(_config(), session=Session(payload))
    with pytest.raises(RuntimeError, match="invalid payload.content"):
        connector._process_page(date(2026, 8, 25), date(2026, 8, 25), 1)
