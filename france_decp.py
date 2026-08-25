"""France DECP construction-contract connector.

The Direction des Affaires juridiques (DAJ) publishes the national consolidated
Données Essentielles de la Commande Publique (DECP) dataset through the public
Explore API.  DECP is post-award/contract data, not tender discovery; this module
therefore emits canonical ``CONTRACT`` signals and never legacy tender rows.

Construction admission uses the publisher-native CPV main code (division 45).
Contract identity is the publisher ``id``.  Later DECP modifications update that
same identity so re-ingestion remains idempotent in the canonical Signal store.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
import time
from urllib.parse import urlparse

import requests


SOURCE = "FR_DECP"
COUNTRY = "FRA"
DECP_DATASET = "decp-2022-marches-valides"
DECP_API = (
    "https://www.data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
    f"{DECP_DATASET}/records"
)
DECP_HUMAN = f"https://www.data.economie.gouv.fr/explore/dataset/{DECP_DATASET}/"
DECP_ATTRIBUTION = "DAJ — Données Essentielles de la Commande Publique (DECP)"
DECP_LICENSE = "Licence Ouverte / Open Licence v2.0"
DECP_PAGE_SIZE = max(1, min(100, int(os.getenv("FR_DECP_PAGE_SIZE", "100"))))
DECP_MAX_PAGES = max(1, min(100, int(os.getenv("FR_DECP_MAX_PAGES", "50"))))
DECP_BOOTSTRAP_DAYS = max(1, min(90, int(os.getenv("FR_DECP_BOOTSTRAP_DAYS", "14"))))
DECP_OVERLAP_DAYS = max(0, min(7, int(os.getenv("FR_DECP_OVERLAP_DAYS", "2"))))
DECP_TIMEOUT = max(5, min(60, int(os.getenv("FR_DECP_TIMEOUT", "30"))))
DECP_RETRIES = max(0, min(4, int(os.getenv("FR_DECP_RETRIES", "2"))))
_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal France DECP connector/1.0 (+official public-data ingestion)",
}


def _text(value):
    return "" if value is None else " ".join(str(value).split())


def _field(row, *names):
    if not isinstance(row, dict):
        return None
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


def _iso_day(value):
    text = _text(value)
    if not text:
        return ""
    for candidate in (text[:10], text):
        try:
            return date.fromisoformat(candidate).isoformat()
        except ValueError:
            pass
    return ""


def _cursor_day(value):
    text = _text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise RuntimeError(f"invalid {SOURCE} cursor") from exc


def _cpv(value):
    return _text(value).replace(" ", "")


def _is_construction_cpv(value):
    code = _cpv(value)
    return len(code) >= 2 and code[:2] == "45" and code[0].isdigit()


def _safe_source_url(value):
    """Preserve only publisher HTTPS links; never forward arbitrary record URLs."""
    text = _text(value)
    if not text:
        return DECP_HUMAN
    parsed = urlparse(text)
    if parsed.scheme == "https" and parsed.hostname in {
        "www.data.economie.gouv.fr",
        "data.economie.gouv.fr",
        "www.data.gouv.fr",
        "data.gouv.fr",
    }:
        return text
    return DECP_HUMAN


def _buyer(row):
    return _text(_field(row, "acheteur_nom", "acheteur.nom", "nomacheteur"))


def _buyer_id(row):
    return _text(_field(row, "acheteur_id", "acheteur.id", "idacheteur"))


def _supplier(row):
    values = []
    for i in (1, 2, 3):
        name = _text(
            _field(
                row,
                f"titulaire_denominationsociale_{i}",
                f"titulaire_denominationSociale_{i}",
            )
        )
        identifier = _text(_field(row, f"titulaire_id_{i}"))
        kind = _text(
            _field(row, f"titulaire_typeidentifiant_{i}", f"titulaire_typeIdentifiant_{i}")
        )
        if name or identifier:
            item = " — ".join(x for x in (name, f"{kind} {identifier}".strip()) if x)
            if item and item not in values:
                values.append(item)
    return " | ".join(values)


def _place(row):
    return _text(
        _field(
            row,
            "lieuexecution_nom",
            "lieuExecution.nom",
            "lieu_execution_nom",
        )
    )


def _source_updated_day(row):
    candidates = [
        _iso_day(_field(row, "datepublicationdonneesmodification", "datePublicationDonneesModification")),
        _iso_day(_field(row, "datenotificationmodification", "dateNotificationModification")),
        _iso_day(_field(row, "datepublicationdonnees", "datePublicationDonnees")),
        _iso_day(_field(row, "datenotification", "dateNotification")),
    ]
    return max((x for x in candidates if x), default="")


def _normalize(row):
    contract_id = _text(_field(row, "id"))
    cpv = _cpv(_field(row, "codecpv", "codeCPV"))
    if not _is_construction_cpv(cpv):
        return None
    updated = _source_updated_day(row)
    if not contract_id or not updated:
        raise RuntimeError(f"{SOURCE} construction record missing id/update date; cursor not advanced")

    title = _text(_field(row, "objet")) or contract_id
    notification = _iso_day(_field(row, "datenotification", "dateNotification"))
    amount = _text(_field(row, "montant"))
    supplier = _supplier(row)
    buyer_id = _buyer_id(row)
    modification = bool(_field(row, "booleanmodification", "booleanModification"))
    duration = _text(_field(row, "dureemois", "dureeMois"))
    procedure = _text(_field(row, "procedure"))
    nature = _text(_field(row, "nature"))
    source_name = _text(_field(row, "source"))
    source_url = _safe_source_url(_field(row, "url", "source_url"))

    description_bits = []
    if nature:
        description_bits.append(nature)
    if procedure:
        description_bits.append(procedure)
    if supplier:
        description_bits.append(f"Titulaire: {supplier}")
    if duration:
        description_bits.append(f"Durée: {duration} mois")

    return {
        "source": SOURCE,
        "signal_type": "CONTRACT",
        "external_id": contract_id,
        "title": title,
        "description": " | ".join(description_bits) or title,
        "buyer": _buyer(row),
        "buyer_id": buyer_id,
        "country": COUNTRY,
        "value": amount,
        "currency": "EUR" if amount else "",
        "deadline": "",
        "target_date": notification,
        "publication_date": updated,
        "published_at": f"{updated}T00:00:00Z",
        "source_updated_at": f"{updated}T00:00:00Z",
        "url": source_url,
        "taxonomy": "CPV",
        "category_code": cpv,
        "cpv": cpv,
        "place": _place(row),
        "source_reference": contract_id,
        "supplier": supplier,
        "procedure": procedure,
        "nature": nature,
        "duration_months": duration,
        "has_modification": modification,
        "publisher_dataset": DECP_DATASET,
        "publisher_source": source_name,
        "attribution": DECP_ATTRIBUTION,
        "license": DECP_LICENSE,
    }


def _request_page(session, *, offset, since):
    params = {
        "select": "*",
        "where": f'startswith(codecpv, "45") and datepublicationdonnees >= date\'{since.isoformat()}\'',
        "order_by": "datepublicationdonnees desc",
        "limit": DECP_PAGE_SIZE,
        "offset": int(offset),
        "timezone": "UTC",
        "include_links": "false",
        "include_app_metas": "false",
    }
    last_error = None
    for attempt in range(DECP_RETRIES + 1):
        try:
            response = session.get(DECP_API, params=params, headers=_HEADERS, timeout=DECP_TIMEOUT)
            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt >= DECP_RETRIES:
                    response.raise_for_status()
                retry_after = response.headers.get("Retry-After", "")
                try:
                    delay = min(5.0, max(0.0, float(retry_after))) if retry_after else min(2.0, 0.5 * (2**attempt))
                except ValueError:
                    delay = min(2.0, 0.5 * (2**attempt))
                time.sleep(delay)
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                raise RuntimeError(f"{SOURCE} unexpected response schema")
            return payload
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            last_error = exc
            if attempt >= DECP_RETRIES:
                raise
            time.sleep(min(2.0, 0.5 * (2**attempt)))
    raise RuntimeError(f"{SOURCE} request failed") from last_error


def fetch_france_decp_contracts(*, watermark=None, session=None, today=None):
    """Return ``(construction CONTRACT signals, cursor)`` from official DECP.

    The cursor is publisher-derived.  We deliberately overlap recent days so late
    republications/modifications are re-observed and idempotently update the same
    contract identity instead of relying on wall-clock success time.
    """
    current = today or datetime.now(timezone.utc).date()
    previous = _cursor_day(watermark)
    since = (previous - timedelta(days=DECP_OVERLAP_DAYS)) if previous else (current - timedelta(days=DECP_BOOTSTRAP_DAYS))
    client = session or requests.Session()

    observations = []
    newest = previous.isoformat() if previous else ""
    offset = 0
    exhausted = False
    for _ in range(DECP_MAX_PAGES):
        payload = _request_page(client, offset=offset, since=since)
        batch = payload.get("results", [])
        for row in batch:
            if not isinstance(row, dict):
                raise RuntimeError(f"{SOURCE} result is not an object; cursor not advanced")
            record = _normalize(row)
            if record is None:
                continue
            observations.append(record)
            record_day = record["source_updated_at"][:10]
            if not newest or record_day > newest:
                newest = record_day
        offset += len(batch)
        total = payload.get("total_count")
        if not batch or len(batch) < DECP_PAGE_SIZE or (isinstance(total, int) and offset >= total):
            exhausted = True
            break

    if not exhausted:
        raise RuntimeError(f"{SOURCE} pagination cap reached; cursor not advanced")

    # Stable identity within one fetch: later duplicate representations win.
    by_id = {}
    for record in observations:
        existing = by_id.get(record["external_id"])
        if existing is None or record["source_updated_at"] >= existing["source_updated_at"]:
            by_id[record["external_id"]] = record
    rows = sorted(by_id.values(), key=lambda row: (row["source_updated_at"], row["external_id"]))
    return rows, (newest or watermark)
