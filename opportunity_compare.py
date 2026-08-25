"""Deterministic, read-only opportunity comparison for ObraSignal.

This module compares existing canonical opportunity facts and account-scoped
persisted decision features. It does not rank, recommend, persist comparisons,
convert currencies, or synthesize missing facts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Sequence

COMPARISON_VERSION = "opportunity-compare-v0"
MIN_OPPORTUNITIES = 2
MAX_OPPORTUNITIES = 5

KNOWN = "KNOWN"
UNKNOWN = "UNKNOWN"
NOT_APPLICABLE = "NOT_APPLICABLE"
FACT = "FACT"
DERIVED = "DERIVED"


class ComparisonError(ValueError):
    """Base validation error for comparison requests."""


class OpportunityNotFoundError(ComparisonError):
    """Raised when a requested opportunity does not exist."""


@dataclass(frozen=True)
class ComparisonDimension:
    key: str
    label: str
    value_type: str
    comparison_behavior: str
    origin: str
    source: str
    extractor: Callable[[Mapping[str, Any], Mapping[str, Any] | None, datetime], Any]

    def contract(self) -> dict[str, str]:
        return {
            "key": self.key,
            "label": self.label,
            "type": self.value_type,
            "comparison_behavior": self.comparison_behavior,
            "origin": self.origin,
            "source": self.source,
        }


def _first(row: Mapping[str, Any], *keys: str):
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return None


def _decision_feature(decision: Mapping[str, Any] | None, key: str):
    if not decision:
        return None
    return (decision.get("features") or {}).get(key)


def _deadline_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _days_remaining(row: Mapping[str, Any], _decision, now: datetime):
    deadline = _deadline_dt(row.get("deadline"))
    if deadline is None:
        return None
    return (deadline.date() - now.astimezone(timezone.utc).date()).days


def _source_available(row: Mapping[str, Any], _decision, _now):
    return bool(_first(row, "source_reference", "url", "source"))


def _economic_fit(_row, decision, _now):
    return _decision_feature(decision, "economic_fit")


def _capacity_fit(_row, decision, _now):
    return _decision_feature(decision, "capability_evidence")


def _geography(row, _decision, _now):
    return _first(row, "place", "location", "region", "country")


def _distance(_row, decision, _now):
    geography = _decision_feature(decision, "geography") or {}
    if isinstance(geography, Mapping):
        return _first(geography, "distance_km", "distance")
    return None


def _status(row, _decision, _now):
    return _first(row, "lifecycle_status", "status", "opportunity_status")


def _lots(row, _decision, _now):
    return _first(row, "lots", "lot_count", "lot_id")


def _requirements(row, _decision, _now):
    return _first(row, "qualification_requirements", "requirements", "eligibility_requirements")


def _confidence(_row, decision, _now):
    return decision.get("confidence") if decision else None


def _decimal_amount(raw: Any) -> Decimal | None:
    """Parse a money amount without binary-float comparison semantics.

    The permissive comma/dot normalization is retained for compatibility with
    the existing comparison input contract, but all material arithmetic and
    ordering is Decimal-backed. Non-finite, boolean and negative amounts fail
    closed instead of becoming comparable money.
    """
    if raw is None or raw == "" or isinstance(raw, bool):
        return None
    if isinstance(raw, Decimal):
        amount = raw
    else:
        token: Any = raw
        if isinstance(raw, str):
            token = raw.strip().replace(" ", "")
            if not token:
                return None
            if "," in token and "." in token:
                decimal_mark = "," if token.rfind(",") > token.rfind(".") else "."
                thousands_mark = "." if decimal_mark == "," else ","
                token = token.replace(thousands_mark, "").replace(decimal_mark, ".")
            elif "," in token:
                parts = token.split(",")
                token = "".join(parts) if len(parts) > 2 or len(parts[-1]) == 3 else ".".join(parts)
        try:
            amount = Decimal(str(token))
        except (InvalidOperation, TypeError, ValueError):
            return None
    if not amount.is_finite() or amount < 0:
        return None
    return amount


def _json_decimal(amount: Decimal) -> int | str:
    """Return a JSON-safe exact representation without fabricating precision."""
    if amount == amount.to_integral_value():
        return int(amount)
    return format(amount, "f")


def _published_value(row, _decision, _now):
    raw = _first(row, "value_numeric", "value")
    amount = _decimal_amount(raw)
    if amount is None:
        return None
    return {"amount": _json_decimal(amount), "currency": row.get("currency")}


COMPARISON_DIMENSIONS: tuple[ComparisonDimension, ...] = (
    ComparisonDimension("published_value", "Published value", "money", "informational; compare only within same currency", FACT, "opportunity.value + opportunity.currency", _published_value),
    ComparisonDimension("deadline", "Submission deadline", "datetime", "earlier/later informational", FACT, "opportunity.deadline", lambda r, d, n: r.get("deadline")),
    ComparisonDimension("days_remaining", "Days remaining", "integer", "lower means nearer deadline", DERIVED, "derived from opportunity.deadline and generated_at date", _days_remaining),
    ComparisonDimension("geography", "Geography", "object|string", "informational", FACT, "canonical opportunity place/location/region/country", _geography),
    ComparisonDimension("distance_km", "Known distance", "distance_km", "lower known distance", DERIVED, "existing account decision geography.distance_km", _distance),
    ComparisonDimension("buyer", "Buyer", "string", "informational", FACT, "opportunity.buyer", lambda r, d, n: r.get("buyer")),
    ComparisonDimension("work_type", "Work type", "string", "informational", FACT, "canonical opportunity procedure/category fields", lambda r, d, n: _first(r, "work_type", "procedure_type", "notice_type", "category", "cpv")),
    ComparisonDimension("lots", "Lots", "object", "informational", FACT, "canonical opportunity lot fields", _lots),
    ComparisonDimension("qualification_requirements", "Qualification requirements", "object|string", "informational", FACT, "canonical opportunity requirement fields", _requirements),
    ComparisonDimension("economic_fit", "Economic fit", "object", "existing account-scoped assessment only", DERIVED, "latest account opportunity_decision.features.economic_fit", _economic_fit),
    ComparisonDimension("capacity_fit", "Capacity fit", "object", "existing account-scoped assessment only", DERIVED, "latest account opportunity_decision.features.capability_evidence", _capacity_fit),
    ComparisonDimension("opportunity_status", "Opportunity status", "string", "informational", FACT, "canonical opportunity lifecycle/status field", _status),
    ComparisonDimension("decision_confidence", "Existing decision confidence", "number", "existing system confidence only", DERIVED, "latest account opportunity_decision.confidence", _confidence),
    ComparisonDimension("source_available", "Source/provenance available", "boolean", "informational", DERIVED, "presence of canonical source/source_reference/url", _source_available),
)


def _normalize_ids(opportunity_ids: Sequence[Any]) -> list[int]:
    if isinstance(opportunity_ids, (str, bytes)) or not isinstance(opportunity_ids, Sequence):
        raise ComparisonError("opportunity_ids must be a sequence")
    normalized: list[int] = []
    for raw in opportunity_ids:
        if isinstance(raw, bool):
            raise ComparisonError("opportunity id must be an integer")
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ComparisonError("opportunity id must be an integer") from None
        if str(raw).strip() != str(value) and not isinstance(raw, int):
            raise ComparisonError("opportunity id must be an integer")
        if value <= 0:
            raise ComparisonError("opportunity id must be positive")
        normalized.append(value)
    if len(normalized) < MIN_OPPORTUNITIES:
        raise ComparisonError(f"compare at least {MIN_OPPORTUNITIES} opportunities")
    if len(normalized) > MAX_OPPORTUNITIES:
        raise ComparisonError(f"compare at most {MAX_OPPORTUNITIES} opportunities")
    if len(set(normalized)) != len(normalized):
        raise ComparisonError("duplicate opportunity ids are not allowed")
    return normalized


def _account_id(account_context: Any) -> str:
    if isinstance(account_context, str):
        value = account_context
    elif isinstance(account_context, Mapping):
        value = account_context.get("account_id")
    else:
        value = getattr(account_context, "account_id", None)
    value = str(value or "").strip()
    if not value:
        raise ComparisonError("account context with account_id is required")
    return value


def _fetch_opportunities(conn, ids: list[int]) -> list[dict[str, Any]]:
    placeholders = ",".join("?" for _ in ids)
    try:
        rows = conn.execute(
            f"""SELECT t.*, lc.lifecycle_status, lc.lifecycle_reason,
                       lc.is_actionable AS lifecycle_is_actionable
                FROM tenders t
                LEFT JOIN opportunity_lifecycle lc
                  ON lc.source=t.source AND lc.external_id=t.external_id
                WHERE t.id IN ({placeholders})""",
            ids,
        ).fetchall()
    except Exception as exc:
        if "no such table: opportunity_lifecycle" not in str(exc).lower():
            raise
        rows = conn.execute(f"SELECT * FROM tenders WHERE id IN ({placeholders})", ids).fetchall()
    by_id = {int(dict(row)["id"]): dict(row) for row in rows}
    missing = [value for value in ids if value not in by_id]
    if missing:
        raise OpportunityNotFoundError(f"opportunity not found: {missing[0]}")
    return [by_id[value] for value in ids]


def _latest_account_decisions(conn, account_id: str, opportunities: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    keys = [(str(r.get("source") or ""), str(r.get("external_id") or r.get("id"))) for r in opportunities]
    external_ids = sorted({external_id for _, external_id in keys})
    if not external_ids:
        return {}
    placeholders = ",".join("?" for _ in external_ids)
    try:
        rows = conn.execute(
            f"""SELECT d.* FROM opportunity_decisions d
                JOIN (
                    SELECT source, external_id, MAX(id) AS max_id
                    FROM opportunity_decisions
                    WHERE account_id=? AND external_id IN ({placeholders})
                    GROUP BY source, external_id
                ) latest ON latest.max_id=d.id""",
            (account_id, *external_ids),
        ).fetchall()
    except Exception as exc:
        if "no such table: opportunity_decisions" in str(exc).lower():
            return {}
        raise
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        item = dict(row)
        raw_features = item.get("features_json")
        if raw_features:
            try:
                item["features"] = json.loads(raw_features)
            except (TypeError, json.JSONDecodeError):
                item["features"] = {}
        else:
            item["features"] = {}
        result[(str(item.get("source") or ""), str(item.get("external_id") or ""))] = item
    return result


def _cell(value: Any, dimension: ComparisonDimension) -> dict[str, Any]:
    if value is None or value == "":
        return {"status": UNKNOWN, "value": None, "origin": dimension.origin, "source": dimension.source}
    return {"status": KNOWN, "value": value, "origin": dimension.origin, "source": dimension.source}


def _money_number(cell: Mapping[str, Any]) -> tuple[Decimal, str] | None:
    if cell.get("status") != KNOWN or not isinstance(cell.get("value"), Mapping):
        return None
    value = cell["value"]
    currency = str(value.get("currency") or "").strip().upper()
    if not currency:
        return None
    amount = _decimal_amount(value.get("amount"))
    if amount is None:
        return None
    return amount, currency


def _highlights(values_by_opportunity: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> list[dict[str, Any]]:
    highlights: list[dict[str, Any]] = []
    missing_counts = {oid: sum(1 for cell in dims.values() if cell["status"] == UNKNOWN) for oid, dims in values_by_opportunity.items()}
    if missing_counts:
        maximum = max(missing_counts.values())
        highlights.append({"key": "most_missing_data", "opportunity_ids": [oid for oid, count in missing_counts.items() if count == maximum], "value": maximum})

    deadlines = []
    for oid, dims in values_by_opportunity.items():
        parsed = _deadline_dt(dims["deadline"].get("value")) if dims["deadline"]["status"] == KNOWN else None
        if parsed is not None:
            deadlines.append((parsed, oid))
    if deadlines:
        earliest = min(value for value, _ in deadlines)
        highlights.append({"key": "nearest_deadline", "opportunity_ids": [oid for value, oid in deadlines if value == earliest], "value": earliest.isoformat()})

    distances = []
    for oid, dims in values_by_opportunity.items():
        cell = dims["distance_km"]
        if cell["status"] == KNOWN:
            try:
                distances.append((float(cell["value"]), oid))
            except (TypeError, ValueError):
                pass
    if distances:
        nearest = min(value for value, _ in distances)
        highlights.append({"key": "lowest_known_distance", "opportunity_ids": [oid for value, oid in distances if value == nearest], "value": nearest})

    money: dict[str, list[tuple[Decimal, str]]] = {}
    for oid, dims in values_by_opportunity.items():
        parsed = _money_number(dims["published_value"])
        if parsed:
            amount, currency = parsed
            money.setdefault(currency, []).append((amount, oid))
    if len(money) == 1:
        currency, entries = next(iter(money.items()))
        highest = max(value for value, _ in entries)
        highlights.append({"key": "highest_published_value", "opportunity_ids": [oid for value, oid in entries if value == highest], "value": {"amount": _json_decimal(highest), "currency": currency}})
    elif len(money) > 1:
        highlights.append({"key": "mixed_currencies", "opportunity_ids": [], "value": sorted(money)})
    return highlights


def compare_opportunities(conn, account_context: Any, opportunity_ids: Sequence[Any], options: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Compare 2-5 existing opportunities without creating new truth.

    ``options['now']`` may be a datetime for deterministic tests. Input order is
    preserved. Source records and account decisions are never mutated.
    """
    ids = _normalize_ids(opportunity_ids)
    account_id = _account_id(account_context)
    options = dict(options or {})
    now = options.get("now") or datetime.now(timezone.utc)
    if not isinstance(now, datetime):
        raise ComparisonError("options.now must be a datetime")
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    opportunities = _fetch_opportunities(conn, ids)
    decisions = _latest_account_decisions(conn, account_id, opportunities)
    values: dict[str, dict[str, dict[str, Any]]] = {}
    missing_data: dict[str, list[str]] = {}
    summaries: list[dict[str, Any]] = []

    for row in opportunities:
        oid = str(row["id"])
        key = (str(row.get("source") or ""), str(row.get("external_id") or row.get("id")))
        decision = decisions.get(key)
        dims = {dimension.key: _cell(dimension.extractor(row, decision, now), dimension) for dimension in COMPARISON_DIMENSIONS}
        values[oid] = dims
        missing_data[oid] = [dimension.key for dimension in COMPARISON_DIMENSIONS if dims[dimension.key]["status"] == UNKNOWN]
        summaries.append({"id": row["id"], "external_id": row.get("external_id"), "source": row.get("source"), "title": row.get("title")})

    total = len(COMPARISON_DIMENSIONS)
    completeness = {oid: {"available_fields": total - len(missing), "expected_fields": total, "ratio": round((total - len(missing)) / total, 4) if total else 1.0} for oid, missing in missing_data.items()}
    digest = sha256((COMPARISON_VERSION + ":" + ",".join(str(v) for v in ids) + ":" + account_id).encode()).hexdigest()[:20]
    currencies = sorted({parsed[1] for oid in values for parsed in [_money_number(values[oid]["published_value"])] if parsed})
    warnings = []
    if len(currencies) > 1:
        warnings.append({"code": "MIXED_CURRENCIES", "message": "Published values use different currencies; no FX conversion or cross-currency value ranking was performed.", "currencies": currencies})

    return {
        "comparison_id": f"cmp_{digest}",
        "comparison_version": COMPARISON_VERSION,
        "generated_at": now.isoformat(),
        "opportunities": summaries,
        "dimensions": [dimension.contract() for dimension in COMPARISON_DIMENSIONS],
        "values_by_opportunity": values,
        "missing_data": missing_data,
        "data_completeness": completeness,
        "highlights": _highlights(values),
        "warnings": warnings,
    }


class OpportunityComparisonService:
    """Small service wrapper for callers that prefer an object boundary."""

    def __init__(self, conn):
        self.conn = conn

    def compare(self, account_context: Any, opportunity_ids: Sequence[Any], options=None):
        return compare_opportunities(self.conn, account_context, opportunity_ids, options)