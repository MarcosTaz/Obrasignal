"""Uruguay ARCE annual procurement-plan early-signal connector.

ARCE's public PAC consultation SPA exposes an unauthenticated paginated JSON API.
This connector deliberately covers the publisher-controlled family code 6
(`CONSTRUCCIONES, MEJORAS Y REPARACIONES EXTRAORDINARIAS`) and planned calls whose
published call window has not started yet. It does not use title keywords and it
does not depend on the currently broken public Excel export.

PAC is a snapshot transport, not the OCDS RSS event stream. Keeping it in this
small module prevents its snapshot semantics from contaminating UY_ARCE's tender
cursor. Runtime composition is a separate integration decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests

from uruguay_arce import ARCE_ATTRIBUTION, ARCE_LICENSE


ARCE_PAC_PUBLIC_URL = "https://www.comprasestatales.gub.uy/consultaplananual/"
ARCE_PAC_CONFIG_URL = urljoin(ARCE_PAC_PUBLIC_URL, "assets/config.json")
ARCE_PAC_EXPECTED_API_BASE = "/consultaplananual"
ARCE_PAC_SEARCH_PATH = "/api/v1/compra-procedimientos"
ARCE_PAC_WORKS_FAMILY_CODE = 6
ARCE_PAC_WORKS_FAMILY_LABEL = "CONSTRUCCIONES, MEJORAS Y REPARACIONES EXTRAORDINARIAS"
ARCE_PAC_TIMEZONE = ZoneInfo("America/Montevideo")
ARCE_PAC_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal ARCE PAC connector/1.0 (+official public data client)",
    "Referer": ARCE_PAC_PUBLIC_URL,
}


@dataclass(frozen=True)
class ARCEPACConfig:
    source: str = "UY_ARCE"
    country: str = "URY"
    page_size: int = 100
    max_pages: int = 50
    timeout: int = 45
    works_family_code: int = ARCE_PAC_WORKS_FAMILY_CODE


def _text(value):
    return "" if value is None else str(value).strip()


def _date(value):
    text = _text(value)
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text[:10]).date().isoformat()
    except ValueError:
        return ""


def _truthy(value):
    if value is True:
        return True
    if value in (False, None, "", 0):
        return False
    return _text(value).lower() in {"1", "true", "t", "yes", "si", "sí", "s"}


def _published(value):
    text = _text(value)
    if not text:
        return None
    candidate = text.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ARCE_PAC_TIMEZONE)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_arce_pac_procedure(row, *, today):
    """Normalize one future family-6 PAC row into canonical PROCUREMENT_PLAN."""
    if not isinstance(row, dict) or _truthy(row.get("dadoBaja")):
        return None

    procedure_id = _text(row.get("id"))
    plan = row.get("planAnual") if isinstance(row.get("planAnual"), dict) else {}
    plan_id = _text(plan.get("id"))
    buyer = _text(plan.get("descUnidadCompra") or plan.get("descUnidadEjecutora") or plan.get("descInciso"))
    title = _text(row.get("objetoCompra"))
    start_date = _date(row.get("periodoConvFechaIni"))
    end_date = _date(row.get("periodoConvFechaFin"))
    current = today.isoformat() if hasattr(today, "isoformat") else _date(today)

    if not procedure_id or not plan_id or not buyer or not title or not start_date or not current:
        return None
    if start_date < current:
        return None
    if end_date and end_date < start_date:
        return None

    published_at = _published(row.get("fechaHoraPublicacion") or plan.get("fechaPublicacion"))
    updated_at = _published(row.get("fechaHoraUltimaActualizacion"))
    source_reference = f"pac:{procedure_id}"
    return {
        "source": "UY_ARCE",
        "signal_type": "PROCUREMENT_PLAN",
        "external_id": source_reference,
        "title": title,
        "description": title,
        "buyer": buyer,
        "country": "URY",
        "value": "",
        "currency": "",
        "deadline": "",
        "target_date": start_date,
        "planned_window_end": end_date,
        "publication_date": (published_at or "")[:10],
        "published_at": published_at,
        "source_updated_at": updated_at,
        "url": ARCE_PAC_PUBLIC_URL,
        "taxonomy": "ARCE_PAC_FAMILY",
        "category_code": str(ARCE_PAC_WORKS_FAMILY_CODE),
        "category_label": ARCE_PAC_WORKS_FAMILY_LABEL,
        "contract_type": "works",
        "source_reference": source_reference,
        "plan_id": plan_id,
        "plan_year": plan.get("anioPlan"),
        "procurement_type_code": row.get("codTipoCompra"),
        "procurement_type": _text(row.get("descTipoCompra")),
        "procurement_subtype_code": row.get("codSubtipoCompra"),
        "procurement_subtype": _text(row.get("descSubtipoCompra")),
        "buyer_agency_code": plan.get("codInciso"),
        "buyer_unit_code": plan.get("codUnidadCompra"),
        "executing_unit_code": plan.get("codUnidadEjecutora"),
        "license": ARCE_LICENSE,
        "attribution": ARCE_ATTRIBUTION,
        "source_dataset": "ARCE — Plan Anual de Compras",
        "source_api_url": urljoin(ARCE_PAC_PUBLIC_URL, ARCE_PAC_SEARCH_PATH.lstrip("/")),
    }


class ARCEPACConnector:
    def __init__(self, config=ARCEPACConfig(), *, session=None):
        self.config = config
        if _text(config.source).upper() != "UY_ARCE":
            raise RuntimeError("ARCE PAC connector source identity must remain UY_ARCE")
        if _text(config.country).upper() != "URY":
            raise RuntimeError("ARCE PAC connector country identity must remain URY")
        if int(config.works_family_code) != ARCE_PAC_WORKS_FAMILY_CODE:
            raise RuntimeError("ARCE PAC only verified construction family code 6")
        if not 1 <= int(config.page_size) <= 100:
            raise RuntimeError("ARCE PAC page_size must stay within the live-verified bound 1..100")
        if not 1 <= int(config.max_pages) <= 50:
            raise RuntimeError("ARCE PAC max_pages must stay within the bounded contract 1..50")
        if not 1 <= int(config.timeout) <= 120:
            raise RuntimeError("ARCE PAC timeout must stay within 1..120 seconds")
        self.session = session or requests.Session()
        self._api_url = None

    def _get(self, url, *, params=None, accept="application/json"):
        headers = dict(ARCE_PAC_HEADERS)
        headers["Accept"] = accept
        response = self.session.get(url, params=params, headers=headers, timeout=self.config.timeout)
        response.raise_for_status()
        return response

    def _bootstrap(self):
        self._get(ARCE_PAC_PUBLIC_URL, accept="text/html,application/xhtml+xml")
        config = self._get(ARCE_PAC_CONFIG_URL).json()
        if not isinstance(config, dict):
            raise RuntimeError("UY_ARCE PAC public config is not a mapping")
        api_base = _text(config.get("apiUrl")).rstrip("/")
        if api_base != ARCE_PAC_EXPECTED_API_BASE:
            raise RuntimeError(f"UY_ARCE PAC unexpected apiUrl {api_base!r}")
        api_url = urljoin(ARCE_PAC_PUBLIC_URL, api_base + "/").rstrip("/")
        parsed = urlparse(api_url)
        if parsed.scheme != "https" or parsed.netloc != "www.comprasestatales.gub.uy" or parsed.path != ARCE_PAC_EXPECTED_API_BASE:
            raise RuntimeError("UY_ARCE PAC resolved API origin/path is outside the approved official contract")
        self._api_url = api_url
        return api_url

    def _rows(self, *, today):
        api_url = self._api_url or self._bootstrap()
        page_size = int(self.config.page_size)
        max_pages = int(self.config.max_pages)
        current = today.isoformat()
        rows = []
        expected_pages = None

        for page in range(max_pages):
            response = self._get(
                api_url + ARCE_PAC_SEARCH_PATH,
                params={
                    "sort": "periodoConvFechaIni,asc",
                    "page": page,
                    "size": page_size,
                    "codFamilia": ARCE_PAC_WORKS_FAMILY_CODE,
                    "fechaConvocatoriaFinDesde": current,
                },
            )
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("content"), list):
                raise RuntimeError("UY_ARCE PAC search returned an invalid paginated JSON contract")
            try:
                total_pages = int(payload.get("totalPages"))
                returned_page = int(payload.get("number"))
            except (TypeError, ValueError):
                raise RuntimeError("UY_ARCE PAC search omitted valid page metadata") from None
            if returned_page != page:
                raise RuntimeError(f"UY_ARCE PAC returned page {returned_page} while page {page} was requested")
            if total_pages < 0:
                raise RuntimeError("UY_ARCE PAC returned a negative totalPages")
            if total_pages > max_pages:
                raise RuntimeError(
                    f"UY_ARCE PAC requires {total_pages} pages, above max_pages={max_pages}; snapshot completeness not proven"
                )
            if expected_pages is None:
                expected_pages = total_pages
            elif total_pages != expected_pages:
                raise RuntimeError("UY_ARCE PAC totalPages changed during bounded snapshot")

            batch = [row for row in payload["content"] if isinstance(row, dict)]
            if page < total_pages and not batch:
                raise RuntimeError("UY_ARCE PAC returned an empty page before snapshot completion")
            rows.extend(batch)
            if page + 1 >= total_pages:
                return rows

        raise RuntimeError(
            f"UY_ARCE PAC reached max_pages={max_pages}; snapshot completeness not proven"
        )

    def fetch_snapshot(self, *, now=None):
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        local_today = current.astimezone(ARCE_PAC_TIMEZONE).date()
        rows = self._rows(today=local_today)
        signals = {}
        for row in rows:
            item = normalize_arce_pac_procedure(row, today=local_today)
            if item is not None:
                signals[item["external_id"]] = item
        return list(signals.values())


def fetch_arce_procurement_plans(*, now=None, connector=None):
    client = connector or ARCEPACConnector()
    return client.fetch_snapshot(now=now)
