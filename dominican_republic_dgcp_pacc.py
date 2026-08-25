"""Dominican Republic DGCP PACC construction early-signal connector.

The official `/pacc/adquisiciones` endpoint exposes the annual procurement plan
with a publisher-controlled `objeto_adquisicion` field. DGCP's PACC guidance
defines that field as a controlled choice including `Obras`, so construction
admission is taxonomy-based rather than keyword-based.

The endpoint does not expose a reliable row-level modified timestamp or an
incremental cursor. Live validation on 2026-08-25 showed that the official API
publishes top-level page/limit/pages/totalResults metadata and accepts limit=1000.
The connector therefore performs a bounded annual snapshot, validates that
metadata across every page, and fails closed if completeness cannot be proven.
Runtime composition is responsible for avoiding more than one PACC snapshot per
Dominican calendar day.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import math
import unicodedata
from zoneinfo import ZoneInfo

import requests

from dominican_republic_dgcp import (
    DGCP_API_ROOT,
    DGCP_ATTRIBUTION,
    DGCP_LICENSE,
    DGCP_PORTAL_URL,
)


DGCP_PACC_ACQUISITIONS_URL = f"{DGCP_API_ROOT}/pacc/adquisiciones"
DGCP_TIMEZONE = ZoneInfo("America/Santo_Domingo")


@dataclass(frozen=True)
class DGCPPACCConfig:
    source: str = "DO_DGCP"
    country: str = "DOM"
    page_size: int = 1000
    max_pages: int = 60
    timeout: int = 45


def _plain(value):
    text = str(value or "").strip().lower()
    return "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )


def _amount(value):
    if value in (None, ""):
        return ""
    text = str(value).strip().replace(",", "")
    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError):
        return ""
    if not amount.is_finite() or amount < 0:
        return ""
    return format(amount, "f")


def _date(value):
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date().isoformat()
        except ValueError:
            return ""


def _version(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _metadata_int(envelope, key):
    if key not in envelope:
        return None
    try:
        return int(envelope.get(key))
    except (TypeError, ValueError):
        raise RuntimeError(f"DGCP PACC pagination field {key} is not an integer") from None


def normalize_dgcp_pacc_acquisition(row):
    """Return one planned works acquisition as a canonical PROCUREMENT_PLAN."""
    if not isinstance(row, dict):
        return None
    if _plain(row.get("objeto_adquisicion")) != "obras":
        return None

    acquisition_id = str(row.get("id_adquisicion") or "").strip()
    pacc_id = str(row.get("uid_pacc") or "").strip()
    buyer = str(row.get("unidad_compra") or "").strip()
    if not acquisition_id or not pacc_id or not buyer:
        return None

    target_date = _date(row.get("fecha_inicio_proceso_compra"))
    if not target_date:
        return None

    title = str(row.get("descripcion") or row.get("finalidad") or "").strip()
    description = str(row.get("finalidad") or row.get("descripcion") or "").strip()
    value = _amount(row.get("valor_presupuestado"))
    external_id = f"{pacc_id}:{acquisition_id}"

    return {
        "source": "DO_DGCP",
        "signal_type": "PROCUREMENT_PLAN",
        "external_id": external_id,
        "title": title or f"PACC works acquisition {acquisition_id}",
        "description": description,
        "buyer": buyer,
        "country": "DOM",
        "value": value,
        "currency": "DOP" if value else "",
        "target_date": target_date,
        "publication_date": "",
        "published_at": "",
        "source_updated_at": "",
        "url": DGCP_PORTAL_URL,
        "taxonomy": "DGCP_PACC_OBJECT",
        "category_code": "OBRAS",
        "contract_type": "works",
        "source_reference": external_id,
        "pacc_id": pacc_id,
        "acquisition_id": acquisition_id,
        "procurement_method": str(row.get("modalidad_adquisicion") or "").strip(),
        "mipyme": row.get("dirigido_mipymes"),
        "mipyme_women": row.get("dirigido_mipymes_mujeres"),
        "pacc_version": row.get("version"),
        "license": DGCP_LICENSE,
        "attribution": DGCP_ATTRIBUTION,
        "source_dataset": "DGCP API — PACC adquisiciones",
        "source_api_url": DGCP_PACC_ACQUISITIONS_URL,
    }


class DGCPPACCConnector:
    def __init__(self, config=DGCPPACCConfig(), *, session=None):
        self.config = config
        if str(config.source or "").strip().upper() != "DO_DGCP":
            raise RuntimeError("DGCP PACC source identity must remain DO_DGCP")
        if str(config.country or "").strip().upper() != "DOM":
            raise RuntimeError("DGCP PACC country identity must remain DOM")
        if not 1 <= int(config.page_size) <= 1000:
            raise RuntimeError("DGCP PACC page_size must stay within the live-verified bound 1..1000")
        if not 1 <= int(config.max_pages) <= 100:
            raise RuntimeError("DGCP PACC max_pages must stay within the bounded contract 1..100")
        if not 1 <= int(config.timeout) <= 120:
            raise RuntimeError("DGCP PACC timeout must stay within 1..120 seconds")
        self.session = session or requests.Session()

    def _rows(self, *, year):
        page_size = int(self.config.page_size)
        max_pages = int(self.config.max_pages)
        all_rows = []
        expected_pages = None
        expected_total = None
        metadata_seen = None

        for page in range(1, max_pages + 1):
            response = self.session.get(
                DGCP_PACC_ACQUISITIONS_URL,
                params={"page": page, "limit": page_size, "año": int(year)},
                headers={
                    "Accept": "application/json",
                    "User-Agent": "ObraSignal DGCP PACC connector/1.0 (+official open-data ingestion)",
                },
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            envelope = response.json()
            if not isinstance(envelope, dict) or envelope.get("hasError") is not False or envelope.get("code") != 200:
                raise RuntimeError("DGCP PACC returned an invalid API envelope")
            payload = envelope.get("payload")
            rows = payload.get("content") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise RuntimeError("DGCP PACC payload has no content list")

            present = [key in envelope for key in ("page", "limit", "pages", "totalResults")]
            if any(present) and not all(present):
                raise RuntimeError("DGCP PACC returned incomplete pagination metadata")
            has_metadata = all(present)
            if metadata_seen is None:
                metadata_seen = has_metadata
            elif metadata_seen != has_metadata:
                raise RuntimeError("DGCP PACC pagination metadata disappeared during snapshot")

            if has_metadata:
                returned_page = _metadata_int(envelope, "page")
                returned_limit = _metadata_int(envelope, "limit")
                pages = _metadata_int(envelope, "pages")
                total = _metadata_int(envelope, "totalResults")
                if returned_page != page:
                    raise RuntimeError(
                        f"DGCP PACC returned page={returned_page} while page={page} was requested"
                    )
                if returned_limit != page_size:
                    raise RuntimeError(
                        f"DGCP PACC returned limit={returned_limit} while limit={page_size} was requested"
                    )
                if pages < 0 or total < 0:
                    raise RuntimeError("DGCP PACC returned negative pagination metadata")
                calculated_pages = math.ceil(total / page_size) if total else 0
                if pages != calculated_pages:
                    raise RuntimeError(
                        f"DGCP PACC pages={pages} is inconsistent with totalResults={total} and limit={page_size}"
                    )
                if pages > max_pages:
                    raise RuntimeError(
                        f"DGCP PACC requires pages={pages}, above max_pages={max_pages}; snapshot completeness not proven"
                    )
                if expected_pages is None:
                    expected_pages = pages
                    expected_total = total
                elif pages != expected_pages or total != expected_total:
                    raise RuntimeError("DGCP PACC pagination totals changed during bounded snapshot")

            all_rows.extend(rows)

            if has_metadata:
                if expected_pages == 0:
                    if rows or expected_total != 0:
                        raise RuntimeError("DGCP PACC zero-page metadata conflicts with returned content")
                    return all_rows
                if page >= expected_pages:
                    if len(all_rows) != expected_total:
                        raise RuntimeError(
                            f"DGCP PACC fetched {len(all_rows)} rows but totalResults={expected_total}; snapshot completeness not proven"
                        )
                    return all_rows
                if not rows:
                    raise RuntimeError("DGCP PACC returned an empty page before snapshot completion")
            elif len(rows) < page_size:
                return all_rows

        raise RuntimeError(
            f"DGCP PACC reached max_pages={max_pages} for year={year}; snapshot completeness not proven"
        )

    def fetch_snapshot(self, *, year=None, now=None):
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        local_today = current.astimezone(DGCP_TIMEZONE).date()
        selected_year = int(year or local_today.year)
        today = local_today.isoformat()
        rows = self._rows(year=selected_year)
        by_identity = {}
        for row in rows:
            item = normalize_dgcp_pacc_acquisition(row)
            if not item or item["target_date"] < today:
                continue
            identity = item["external_id"]
            existing = by_identity.get(identity)
            if existing is None or _version(item.get("pacc_version")) > _version(existing.get("pacc_version")):
                by_identity[identity] = item
        return list(by_identity.values())


def fetch_dgcp_procurement_plans(*, year=None, now=None, connector=None):
    client = connector or DGCPPACCConnector()
    return client.fetch_snapshot(year=year, now=now)
