"""Brazil PNCP construction procurement-plan connector.

National discovery uses PNCP's own public PCA search service, the same service
used by the public portal. Hydration uses documented PNCP open consultation
endpoints. Only publisher-native PCA categories 3/4/8 (works / engineering
services / works and engineering services) can become ObraSignal signals.

This connector intentionally emits ``PROCUREMENT_PLAN`` signals, never legacy
TENDER rows. ``dataDesejada`` is a future need/target date, not a bid deadline.
The initial sync is bounded and recent-only; no historical-completeness claim is
made.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time
from typing import Mapping
from urllib.parse import urljoin

import requests


SOURCE = "BR_PNCP_PCA"
COUNTRY = "BRA"
SIGNAL_TYPE = "PROCUREMENT_PLAN"
SEARCH_URL = "https://pncp.gov.br/api/search/"
API_BASE = "https://pncp.gov.br/api/pncp/v1"
APP_BASE = "https://pncp.gov.br/app/"
MANUAL_URL = "https://pncp.gov.br/manual/pt-br/latest/singlehtml/"
OPEN_DATA_URL = "https://www.gov.br/pncp/pt-br/acesso-a-informacao/dados-abertos"
ATTRIBUTION = "Portal Nacional de Contratações Públicas (PNCP), Brasil"
DATASET = "PNCP — Plano de Contratações Anual (PCA)"

WORK_CATEGORY_IDS = frozenset({"3", "4", "8"})
SEARCH_PAGE_SIZE = 100
SEARCH_MAX_PAGES = 20
UNIT_PAGE_SIZE = 100
UNIT_MAX_PAGES = 10
ITEM_PAGE_SIZE = 100
ITEM_MAX_PAGES_PER_CATEGORY = 30
INITIAL_LOOKBACK_HOURS = 12
OVERLAP_MINUTES = 30
HTTP_TIMEOUT_SECONDS = 40
HTTP_MAX_ATTEMPTS = 5
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "ObraSignal Brazil PNCP PCA connector/1.0 (+official public-data ingestion)",
    "Referer": "https://pncp.gov.br/app/pca",
    # PNCP has intermittently closed reused keep-alive connections during live
    # validation. Fresh connections are slower but materially reduce ambiguity
    # and keep retry behavior bounded and explicit.
    "Connection": "close",
}


def _text(value) -> str:
    return "" if value is None else " ".join(str(value).split())


def _publisher_dt(value, *, label="timestamp") -> datetime:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError(f"{SOURCE} missing {label}")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError(f"{SOURCE} invalid {label}: {text!r}") from exc
    # PNCP currently emits naive local publisher timestamps. Keep that clock
    # domain for cursor comparisons instead of inventing a timezone. If a future
    # payload becomes offset-aware, normalize it to UTC then drop tzinfo so all
    # comparisons remain in one deterministic domain.
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _cursor_text(value: datetime) -> str:
    return value.isoformat(timespec="microseconds")


def _retry_delay(attempt: int) -> int:
    """Return bounded exponential backoff seconds after a failed attempt."""
    return min(2 ** int(attempt), 8)


def _request_json(url, *, params=None, allow_empty=False):
    """Fetch JSON with bounded retries.

    ``allow_empty`` exists only for publisher contracts where a successful empty
    body has been live-proven to mean an empty result set. Callers must opt in
    explicitly; discovery and identity endpoints remain strict.
    """
    last_error = None
    for attempt in range(HTTP_MAX_ATTEMPTS):
        try:
            response = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            if response.status_code in _RETRYABLE_STATUS:
                last_error = RuntimeError(f"HTTP {response.status_code}")
                if attempt + 1 < HTTP_MAX_ATTEMPTS:
                    time.sleep(_retry_delay(attempt))
                    continue
            response.raise_for_status()
            if not response.content:
                if allow_empty:
                    return None
                raise RuntimeError(f"{SOURCE} returned an empty response for {url}")
            try:
                return response.json()
            except ValueError as exc:
                raise RuntimeError(f"{SOURCE} returned non-JSON content for {url}") from exc
        except (requests.RequestException, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 < HTTP_MAX_ATTEMPTS:
                time.sleep(_retry_delay(attempt))
                continue
    raise RuntimeError(f"{SOURCE} request failed after bounded retries: {last_error}")


def _list_payload(payload, *, context):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "data", "content", "results", "resultados"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    raise RuntimeError(f"{SOURCE} unexpected {context} response envelope")


def _search_page(page: int):
    payload = _request_json(
        SEARCH_URL,
        params={
            "q": "",
            "tipos_documento": "pcaorgao",
            "ordenacao": "-data",
            "pagina": int(page),
            "tam_pagina": SEARCH_PAGE_SIZE,
        },
    )
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise RuntimeError(f"{SOURCE} unexpected national search envelope")
    try:
        total = int(payload.get("total"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{SOURCE} national search missing total") from exc
    if total < 0:
        raise RuntimeError(f"{SOURCE} national search invalid total")
    return payload["items"], total


def _search_identity(row: Mapping):
    record_id = _text(row.get("id"))
    cnpj = _text(row.get("orgao_cnpj"))
    year = _text(row.get("ano"))
    update_text = _text(row.get("data_atualizacao_pncp"))
    if not record_id or not cnpj or not year or not update_text:
        raise RuntimeError(f"{SOURCE} national search row missing id/cnpj/ano/update")
    update = _publisher_dt(update_text, label="data_atualizacao_pncp")
    return record_id, cnpj, year, update


def _scan_recent_once(cutoff: datetime):
    """Return a bounded, recent-first snapshot through ``cutoff``.

    The scan fails closed when its hard page bound is reached before crossing the
    cutoff, so a cursor can never skip an unobserved backlog.
    """
    selected = []
    seen_ids = set()
    expected_total = None
    previous_update = None
    crossed_cutoff = False

    for page in range(1, SEARCH_MAX_PAGES + 1):
        rows, total = _search_page(page)
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise RuntimeError(f"{SOURCE} national search total drifted during scan")
        if not rows:
            crossed_cutoff = True
            break

        for raw in rows:
            if not isinstance(raw, Mapping):
                raise RuntimeError(f"{SOURCE} national search row is not an object")
            record_id, cnpj, year, updated = _search_identity(raw)
            if record_id in seen_ids:
                raise RuntimeError(f"{SOURCE} duplicate national search id across pages")
            seen_ids.add(record_id)
            if previous_update is not None and updated > previous_update:
                raise RuntimeError(f"{SOURCE} national search is not recent-first")
            previous_update = updated

            if updated < cutoff:
                crossed_cutoff = True
                break
            selected.append(
                {
                    "id": record_id,
                    "cnpj": cnpj,
                    "year": year,
                    "updated": updated,
                    "updated_raw": _text(raw.get("data_atualizacao_pncp")),
                    "published_raw": _text(raw.get("data_publicacao_pncp")),
                    "buyer": _text(raw.get("orgao_nome")),
                    "value_global": raw.get("valor_global"),
                    "cancelled": bool(raw.get("cancelado")),
                    "item_url": _text(raw.get("item_url")),
                }
            )
        if crossed_cutoff:
            break
        if len(rows) < SEARCH_PAGE_SIZE:
            crossed_cutoff = True
            break

    if not crossed_cutoff:
        raise RuntimeError(f"{SOURCE} recent backlog exceeds bounded national scan")
    return selected


def _stable_recent_snapshot(watermark=None):
    first_page, _ = _search_page(1)
    if not first_page:
        raise RuntimeError(f"{SOURCE} national search unexpectedly returned no PCA rows")
    newest = _search_identity(first_page[0])[3]

    if watermark:
        cursor = _publisher_dt(watermark, label="cursor")
        # A future cursor indicates corrupt state or a source clock reversal.
        if cursor > newest + timedelta(minutes=OVERLAP_MINUTES):
            raise RuntimeError(f"{SOURCE} cursor is ahead of publisher data")
        cutoff = cursor - timedelta(minutes=OVERLAP_MINUTES)
    else:
        cutoff = newest - timedelta(hours=INITIAL_LOOKBACK_HOURS)

    # Reuse none of the first-page data: both bounded scans independently prove
    # a stable offset snapshot. The extra request is deliberate safety overhead.
    first = _scan_recent_once(cutoff)
    second = _scan_recent_once(cutoff)

    def fingerprint(rows):
        return tuple(
            (row["id"], row["cnpj"], row["year"], _cursor_text(row["updated"]))
            for row in rows
        )

    if fingerprint(first) != fingerprint(second):
        raise RuntimeError(f"{SOURCE} national search drifted between stable scans")
    return first, newest, cutoff


def _consolidated_units(cnpj: str, year: str):
    url = f"{API_BASE}/orgaos/{cnpj}/pca/{year}/consolidado/unidades"
    out = []
    seen = set()
    for page in range(1, UNIT_MAX_PAGES + 1):
        payload = _request_json(
            url,
            params={"pagina": page, "tamanhoPagina": UNIT_PAGE_SIZE},
        )
        rows = _list_payload(payload, context="consolidated PCA")
        if not rows:
            return out
        for row in rows:
            if not isinstance(row, Mapping):
                raise RuntimeError(f"{SOURCE} consolidated PCA row is not an object")
            row_cnpj = _text(row.get("cnpj"))
            row_year = _text(row.get("anoPca"))
            seq = _text(row.get("sequencialPca"))
            control = _text(row.get("numeroControlePNCP"))
            update_raw = _text(row.get("dataAtualizacao"))
            if row_cnpj != cnpj or row_year != year:
                raise RuntimeError(f"{SOURCE} consolidated PCA identity mismatch")
            if not seq or not control or not update_raw:
                raise RuntimeError(f"{SOURCE} consolidated PCA missing sequence/control/update")
            identity = (seq, control)
            if identity in seen:
                raise RuntimeError(f"{SOURCE} duplicate consolidated PCA identity")
            seen.add(identity)
            normalized = dict(row)
            normalized["_updated"] = _publisher_dt(update_raw, label="PCA unit dataAtualizacao")
            out.append(normalized)
        if len(rows) < UNIT_PAGE_SIZE:
            return out
    raise RuntimeError(f"{SOURCE} consolidated PCA exceeds bounded pagination")


def _category_items(cnpj: str, year: str, sequence: str, category: str):
    if category not in WORK_CATEGORY_IDS:
        raise ValueError("unsupported PNCP PCA construction category")
    url = f"{API_BASE}/orgaos/{cnpj}/pca/{year}/{sequence}/itens"
    out = []
    seen_numbers = set()
    for page in range(1, ITEM_MAX_PAGES_PER_CATEGORY + 1):
        payload = _request_json(
            url,
            params={
                "categoria": category,
                "pagina": page,
                "tamanhoPagina": ITEM_PAGE_SIZE,
            },
            # Live PNCP validation on 2026-08-24 proved this filtered endpoint
            # may return HTTP 200 with an empty body when the category has zero
            # matches. This exception is deliberately scoped to category items.
            allow_empty=True,
        )
        if payload is None:
            return out
        rows = _list_payload(payload, context="PCA items")
        if not rows:
            return out
        for row in rows:
            if not isinstance(row, Mapping):
                raise RuntimeError(f"{SOURCE} PCA item is not an object")
            row_cnpj = _text(row.get("cnpj"))
            row_year = _text(row.get("anoPca"))
            row_sequence = _text(row.get("sequencialPca"))
            item_number = _text(row.get("numeroItem"))
            row_category = _text(row.get("categoriaItemPcaId") or row.get("categoriaItemPcaid"))
            if (row_cnpj, row_year, row_sequence) != (cnpj, year, sequence):
                raise RuntimeError(f"{SOURCE} PCA item identity mismatch")
            if row_category != category:
                raise RuntimeError(f"{SOURCE} PCA category filter was ignored or changed")
            if not item_number:
                raise RuntimeError(f"{SOURCE} PCA Works item missing numeroItem")
            if item_number in seen_numbers:
                raise RuntimeError(f"{SOURCE} duplicate PCA item within category pagination")
            seen_numbers.add(item_number)
            out.append(dict(row))
        if len(rows) < ITEM_PAGE_SIZE:
            return out
    raise RuntimeError(f"{SOURCE} PCA item category exceeds bounded pagination")


def _human_url(search_row, *, cnpj, year):
    path = _text(search_row.get("item_url"))
    if path:
        return urljoin(APP_BASE, path.lstrip("/"))
    return f"{APP_BASE}pca/{cnpj}/{year}"


def _value(value):
    return "" if value in (None, "") else str(value)


def _normalize_item(*, search_row, unit, item, category):
    cnpj = _text(unit.get("cnpj"))
    year = _text(unit.get("anoPca"))
    sequence = _text(unit.get("sequencialPca"))
    control = _text(unit.get("numeroControlePNCP"))
    item_number = _text(item.get("numeroItem"))
    if not control or not item_number:
        raise RuntimeError(f"{SOURCE} cannot construct publisher-native item identity")

    category_name = _text(item.get("categoriaItemPcaNome"))
    group_name = _text(item.get("grupoContratacaoNome"))
    description = _text(item.get("descricao"))
    classification_name = _text(item.get("classificacaoSuperiorNome"))
    title = group_name or description or classification_name or f"PCA {control} item {item_number}"
    source_updated_at = _text(item.get("dataAtualizacao")) or _text(unit.get("dataAtualizacao"))
    if not source_updated_at:
        raise RuntimeError(f"{SOURCE} Works item missing update timestamp")
    # Validate timestamp syntax even though the raw publisher value is retained.
    _publisher_dt(source_updated_at, label="PCA item dataAtualizacao")

    published_at = _text(item.get("dataPublicacaoPncp")) or _text(unit.get("dataPublicacaoPncp"))
    target_date = _text(item.get("dataDesejada"))
    buyer = _text(unit.get("razaoSocial")) or _text(search_row.get("buyer"))

    return {
        "source": SOURCE,
        "signal_type": SIGNAL_TYPE,
        "external_id": f"{control}:{item_number}",
        "country": COUNTRY,
        "title": title,
        "description": description or title,
        "buyer": buyer,
        "value": _value(item.get("valorTotal")),
        "currency": "BRL" if item.get("valorTotal") not in (None, "") else "",
        "deadline": "",
        "target_date": target_date,
        "publication_date": published_at[:10] if len(published_at) >= 10 else "",
        "published_at": published_at,
        "source_updated_at": source_updated_at,
        "url": _human_url(search_row, cnpj=cnpj, year=year),
        "taxonomy": "PNCP_PCA_CATEGORY",
        "category_code": category,
        "source_reference": control,
        "plan_control_id": control,
        "plan_sequence": sequence,
        "plan_year": year,
        "plan_cancelled": bool(search_row.get("cancelled")),
        "item_number": item_number,
        "category_name": category_name,
        "classification_catalog_id": item.get("classificacaoCatalogoId"),
        "classification_code": _text(item.get("classificacaoSuperiorCodigo")),
        "classification_name": classification_name,
        "catalog_id": item.get("catalogoId"),
        "catalog_name": _text(item.get("nomeCatalogo")),
        "catalog_item_code": _text(item.get("codigoItem")),
        "catalog_classification": _text(item.get("nomeClassificacao")),
        "pdm_code": _text(item.get("pdmCodigo")),
        "pdm_description": _text(item.get("pdmDescricao")),
        "procurement_group_code": _text(item.get("grupoContratacaoCodigo")),
        "procurement_group_name": group_name,
        "quantity": item.get("quantidade"),
        "unit_of_supply": _text(item.get("unidadeFornecimento")),
        "requesting_unit": _text(item.get("unidadeRequisitante")),
        "unit_code": _text(item.get("codigoUnidade")) or _text(unit.get("codigoUnidade")),
        "unit_name": _text(item.get("nomeUnidade")) or _text(unit.get("nomeUnidade")),
        "unit_value": item.get("valorUnitario"),
        "budget_year_value": item.get("valorOrcamentoExercicio"),
        "source_included_at": _text(item.get("dataInclusao")),
        "source_dataset": DATASET,
        "source_attribution": ATTRIBUTION,
        "source_manual": MANUAL_URL,
        "source_open_data": OPEN_DATA_URL,
    }


def fetch_brazil_pncp_pca_plans(*, watermark=None):
    """Fetch recent publisher-native construction PCA items.

    Returns ``(signals, cursor)`` for the generic incremental runtime. The cursor
    advances only after the caller atomically commits every returned Signal.
    """
    stable_rows, newest, cutoff = _stable_recent_snapshot(watermark)
    signals = []
    identities = {}

    for search_row in stable_rows:
        cnpj = search_row["cnpj"]
        year = search_row["year"]
        units = _consolidated_units(cnpj, year)
        changed_units = [unit for unit in units if unit["_updated"] >= cutoff]

        for unit in changed_units:
            sequence = _text(unit.get("sequencialPca"))
            control = _text(unit.get("numeroControlePNCP"))
            if not sequence or not control:
                raise RuntimeError(f"{SOURCE} changed PCA unit missing identity")

            for category in sorted(WORK_CATEGORY_IDS):
                for item in _category_items(cnpj, year, sequence, category):
                    normalized = _normalize_item(
                        search_row=search_row,
                        unit=unit,
                        item=item,
                        category=category,
                    )
                    identity = normalized["external_id"]
                    existing = identities.get(identity)
                    if existing is not None and existing != normalized:
                        raise RuntimeError(f"{SOURCE} conflicting duplicate PCA item identity")
                    if existing is None:
                        identities[identity] = normalized
                        signals.append(normalized)

    signals.sort(key=lambda row: (row.get("source_updated_at") or "", row["external_id"]))
    return signals, _cursor_text(newest)
