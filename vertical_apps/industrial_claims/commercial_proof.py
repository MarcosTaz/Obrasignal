from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


class CommercialProofError(ValueError):
    pass


REAL = "REAL"
TEST = "TEST"

EVENT_TYPES = {
    "QUALIFIED_BUYER",
    "BOUNDED_CASE_CONFIRMED",
    "SECURE_DATA_PATH_WILLINGNESS",
    "PAID_AUDIT_COMMITMENT",
    "CUSTOMER_PAYMENT",
    "VERIFIED_CASE_OUTCOME",
    "REPEAT_OR_MONITORING_INTENT",
}


@dataclass(frozen=True)
class CommercialProofEvent:
    event_id: str
    account_id: str
    event_type: str
    evidence_class: str
    evidence_ref: str
    actor_id: str
    created_at: str


@dataclass(frozen=True)
class CommercialProofState:
    account_id: str
    stage: str
    real_event_types: tuple[str, ...]
    test_event_types: tuple[str, ...]
    real_customer_payment_proven: bool
    paid_audit_proven: bool
    verified_outcome_proven: bool
    repeat_intent_proven: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "account_id": self.account_id,
            "stage": self.stage,
            "real_event_types": list(self.real_event_types),
            "test_event_types": list(self.test_event_types),
            "real_customer_payment_proven": self.real_customer_payment_proven,
            "paid_audit_proven": self.paid_audit_proven,
            "verified_outcome_proven": self.verified_outcome_proven,
            "repeat_intent_proven": self.repeat_intent_proven,
            "test_or_synthetic_evidence_counts_as_commercial_proof": False,
        }


def _text(value: object, *, label: str, limit: int = 512) -> str:
    text = str(value or "").strip()
    if not text:
        raise CommercialProofError(f"{label} is required")
    if len(text) > limit:
        raise CommercialProofError(f"{label} is too long")
    if any((ord(char) < 32 and char not in "\t\n\r") or ord(char) == 127 for char in text):
        raise CommercialProofError(f"{label} contains forbidden control characters")
    return text


class CommercialProofStore:
    """Append-only VINDORUM proof ledger separating market truth from tests."""

    TABLE = "vindorum_commercial_proof_events"
    ACCOUNT_INDEX = "idx_vindorum_commercial_proof_account"

    def __init__(self, database: str | Path):
        self.database = str(database)
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE} (
                    event_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    evidence_class TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {self.ACCOUNT_INDEX}
                ON {self.TABLE} (account_id, created_at, event_id)
                """
            )
            connection.commit()

    def append(self, *, event_id: str, account_id: str, event_type: str, evidence_class: str, evidence_ref: str, actor_id: str) -> CommercialProofEvent:
        event = _text(event_id, label="event_id")
        account = _text(account_id, label="account_id")
        kind = _text(event_type, label="event_type").upper()
        if kind not in EVENT_TYPES:
            raise CommercialProofError("unsupported commercial proof event type")
        klass = _text(evidence_class, label="evidence_class").upper()
        if klass not in {REAL, TEST}:
            raise CommercialProofError("evidence_class must be REAL or TEST")
        reference = _text(evidence_ref, label="evidence_ref", limit=2048)
        actor = _text(actor_id, label="actor_id")

        with sqlite3.connect(self.database) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(f"SELECT * FROM {self.TABLE} WHERE event_id=?", (event,)).fetchone()
            if existing is not None:
                same = (
                    str(existing["account_id"]) == account
                    and str(existing["event_type"]) == kind
                    and str(existing["evidence_class"]) == klass
                    and str(existing["evidence_ref"]) == reference
                    and str(existing["actor_id"]) == actor
                )
                if not same:
                    raise CommercialProofError("commercial proof event id collision")
                connection.commit()
                return self._event(existing)

            connection.execute(
                f"INSERT INTO {self.TABLE} (event_id,account_id,event_type,evidence_class,evidence_ref,actor_id) VALUES (?,?,?,?,?,?)",
                (event, account, kind, klass, reference, actor),
            )
            row = connection.execute(f"SELECT * FROM {self.TABLE} WHERE event_id=?", (event,)).fetchone()
            connection.commit()

        if row is None:
            raise CommercialProofError("commercial proof persistence failed")
        return self._event(row)

    @staticmethod
    def _event(row: sqlite3.Row) -> CommercialProofEvent:
        return CommercialProofEvent(
            event_id=str(row["event_id"]), account_id=str(row["account_id"]), event_type=str(row["event_type"]),
            evidence_class=str(row["evidence_class"]), evidence_ref=str(row["evidence_ref"]), actor_id=str(row["actor_id"]),
            created_at=str(row["created_at"]),
        )

    def events(self, *, account_id: str) -> tuple[CommercialProofEvent, ...]:
        account = _text(account_id, label="account_id")
        with sqlite3.connect(self.database) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"SELECT * FROM {self.TABLE} WHERE account_id=? ORDER BY created_at ASC, event_id ASC", (account,)
            ).fetchall()
        return tuple(self._event(row) for row in rows)

    def state(self, *, account_id: str) -> CommercialProofState:
        account = _text(account_id, label="account_id")
        events = self.events(account_id=account)
        real_types = {event.event_type for event in events if event.evidence_class == REAL}
        test_types = {event.event_type for event in events if event.evidence_class == TEST}

        stage = "T0_INTERNAL_ONLY"
        if "QUALIFIED_BUYER" in real_types:
            stage = "T1_QUALIFIED_BUYER"
            if "BOUNDED_CASE_CONFIRMED" in real_types:
                stage = "T2_BOUNDED_REAL_CASE"
                if "PAID_AUDIT_COMMITMENT" in real_types:
                    stage = "T3_COSTLY_COMMERCIAL_COMMITMENT"
                    if "VERIFIED_CASE_OUTCOME" in real_types:
                        stage = "T4_VERIFIED_OUTCOME"
                        if "CUSTOMER_PAYMENT" in real_types and "REPEAT_OR_MONITORING_INTENT" in real_types:
                            stage = "T5_PAYMENT_AND_REPEAT_SIGNAL"

        return CommercialProofState(
            account_id=account,
            stage=stage,
            real_event_types=tuple(sorted(real_types)),
            test_event_types=tuple(sorted(test_types)),
            real_customer_payment_proven="CUSTOMER_PAYMENT" in real_types,
            paid_audit_proven="PAID_AUDIT_COMMITMENT" in real_types,
            verified_outcome_proven="VERIFIED_CASE_OUTCOME" in real_types,
            repeat_intent_proven="REPEAT_OR_MONITORING_INTENT" in real_types,
        )
