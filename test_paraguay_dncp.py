from datetime import date

import pytest

import paraguay_dncp
from paraguay_dncp import (
    DNCP_CONFIG,
    DNCP_SEARCH_URL,
    DNCPTokenProvider,
    dncp_search_params,
    normalize_dncp_process,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload=None):
        self.payload = payload or {"access_token": "access-123"}
        self.posts = []

    def post(self, url, *, json, timeout):
        self.posts.append({"url": url, "json": dict(json), "timeout": timeout})
        return FakeResponse(self.payload)


def _record(*, status="active", url=None):
    return {
        "ocid": "ocds-03ad3f-500001-1",
        "compiledRelease": {
            "ocid": "ocds-03ad3f-500001-1",
            "id": "500001-obras-release",
            "date": "2026-08-24T08:00:00-03:00",
            "tag": ["planning", "tender"],
            "buyer": {"name": "Ministerio de Obras Públicas"},
            "tender": {
                "id": "500001-obras-1",
                "title": "Construcción de puente",
                "description": "Obras civiles",
                "status": status,
                "statusDetails": "Convocatoria abierta",
                "procurementMethod": "open",
                "procurementMethodDetails": "Licitación Pública Nacional",
                "mainProcurementCategory": "works",
                "url": url,
                "tenderPeriod": {"endDate": "2026-09-12T09:00:00-03:00"},
                "value": {"amount": 9500000000, "currency": "PYG"},
                "items": [{"classification": {"scheme": "DNCP", "id": "72000000"}}],
            },
        },
    }


def test_dncp_config_targets_official_v3_search_and_safe_daily_windows():
    assert DNCP_CONFIG.source == "PY_DNCP"
    assert DNCP_CONFIG.search_url == DNCP_SEARCH_URL
    assert DNCP_CONFIG.search_url.endswith("/datos/api/v3/doc/search/processes")
    assert DNCP_CONFIG.window_days == 1
    assert DNCP_CONFIG.max_pages_per_window * DNCP_CONFIG.page_size == 10000


def test_dncp_search_is_server_side_works_and_release_date_incremental():
    params = dncp_search_params(date(2026, 8, 23), date(2026, 8, 24))
    assert params["fecha_desde"] == "2026-08-23"
    assert params["fecha_hasta"] == "2026-08-24"
    assert params["tipo_fecha"] == "fecha_release"
    assert params["tender.mainProcurementCategory"] == "works"
    assert params["order"] == "date asc"


def test_production_auth_fails_closed_without_credentials(monkeypatch):
    monkeypatch.delenv("DNCP_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("DNCP_REQUEST_TOKEN", raising=False)
    provider = DNCPTokenProvider(session=FakeSession(), allow_anonymous=False)
    with pytest.raises(RuntimeError, match="requires DNCP_REQUEST_TOKEN or DNCP_ACCESS_TOKEN"):
        provider.headers()


def test_anonymous_auth_is_explicitly_testing_only(monkeypatch):
    monkeypatch.delenv("DNCP_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("DNCP_REQUEST_TOKEN", raising=False)
    provider = DNCPTokenProvider(session=FakeSession(), allow_anonymous=True)
    assert provider.headers() == {}


def test_direct_access_token_is_passed_in_v3_authorization_header(monkeypatch):
    monkeypatch.setenv("DNCP_ACCESS_TOKEN", "direct-token")
    monkeypatch.delenv("DNCP_REQUEST_TOKEN", raising=False)
    provider = DNCPTokenProvider(session=FakeSession())
    assert provider.headers() == {"Authorization": "direct-token"}


def test_request_token_exchange_is_cached(monkeypatch):
    monkeypatch.delenv("DNCP_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("DNCP_REQUEST_TOKEN", "request-abc")
    session = FakeSession({"access_token": "generated-token"})
    provider = DNCPTokenProvider(session=session)

    assert provider.headers() == {"Authorization": "generated-token"}
    assert provider.headers() == {"Authorization": "generated-token"}
    assert len(session.posts) == 1
    assert session.posts[0]["json"] == {"request_token": "request-abc"}
    assert session.posts[0]["url"].endswith("/datos/api/v3/doc/oauth/token")


def test_dncp_normalizer_keeps_native_classification_and_official_fallback_url():
    item = normalize_dncp_process(_record())
    assert item["source"] == "PY_DNCP"
    assert item["external_id"] == "ocds-03ad3f-500001-1"
    assert item["country"] == "PRY"
    assert item["taxonomy"] == "DNCP"
    assert item["category_code"] == "72000000"
    assert item["cpv"] == ""
    assert item["contract_type"] == "works"
    assert item["procurement_method"] == "Licitación Pública Nacional"
    assert item["currency"] == "PYG"
    assert item["url"] == paraguay_dncp.DNCP_PORTAL_URL


def test_dncp_normalizer_rejects_completed_tender_from_discovery_signal():
    assert normalize_dncp_process(_record(status="complete")) is None
