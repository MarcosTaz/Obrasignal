from __future__ import annotations

import re
from typing import Any, Mapping

from factory_cloud.billing_core import BillingConfigurationError, billing_route_for, load_billing_policy
from factory_cloud.factory_switchboard import load_switchboard
from factory_cloud.stripe_billing_provider import StripeBillingProvider, stable_idempotency_key


FACTORY_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,99}$")


def b2b_billing_owners(
    registry: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
) -> list[dict[str, str]]:
    registry = dict(registry or load_switchboard())
    policy = dict(policy or load_billing_policy())
    owners: list[dict[str, str]] = []
    for factory in registry.get("factories", []):
        factory_id = str(factory["id"])
        route = billing_route_for(factory_id, registry, policy)
        if route.mode != "b2b_invoice" or route.billing_owner_id != factory_id:
            continue
        if route.provider != "stripe":
            raise BillingConfigurationError(
                f"B2B billing owner {factory_id} does not use the shared Stripe provider"
            )
        owners.append({"factory_id": factory_id, "name": str(factory["name"])})
    owners.sort(key=lambda item: item["factory_id"])
    return owners


def _query_for(factory_id: str) -> str:
    if not FACTORY_ID.fullmatch(str(factory_id)):
        raise BillingConfigurationError(f"factory id is unsafe for provider search: {factory_id!r}")
    return f"metadata['factory_id']:'{factory_id}'"


def find_b2b_product(provider: StripeBillingProvider, factory_id: str) -> dict[str, Any] | None:
    payload = provider._request(  # package-private provider primitive; keeps auth/mode checks centralized
        "GET",
        "/products/search",
        params={"query": _query_for(factory_id), "limit": 10},
    )
    data = payload.get("data")
    if not isinstance(data, list):
        raise BillingConfigurationError("Stripe product search returned invalid data")
    matches = []
    for item in data:
        if not isinstance(item, Mapping):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
        if (
            str(metadata.get("factory_id") or "") == factory_id
            and str(metadata.get("billing_model") or "") == "b2b_invoice_dynamic"
            and item.get("active") is not False
        ):
            matches.append(dict(item))
    if len(matches) > 1:
        raise BillingConfigurationError(f"multiple active Stripe B2B products exist for {factory_id}")
    return matches[0] if matches else None


def ensure_b2b_product(
    provider: StripeBillingProvider,
    *,
    factory_id: str,
    name: str,
    allow_create: bool = False,
) -> dict[str, Any]:
    existing = find_b2b_product(provider, factory_id)
    if existing is not None:
        return {"factory_id": factory_id, "status": "EXISTS", "provider_ref_present": True}
    if not allow_create:
        return {"factory_id": factory_id, "status": "MISSING", "provider_ref_present": False}
    created = provider._request(
        "POST",
        "/products",
        params={
            "name": f"[TEST] {name}" if not provider.config.livemode else name,
            "description": (
                "Dynamic B2B engagement. Amount is created only from an approved engagement "
                "or verified fee event; no fixed price is implied."
            ),
            "metadata": {
                "factory_id": factory_id,
                "billing_model": "b2b_invoice_dynamic",
                "fixed_price": "false",
                "environment": "live" if provider.config.livemode else "test",
            },
        },
        idempotency_key=stable_idempotency_key("catalog", factory_id),
    )
    if not str(created.get("id") or "").strip():
        raise BillingConfigurationError(f"Stripe product creation returned no identity for {factory_id}")
    return {"factory_id": factory_id, "status": "CREATED", "provider_ref_present": True}


def sync_b2b_catalog(
    provider: StripeBillingProvider,
    *,
    registry: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
    allow_create: bool = False,
) -> dict[str, Any]:
    owners = b2b_billing_owners(registry, policy)
    results = [
        ensure_b2b_product(
            provider,
            factory_id=owner["factory_id"],
            name=owner["name"],
            allow_create=allow_create,
        )
        for owner in owners
    ]
    return {
        "expected_b2b_billing_owners": len(owners),
        "existing": sum(item["status"] == "EXISTS" for item in results),
        "created": sum(item["status"] == "CREATED" for item in results),
        "missing": sum(item["status"] == "MISSING" for item in results),
        "allow_create": bool(allow_create),
        "provider_ids_returned": False,
        "results": results,
    }
