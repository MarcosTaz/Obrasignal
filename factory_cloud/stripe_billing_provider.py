from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from factory_cloud.billing_core import BillingConfigurationError, BillingStateError, money


class BillingProviderError(RuntimeError):
    pass


Transport = Callable[[str, str, Mapping[str, str], bytes | None], tuple[int, bytes]]


def _parse_bool(value: str | bool | None, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    if not normalized:
        return default
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise BillingConfigurationError(f"invalid boolean configuration: {value!r}")


def _flatten(prefix: str, value: Any) -> list[tuple[str, str]]:
    if value is None:
        return []
    if isinstance(value, bool):
        return [(prefix, "true" if value else "false")]
    if isinstance(value, Mapping):
        result: list[tuple[str, str]] = []
        for key, item in value.items():
            result.extend(_flatten(f"{prefix}[{key}]", item))
        return result
    if isinstance(value, (list, tuple)):
        result: list[tuple[str, str]] = []
        for index, item in enumerate(value):
            result.extend(_flatten(f"{prefix}[{index}]", item))
        return result
    return [(prefix, str(value))]


def _form_payload(params: Mapping[str, Any]) -> bytes:
    pairs: list[tuple[str, str]] = []
    for key, value in params.items():
        pairs.extend(_flatten(str(key), value))
    return urlencode(pairs).encode("utf-8")


def stable_idempotency_key(*parts: str) -> str:
    joined = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return f"factory-finance-{digest[:48]}"


def eur_minor_units(value: Decimal | str | int | float) -> int:
    amount = money(value)
    if amount < 0:
        raise BillingStateError("invoice amount cannot be negative")
    return int((amount * Decimal("100")).to_integral_exact())


def normalize_fiscal_document_ref(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if len(normalized) > 160:
        raise BillingStateError("fiscal document reference is too long")
    if any(ord(char) < 32 for char in normalized):
        raise BillingStateError("fiscal document reference contains control characters")
    return normalized


@dataclass(frozen=True)
class StripeProviderConfig:
    secret_key: str
    webhook_secret: str
    livemode: bool
    customer_delivery_enabled: bool = False
    production_legal_entity_verified: bool = False
    production_fiscal_invoice_ready: bool = False
    production_payout_bank_verified: bool = False
    api_base: str = "https://api.stripe.com/v1"

    @property
    def production_activation_ready(self) -> bool:
        return bool(
            self.production_legal_entity_verified
            and self.production_fiscal_invoice_ready
            and self.production_payout_bank_verified
        )

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "StripeProviderConfig":
        environ = environ or os.environ
        secret_key = str(environ.get("FACTORY_STRIPE_SECRET_KEY") or "").strip()
        webhook_secret = str(environ.get("FACTORY_STRIPE_WEBHOOK_SECRET") or "").strip()
        if not secret_key:
            raise BillingConfigurationError("FACTORY_STRIPE_SECRET_KEY is not configured")
        if not webhook_secret:
            raise BillingConfigurationError("FACTORY_STRIPE_WEBHOOK_SECRET is not configured")
        return cls(
            secret_key=secret_key,
            webhook_secret=webhook_secret,
            livemode=_parse_bool(environ.get("FACTORY_STRIPE_LIVEMODE"), default=False),
            customer_delivery_enabled=_parse_bool(
                environ.get("FACTORY_STRIPE_CUSTOMER_DELIVERY_ENABLED"), default=False
            ),
            production_legal_entity_verified=_parse_bool(
                environ.get("FACTORY_PRODUCTION_LEGAL_ENTITY_VERIFIED"), default=False
            ),
            production_fiscal_invoice_ready=_parse_bool(
                environ.get("FACTORY_PRODUCTION_FISCAL_INVOICE_READY"), default=False
            ),
            production_payout_bank_verified=_parse_bool(
                environ.get("FACTORY_PRODUCTION_PAYOUT_BANK_VERIFIED"), default=False
            ),
        )


class StripeBillingProvider:
    """Minimal Stripe Invoicing adapter for the shared B2B rail.

    It never handles raw card/bank credentials. Invoice creation and finalization are
    separated from customer delivery; sending an invoice requires an explicit runtime
    delivery gate. Any live-mode write additionally requires legal-entity, fiscal-invoice
    and payout-bank readiness gates. Every live B2B collection invoice must also carry a
    concrete external fiscal-document reference from the AT-compliant invoicing authority.
    Idempotency keys are deterministic per engagement.
    """

    def __init__(self, config: StripeProviderConfig, *, transport: Transport | None = None) -> None:
        self.config = config
        self.transport = transport or self._urlopen_transport

    def require_write_ready(self, operation: str) -> None:
        if self.config.livemode and not self.config.production_activation_ready:
            raise BillingConfigurationError(
                f"live Stripe write blocked for {operation}: legal entity, fiscal invoice, "
                "and payout bank must all be explicitly verified"
            )

    def require_fiscal_document_ref(self, value: str | None, *, operation: str) -> str | None:
        normalized = normalize_fiscal_document_ref(value)
        if self.config.livemode and not normalized:
            raise BillingConfigurationError(
                f"live Stripe write blocked for {operation}: an external fiscal document "
                "reference from the AT-compliant invoicing authority is required"
            )
        return normalized

    def _urlopen_transport(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> tuple[int, bytes]:
        request = Request(url, data=body, headers=dict(headers), method=method)
        try:
            with urlopen(request, timeout=12) as response:
                return int(response.status), response.read()
        except HTTPError as exc:
            raw = exc.read() if hasattr(exc, "read") else b""
            return int(exc.code), raw
        except (URLError, TimeoutError, OSError) as exc:
            raise BillingProviderError("Stripe provider unavailable") from exc

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        method = method.upper()
        params = dict(params or {})
        url = self.config.api_base.rstrip("/") + "/" + path.lstrip("/")
        body: bytes | None = None
        if method == "GET" and params:
            query = _form_payload(params).decode("utf-8")
            url += "?" + query
        elif method != "GET":
            body = _form_payload(params)
        headers = {
            "Authorization": f"Bearer {self.config.secret_key}",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        status, raw = self.transport(method, url, headers, body)
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BillingProviderError("Stripe returned a non-JSON response") from exc
        if status < 200 or status >= 300:
            error = payload.get("error") if isinstance(payload, dict) else None
            code = error.get("code") if isinstance(error, dict) else None
            raise BillingProviderError(f"Stripe request failed ({status}{':' + str(code) if code else ''})")
        if not isinstance(payload, dict):
            raise BillingProviderError("Stripe response shape is invalid")
        response_mode = payload.get("livemode")
        if isinstance(response_mode, bool) and response_mode != self.config.livemode:
            raise BillingProviderError("Stripe response livemode does not match configured authority")
        return payload

    def create_customer(
        self,
        *,
        customer_key: str,
        name: str,
        email: str,
        factory_id: str,
    ) -> dict[str, Any]:
        self.require_write_ready("create_customer")
        if not str(email).strip():
            raise BillingStateError("B2B invoice customer email is required")
        return self._request(
            "POST",
            "/customers",
            params={
                "name": str(name),
                "email": str(email),
                "metadata": {
                    "customer_key": str(customer_key),
                    "factory_id": str(factory_id),
                    "billing_system": "factory_finance",
                },
            },
            idempotency_key=stable_idempotency_key("customer", customer_key),
        )

    def create_b2b_invoice(
        self,
        *,
        customer_ref: str,
        factory_id: str,
        engagement_id: str,
        fee_amount: Decimal | str | int | float,
        description: str,
        days_until_due: int = 15,
        fiscal_document_ref: str | None = None,
    ) -> dict[str, Any]:
        self.require_write_ready("create_b2b_invoice")
        fiscal_document_ref = self.require_fiscal_document_ref(
            fiscal_document_ref, operation="create_b2b_invoice"
        )
        amount = eur_minor_units(fee_amount)
        if amount <= 0:
            raise BillingStateError("B2B invoice fee must be greater than zero")
        if not (1 <= int(days_until_due) <= 365):
            raise BillingStateError("invoice due days must be between 1 and 365")
        identity = {
            "factory_id": str(factory_id),
            "engagement_id": str(engagement_id),
            "billing_system": "factory_finance",
        }
        if fiscal_document_ref:
            identity["fiscal_document_ref"] = fiscal_document_ref
        self._request(
            "POST",
            "/invoiceitems",
            params={
                "customer": str(customer_ref),
                "amount": amount,
                "currency": "eur",
                "description": str(description),
                "metadata": identity,
            },
            idempotency_key=stable_idempotency_key(factory_id, engagement_id, "invoice-item"),
        )
        invoice = self._request(
            "POST",
            "/invoices",
            params={
                "customer": str(customer_ref),
                "collection_method": "send_invoice",
                "days_until_due": int(days_until_due),
                "pending_invoice_items_behavior": "include",
                "auto_advance": False,
                "currency": "eur",
                "description": str(description),
                "metadata": identity,
            },
            idempotency_key=stable_idempotency_key(factory_id, engagement_id, "invoice"),
        )
        invoice_id = str(invoice.get("id") or "").strip()
        if not invoice_id:
            raise BillingProviderError("Stripe invoice creation returned no invoice id")
        finalized = self._request(
            "POST",
            f"/invoices/{quote(invoice_id, safe='')}/finalize",
            params={"auto_advance": False},
            idempotency_key=stable_idempotency_key(factory_id, engagement_id, "finalize"),
        )
        if finalized.get("status") not in {"open", "paid"}:
            raise BillingProviderError("Stripe invoice did not reach an authoritative finalized state")
        return finalized

    def send_invoice(self, invoice_ref: str, *, factory_id: str, engagement_id: str) -> dict[str, Any]:
        self.require_write_ready("send_invoice")
        if not self.config.customer_delivery_enabled:
            raise BillingConfigurationError(
                "customer invoice delivery is disabled; set FACTORY_STRIPE_CUSTOMER_DELIVERY_ENABLED only after approval"
            )
        if self.config.livemode:
            authoritative = self.retrieve_invoice(invoice_ref)
            metadata = authoritative.get("metadata") if isinstance(authoritative.get("metadata"), Mapping) else {}
            self.require_fiscal_document_ref(
                str(metadata.get("fiscal_document_ref") or ""), operation="send_invoice"
            )
        return self._request(
            "POST",
            f"/invoices/{quote(str(invoice_ref), safe='')}/send",
            params={},
            idempotency_key=stable_idempotency_key(factory_id, engagement_id, "send"),
        )

    def retrieve_invoice(self, invoice_ref: str) -> dict[str, Any]:
        return self._request("GET", f"/invoices/{quote(str(invoice_ref), safe='')}")

    def verify_webhook(
        self,
        payload: bytes,
        stripe_signature: str,
        *,
        now: int | None = None,
        tolerance_seconds: int = 300,
    ) -> dict[str, Any]:
        timestamp: int | None = None
        signatures: list[str] = []
        for part in str(stripe_signature or "").split(","):
            key, separator, value = part.partition("=")
            if not separator:
                continue
            if key == "t":
                try:
                    timestamp = int(value)
                except ValueError:
                    timestamp = None
            elif key == "v1":
                signatures.append(value)
        if timestamp is None or not signatures:
            raise BillingProviderError("Stripe webhook signature is incomplete")
        current = int(time.time() if now is None else now)
        if abs(current - timestamp) > int(tolerance_seconds):
            raise BillingProviderError("Stripe webhook signature timestamp is outside tolerance")
        signed = str(timestamp).encode("ascii") + b"." + payload
        expected = hmac.new(
            self.config.webhook_secret.encode("utf-8"), signed, hashlib.sha256
        ).hexdigest()
        if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
            raise BillingProviderError("Stripe webhook signature is invalid")
        try:
            event = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BillingProviderError("Stripe webhook payload is invalid JSON") from exc
        if not isinstance(event, dict):
            raise BillingProviderError("Stripe webhook payload shape is invalid")
        if event.get("livemode") is not self.config.livemode:
            raise BillingProviderError("Stripe webhook livemode does not match configured authority")
        return event

    def paid_event_evidence(self, event: Mapping[str, Any]) -> dict[str, str]:
        if event.get("type") != "invoice.paid":
            raise BillingStateError("only invoice.paid can prove an invoice payment")
        data = event.get("data")
        invoice = data.get("object") if isinstance(data, Mapping) else None
        if not isinstance(invoice, Mapping) or invoice.get("object") != "invoice":
            raise BillingStateError("invoice.paid event does not contain an invoice object")
        invoice_ref = str(invoice.get("id") or "").strip()
        event_ref = str(event.get("id") or "").strip()
        metadata = invoice.get("metadata") if isinstance(invoice.get("metadata"), Mapping) else {}
        factory_id = str(metadata.get("factory_id") or "").strip()
        engagement_id = str(metadata.get("engagement_id") or "").strip()
        if not invoice_ref or not event_ref or not factory_id or not engagement_id:
            raise BillingStateError("invoice.paid evidence is missing Factory identity")
        if self.config.livemode:
            self.require_fiscal_document_ref(
                str(metadata.get("fiscal_document_ref") or ""), operation="invoice.paid evidence"
            )
        return {
            "provider": "stripe",
            "provider_event_id": event_ref,
            "invoice_ref": invoice_ref,
            "factory_id": factory_id,
            "engagement_id": engagement_id,
            "evidence_ref": f"stripe:event:{event_ref}:invoice:{invoice_ref}",
        }
