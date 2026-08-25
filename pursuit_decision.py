"""Append-only, account-scoped pursuit decision journal for opportunities."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

DECISION_TYPES = ("PURSUE", "NO_BID", "HOLD", "NEEDS_INFO", "UNDECIDED")
REASON_CODES = (
    "GOOD_FIT", "MARGIN_CONCERN", "DEADLINE_TOO_SHORT", "QUALIFICATION_GAP",
    "CAPACITY_CONSTRAINT", "LOCATION", "COMMERCIAL_RISK",
    "INSUFFICIENT_INFORMATION", "STRATEGIC_PRIORITY", "OTHER",
)
ACTOR_TYPES = ("HUMAN", "SYSTEM_SUGGESTED", "IMPORTED")

SCHEMA = '''CREATE TABLE IF NOT EXISTS opportunity_pursuit_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT NOT NULL UNIQUE,
    account_id TEXT NOT NULL,
    opportunity_id INTEGER NOT NULL,
    decision_type TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    actor_id TEXT,
    actor_type TEXT NOT NULL,
    reason_codes_json TEXT NOT NULL,
    freeform_note TEXT,
    blockers_json TEXT NOT NULL,
    unknowns_json TEXT NOT NULL,
    readiness_ref TEXT,
    evidence_refs_json TEXT NOT NULL,
    opportunity_revision_ref TEXT,
    opportunity_state_json TEXT NOT NULL,
    confidence REAL,
    supersedes_decision_id TEXT,
    idempotency_key TEXT,
    request_fingerprint TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(account_id, idempotency_key)
)'''


class DecisionValidationError(ValueError):
    pass


class IdempotencyConflict(ValueError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def ensure_pursuit_decision_table(conn):
    conn.execute(SCHEMA)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pursuit_decision_current ON opportunity_pursuit_decisions(account_id, opportunity_id, id DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pursuit_decision_supersedes ON opportunity_pursuit_decisions(account_id, supersedes_decision_id)")
    conn.commit()


def _choice(value, allowed, field):
    value = str(value or "").strip().upper()
    if value not in allowed:
        raise DecisionValidationError(f"invalid {field}: {value}")
    return value


def _text(value, field, max_length=500, required=False):
    if value is None:
        if required:
            raise DecisionValidationError(f"{field} is required")
        return None
    value = str(value).strip()
    if required and not value:
        raise DecisionValidationError(f"{field} is required")
    if len(value) > max_length:
        raise DecisionValidationError(f"{field} exceeds {max_length} characters")
    return value or None


def _list(value, field, max_items=25, max_item_length=500):
    if value in (None, ""):
        return []
    if not isinstance(value, (list, tuple)):
        raise DecisionValidationError(f"{field} must be a list")
    if len(value) > max_items:
        raise DecisionValidationError(f"{field} exceeds {max_items} items")
    out = []
    for item in value:
        item = _text(item, field, max_item_length, True)
        if item not in out:
            out.append(item)
    return out


def _confidence(value):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise DecisionValidationError("confidence must be a number") from exc
    if not 0 <= value <= 1:
        raise DecisionValidationError("confidence must be between 0 and 1")
    return value


def _decode(row):
    if row is None:
        return None
    item = dict(row)
    for target, source, default in (
        ("reason_codes", "reason_codes_json", "[]"),
        ("blockers", "blockers_json", "[]"),
        ("unknowns", "unknowns_json", "[]"),
        ("evidence_refs", "evidence_refs_json", "[]"),
        ("opportunity_state", "opportunity_state_json", "{}"),
    ):
        item[target] = json.loads(item.pop(source) or default)
    item.pop("request_fingerprint", None)
    item.pop("id", None)
    return item


def _current_row(conn, account_id, opportunity_id):
    return conn.execute(
        '''SELECT d.* FROM opportunity_pursuit_decisions d
           WHERE d.account_id=? AND d.opportunity_id=?
             AND NOT EXISTS (
                 SELECT 1 FROM opportunity_pursuit_decisions n
                 WHERE n.account_id=d.account_id AND n.supersedes_decision_id=d.decision_id
             )
           ORDER BY d.id DESC LIMIT 1''',
        (str(account_id), int(opportunity_id)),
    ).fetchone()


def current_decision(conn, account_id, opportunity_id):
    ensure_pursuit_decision_table(conn)
    return _decode(_current_row(conn, account_id, opportunity_id))


def decision_history(conn, account_id, opportunity_id):
    ensure_pursuit_decision_table(conn)
    rows = conn.execute(
        '''SELECT * FROM opportunity_pursuit_decisions
           WHERE account_id=? AND opportunity_id=?
           ORDER BY decided_at ASC, created_at ASC, id ASC''',
        (str(account_id), int(opportunity_id)),
    ).fetchall()
    return [_decode(row) for row in rows]


def record_pursuit_decision(conn, *, account_id, opportunity_id, decision_type,
                            reason_codes=None, freeform_note=None, blockers=None,
                            unknowns=None, readiness_ref=None, evidence_refs=None,
                            opportunity_revision_ref=None, opportunity_state=None,
                            confidence=None, actor_id=None, actor_type="HUMAN",
                            decided_at=None, idempotency_key=None):
    """Append a commercial choice; never infer it from readiness or mutate Opportunity."""
    ensure_pursuit_decision_table(conn)
    account_id = _text(account_id, "account_id", 64, True)
    try:
        opportunity_id = int(opportunity_id)
    except (TypeError, ValueError) as exc:
        raise DecisionValidationError("opportunity_id must be an integer") from exc
    if opportunity_id <= 0:
        raise DecisionValidationError("opportunity_id must be positive")
    decision_type = _choice(decision_type, DECISION_TYPES, "decision_type")
    actor_type = _choice(actor_type, ACTOR_TYPES, "actor_type")
    reason_codes = _list(reason_codes, "reason_codes", 10, 64)
    invalid = [code for code in reason_codes if code.upper() not in REASON_CODES]
    if invalid:
        raise DecisionValidationError(f"invalid reason_code: {invalid[0]}")
    reason_codes = [code.upper() for code in reason_codes]
    freeform_note = _text(freeform_note, "freeform_note", 1000)
    blockers = _list(blockers, "blockers", 25, 500)
    unknowns = _list(unknowns, "unknowns", 25, 500)
    evidence_refs = _list(evidence_refs, "evidence_refs", 50, 250)
    readiness_ref = _text(readiness_ref, "readiness_ref", 250)
    opportunity_revision_ref = _text(opportunity_revision_ref, "opportunity_revision_ref", 250)
    actor_id = _text(actor_id, "actor_id", 250)
    idempotency_key = _text(idempotency_key, "idempotency_key", 250)
    confidence = _confidence(confidence)
    opportunity_state = {} if opportunity_state is None else opportunity_state
    if not isinstance(opportunity_state, dict):
        raise DecisionValidationError("opportunity_state must be an object")
    requested_decided_at = _text(decided_at, "decided_at", 80)
    normalized = {
        "opportunity_id": opportunity_id, "decision_type": decision_type,
        "reason_codes": reason_codes, "freeform_note": freeform_note,
        "blockers": blockers, "unknowns": unknowns, "readiness_ref": readiness_ref,
        "evidence_refs": evidence_refs, "opportunity_revision_ref": opportunity_revision_ref,
        "opportunity_state": opportunity_state, "confidence": confidence,
        "actor_id": actor_id, "actor_type": actor_type, "decided_at": requested_decided_at,
    }
    fingerprint = hashlib.sha256(json.dumps(normalized, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    if idempotency_key:
        existing = conn.execute(
            "SELECT * FROM opportunity_pursuit_decisions WHERE account_id=? AND idempotency_key=?",
            (account_id, idempotency_key),
        ).fetchone()
        if existing is not None:
            if existing["request_fingerprint"] != fingerprint:
                raise IdempotencyConflict("idempotency key already used with a different request")
            return _decode(existing), False
    previous = _current_row(conn, account_id, opportunity_id)
    decision_id = str(uuid.uuid4())
    created_at = _now()
    conn.execute(
        '''INSERT INTO opportunity_pursuit_decisions(
           decision_id, account_id, opportunity_id, decision_type, decided_at,
           actor_id, actor_type, reason_codes_json, freeform_note, blockers_json,
           unknowns_json, readiness_ref, evidence_refs_json, opportunity_revision_ref,
           opportunity_state_json, confidence, supersedes_decision_id, idempotency_key,
           request_fingerprint, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (decision_id, account_id, opportunity_id, decision_type, requested_decided_at or created_at,
         actor_id, actor_type, json.dumps(reason_codes, ensure_ascii=False), freeform_note,
         json.dumps(blockers, ensure_ascii=False), json.dumps(unknowns, ensure_ascii=False),
         readiness_ref, json.dumps(evidence_refs, ensure_ascii=False), opportunity_revision_ref,
         json.dumps(opportunity_state, ensure_ascii=False, sort_keys=True), confidence,
         previous["decision_id"] if previous else None, idempotency_key, fingerprint, created_at),
    )
    conn.commit()
    return _decode(conn.execute("SELECT * FROM opportunity_pursuit_decisions WHERE decision_id=?", (decision_id,)).fetchone()), True
