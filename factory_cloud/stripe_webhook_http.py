from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from factory_cloud.billing_core import BillingConfigurationError, BillingStateError
from factory_cloud.billing_service import SharedBillingService
from factory_cloud.revenue_ledger import RevenueLedger
from factory_cloud.stripe_billing_provider import (
    BillingProviderError,
    StripeBillingProvider,
    StripeProviderConfig,
)


MAX_WEBHOOK_BYTES = 1_048_576
DEFAULT_LEDGER_PATH = Path(".factory_cloud") / "factory_finance.sqlite3"


def _header(headers: Mapping[str, str], name: str) -> str:
    target = name.lower()
    for key, value in headers.items():
        if str(key).lower() == target:
            return str(value)
    return ""


def handle_stripe_webhook(
    body: bytes,
    headers: Mapping[str, str],
    *,
    environ: Mapping[str, str] | None = None,
    ledger_path: Path | str | None = None,
    now: int | None = None,
) -> tuple[int, dict[str, Any]]:
    """Verify and ingest one Stripe webhook without a web-framework dependency.

    The caller must pass the exact raw HTTP body. No JSON re-serialization is allowed
    before signature verification. Secrets and raw provider payloads are never returned.
    """

    if not isinstance(body, (bytes, bytearray)):
        return 400, {"accepted": False, "error": "raw_body_required"}
    raw = bytes(body)
    if not raw:
        return 400, {"accepted": False, "error": "empty_body"}
    if len(raw) > MAX_WEBHOOK_BYTES:
        return 413, {"accepted": False, "error": "payload_too_large"}

    signature = _header(headers, "Stripe-Signature").strip()
    if not signature:
        return 400, {"accepted": False, "error": "missing_signature"}

    environ = environ or os.environ
    target_path = Path(
        ledger_path
        or str(environ.get("FACTORY_FINANCE_LEDGER_PATH") or DEFAULT_LEDGER_PATH)
    )

    try:
        config = StripeProviderConfig.from_env(environ)
        provider = StripeBillingProvider(config)
        ledger = RevenueLedger(target_path)
        service = SharedBillingService(ledger, stripe_provider=provider)
        result = service.ingest_stripe_webhook(raw, signature, now=now)
    except BillingConfigurationError:
        return 503, {"accepted": False, "error": "billing_not_configured"}
    except (BillingProviderError, BillingStateError, ValueError, KeyError):
        return 400, {"accepted": False, "error": "invalid_provider_evidence"}

    response = {
        "accepted": bool(result.get("accepted")),
        "duplicate": bool(result.get("duplicate")),
        "state_changed": bool(result.get("state_changed")),
        "type": str(result.get("type") or ""),
    }
    return 200, response


def response_json(status: int, payload: Mapping[str, Any]) -> tuple[int, bytes, dict[str, str]]:
    encoded = json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return status, encoded, {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
        "Content-Length": str(len(encoded)),
    }
