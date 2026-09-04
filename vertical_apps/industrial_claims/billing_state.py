from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


class BillingStateError(ValueError):
    pass


@dataclass(frozen=True)
class BillingState:
    account_id: str
    customer_id: str | None
    subscription_id: str | None
    state: str
    last_event_id: str


class BillingStateStore:
    """Server-verified billing projection for VINDORUM.

    Client-side checkout success never grants paid access. State changes only
    from verified payment-provider events supplied by the webhook boundary.
    Event receipts are immutable, stale delivery cannot regress the projection,
    and an existing account/customer binding cannot be silently rebound.
    """

    _TERMINAL_STATES = {"CANCELLED", "REFUNDED"}

    def __init__(self, database: str | Path):
        self.database = str(database)
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS vindorum_billing_state (
                    account_id TEXT PRIMARY KEY,
                    customer_id TEXT,
                    subscription_id TEXT,
                    state TEXT NOT NULL,
                    last_event_id TEXT NOT NULL,
                    last_event_created INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS vindorum_billing_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    event_created INTEGER NOT NULL DEFAULT 0,
                    event_fingerprint TEXT,
                    applied_to_projection INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            self._ensure_column(
                connection,
                "vindorum_billing_state",
                "last_event_created",
                "INTEGER NOT NULL DEFAULT 0",
            )
            self._ensure_column(
                connection,
                "vindorum_billing_events",
                "event_created",
                "INTEGER NOT NULL DEFAULT 0",
            )
            self._ensure_column(
                connection,
                "vindorum_billing_events",
                "event_fingerprint",
                "TEXT",
            )
            self._ensure_column(
                connection,
                "vindorum_billing_events",
                "applied_to_projection",
                "INTEGER NOT NULL DEFAULT 1",
            )

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    @staticmethod
    def _text(value, field: str, *, optional: bool = False) -> str | None:
        if value is None and optional:
            return None
        text = str(value or "").strip()
        if not text:
            if optional:
                return None
            raise BillingStateError(f"{field} is required")
        if len(text) > 512:
            raise BillingStateError(f"{field} is too long")
        return text

    @staticmethod
    def _event_created(value) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise BillingStateError("event created must be a non-negative integer")
        return value

    @staticmethod
    def _fingerprint(event: dict) -> str:
        try:
            canonical = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise BillingStateError("event must be JSON serializable") from exc
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _row_to_state(row) -> BillingState:
        return BillingState(row[0], row[1], row[2], row[3], row[4])

    @staticmethod
    def _insert_receipt(
        connection: sqlite3.Connection,
        *,
        event_id: str,
        event_type: str,
        account_id: str,
        event_created: int,
        fingerprint: str,
        applied: bool,
    ) -> None:
        connection.execute(
            """
            INSERT INTO vindorum_billing_events(
                event_id, event_type, account_id, event_created, event_fingerprint, applied_to_projection
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, event_type, account_id, event_created, fingerprint, int(applied)),
        )

    @classmethod
    def _ignore_without_regression(
        cls,
        *,
        current_state: str,
        current_subscription: str | None,
        incoming_subscription: str | None,
        next_state: str,
    ) -> bool:
        subscription_rebind = bool(
            current_subscription and incoming_subscription and incoming_subscription != current_subscription
        )
        if current_state == "REFUNDED" and not subscription_rebind:
            return next_state != "REFUNDED"
        if current_state == "CANCELLED" and not subscription_rebind:
            return next_state in {"PENDING_PAYMENT_CONFIRMATION", "ACTIVE", "PAST_DUE"}
        if current_state in {"ACTIVE", "PAST_DUE"} and next_state == "PENDING_PAYMENT_CONFIRMATION":
            return True
        return False

    @classmethod
    def _same_timestamp_transition_is_safe(
        cls,
        *,
        current_state: str,
        next_state: str,
        subscription_rebind: bool,
    ) -> bool:
        if current_state == next_state:
            return True
        if subscription_rebind and current_state in cls._TERMINAL_STATES:
            return next_state in {"PENDING_PAYMENT_CONFIRMATION", "ACTIVE"}
        return (current_state, next_state) in {
            ("PENDING_PAYMENT_CONFIRMATION", "ACTIVE"),
            ("PENDING_PAYMENT_CONFIRMATION", "PAST_DUE"),
            ("PENDING_PAYMENT_CONFIRMATION", "CANCELLED"),
            ("PENDING_PAYMENT_CONFIRMATION", "REFUNDED"),
            ("ACTIVE", "CANCELLED"),
            ("ACTIVE", "REFUNDED"),
            ("PAST_DUE", "CANCELLED"),
            ("PAST_DUE", "REFUNDED"),
            ("CANCELLED", "REFUNDED"),
        }

    def apply_verified_event(self, event: dict) -> BillingState:
        if not isinstance(event, dict):
            raise BillingStateError("event must be an object")
        event_id = self._text(event.get("id"), "event id")
        event_type = self._text(event.get("type"), "event type")
        event_created = self._event_created(event.get("created"))
        fingerprint = self._fingerprint(event)
        data = event.get("data")
        obj = data.get("object") if isinstance(data, dict) else None
        if not isinstance(obj, dict):
            raise BillingStateError("event object is required")
        metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
        account_id = self._text(metadata.get("vindorum_account_id"), "vindorum_account_id")
        customer_id = self._text(obj.get("customer"), "customer", optional=True)
        subscription_id = self._text(
            obj.get("subscription") or obj.get("id" if event_type.startswith("customer.subscription.") else ""),
            "subscription",
            optional=True,
        )

        transitions = {
            "checkout.session.completed": "PENDING_PAYMENT_CONFIRMATION",
            "invoice.paid": "ACTIVE",
            "invoice.payment_failed": "PAST_DUE",
            "customer.subscription.deleted": "CANCELLED",
            "charge.refunded": "REFUNDED",
        }
        next_state = transitions.get(event_type)
        if next_state is None:
            raise BillingStateError("unsupported billing event type")

        with sqlite3.connect(self.database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            seen = connection.execute(
                """
                SELECT event_type, account_id, event_created, event_fingerprint
                FROM vindorum_billing_events WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()
            if seen:
                if seen != (event_type, account_id, event_created, fingerprint):
                    raise BillingStateError("event id collision")
                row = connection.execute(
                    """
                    SELECT account_id, customer_id, subscription_id, state, last_event_id
                    FROM vindorum_billing_state WHERE account_id = ?
                    """,
                    (account_id,),
                ).fetchone()
                if not row:
                    raise BillingStateError("replayed event has no projected state")
                return self._row_to_state(row)

            current = connection.execute(
                """
                SELECT account_id, customer_id, subscription_id, state, last_event_id, last_event_created
                FROM vindorum_billing_state WHERE account_id = ?
                """,
                (account_id,),
            ).fetchone()

            if current:
                current_customer = current[1]
                current_subscription = current[2]
                current_state = current[3]
                last_event_created = current[5]

                if event_created < last_event_created:
                    self._insert_receipt(
                        connection,
                        event_id=event_id,
                        event_type=event_type,
                        account_id=account_id,
                        event_created=event_created,
                        fingerprint=fingerprint,
                        applied=False,
                    )
                    return self._row_to_state(current[:5])

                if current_customer and customer_id and customer_id != current_customer:
                    raise BillingStateError("customer binding mismatch")

                subscription_rebind = bool(
                    current_subscription and subscription_id and subscription_id != current_subscription
                )
                if subscription_rebind and not (
                    current_state in self._TERMINAL_STATES
                    and event_type in {"checkout.session.completed", "invoice.paid"}
                ):
                    raise BillingStateError("subscription binding mismatch")

                if self._ignore_without_regression(
                    current_state=current_state,
                    current_subscription=current_subscription,
                    incoming_subscription=subscription_id,
                    next_state=next_state,
                ):
                    self._insert_receipt(
                        connection,
                        event_id=event_id,
                        event_type=event_type,
                        account_id=account_id,
                        event_created=event_created,
                        fingerprint=fingerprint,
                        applied=False,
                    )
                    return self._row_to_state(current[:5])

                if event_created == last_event_created and not self._same_timestamp_transition_is_safe(
                    current_state=current_state,
                    next_state=next_state,
                    subscription_rebind=subscription_rebind,
                ):
                    raise BillingStateError("ambiguous same-timestamp billing transition")

                effective_customer = customer_id or current_customer
                effective_subscription = subscription_id or current_subscription
            else:
                effective_customer = customer_id
                effective_subscription = subscription_id

            self._insert_receipt(
                connection,
                event_id=event_id,
                event_type=event_type,
                account_id=account_id,
                event_created=event_created,
                fingerprint=fingerprint,
                applied=True,
            )
            connection.execute(
                """
                INSERT INTO vindorum_billing_state(
                    account_id, customer_id, subscription_id, state, last_event_id, last_event_created
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id) DO UPDATE SET
                    customer_id=excluded.customer_id,
                    subscription_id=excluded.subscription_id,
                    state=excluded.state,
                    last_event_id=excluded.last_event_id,
                    last_event_created=excluded.last_event_created
                """,
                (
                    account_id,
                    effective_customer,
                    effective_subscription,
                    next_state,
                    event_id,
                    event_created,
                ),
            )
            return BillingState(account_id, effective_customer, effective_subscription, next_state, event_id)
