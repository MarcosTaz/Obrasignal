from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Mapping

from factory_cloud.billing_core import (
    BillingConfigurationError,
    BillingStateError,
    billing_route_for,
    create_revenue_record,
    load_billing_policy,
    money,
    success_fee,
)
from factory_cloud.factory_switchboard import load_switchboard
from factory_cloud.revenue_ledger import RevenueLedger
from factory_cloud.stripe_billing_provider import StripeBillingProvider


class SharedBillingService:
    """Compose Factory billing policy, durable revenue truth and provider evidence."""

    def __init__(
        self,
        ledger: RevenueLedger,
        *,
        stripe_provider: StripeBillingProvider | None = None,
        registry: Mapping[str, Any] | None = None,
        policy: Mapping[str, Any] | None = None,
    ) -> None:
        self.ledger = ledger
        self.stripe_provider = stripe_provider
        self.registry = dict(registry or load_switchboard())
        self.policy = dict(policy or load_billing_policy())

    def _route(self, factory_id: str):
        return billing_route_for(factory_id, self.registry, self.policy)

    def register_b2b_fee(
        self,
        *,
        factory_id: str,
        engagement_id: str,
        customer_id: str,
        recovery_amount: Decimal | str | int | float | None = None,
        platform_fee_amount: Decimal | str | int | float | None = None,
        success_fee_percentage: Decimal | str | int | float | None = None,
    ) -> str:
        route = self._route(factory_id)
        if route.mode != "b2b_invoice":
            raise BillingStateError(f"{factory_id} is not a B2B invoice Factory")
        if platform_fee_amount is not None and success_fee_percentage is not None:
            raise BillingStateError("use either explicit platform fee or success-fee percentage, not both")
        if success_fee_percentage is not None:
            if recovery_amount is None:
                raise BillingStateError("success-fee percentage requires verified recovery amount")
            platform_fee_amount = success_fee(recovery_amount, success_fee_percentage)
        if platform_fee_amount is None:
            raise BillingStateError("platform fee is not established")
        fee = money(platform_fee_amount)
        if fee <= 0:
            raise BillingStateError("platform fee must be greater than zero before it is earned")
        record = create_revenue_record(
            factory_id=factory_id,
            engagement_id=engagement_id,
            customer_id=customer_id,
            recovery_amount=recovery_amount,
            platform_fee_amount=fee,
            currency=route.currency,
        )
        revenue_id = self.ledger.create(record, billing_owner_id=route.billing_owner_id)
        self.ledger.transition(revenue_id, "FEE_EARNED")
        return revenue_id

    def approve_invoice(self, revenue_id: str) -> dict[str, Any]:
        record = self.ledger.get(revenue_id)
        route = self._route(record["factory_id"])
        if route.mode != "b2b_invoice":
            raise BillingStateError("only B2B fee records can enter invoice approval")
        return self.ledger.transition(revenue_id, "INVOICE_APPROVED")

    def create_stripe_invoice(
        self,
        revenue_id: str,
        *,
        provider_customer_ref: str,
        description: str,
        days_until_due: int = 15,
    ) -> dict[str, Any]:
        if self.stripe_provider is None:
            raise BillingConfigurationError("Stripe provider is not configured")
        record = self.ledger.get(revenue_id)
        route = self._route(record["factory_id"])
        if route.mode != "b2b_invoice" or route.provider != "stripe":
            raise BillingStateError("record is not owned by the shared Stripe B2B rail")
        if "stripe_hosted_invoice" not in route.collection_rails:
            raise BillingStateError("Stripe Hosted Invoice is not authorized for this Factory")
        if record["state"] == "PAYMENT_PENDING" and record.get("provider_invoice_ref"):
            return {
                "id": record["provider_invoice_ref"],
                "status": "open",
                "idempotent_replay": True,
            }
        if record["state"] != "INVOICE_APPROVED":
            raise BillingStateError(
                f"Stripe invoice creation requires INVOICE_APPROVED, got {record['state']}"
            )
        invoice = self.stripe_provider.create_b2b_invoice(
            customer_ref=provider_customer_ref,
            factory_id=record["factory_id"],
            engagement_id=record["engagement_id"],
            fee_amount=record["platform_fee_amount"],
            description=description,
            days_until_due=days_until_due,
        )
        invoice_ref = str(invoice.get("id") or "").strip()
        if not invoice_ref:
            raise BillingStateError("provider invoice has no identity")
        self.ledger.attach_provider_ref(
            revenue_id, "customer", provider_customer_ref, provider="stripe"
        )
        self.ledger.attach_provider_ref(revenue_id, "invoice", invoice_ref, provider="stripe")
        self.ledger.transition(
            revenue_id,
            "INVOICED",
            evidence_ref=f"stripe:invoice:{invoice_ref}:finalized",
        )
        self.ledger.transition(revenue_id, "PAYMENT_PENDING")
        return invoice

    def send_stripe_invoice(self, revenue_id: str) -> dict[str, Any]:
        if self.stripe_provider is None:
            raise BillingConfigurationError("Stripe provider is not configured")
        record = self.ledger.get(revenue_id)
        invoice_ref = str(record.get("provider_invoice_ref") or "").strip()
        if record["state"] != "PAYMENT_PENDING" or not invoice_ref:
            raise BillingStateError("only a finalized pending invoice can be sent")
        return self.stripe_provider.send_invoice(
            invoice_ref,
            factory_id=record["factory_id"],
            engagement_id=record["engagement_id"],
        )

    def record_direct_bank_paid(self, revenue_id: str, *, bank_evidence_ref: str) -> dict[str, Any]:
        record = self.ledger.get(revenue_id)
        route = self._route(record["factory_id"])
        if "direct_bank_transfer" not in route.collection_rails:
            raise BillingStateError("direct bank transfer is not authorized for this Factory")
        if record["state"] != "PAYMENT_PENDING":
            raise BillingStateError("direct bank payment can only settle a pending invoice")
        if not str(bank_evidence_ref or "").strip():
            raise BillingStateError("direct bank payment requires durable bank evidence")
        return self.ledger.transition(revenue_id, "PAID", evidence_ref=bank_evidence_ref)

    def reconcile(self, revenue_id: str, *, evidence_ref: str) -> dict[str, Any]:
        record = self.ledger.get(revenue_id)
        if record["state"] != "PAID":
            raise BillingStateError("only PAID revenue can be reconciled")
        return self.ledger.transition(revenue_id, "RECONCILED", evidence_ref=evidence_ref)

    def ingest_stripe_webhook(
        self,
        payload: bytes,
        stripe_signature: str,
        *,
        now: int | None = None,
    ) -> dict[str, Any]:
        if self.stripe_provider is None:
            raise BillingConfigurationError("Stripe provider is not configured")
        event = self.stripe_provider.verify_webhook(payload, stripe_signature, now=now)
        event_type = str(event.get("type") or "").strip()
        if event_type == "invoice.paid":
            return self._ingest_invoice_paid(event, payload)
        if event_type == "checkout.session.completed":
            return self._ingest_supporter_checkout(event, payload)

        event_id = str(event.get("id") or "").strip()
        data = event.get("data")
        obj = data.get("object") if isinstance(data, Mapping) else None
        object_ref = str(obj.get("id") or "").strip() if isinstance(obj, Mapping) else None
        if not event_id or not event_type:
            raise BillingStateError("Stripe event identity is incomplete")
        first = self.ledger.record_provider_event(
            provider="stripe",
            provider_event_id=event_id,
            event_type=event_type,
            object_ref=object_ref,
            payload=payload,
        )
        return {"accepted": True, "duplicate": not first, "state_changed": False, "type": event_type}

    def _ingest_invoice_paid(self, event: Mapping[str, Any], payload: bytes) -> dict[str, Any]:
        evidence = self.stripe_provider.paid_event_evidence(event)
        record = self.ledger.find(evidence["factory_id"], evidence["engagement_id"])
        invoice_ref = str(record.get("provider_invoice_ref") or "").strip()
        if record.get("provider") != "stripe" or invoice_ref != evidence["invoice_ref"]:
            raise BillingStateError("invoice.paid does not match the durable provider invoice authority")

        changed = False
        if record["state"] == "PAYMENT_PENDING":
            record = self.ledger.transition(
                record["revenue_id"],
                "PAID",
                evidence_ref=evidence["evidence_ref"],
                provider_event_id=evidence["provider_event_id"],
            )
            changed = True
        elif record["state"] in {"PAID", "RECONCILED"}:
            if record.get("evidence_ref") != evidence["evidence_ref"] and record["state"] == "PAID":
                raise BillingStateError("paid record has different durable payment evidence")
        else:
            raise BillingStateError(f"invoice.paid cannot advance revenue from {record['state']}")

        first = self.ledger.record_provider_event(
            provider="stripe",
            provider_event_id=evidence["provider_event_id"],
            event_type="invoice.paid",
            object_ref=evidence["invoice_ref"],
            payload=payload,
        )
        return {
            "accepted": True,
            "duplicate": not first,
            "state_changed": changed,
            "type": "invoice.paid",
            "revenue_id": record["revenue_id"],
            "state": record["state"],
        }

    def _ingest_supporter_checkout(self, event: Mapping[str, Any], payload: bytes) -> dict[str, Any]:
        event_id = str(event.get("id") or "").strip()
        data = event.get("data")
        session = data.get("object") if isinstance(data, Mapping) else None
        if not isinstance(session, Mapping) or session.get("object") != "checkout.session":
            raise BillingStateError("checkout.session.completed does not contain a Checkout Session")
        session_ref = str(session.get("id") or "").strip()
        metadata = session.get("metadata") if isinstance(session.get("metadata"), Mapping) else {}
        factory_id = str(metadata.get("factory_id") or "").strip()
        if factory_id != "k3-fatality":
            raise BillingStateError("supporter checkout is not authorized for this Factory")
        route = self._route(factory_id)
        if route.mode != "supporter_contribution" or route.grants_entitlement is not False:
            raise BillingStateError("K3 supporter policy no longer matches the no-entitlement contract")
        if session.get("payment_status") != "paid":
            raise BillingStateError("checkout completion without paid status cannot prove supporter revenue")
        if str(session.get("currency") or "").lower() != "eur":
            raise BillingStateError("K3 supporter checkout must settle in EUR")
        try:
            amount_total = int(session.get("amount_total"))
        except (TypeError, ValueError) as exc:
            raise BillingStateError("supporter checkout amount is invalid") from exc
        if amount_total <= 0:
            raise BillingStateError("supporter checkout amount must be positive")
        if not event_id or not session_ref:
            raise BillingStateError("supporter checkout evidence is missing identity")

        evidence_ref = f"stripe:event:{event_id}:checkout:{session_ref}"
        try:
            record = self.ledger.find(factory_id, session_ref)
        except KeyError:
            customer_ref = str(session.get("customer") or session.get("client_reference_id") or session_ref)
            created = create_revenue_record(
                factory_id=factory_id,
                engagement_id=session_ref,
                customer_id=customer_ref,
                platform_fee_amount=Decimal(amount_total) / Decimal("100"),
                currency="EUR",
            )
            revenue_id = self.ledger.create(created, billing_owner_id=route.billing_owner_id)
            payment_ref = str(session.get("payment_intent") or session_ref)
            self.ledger.attach_provider_ref(revenue_id, "payment", payment_ref, provider="stripe")
            self.ledger.transition(revenue_id, "PAYMENT_PENDING")
            record = self.ledger.transition(
                revenue_id,
                "PAID",
                evidence_ref=evidence_ref,
                provider_event_id=event_id,
            )
            changed = True
        else:
            changed = False
            if record["state"] not in {"PAID", "RECONCILED"}:
                raise BillingStateError("existing supporter record is not in a terminal paid state")
            if record["state"] == "PAID" and record.get("evidence_ref") != evidence_ref:
                raise BillingStateError("supporter record has conflicting payment evidence")

        first = self.ledger.record_provider_event(
            provider="stripe",
            provider_event_id=event_id,
            event_type="checkout.session.completed",
            object_ref=session_ref,
            payload=payload,
        )
        return {
            "accepted": True,
            "duplicate": not first,
            "state_changed": changed,
            "type": "checkout.session.completed",
            "revenue_id": record["revenue_id"],
            "state": record["state"],
            "grants_entitlement": False,
        }
