"""Auditable, tenant-scoped Value Created ledger v0.

Passive domain capability. It records economic/value observations but never infers
that an opportunity's contract value is value created.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import json
import math
import re
import sqlite3
import uuid

CONTRACT_VERSION = "value-created-ledger.v0"


class ValueType(str, Enum):
    MEASURED = "MEASURED"
    ESTIMATED = "ESTIMATED"
    QUALIFIED = "QUALIFIED"
    UNKNOWN = "UNKNOWN"


class ValueStatus(str, Enum):
    PROPOSED = "PROPOSED"
    OBSERVED = "OBSERVED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


ALLOWED_CATEGORIES = frozenset({
    "qualified_opportunity",
    "bad_bid_avoided",
    "mobilization_saving",
    "sourcing_saving",
    "margin_preserved",
    "time_saved",
    "idle_capacity_recovered",
    "contractual_value_protected",
    "financing_cost_avoided",
    "operational_cost_reduction",
})

SCHEMA = """
CREATE TABLE IF NOT EXISTS value_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    account_id TEXT NOT NULL,
    category TEXT NOT NULL,
    value_type TEXT NOT NULL,
    amount_text TEXT,
    currency TEXT,
    unit TEXT,
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    source TEXT NOT NULL,
    decision_id TEXT,
    opportunity_id TEXT,
    project_id TEXT,
    method TEXT,
    confidence TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    assumptions_json TEXT NOT NULL,
    notes TEXT,
    status TEXT NOT NULL,
    deduplication_key TEXT,
    causal_reference TEXT,
    corrects_event_id TEXT,
    supersedes_event_id TEXT,
    CHECK (value_type IN ('MEASURED','ESTIMATED','QUALIFIED','UNKNOWN')),
    CHECK (status IN ('PROPOSED','OBSERVED','VERIFIED','REJECTED','SUPERSEDED')),
    CHECK (confidence IN ('HIGH','MEDIUM','LOW','UNKNOWN'))
)
"""

INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_value_events_account_occurred ON value_events(account_id, occurred_at)",
    "CREATE INDEX IF NOT EXISTS idx_value_events_account_category ON value_events(account_id, category)",
    "CREATE INDEX IF NOT EXISTS idx_value_events_account_type_currency ON value_events(account_id, value_type, currency)",
    "CREATE INDEX IF NOT EXISTS idx_value_events_opportunity ON value_events(account_id, opportunity_id)",
    "CREATE INDEX IF NOT EXISTS idx_value_events_project ON value_events(account_id, project_id)",
    "CREATE INDEX IF NOT EXISTS idx_value_events_decision ON value_events(account_id, decision_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_value_events_account_dedup ON value_events(account_id, deduplication_key) WHERE deduplication_key IS NOT NULL",
)


@dataclass(frozen=True)
class ValueEvent:
    event_id: str
    account_id: str
    category: str
    value_type: ValueType
    amount: Decimal | None
    currency: str | None
    unit: str | None
    occurred_at: str
    recorded_at: str
    source: str
    decision_id: str | None
    opportunity_id: str | None
    project_id: str | None
    method: str | None
    confidence: Confidence
    evidence_refs: tuple[str, ...]
    assumptions: tuple[str, ...]
    notes: str | None
    status: ValueStatus
    deduplication_key: str | None
    causal_reference: str | None
    corrects_event_id: str | None
    supersedes_event_id: str | None


@dataclass(frozen=True)
class ValueSummary:
    account_id: str
    start_at: str | None
    end_at: str | None
    measured_by_currency: dict[str, Decimal]
    estimated_by_currency: dict[str, Decimal]
    qualified_by_currency: dict[str, Decimal]
    time_saved_by_unit: dict[str, Decimal]
    estimated_time_saved_by_unit: dict[str, Decimal]
    other_non_monetary: dict[str, dict[str, Decimal]]
    estimated_other_non_monetary: dict[str, dict[str, Decimal]]
    breakdown: dict[str, dict[str, dict[str, Decimal]]]


def ensure_value_ledger_schema(conn) -> None:
    """Idempotent, additive schema initializer for the existing SQLite database."""
    conn.execute(SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(value_events)").fetchall()}
    migrations = {
        "deduplication_key": "ALTER TABLE value_events ADD COLUMN deduplication_key TEXT",
        "causal_reference": "ALTER TABLE value_events ADD COLUMN causal_reference TEXT",
        "corrects_event_id": "ALTER TABLE value_events ADD COLUMN corrects_event_id TEXT",
        "supersedes_event_id": "ALTER TABLE value_events ADD COLUMN supersedes_event_id TEXT",
    }
    for name, sql in migrations.items():
        if name not in columns:
            conn.execute(sql)
    for sql in INDEXES:
        conn.execute(sql)
    conn.commit()


def _utc_iso(value: datetime | str | None, *, default_now: bool = False) -> str:
    if value is None:
        if not default_now:
            raise ValueError("timestamp is required")
        value = datetime.now(timezone.utc)
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid ISO timestamp") from exc
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc).isoformat()


def _decimal(value) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("amount must be numeric")
    try:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("amount must be finite")
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("amount must be a finite decimal") from exc
    if not amount.is_finite():
        raise ValueError("amount must be finite")
    return amount


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _enum(enum_cls, value, label):
    try:
        return value if isinstance(value, enum_cls) else enum_cls(str(value).upper())
    except ValueError as exc:
        raise ValueError(f"invalid {label}: {value}") from exc


def _clean_ref(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or len(text) > 256 or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {label}")
    return text


def _clean_list(values, label: str) -> tuple[str, ...]:
    cleaned = tuple(_clean_ref(v, label) for v in (values or ()))
    return tuple(v for v in cleaned if v is not None)


def _validate_currency(currency: str | None) -> str | None:
    if currency is None or str(currency).strip() == "":
        return None
    code = str(currency).strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", code):
        raise ValueError("currency must be a 3-letter ISO-style code")
    return code


def _row_to_event(row) -> ValueEvent:
    item = dict(row)
    return ValueEvent(
        event_id=item["event_id"],
        account_id=item["account_id"],
        category=item["category"],
        value_type=ValueType(item["value_type"]),
        amount=_decimal(item["amount_text"]),
        currency=item["currency"],
        unit=item["unit"],
        occurred_at=item["occurred_at"],
        recorded_at=item["recorded_at"],
        source=item["source"],
        decision_id=item["decision_id"],
        opportunity_id=item["opportunity_id"],
        project_id=item["project_id"],
        method=item["method"],
        confidence=Confidence(item["confidence"]),
        evidence_refs=tuple(json.loads(item["evidence_refs_json"] or "[]")),
        assumptions=tuple(json.loads(item["assumptions_json"] or "[]")),
        notes=item["notes"],
        status=ValueStatus(item["status"]),
        deduplication_key=item["deduplication_key"],
        causal_reference=item["causal_reference"],
        corrects_event_id=item["corrects_event_id"],
        supersedes_event_id=item["supersedes_event_id"],
    )


def record_value_event(
    conn, *, account_id, category, value_type, occurred_at, source,
    amount=None, currency=None, unit=None, method=None, confidence=Confidence.UNKNOWN,
    evidence_refs=(), assumptions=(), notes=None, status=None, decision_id=None,
    opportunity_id=None, project_id=None, event_id=None, deduplication_key=None,
    causal_reference=None, corrects_event_id=None, supersedes_event_id=None,
) -> ValueEvent:
    """Append one immutable value observation."""
    ensure_value_ledger_schema(conn)
    account = _clean_ref(account_id, "account_id")
    if account is None:
        raise ValueError("account_id is required")

    category = str(category or "").strip().lower()
    if category not in ALLOWED_CATEGORIES:
        raise ValueError(f"unsupported value category: {category}")
    vt = _enum(ValueType, value_type, "value_type")
    conf = _enum(Confidence, confidence, "confidence")
    st = (_enum(ValueStatus, status, "status") if status is not None
          else (ValueStatus.OBSERVED if vt != ValueType.UNKNOWN else ValueStatus.PROPOSED))
    amt = _decimal(amount)
    curr = _validate_currency(currency)
    clean_unit = _clean_ref(unit, "unit")
    method = _clean_ref(method, "method")
    clean_source = _clean_ref(source, "source")
    if clean_source is None:
        raise ValueError("source is required")

    if vt == ValueType.UNKNOWN and amt is not None:
        raise ValueError("UNKNOWN value cannot carry a numeric amount")
    if amt is not None and curr is None and clean_unit is None:
        raise ValueError("non-monetary amount requires unit")
    if curr is not None and clean_unit is not None:
        raise ValueError("event cannot mix currency and non-monetary unit")
    if curr is not None and amt is None and vt != ValueType.UNKNOWN:
        raise ValueError("monetary event requires amount unless value_type is UNKNOWN")
    if vt == ValueType.ESTIMATED and amt is not None and not method:
        raise ValueError("estimated value requires a traceable method")
    if vt == ValueType.QUALIFIED:
        if category != "qualified_opportunity":
            raise ValueError("QUALIFIED value is reserved for qualified_opportunity")
        if amt is None or curr is None or clean_unit is not None:
            raise ValueError("QUALIFIED opportunity value must be a monetary amount with currency")
    if category == "qualified_opportunity" and vt not in {ValueType.QUALIFIED, ValueType.UNKNOWN}:
        raise ValueError("qualified opportunity cannot be presented as measured/estimated value created")
    if corrects_event_id and supersedes_event_id:
        raise ValueError("event cannot both correct and supersede another event")

    eid = _clean_ref(event_id or str(uuid.uuid4()), "event_id")
    occurred = _utc_iso(occurred_at)
    recorded = _utc_iso(None, default_now=True)
    refs = _clean_list(evidence_refs, "evidence_ref")
    assumps = _clean_list(assumptions, "assumption")
    dedup = _clean_ref(deduplication_key, "deduplication_key")
    causal = _clean_ref(causal_reference, "causal_reference")
    corrects = _clean_ref(corrects_event_id, "corrects_event_id")
    supersedes = _clean_ref(supersedes_event_id, "supersedes_event_id")

    for relation, target in (("corrects", corrects), ("supersedes", supersedes)):
        if not target:
            continue
        target_row = conn.execute(
            "SELECT account_id FROM value_events WHERE event_id=?", (target,)
        ).fetchone()
        if target_row is None:
            raise ValueError(f"{relation} target does not exist")
        target_account = target_row["account_id"] if hasattr(target_row, "keys") else target_row[0]
        if target_account != account:
            raise ValueError(f"{relation} target belongs to another account")

    try:
        conn.execute(
            """INSERT INTO value_events(
                event_id, account_id, category, value_type, amount_text, currency, unit,
                occurred_at, recorded_at, source, decision_id, opportunity_id, project_id,
                method, confidence, evidence_refs_json, assumptions_json, notes, status,
                deduplication_key, causal_reference, corrects_event_id, supersedes_event_id
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                eid, account, category, vt.value, _decimal_text(amt), curr, clean_unit, occurred, recorded,
                clean_source, _clean_ref(decision_id, "decision_id"),
                _clean_ref(opportunity_id, "opportunity_id"), _clean_ref(project_id, "project_id"),
                method, conf.value, json.dumps(refs, ensure_ascii=False, separators=(",", ":")),
                json.dumps(assumps, ensure_ascii=False, separators=(",", ":")), notes, st.value,
                dedup, causal, corrects, supersedes,
            ),
        )
    except sqlite3.IntegrityError as exc:
        message = str(exc).upper()
        if dedup and "DEDUPLICATION_KEY" in message:
            raise ValueError("duplicate value event for account/deduplication_key") from exc
        if "EVENT_ID" in message:
            raise ValueError("duplicate event_id") from exc
        raise
    conn.commit()
    row = conn.execute(
        "SELECT * FROM value_events WHERE event_id=? AND account_id=?", (eid, account)
    ).fetchone()
    return _row_to_event(row)


def get_value_event(conn, *, account_id, event_id) -> ValueEvent | None:
    ensure_value_ledger_schema(conn)
    account = _clean_ref(account_id, "account_id")
    eid = _clean_ref(event_id, "event_id")
    if account is None or eid is None:
        return None
    row = conn.execute(
        "SELECT * FROM value_events WHERE account_id=? AND event_id=?", (account, eid)
    ).fetchone()
    return _row_to_event(row) if row else None


def _add_nested(target, *keys, amount: Decimal):
    current = target
    for key in keys[:-1]:
        current = current.setdefault(key, {})
    current[keys[-1]] = current.get(keys[-1], Decimal("0")) + amount


def _sorted_two_level(data):
    return {k: dict(sorted(v.items())) for k, v in sorted(data.items())}


def get_value_summary(conn, *, account_id, start_at=None, end_at=None) -> ValueSummary:
    """Return deterministic, type-separated value buckets for exactly one tenant.

    Known causal duplicates are counted once per value_type/currency/unit. If two
    active observations claim the same causal benefit but disagree on the amount,
    reporting fails closed instead of selecting a value based on row order.
    """
    ensure_value_ledger_schema(conn)
    account = _clean_ref(account_id, "account_id")
    if account is None:
        raise ValueError("account_id is required")
    start = _utc_iso(start_at) if start_at is not None else None
    end = _utc_iso(end_at) if end_at is not None else None
    if start and end and start > end:
        raise ValueError("start_at must not be after end_at")

    clauses = ["account_id=?", "status IN ('OBSERVED','VERIFIED')"]
    params = [account]
    if start:
        clauses.append("occurred_at>=?")
        params.append(start)
    if end:
        clauses.append("occurred_at<=?")
        params.append(end)
    rows = conn.execute(
        "SELECT * FROM value_events WHERE " + " AND ".join(clauses) + " ORDER BY occurred_at, id",
        tuple(params),
    ).fetchall()

    excluded_ids = {r["corrects_event_id"] for r in rows if r["corrects_event_id"]}
    excluded_ids |= {r["supersedes_event_id"] for r in rows if r["supersedes_event_id"]}

    measured, estimated, qualified = {}, {}, {}
    measured_time, estimated_time = {}, {}
    measured_other, estimated_other, breakdown = {}, {}, {}
    causal_amounts: dict[tuple[str, str, str, str], Decimal] = {}

    for row in rows:
        if row["event_id"] in excluded_ids:
            continue
        event = _row_to_event(row)
        amount = event.amount
        if amount is None:
            continue

        if event.causal_reference:
            causal_key = (
                event.causal_reference,
                event.value_type.value,
                event.currency or "",
                event.unit or "",
            )
            previous = causal_amounts.get(causal_key)
            if previous is not None:
                if previous != amount:
                    raise ValueError(
                        "conflicting amounts for causal_reference; reconcile with correction/supersession"
                    )
                continue
            causal_amounts[causal_key] = amount

        dimension = event.currency or event.unit or "unknown"
        _add_nested(breakdown, event.category, event.value_type.value, dimension, amount=amount)

        if event.currency:
            if event.value_type == ValueType.MEASURED:
                measured[event.currency] = measured.get(event.currency, Decimal("0")) + amount
            elif event.value_type == ValueType.ESTIMATED:
                estimated[event.currency] = estimated.get(event.currency, Decimal("0")) + amount
            elif event.value_type == ValueType.QUALIFIED:
                qualified[event.currency] = qualified.get(event.currency, Decimal("0")) + amount
            continue

        unit_name = event.unit or "unknown"
        if event.category == "time_saved":
            if event.value_type == ValueType.MEASURED:
                measured_time[unit_name] = measured_time.get(unit_name, Decimal("0")) + amount
            elif event.value_type == ValueType.ESTIMATED:
                estimated_time[unit_name] = estimated_time.get(unit_name, Decimal("0")) + amount
            continue

        if event.value_type == ValueType.MEASURED:
            measured_other.setdefault(event.category, {})[unit_name] = (
                measured_other.setdefault(event.category, {}).get(unit_name, Decimal("0")) + amount
            )
        elif event.value_type == ValueType.ESTIMATED:
            estimated_other.setdefault(event.category, {})[unit_name] = (
                estimated_other.setdefault(event.category, {}).get(unit_name, Decimal("0")) + amount
            )

    return ValueSummary(
        account_id=account,
        start_at=start,
        end_at=end,
        measured_by_currency=dict(sorted(measured.items())),
        estimated_by_currency=dict(sorted(estimated.items())),
        qualified_by_currency=dict(sorted(qualified.items())),
        time_saved_by_unit=dict(sorted(measured_time.items())),
        estimated_time_saved_by_unit=dict(sorted(estimated_time.items())),
        other_non_monetary=_sorted_two_level(measured_other),
        estimated_other_non_monetary=_sorted_two_level(estimated_other),
        breakdown={
            k: {t: dict(sorted(v.items())) for t, v in sorted(types.items())}
            for k, types in sorted(breakdown.items())
        },
    )