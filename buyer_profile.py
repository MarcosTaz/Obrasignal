"""Coverage-aware buyer profile snapshot built from existing normalized signals.

Observed ObraSignal records are evidence, not the buyer's complete procurement
history. Identity never uses fuzzy name matching and this read model never
mutates canonical signal rows.
"""
from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from calendar import monthrange
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from typing import Any, Mapping

SNAPSHOT_VERSION = "buyer-profile.v0"
MAX_BUYER_ID_LENGTH = 1024
MAX_RECENT_LIMIT = 50
SUPPORTED_WINDOWS = {"12m": 12, "24m": 24, "all": None, "all_observed": None}
ACTIVITY_TYPES = ("TENDER", "AWARD", "CONTRACT")
_IDENTIFIER_KEYS = (
    "buyer_identifier", "buyer_id", "organization_id", "contracting_authority_id",
    "procuring_entity_id", "purchaser_id", "issuer_id",
)
_IDENTITY_OBJECT_KEYS = ("buyer", "procuring_entity", "contracting_authority", "purchaser", "issuer")
_PROCUREMENT_ID_KEYS = ("canonical_opportunity_id", "procurement_id", "procedure_id", "ocid", "tender_id")
_AWARD_ID_KEYS = ("canonical_award_id", "award_id", "award_identifier")
_CONTRACT_ID_KEYS = ("canonical_contract_id", "contract_id", "contract_identifier")
_LOT_ID_KEYS = ("lot_id", "lot_identifier")


@dataclass(frozen=True)
class BuyerIdentity:
    buyer_id: str
    canonical_name: str
    jurisdiction: str | None
    identifiers: tuple[dict[str, str], ...]
    identity_strength: str
    source_scope: str


@dataclass(frozen=True)
class BuyerProfileSnapshot:
    buyer_id: str
    canonical_name: str
    identifiers: tuple[dict[str, str], ...]
    jurisdiction: str | None
    known_locations: tuple[dict[str, str], ...]
    known_opportunity_count: int
    known_award_count: int
    known_contract_count: int
    observed_lot_count: int
    known_published_opportunity_values_by_currency: dict[str, str]
    known_award_values_by_currency: dict[str, str]
    known_contract_values_by_currency: dict[str, str]
    known_categories: tuple[dict[str, Any], ...]
    recent_activity: tuple[dict[str, Any], ...]
    observed_from: str | None
    observed_to: str | None
    source_refs: tuple[dict[str, str], ...]
    coverage_notes: tuple[str, ...]
    generated_at: str
    snapshot_version: str = SNAPSHOT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _b64(value: str) -> str:
    return urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _unb64(value: str) -> str:
    if not value or len(value) > MAX_BUYER_ID_LENGTH:
        raise ValueError("malformed buyer_id")
    padding = "=" * (-len(value) % 4)
    try:
        return urlsafe_b64decode((value + padding).encode("ascii")).decode("utf-8")
    except Exception as exc:
        raise ValueError("malformed buyer_id") from exc


def _identifier(value: Any, default_scheme: str) -> tuple[str, str] | None:
    if isinstance(value, Mapping):
        ident = _text(value.get("id") or value.get("identifier") or value.get("value"))
        scheme = _text(value.get("scheme") or value.get("type") or default_scheme)
    else:
        ident = _text(value)
        scheme = default_scheme
    return (scheme, ident) if ident else None


def _buyer_identifier(payload: Mapping[str, Any]) -> tuple[str, str] | None:
    for key in _IDENTIFIER_KEYS:
        candidate = _identifier(payload.get(key), key)
        if candidate:
            return candidate
    for key in _IDENTITY_OBJECT_KEYS:
        obj = payload.get(key)
        if isinstance(obj, Mapping):
            candidate = _identifier(obj.get("identifier") or obj.get("id"), key)
            if candidate:
                return candidate
    return None


def _record_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("normalized_json")
    if isinstance(raw, Mapping):
        return dict(raw)
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def buyer_identity_from_record(row: Mapping[str, Any]) -> BuyerIdentity:
    payload = _record_payload(row)
    source = _text(row.get("source") or payload.get("source"))
    jurisdiction = _text(row.get("country") or payload.get("country")) or None
    name = _text(row.get("buyer") or payload.get("buyer"))
    if not source or not name:
        raise ValueError("buyer identity requires source and canonical buyer name")
    official = _buyer_identifier(payload)
    if official:
        scheme, value = official
        buyer_id = ":".join(("buyer", "v0", "official", _b64(source), _b64(jurisdiction or ""), _b64(scheme), _b64(value)))
        identifiers = ({"scheme": scheme, "value": value, "source": source},)
        strength = "official_identifier"
    else:
        buyer_id = ":".join(("buyer", "v0", "name_scoped", _b64(source), _b64(jurisdiction or ""), _b64(name)))
        identifiers = ()
        strength = "name_scoped"
    return BuyerIdentity(buyer_id, name, jurisdiction, identifiers, strength, source)


def _parse_buyer_id(buyer_id: str) -> dict[str, str]:
    value = _text(buyer_id)
    if not value or len(value) > MAX_BUYER_ID_LENGTH:
        raise ValueError("malformed buyer_id")
    parts = value.split(":")
    if len(parts) not in (6, 7) or parts[:2] != ["buyer", "v0"]:
        raise ValueError("malformed buyer_id")
    mode = parts[2]
    if mode == "name_scoped" and len(parts) == 6:
        source, country, name = map(_unb64, parts[3:6])
        if not source or not name:
            raise ValueError("malformed buyer_id")
        return {"mode": mode, "source": source, "country": country, "name": name}
    if mode == "official" and len(parts) == 7:
        source, country, scheme, identifier = map(_unb64, parts[3:7])
        if not source or not scheme or not identifier:
            raise ValueError("malformed buyer_id")
        return {"mode": mode, "source": source, "country": country, "scheme": scheme, "identifier": identifier}
    raise ValueError("malformed buyer_id")


def _parse_dt(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            dt = datetime.combine(date.fromisoformat(text[:10]), datetime.min.time())
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _subtract_months(dt: datetime, months: int) -> datetime:
    total = dt.year * 12 + (dt.month - 1) - months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    day = min(dt.day, monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _activity_dt(row: Mapping[str, Any]) -> datetime | None:
    for key in ("published_at", "publication_date", "source_updated_at", "last_observed", "first_observed"):
        parsed = _parse_dt(row.get(key))
        if parsed:
            return parsed
    return None


def _payload_id(payload: Mapping[str, Any], keys: tuple[str, ...], nested_key: str | None = None) -> str:
    for key in keys:
        raw = payload.get(key)
        if isinstance(raw, Mapping):
            value = _text(raw.get("id") or raw.get("identifier") or raw.get("value"))
        else:
            value = _text(raw)
        if value:
            return value
    if nested_key:
        nested = payload.get(nested_key)
        if isinstance(nested, Mapping):
            value = _text(nested.get("id") or nested.get("identifier"))
            if value:
                return value
    return ""


def _procurement_key(row: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    value = _payload_id(payload, _PROCUREMENT_ID_KEYS)
    if value:
        return f"{_text(row.get('source'))}:{value}"
    return f"{_text(row.get('source'))}:{_text(row.get('external_id'))}"


def _activity_identity(row: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    signal_type = _text(row.get("signal_type")).upper()
    source = _text(row.get("source"))
    external_id = _text(row.get("external_id"))
    if signal_type == "TENDER":
        return _procurement_key(row, payload)
    if signal_type == "AWARD":
        award_id = _payload_id(payload, _AWARD_ID_KEYS, "award")
        return f"{source}:{award_id}" if award_id else f"{source}:{external_id}"
    if signal_type == "CONTRACT":
        contract_id = _payload_id(payload, _CONTRACT_ID_KEYS, "contract")
        return f"{source}:{contract_id}" if contract_id else f"{source}:{external_id}"
    return f"{source}:{external_id}"


def _lot_key(payload: Mapping[str, Any]) -> str | None:
    for key in _LOT_ID_KEYS:
        value = _text(payload.get(key))
        if value:
            return value
    return None


def _amount(value: Any) -> Decimal | None:
    text = _text(value)
    if not text or len(text) > 128:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if not number.is_finite() or number < 0:
        return None
    adjusted = number.adjusted() if number else 0
    if adjusted > 30 or adjusted < -12:
        return None
    return number


def _format_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _value_totals(records: list[Mapping[str, Any]]) -> dict[str, str]:
    totals: dict[str, Decimal] = {}
    for row in records:
        currency = _text(row.get("currency")).upper()
        amount = _amount(row.get("value"))
        if currency and amount is not None:
            totals[currency] = totals.get(currency, Decimal("0")) + amount
    return {currency: _format_decimal(totals[currency]) for currency in sorted(totals)}


def _encode(parsed: Mapping[str, str]) -> str:
    if parsed["mode"] == "name_scoped":
        return ":".join(("buyer", "v0", "name_scoped", _b64(parsed["source"]), _b64(parsed.get("country", "")), _b64(parsed["name"])))
    return ":".join(("buyer", "v0", "official", _b64(parsed["source"]), _b64(parsed.get("country", "")), _b64(parsed["scheme"]), _b64(parsed["identifier"])))


def _select_identity_rows(conn, parsed: Mapping[str, str]) -> list[dict[str, Any]]:
    params: list[Any] = [parsed["source"]]
    where = ["source=?", "TRIM(COALESCE(buyer,''))<>''"]
    country = parsed.get("country", "")
    if country:
        where.append("country=?")
        params.append(country)
    elif parsed["mode"] == "name_scoped":
        where.append("COALESCE(country,'')='' ")
    if parsed["mode"] == "name_scoped":
        where.append("buyer=?")
        params.append(parsed["name"])
    rows = conn.execute(
        f"SELECT * FROM signal_records WHERE {' AND '.join(where)} ORDER BY last_observed DESC, signal_type, external_id",
        tuple(params),
    ).fetchall()
    candidates = [dict(row) for row in rows]
    if parsed["mode"] == "name_scoped":
        return [row for row in candidates if buyer_identity_from_record(row).buyer_id == _encode(parsed)]
    return [row for row in candidates if _buyer_identifier(_record_payload(row)) == (parsed["scheme"], parsed["identifier"])]


def _dedupe(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    lots: set[tuple[str, str]] = set()
    floor = datetime.min.replace(tzinfo=timezone.utc)
    for row in records:
        payload = _record_payload(row)
        signal_type = _text(row.get("signal_type")).upper()
        identity = _activity_identity(row, payload)
        key = (signal_type, identity)
        if signal_type == "TENDER":
            lot = _lot_key(payload)
            if lot:
                lots.add((_procurement_key(row, payload), lot))
        current = selected.get(key)
        candidate_rank = (_activity_dt(row) or floor, _text(row.get("external_id")))
        current_rank = (
            (_activity_dt(current) or floor, _text(current.get("external_id")))
            if current is not None else None
        )
        if current_rank is None or candidate_rank > current_rank:
            selected[key] = row
    ordered = [selected[key] for key in sorted(selected)]
    return ordered, len(lots)


def build_buyer_profile_snapshot(conn, buyer_id: str, window: str = "12m", context: Any = None, *, now: datetime | None = None, recent_limit: int = 10) -> BuyerProfileSnapshot | None:
    """Build an on-demand, deterministic buyer snapshot from normalized public records."""
    del context
    parsed = _parse_buyer_id(buyer_id)
    if window not in SUPPORTED_WINDOWS:
        raise ValueError("unsupported buyer profile window")
    try:
        recent_limit = int(recent_limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("recent_limit must be an integer") from exc
    if recent_limit < 1 or recent_limit > MAX_RECENT_LIMIT:
        raise ValueError(f"recent_limit must be between 1 and {MAX_RECENT_LIMIT}")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    months = SUPPORTED_WINDOWS[window]
    cutoff = _subtract_months(now, months) if months is not None else None

    matched = _select_identity_rows(conn, parsed)
    if not matched:
        return None
    identities = [buyer_identity_from_record(row) for row in matched]
    canonical_name = next((item.canonical_name for item in identities if item.canonical_name), parsed.get("name", ""))
    identifiers: dict[tuple[str, str, str], dict[str, str]] = {}
    for identity in identities:
        for item in identity.identifiers:
            identifiers[(item["scheme"], item["value"], item["source"])] = item

    def in_window(row):
        dt = _activity_dt(row)
        return (cutoff is None if dt is None else dt <= now and (cutoff is None or dt >= cutoff))

    visible = [row for row in matched if _text(row.get("signal_type")).upper() in ACTIVITY_TYPES and in_window(row)]
    deduped, observed_lot_count = _dedupe(visible)
    by_type = {kind: [row for row in deduped if _text(row.get("signal_type")).upper() == kind] for kind in ACTIVITY_TYPES}
    location_values = sorted({_text(row.get("place")) for row in visible if _text(row.get("place"))})
    locations = tuple({"kind": "source_record_location", "value": value} for value in location_values)

    categories: dict[tuple[str, str], int] = {}
    for row in by_type["TENDER"]:
        taxonomy, code = _text(row.get("taxonomy")) or "UNKNOWN", _text(row.get("category_code"))
        if code:
            categories[(taxonomy, code)] = categories.get((taxonomy, code), 0) + 1
    category_items = tuple(
        {"taxonomy": t, "code": c, "known_opportunity_count": n}
        for (t, c), n in sorted(categories.items(), key=lambda item: (-item[1], item[0]))
    )

    recent = []
    for row in deduped:
        dt = _activity_dt(row)
        recent.append({
            "signal_type": _text(row.get("signal_type")).upper(),
            "source": _text(row.get("source")),
            "external_id": _text(row.get("external_id")),
            "title": _text(row.get("title")),
            "activity_date": dt.isoformat() if dt else None,
            "source_reference": _text(row.get("source_reference")) or None,
        })
    recent.sort(
        key=lambda item: (
            item["activity_date"] or "",
            item["signal_type"],
            item["source"],
            item["external_id"],
        ),
        reverse=True,
    )

    dates = [dt for row in visible if (dt := _activity_dt(row))]
    source_ref_pairs = sorted({
        (_text(row.get("source")), _text(row.get("source_reference") or row.get("url") or row.get("external_id")))
        for row in visible
        if _text(row.get("source")) and _text(row.get("source_reference") or row.get("url") or row.get("external_id"))
    })
    source_refs = tuple({"source": source, "reference": ref} for source, ref in source_ref_pairs)
    sources = sorted({_text(row.get("source")) for row in matched if _text(row.get("source"))})
    notes = [
        "Known activity reflects only normalized procurement records currently available to ObraSignal; it is not the buyer's total real-world procurement activity.",
        f"Observed source scope: {', '.join(sources)}." if sources else "Observed source scope is unknown.",
        f"Activity window: {window}; records without a usable activity date are {'included' if cutoff is None else 'excluded'} from windowed activity metrics.",
        "Opportunity, award and contract published values are kept separate and currencies are never converted or summed together.",
        "Opportunity counts use procedure-level canonical keys when present; awards/contracts use their own identifiers when present and otherwise source external IDs; observed lot identifiers are reported separately.",
        "Locations are source-record locations only; the current Signal contract does not reliably distinguish buyer registered address from project/opportunity location, so no registered-location claim is made.",
    ]
    if parsed["mode"] == "name_scoped":
        notes.append("Buyer identity is source/jurisdiction/name scoped because no stronger identifier is present in the available normalized record; no fuzzy merge is performed.")

    return BuyerProfileSnapshot(
        buyer_id=_encode(parsed),
        canonical_name=canonical_name,
        identifiers=tuple(identifiers[key] for key in sorted(identifiers)),
        jurisdiction=parsed.get("country") or None,
        known_locations=locations,
        known_opportunity_count=len(by_type["TENDER"]),
        known_award_count=len(by_type["AWARD"]),
        known_contract_count=len(by_type["CONTRACT"]),
        observed_lot_count=observed_lot_count,
        known_published_opportunity_values_by_currency=_value_totals(by_type["TENDER"]),
        known_award_values_by_currency=_value_totals(by_type["AWARD"]),
        known_contract_values_by_currency=_value_totals(by_type["CONTRACT"]),
        known_categories=category_items,
        recent_activity=tuple(recent[:recent_limit]),
        observed_from=min(dates).isoformat() if dates else None,
        observed_to=max(dates).isoformat() if dates else None,
        source_refs=source_refs,
        coverage_notes=tuple(notes),
        generated_at=now.isoformat(),
    )
