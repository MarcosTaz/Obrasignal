"""Tenant-scoped, append-only opportunity outcome capture.

Decision and outcome are intentionally separate.  This module records observed or
explicitly confirmed post-decision facts without inferring win/loss from pursuit,
watchlist state, missing awards, or organization-name similarity.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
import uuid

OUTCOME_TYPES = (
    "BID_SUBMITTED",
    "WON",
    "LOST",
    "WITHDRAWN",
    "NO_SUBMISSION",
    "CANCELLED",
    "UNKNOWN",
)
SOURCE_TYPES = (
    "OFFICIAL_SOURCE",
    "USER_CONFIRMED",
    "SYSTEM_DERIVED",
    "IMPORTED",
    "UNKNOWN",
)
REASON_CODES = (
    "PRICE",
    "QUALIFICATION",
    "TECHNICAL",
    "CAPACITY",
    "DEADLINE",
    "WITHDRAWN",
    "NO_SUBMISSION",
    "BUYER_DECISION",
    "CANCELLED_PROCEDURE",
    "UNKNOWN",
    "OTHER",
)
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

SCHEMA = '''CREATE TABLE IF NOT EXISTS opportunity_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    outcome_id TEXT NOT NULL UNIQUE,
    account_id TEXT NOT NULL,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    lot_id TEXT,
    decision_id TEXT,
    outcome_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_ref TEXT,
    source_publication TEXT,
    source_native_id TEXT,
    award_value TEXT,
    currency TEXT,
    reason_code TEXT,
    note TEXT,
    evidence_refs_json TEXT NOT NULL,
    confidence REAL,
    supersedes_outcome_id TEXT,
    idempotency_key TEXT,
    request_fingerprint TEXT NOT NULL,
    official_event_key TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(account_id, idempotency_key),
    UNIQUE(account_id, official_event_key)
)'''


class OutcomeValidationError(ValueError):
    pass


class OutcomeIdempotencyConflict(ValueError):
    pass


class OutcomeNotFound(LookupError):
    pass


def _now_dt():
    return datetime.now(timezone.utc)


def _now():
    return _now_dt().isoformat()


def ensure_outcome_table(conn):
    """Backward-compatible migration: only adds a new capability-owned table."""
    conn.execute(SCHEMA)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_outcome_current "
        "ON opportunity_outcomes(account_id, source, external_id, lot_id, id DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_outcome_supersedes "
        "ON opportunity_outcomes(account_id, supersedes_outcome_id)"
    )
    conn.commit()


def _choice(value, allowed, field):
    value = str(value or "").strip().upper()
    if value not in allowed:
        raise OutcomeValidationError(f"invalid {field}: {value}")
    return value


def _text(value, field, max_length=500, required=False):
    if value is None:
        if required:
            raise OutcomeValidationError(f"{field} is required")
        return None
    value = str(value).strip()
    if required and not value:
        raise OutcomeValidationError(f"{field} is required")
    if len(value) > max_length:
        raise OutcomeValidationError(f"{field} exceeds {max_length} characters")
    if _CONTROL_RE.search(value):
        raise OutcomeValidationError(f"{field} contains unsafe control characters")
    return value or None


def _timestamp(value, field, *, default_now=False, reject_future=False):
    if value in (None, ""):
        if default_now:
            return _now()
        raise OutcomeValidationError(f"{field} is required")
    text = _text(value, field, 80, True)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OutcomeValidationError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise OutcomeValidationError(f"{field} must include a timezone")
    parsed = parsed.astimezone(timezone.utc)
    if reject_future and parsed > _now_dt() + timedelta(minutes=5):
        raise OutcomeValidationError(f"{field} cannot be in the future")
    return parsed.isoformat()


def _evidence_refs(value):
    if value in (None, ""):
        return []
    if not isinstance(value, (list, tuple)):
        raise OutcomeValidationError("evidence_refs must be a list")
    if len(value) > 50:
        raise OutcomeValidationError("evidence_refs exceeds 50 items")
    result = []
    for item in value:
        item = _text(item, "evidence_ref", 500, True)
        if item not in result:
            result.append(item)
    return result


def _confidence(value):
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise OutcomeValidationError("confidence must be a number") from exc
    if not 0 <= result <= 1:
        raise OutcomeValidationError("confidence must be between 0 and 1")
    return result


def _money(value, currency, outcome_type):
    if value in (None, ""):
        if currency not in (None, ""):
            raise OutcomeValidationError("currency requires award_value")
        return None, None
    if outcome_type != "WON":
        raise OutcomeValidationError("award_value is only valid for WON outcomes")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise OutcomeValidationError("award_value must be a decimal number") from exc
    if not amount.is_finite() or amount < 0:
        raise OutcomeValidationError("award_value must be finite and non-negative")
    if len(amount.as_tuple().digits) > 24:
        raise OutcomeValidationError("award_value exceeds supported precision")
    currency = str(currency or "").strip().upper()
    if not _CURRENCY_RE.fullmatch(currency):
        raise OutcomeValidationError("currency must be a three-letter code")
    normalized = format(amount, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".") or "0"
    return normalized, currency


def _table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _resolve_opportunity(conn, source, external_id):
    """Resolve an existing Opportunity without mutating it.

    The production product still has a legacy ``tenders`` projection while the
    provenance-first Signal store is canonical for normalized signals.  Accept
    either existing representation and return the legacy integer id when present
    so a parallel Decision Journal reference can be verified safely.
    """
    source = _text(source, "source", 100, True)
    external_id = _text(external_id, "external_id", 250, True)
    tender_id = None
    if _table_exists(conn, "tenders"):
        row = conn.execute(
            "SELECT id FROM tenders WHERE source=? AND external_id=?",
            (source, external_id),
        ).fetchone()
        tender_id = int(row[0]) if row else None
    signal_exists = False
    if _table_exists(conn, "signal_records"):
        signal_exists = conn.execute(
            "SELECT 1 FROM signal_records WHERE source=? AND signal_type='TENDER' AND external_id=?",
            (source, external_id),
        ).fetchone() is not None
    if tender_id is None and not signal_exists:
        raise OutcomeNotFound("opportunity not found")
    return source, external_id, tender_id


def _validate_decision_ref(conn, account_id, decision_id, tender_id):
    decision_id = _text(decision_id, "decision_id", 100)
    if not decision_id:
        return None
    if not _table_exists(conn, "opportunity_pursuit_decisions"):
        raise OutcomeValidationError("decision reference is not available in this repository state")
    if tender_id is None:
        raise OutcomeValidationError("decision reference requires a legacy opportunity id mapping")
    row = conn.execute(
        "SELECT 1 FROM opportunity_pursuit_decisions WHERE decision_id=? AND account_id=? AND opportunity_id=?",
        (decision_id, account_id, tender_id),
    ).fetchone()
    if row is None:
        raise OutcomeValidationError("decision reference does not belong to this account/opportunity")
    return decision_id


def _decode(row, status=None):
    if row is None:
        return None
    item = dict(row)
    item["evidence_refs"] = json.loads(item.pop("evidence_refs_json") or "[]")
    item.pop("request_fingerprint", None)
    item.pop("official_event_key", None)
    item.pop("id", None)
    if status:
        item["status"] = status
    return item


def _current_row(conn, account_id, source, external_id, lot_id=None):
    lot_clause = "lot_id IS NULL" if lot_id is None else "lot_id=?"
    params = [str(account_id), str(source), str(external_id)]
    if lot_id is not None:
        params.append(str(lot_id))
    return conn.execute(
        f'''SELECT d.* FROM opportunity_outcomes d
            WHERE d.account_id=? AND d.source=? AND d.external_id=? AND {lot_clause}
              AND NOT EXISTS (
                  SELECT 1 FROM opportunity_outcomes n
                  WHERE n.account_id=d.account_id
                    AND n.supersedes_outcome_id=d.outcome_id
              )
            ORDER BY d.id DESC LIMIT 1''',
        params,
    ).fetchone()


def current_outcome(conn, account_id, source, external_id, lot_id=None):
    ensure_outcome_table(conn)
    return _decode(_current_row(conn, account_id, source, external_id, lot_id), "CURRENT")


def outcome_history(conn, account_id, source, external_id, lot_id=None):
    ensure_outcome_table(conn)
    lot_clause = "d.lot_id IS NULL" if lot_id is None else "d.lot_id=?"
    params = [str(account_id), str(source), str(external_id)]
    if lot_id is not None:
        params.append(str(lot_id))
    rows = conn.execute(
        f'''SELECT d.*,
                   CASE WHEN EXISTS (
                       SELECT 1 FROM opportunity_outcomes n
                       WHERE n.account_id=d.account_id
                         AND n.supersedes_outcome_id=d.outcome_id
                   ) THEN 1 ELSE 0 END AS is_superseded
            FROM opportunity_outcomes d
            WHERE d.account_id=? AND d.source=? AND d.external_id=? AND {lot_clause}
            ORDER BY d.id ASC''',
        params,
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        superseded = bool(item.pop("is_superseded"))
        result.append(_decode(item, "SUPERSEDED" if superseded else "CURRENT"))
    return result


def _official_event_key(account_id, source, external_id, lot_id, outcome_type,
                        source_native_id, source_ref, source_type):
    if source_type not in ("OFFICIAL_SOURCE", "SYSTEM_DERIVED"):
        return None
    native = source_native_id or source_ref
    if not native:
        return None
    raw = "|".join(
        str(x or "") for x in
        (account_id, source, external_id, lot_id, outcome_type, source_type, native)
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def record_outcome(
    conn,
    *,
    account_id,
    source,
    external_id,
    outcome_type,
    occurred_at=None,
    source_type="USER_CONFIRMED",
    lot_id=None,
    decision_id=None,
    source_ref=None,
    source_publication=None,
    source_native_id=None,
    award_value=None,
    currency=None,
    reason_code=None,
    note=None,
    evidence_refs=None,
    confidence=None,
    supersedes_outcome_id=None,
    idempotency_key=None,
):
    """Append one observed/confirmed outcome; never mutate Opportunity or Decision."""
    ensure_outcome_table(conn)
    account_id = _text(account_id, "account_id", 64, True)
    source, external_id, tender_id = _resolve_opportunity(conn, source, external_id)
    lot_id = _text(lot_id, "lot_id", 250)
    decision_id = _validate_decision_ref(conn, account_id, decision_id, tender_id)
    outcome_type = _choice(outcome_type, OUTCOME_TYPES, "outcome_type")
    source_type = _choice(source_type, SOURCE_TYPES, "source_type")
    reason_code = _choice(reason_code, REASON_CODES, "reason_code") if reason_code else None
    occurred_at = _timestamp(occurred_at, "occurred_at", default_now=True, reject_future=True)
    recorded_at = _now()
    source_ref = _text(source_ref, "source_ref", 500)
    source_publication = _text(source_publication, "source_publication", 250)
    source_native_id = _text(source_native_id, "source_native_id", 250)
    note = _text(note, "note", 1000)
    evidence_refs = _evidence_refs(evidence_refs)
    confidence = _confidence(confidence)
    idempotency_key = _text(idempotency_key, "idempotency_key", 250)
    supersedes_outcome_id = _text(supersedes_outcome_id, "supersedes_outcome_id", 100)
    award_value, currency = _money(award_value, currency, outcome_type)

    if source_type in ("OFFICIAL_SOURCE", "SYSTEM_DERIVED") and not (
        source_ref or source_native_id or evidence_refs
    ):
        raise OutcomeValidationError("official/derived outcomes require provenance")

    if supersedes_outcome_id:
        previous = conn.execute(
            '''SELECT * FROM opportunity_outcomes
               WHERE outcome_id=? AND account_id=? AND source=? AND external_id=?''',
            (supersedes_outcome_id, account_id, source, external_id),
        ).fetchone()
        if previous is None:
            raise OutcomeValidationError("superseded outcome does not belong to this account/opportunity")
        previous_lot = previous["lot_id"]
        if (previous_lot or None) != (lot_id or None):
            raise OutcomeValidationError("correction must preserve lot scope")
        already = conn.execute(
            "SELECT 1 FROM opportunity_outcomes WHERE account_id=? AND supersedes_outcome_id=?",
            (account_id, supersedes_outcome_id),
        ).fetchone()
        if already is not None:
            raise OutcomeValidationError("outcome has already been superseded")

    normalized = {
        "source": source,
        "external_id": external_id,
        "lot_id": lot_id,
        "decision_id": decision_id,
        "outcome_type": outcome_type,
        "occurred_at": occurred_at,
        "source_type": source_type,
        "source_ref": source_ref,
        "source_publication": source_publication,
        "source_native_id": source_native_id,
        "award_value": award_value,
        "currency": currency,
        "reason_code": reason_code,
        "note": note,
        "evidence_refs": evidence_refs,
        "confidence": confidence,
        "supersedes_outcome_id": supersedes_outcome_id,
    }
    fingerprint = hashlib.sha256(
        json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    if idempotency_key:
        existing = conn.execute(
            "SELECT * FROM opportunity_outcomes WHERE account_id=? AND idempotency_key=?",
            (account_id, idempotency_key),
        ).fetchone()
        if existing is not None:
            if existing["request_fingerprint"] != fingerprint:
                raise OutcomeIdempotencyConflict(
                    "idempotency key already used with a different request"
                )
            return _decode(existing, "CURRENT"), False

    official_key = _official_event_key(
        account_id, source, external_id, lot_id, outcome_type,
        source_native_id, source_ref, source_type,
    )
    if official_key:
        existing = conn.execute(
            "SELECT * FROM opportunity_outcomes WHERE account_id=? AND official_event_key=?",
            (account_id, official_key),
        ).fetchone()
        if existing is not None:
            return _decode(existing, "CURRENT"), False

    outcome_id = str(uuid.uuid4())
    created_at = recorded_at
    conn.execute(
        '''INSERT INTO opportunity_outcomes(
           outcome_id, account_id, source, external_id, lot_id, decision_id,
           outcome_type, occurred_at, recorded_at, source_type, source_ref,
           source_publication, source_native_id, award_value, currency, reason_code,
           note, evidence_refs_json, confidence, supersedes_outcome_id,
           idempotency_key, request_fingerprint, official_event_key, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (
            outcome_id, account_id, source, external_id, lot_id, decision_id,
            outcome_type, occurred_at, recorded_at, source_type, source_ref,
            source_publication, source_native_id, award_value, currency, reason_code,
            note, json.dumps(evidence_refs, ensure_ascii=False), confidence,
            supersedes_outcome_id, idempotency_key, fingerprint, official_key, created_at,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM opportunity_outcomes WHERE outcome_id=?", (outcome_id,)
    ).fetchone()
    return _decode(row, "CURRENT"), True


def correct_outcome(conn, *, account_id, outcome_id, **changes):
    """Correct by appending a new version; historical data remains queryable."""
    ensure_outcome_table(conn)
    account_id = _text(account_id, "account_id", 64, True)
    previous = conn.execute(
        "SELECT * FROM opportunity_outcomes WHERE outcome_id=? AND account_id=?",
        (_text(outcome_id, "outcome_id", 100, True), account_id),
    ).fetchone()
    if previous is None:
        raise OutcomeNotFound("outcome not found")
    defaults = {
        "source": previous["source"],
        "external_id": previous["external_id"],
        "lot_id": previous["lot_id"],
        "decision_id": previous["decision_id"],
        "outcome_type": previous["outcome_type"],
        "occurred_at": previous["occurred_at"],
        "source_type": previous["source_type"],
        "source_ref": previous["source_ref"],
        "source_publication": previous["source_publication"],
        "source_native_id": previous["source_native_id"],
        "award_value": previous["award_value"],
        "currency": previous["currency"],
        "reason_code": previous["reason_code"],
        "note": previous["note"],
        "evidence_refs": json.loads(previous["evidence_refs_json"] or "[]"),
        "confidence": previous["confidence"],
    }
    allowed = set(defaults) - {"source", "external_id", "lot_id"}
    unknown = set(changes) - allowed - {"idempotency_key"}
    if unknown:
        raise OutcomeValidationError(f"unsupported correction field: {sorted(unknown)[0]}")
    for key in allowed:
        if key in changes:
            defaults[key] = changes[key]
    return record_outcome(
        conn,
        account_id=account_id,
        supersedes_outcome_id=previous["outcome_id"],
        idempotency_key=changes.get("idempotency_key"),
        **defaults,
    )


def official_award_candidate(
    *,
    account_identifiers,
    winner_identifiers=None,
    procedure_cancelled=False,
    source_ref=None,
    source_native_id=None,
    occurred_at=None,
    award_value=None,
    currency=None,
    lot_id=None,
):
    """Return a safe candidate from official facts, or ``None`` when identity is uncertain.

    Identifiers are exact canonical strings (preferably ``scheme:id``). Names are
    deliberately not accepted.  Another winner or the absence of an award is not
    evidence that this account lost.
    """
    if procedure_cancelled:
        return {
            "outcome_type": "CANCELLED",
            "source_type": "SYSTEM_DERIVED",
            "source_ref": source_ref,
            "source_native_id": source_native_id,
            "occurred_at": occurred_at,
            "lot_id": lot_id,
            "reason_code": "CANCELLED_PROCEDURE",
        }
    account_ids = {str(v).strip() for v in (account_identifiers or []) if str(v).strip()}
    winner_ids = {str(v).strip() for v in (winner_identifiers or []) if str(v).strip()}
    if not account_ids or not winner_ids or account_ids.isdisjoint(winner_ids):
        return None
    return {
        "outcome_type": "WON",
        "source_type": "OFFICIAL_SOURCE",
        "source_ref": source_ref,
        "source_native_id": source_native_id,
        "occurred_at": occurred_at,
        "award_value": award_value,
        "currency": currency,
        "lot_id": lot_id,
    }
