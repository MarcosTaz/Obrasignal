from __future__ import annotations

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
    """Minimal Stripe-event projection for sandbox and production parity.

    This store never trusts client-side checkout success. Access state changes only
    from server-verified Stripe event payloads supplied by the webhook boundary.
    """

    def __init__(self, database: str | Path):
        self.database = str(database)
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS certactum_billing_state (
                    account_id TEXT PRIMARY KEY,
                    customer_id TEXT,
                    subscription_id TEXT,
                    state TEXT NOT NULL,
                    last_event_id TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS certactum_billing_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    account_id TEXT NOT NULL
                )
                """
            )

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

    def apply_verified_event(self, event: dict) -> BillingState:
        if not isinstance(event, dict):
            raise BillingStateError("event must be an object")
        event_id = self._text(event.get("id"), "event id")
        event_type = self._text(event.get("type"), "event type")
        data = event.get("data")
        obj = data.get("object") if isinstance(data, dict) else None
        if not isinstance(obj, dict):
            raise BillingStateError("event object is required")
        metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
        account_id = self._text(metadata.get("certactum_account_id"), "certactum_account_id")
        customer_id = self._text(obj.get("customer"), "customer", optional=True)
        subscription_id = self._text(obj.get("subscription") or obj.get("id" if event_type.startswith("customer.subscription.") else ""), "subscription", optional=True)

        transitions = {
            "checkout.session.completed": "PENDING_PAYMENT_CONFIRMATION",
            "invoice.paid": "ACTIVE",
            "invoice.payment_failed": "PAST_DUE",
            "customer.subscription.deleted": "CANCELLED",
            "charge.refunded": "REFUNDED",
        }
        state = transitions.get(event_type)
        if state is None:
            raise BillingStateError("unsupported billing event type")

        with sqlite3.connect(self.database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            seen = connection.execute(
                "SELECT event_type, account_id FROM certactum_billing_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if seen:
                if seen != (event_type, account_id):
                    raise BillingStateError("event id collision")
                row = connection.execute(
                    "SELECT account_id, customer_id, subscription_id, state, last_event_id FROM certactum_billing_state WHERE account_id = ?",
                    (account_id,),
                ).fetchone()
                if not row:
                    raise BillingStateError("replayed event has no projected state")
                return BillingState(*row)

            current = connection.execute(
                "SELECT customer_id, subscription_id FROM certactum_billing_state WHERE account_id = ?",
                (account_id,),
            ).fetchone()
            effective_customer = customer_id or (current[0] if current else None)
            effective_subscription = subscription_id or (current[1] if current else None)
            connection.execute(
                "INSERT INTO certactum_billing_events(event_id, event_type, account_id) VALUES (?, ?, ?)",
                (event_id, event_type, account_id),
            )
            connection.execute(
                """
                INSERT INTO certactum_billing_state(account_id, customer_id, subscription_id, state, last_event_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(account_id) DO UPDATE SET
                    customer_id=excluded.customer_id,
                    subscription_id=excluded.subscription_id,
                    state=excluded.state,
                    last_event_id=excluded.last_event_id
                """,
                (account_id, effective_customer, effective_subscription, state, event_id),
            )
            return BillingState(account_id, effective_customer, effective_subscription, state, event_id)
