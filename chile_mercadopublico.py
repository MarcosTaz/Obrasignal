"""Chile Mercado Público construction-opportunity connector.

The official API is free/public-data infrastructure but normal machine use requires
an individual ChileCompra ticket. The public documentation ticket is test-only and
is never embedded in production runtime.

Publisher-native construction admission:
- ``Obras == 2`` (ChileCompra's explicit works flag), OR
- an item ``CodigoCategoria`` in UNSPSC segment 72 (building/construction/
  maintenance services).

This deliberately excludes construction-material supply tenders (for example
segment 30 steel beams) from the contractor-works feed even if the title contains
construction language.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import os
import time
from zoneinfo import ZoneInfo

import requests

SOURCE = "CL_MERCADOPUBLICO"
COUNTRY = "CHL"
API_BASE = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
PORTAL_BASE = "https://www.mercadopublico.cl"
ATTRIBUTION = "Dirección ChileCompra — Mercado Público"
TEST_TICKET = "F8537A18-6766-4DEF-9E59-426B4FEE2844"
CHILE_TZ = ZoneInfo("America/Santiago")
STATE_NAMES = {
    5: "Publicada",
    6: "Cerrada",
    7: "Desierta",
    8: "Adjudicada",
    18: "Revocada",
    19: "Suspendida",
}


class MercadoPublicoCredentialError(RuntimeError):
    pass


def _text(value):
    return str(value or "").strip()


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_dt(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CHILE_TZ)
    return parsed.astimezone(timezone.utc)


def _iso(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z") if value else None


def _items(tender):
    raw = (tender.get("Items") or {}).get("Listado") or []
    return raw if isinstance(raw, list) else []


def _is_construction(tender):
    if _int(tender.get("Obras")) == 2:
        return True
    for item in _items(tender):
        code = _text(item.get("CodigoCategoria"))
        if code.startswith("72"):
            return True
    return False


def _lifecycle(code):
    return {
        5: "open",
        6: "closed",
        7: "unsuccessful",
        8: "awarded",
        18: "revoked",
        19: "suspended",
    }.get(_int(code), "unknown")


def _observation(tender):
    if not _is_construction(tender):
        raise RuntimeError(f"{SOURCE} non-construction tender crossed admission gate; cursor not advanced")
    external_id = _text(tender.get("CodigoExterno"))
    if not external_id:
        raise RuntimeError(f"{SOURCE} construction tender missing CodigoExterno; cursor not advanced")
    fechas = tender.get("Fechas") or {}
    buyer = tender.get("Comprador") or {}
    items = _items(tender)
    codes = sorted({_text(i.get("CodigoCategoria")) for i in items if _text(i.get("CodigoCategoria"))})
    deadline = _parse_dt(fechas.get("FechaCierre") or tender.get("FechaCierre"))
    published = _parse_dt(fechas.get("FechaPublicacion"))
    status_code = _int(tender.get("CodigoEstado"))
    visible_amount = _int(tender.get("VisibilidadMonto")) == 1
    amount = tender.get("MontoEstimado") if visible_amount else None
    currency = _text(tender.get("Moneda")) if amount not in (None, "") else ""
    descriptions = [_text(i.get("Descripcion")) for i in items if _text(i.get("Descripcion"))]
    item_names = [_text(i.get("NombreProducto")) for i in items if _text(i.get("NombreProducto"))]
    return {
        "source": SOURCE,
        "external_id": external_id,
        "title": _text(tender.get("Nombre")),
        "description": _text(tender.get("Descripcion")) or " | ".join(descriptions),
        "buyer": _text(buyer.get("NombreOrganismo")),
        "buyer_unit": _text(buyer.get("NombreUnidad")),
        "country": COUNTRY,
        "cpv": "",
        "taxonomy": "UNSPSC",
        "category_code": "|".join(codes),
        "cpv_codes": [],
        "unspsc_codes": codes,
        "value": str(amount) if amount not in (None, "") else "",
        "currency": currency,
        "deadline": _iso(deadline),
        "publication_date": _text(fechas.get("FechaPublicacion"))[:10],
        "published_at": _iso(published),
        "source_updated_at": None,
        "url": f"{PORTAL_BASE}/fichaLicitacion.html?idLicitacion={external_id}",
        "market": "GLOBAL",
        "place": " | ".join(x for x in (_text(buyer.get("ComunaUnidad")), _text(buyer.get("RegionUnidad"))) if x),
        "source_status": _text(tender.get("Estado")) or STATE_NAMES.get(status_code, ""),
        "source_phase": _text(tender.get("Tipo")),
        "signal_type": "TENDER",
        "contract_type": "works",
        "source_reference": external_id,
        "notice_identifier": external_id,
        "procedure_reference": external_id,
        "buyer_code": _text(buyer.get("CodigoOrganismo")),
        "buyer_unit_code": _text(buyer.get("CodigoUnidad")),
        "works_flag": _int(tender.get("Obras")),
        "item_names": item_names,
        "subcontracting_allowed": _text(tender.get("SubContratacion")) == "1",
        "lifecycle_status": _lifecycle(status_code),
        "lifecycle_reason": f"publisher_status_{status_code}" if status_code is not None else "publisher_status_unknown",
        "is_actionable": status_code == 5,
        "attribution": ATTRIBUTION,
        "source_api_url": API_BASE,
    }


@dataclass
class MercadoPublicoCursor:
    seen_by_day: dict[str, list[str]] = field(default_factory=dict)
    tracked: list[str] = field(default_factory=list)

    @classmethod
    def decode(cls, value):
        if value in (None, ""):
            return cls()
        try:
            payload = json.loads(value)
        except Exception as exc:
            raise RuntimeError(f"invalid {SOURCE} cursor; cursor not advanced") from exc
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise RuntimeError(f"invalid {SOURCE} cursor version; cursor not advanced")
        seen = payload.get("seen_by_day") or {}
        tracked = payload.get("tracked") or []
        if not isinstance(seen, dict) or not isinstance(tracked, list):
            raise RuntimeError(f"invalid {SOURCE} cursor shape; cursor not advanced")
        return cls(
            seen_by_day={str(k): sorted({str(x) for x in v}) for k, v in seen.items() if isinstance(v, list)},
            tracked=sorted({str(x) for x in tracked}),
        )

    def encode(self):
        return json.dumps({"version": 1, "seen_by_day": self.seen_by_day, "tracked": self.tracked}, sort_keys=True, separators=(",", ":"))


class MercadoPublicoConnector:
    def __init__(self, *, ticket=None, session=None, sleeper=None, min_interval_seconds=None, now_fn=None):
        self.ticket = _text(ticket or os.getenv("MERCADOPUBLICO_TICKET"))
        if not self.ticket:
            raise MercadoPublicoCredentialError("MERCADOPUBLICO_TICKET is required; public documentation ticket is test-only")
        if self.ticket == TEST_TICKET and os.getenv("OBRASIGNAL_ALLOW_MERCADOPUBLICO_TEST_TICKET") != "1":
            raise MercadoPublicoCredentialError("ChileCompra documentation ticket is test-only and disabled in production")
        self.session = session or requests.Session()
        self.sleeper = sleeper or time.sleep
        self.min_interval = float(min_interval_seconds if min_interval_seconds is not None else os.getenv("MERCADOPUBLICO_MIN_INTERVAL_SECONDS", "4"))
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._last_request_monotonic = None

    def _throttle(self):
        if self._last_request_monotonic is not None and self.min_interval > 0:
            elapsed = time.monotonic() - self._last_request_monotonic
            if elapsed < self.min_interval:
                self.sleeper(self.min_interval - elapsed)

    def _get(self, params, *, max_attempts=4):
        last = None
        for attempt in range(max_attempts):
            self._throttle()
            response = self.session.get(API_BASE, params={**params, "ticket": self.ticket}, timeout=45)
            self._last_request_monotonic = time.monotonic()
            if response.status_code != 429:
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or "Listado" not in payload:
                    raise RuntimeError(f"{SOURCE} unexpected API payload; cursor not advanced")
                return payload
            last = response
            if attempt + 1 < max_attempts:
                self.sleeper(max(self.min_interval, 5.0 * (2 ** attempt)))
        raise RuntimeError(f"{SOURCE} rate limited after {max_attempts} attempts; cursor not advanced: {getattr(last, 'text', '')[:200]}")

    def _date_list(self, day):
        payload = self._get({"fecha": day.strftime("%d%m%Y")})
        rows = payload.get("Listado") or []
        return rows if isinstance(rows, list) else []

    def _active_ids(self):
        payload = self._get({"estado": "activas"})
        return {_text(row.get("CodigoExterno")) for row in (payload.get("Listado") or []) if _text(row.get("CodigoExterno"))}

    def _detail(self, external_id):
        payload = self._get({"codigo": external_id})
        rows = payload.get("Listado") or []
        if len(rows) != 1:
            raise RuntimeError(f"{SOURCE} detail for {external_id} returned {len(rows)} records; cursor not advanced")
        row = rows[0]
        if _text(row.get("CodigoExterno")) != external_id:
            raise RuntimeError(f"{SOURCE} detail identity mismatch for {external_id}; cursor not advanced")
        return row

    def fetch(self, *, watermark=None):
        cursor = MercadoPublicoCursor.decode(watermark)
        now = self.now_fn().astimezone(CHILE_TZ)
        days = [now.date() - timedelta(days=1), now.date()]
        candidate_ids = []
        next_seen = {}
        for day in days:
            key = day.isoformat()
            listed = [_text(x.get("CodigoExterno")) for x in self._date_list(day)]
            listed = [x for x in listed if x]
            previous = set(cursor.seen_by_day.get(key, []))
            candidate_ids.extend(x for x in listed if x not in previous)
            next_seen[key] = sorted(set(listed))

        active_ids = self._active_ids()
        tracked = set(cursor.tracked)
        observations = []
        for external_id in dict.fromkeys(candidate_ids):
            detail = self._detail(external_id)
            if _is_construction(detail):
                observations.append(_observation(detail))
                if _int(detail.get("CodigoEstado")) == 5:
                    tracked.add(external_id)

        disappeared = sorted(tracked - active_ids)
        for external_id in disappeared:
            detail = self._detail(external_id)
            if _is_construction(detail):
                observations.append(_observation(detail))
            if _int(detail.get("CodigoEstado")) != 5:
                tracked.discard(external_id)

        next_cursor = MercadoPublicoCursor(seen_by_day=next_seen, tracked=sorted(tracked)).encode()
        return observations, next_cursor


def fetch_chile_mercadopublico_tenders(*, watermark=None, ticket=None, session=None):
    return MercadoPublicoConnector(ticket=ticket, session=session).fetch(watermark=watermark)
