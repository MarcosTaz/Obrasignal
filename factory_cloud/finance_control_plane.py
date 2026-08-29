from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from factory_cloud.billing_core import (
    BillingConfigurationError,
    bank_destination_from_env,
    billing_plan,
    load_billing_policy,
)
from factory_cloud.factory_switchboard import load_switchboard
from factory_cloud.revenue_ledger import RevenueLedger


def _bool_setting(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _decimal_strings(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _decimal_strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decimal_strings(item) for item in value]
    return value


def finance_status(
    *,
    environ: Mapping[str, str] | None = None,
    registry: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
    ledger: RevenueLedger | None = None,
) -> dict[str, Any]:
    environ = environ or os.environ
    registry = dict(registry or load_switchboard())
    policy = dict(policy or load_billing_policy())
    plan = billing_plan(registry, policy)

    stripe_secret_key = str(policy.get("stripe_secret_key_env") or "FACTORY_STRIPE_SECRET_KEY")
    stripe_webhook_key = str(
        policy.get("stripe_webhook_secret_env") or "FACTORY_STRIPE_WEBHOOK_SECRET"
    )
    stripe_livemode_key = str(policy.get("stripe_livemode_env") or "FACTORY_STRIPE_LIVEMODE")
    delivery_key = str(
        policy.get("stripe_customer_delivery_env") or "FACTORY_STRIPE_CUSTOMER_DELIVERY_ENABLED"
    )
    livemode_raw = str(environ.get(stripe_livemode_key) or "").strip().lower()
    if not livemode_raw:
        stripe_mode = "UNCONFIGURED"
    elif livemode_raw in {"1", "true", "yes", "on"}:
        stripe_mode = "LIVE_REQUESTED"
    elif livemode_raw in {"0", "false", "no", "off"}:
        stripe_mode = "TEST_REQUESTED"
    else:
        stripe_mode = "INVALID"

    try:
        bank = bank_destination_from_env(policy, environ)
    except BillingConfigurationError:
        direct_bank = {"configured": False, "masked_iban": None, "bic_configured": False}
    else:
        direct_bank = {
            "configured": True,
            "masked_iban": bank.masked_iban,
            "bic_configured": bool(bank.bic),
        }

    runtime = {
        "stripe_secret_configured": bool(str(environ.get(stripe_secret_key) or "").strip()),
        "stripe_webhook_secret_configured": bool(
            str(environ.get(stripe_webhook_key) or "").strip()
        ),
        "stripe_mode": stripe_mode,
        "stripe_customer_delivery_enabled": _bool_setting(environ.get(delivery_key)),
        "direct_bank": direct_bank,
        "secrets_exposed": False,
        "full_iban_exposed": False,
    }
    runtime["stripe_runtime_flags_ready"] = bool(
        runtime["stripe_secret_configured"]
        and runtime["stripe_webhook_secret_configured"]
        and runtime["stripe_mode"] in {"TEST_REQUESTED", "LIVE_REQUESTED"}
    )
    runtime["live_customer_delivery_flags_ready"] = bool(
        runtime["stripe_runtime_flags_ready"]
        and runtime["stripe_mode"] == "LIVE_REQUESTED"
        and runtime["stripe_customer_delivery_enabled"]
    )

    routes = []
    owners: dict[str, dict[str, Any]] = {}
    for route in plan["routes"]:
        row = {
            "factory_id": route["factory_id"],
            "billing_owner_id": route["billing_owner_id"],
            "mode": route["mode"],
            "provider": route.get("provider"),
            "payment_rail": route["payment_rail"],
            "collection_rails": route.get("collection_rails", []),
        }
        routes.append(row)
        owner_id = row["billing_owner_id"]
        owners.setdefault(
            owner_id,
            {
                "billing_owner_id": owner_id,
                "provider": row["provider"],
                "payment_rail": row["payment_rail"],
                "collection_rails": row["collection_rails"],
                "factories": [],
            },
        )["factories"].append(row["factory_id"])

    status: dict[str, Any] = {
        "schema_version": 1,
        "registered_factories": plan["registered_factories"],
        "billing_owners": plan["billing_owners"],
        "all_registered_factories_covered": plan["all_registered_factories_covered"],
        "runtime": runtime,
        "owners": sorted(owners.values(), key=lambda item: item["billing_owner_id"]),
        "routes": routes,
        "production_truth": {
            "provider_live_operation_verified": False,
            "bank_payout_verified": False,
            "fiscal_invoice_compliance_verified": False,
            "reason": "runtime flags are configuration evidence only, not production settlement proof",
        },
    }
    if ledger is not None:
        status["ledger"] = _decimal_strings(ledger.report())
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Factory Finance Control Plane")
    parser.add_argument("--ledger", type=Path)
    args = parser.parse_args()
    ledger = RevenueLedger(args.ledger) if args.ledger else None
    print(json.dumps(finance_status(ledger=ledger), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
