from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping

from factory_cloud.factory_switchboard import REGISTRY_PATH, load_switchboard


POLICY_PATH = Path(__file__).with_name("billing_policy.json")


class BillingError(RuntimeError):
    pass


class BillingConfigurationError(BillingError):
    pass


class BillingStateError(BillingError):
    pass


@dataclass(frozen=True)
class BillingRoute:
    factory_id: str
    billing_owner_id: str
    mode: str
    payment_rail: str
    currency: str
    collection_rails: tuple[str, ...] = ()
    provider: str | None = None
    entitlement: str | None = None
    product_id: str | None = None
    grants_entitlement: bool | None = None
    subscription_enabled: bool | None = None


@dataclass(frozen=True)
class BankDestination:
    iban: str
    bic: str | None

    @property
    def masked_iban(self) -> str:
        compact = self.iban.replace(" ", "")
        if len(compact) <= 8:
            return "*" * len(compact)
        return f"{compact[:4]}{'*' * (len(compact) - 8)}{compact[-4:]}"


@dataclass(frozen=True)
class RevenueRecord:
    factory_id: str
    engagement_id: str
    customer_id: str
    currency: str
    recovery_amount: Decimal | None
    platform_fee_amount: Decimal
    state: str
    evidence_ref: str | None = None


ALLOWED_STATES = (
    "NOT_BILLABLE",
    "FEE_EARNED",
    "INVOICE_APPROVED",
    "INVOICED",
    "PAYMENT_PENDING",
    "PAID",
    "RECONCILED",
)

ALLOWED_TRANSITIONS = {
    "NOT_BILLABLE": {"FEE_EARNED", "PAYMENT_PENDING"},
    "FEE_EARNED": {"INVOICE_APPROVED"},
    "INVOICE_APPROVED": {"INVOICED"},
    "INVOICED": {"PAYMENT_PENDING"},
    "PAYMENT_PENDING": {"PAID"},
    "PAID": {"RECONCILED"},
    "RECONCILED": set(),
}


def load_billing_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        policy = json.load(handle)
    if policy.get("scope") != "shared_billing_core":
        raise BillingConfigurationError("billing policy must remain shared_billing_core")
    if not isinstance(policy.get("defaults_by_group"), dict):
        raise BillingConfigurationError("defaults_by_group is required")
    if not isinstance(policy.get("overrides"), dict):
        raise BillingConfigurationError("overrides is required")
    if policy.get("provider_ids_embedded_in_repository") is not False:
        raise BillingConfigurationError("provider IDs must not be embedded in repository policy")
    return policy


def _factory_map(registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["id"]): dict(item) for item in registry.get("factories", [])}


def _raw_policy_for(factory: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    factory_id = str(factory["id"])
    override = policy.get("overrides", {}).get(factory_id)
    if override is not None:
        return dict(override)
    group = str(factory.get("group") or "")
    default = policy.get("defaults_by_group", {}).get(group)
    if default is None:
        raise BillingConfigurationError(f"no billing policy for factory group: {group or '<empty>'}")
    return dict(default)


def billing_route_for(
    factory_id: str,
    registry: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    _seen: set[str] | None = None,
) -> BillingRoute:
    factories = _factory_map(registry)
    factory = factories.get(str(factory_id))
    if factory is None:
        raise BillingConfigurationError(f"unknown factory: {factory_id}")

    raw = _raw_policy_for(factory, policy)
    mode = str(raw.get("mode") or "").strip()
    seen = set(_seen or set())
    if factory_id in seen:
        raise BillingConfigurationError(f"billing inheritance cycle at {factory_id}")
    seen.add(factory_id)

    if mode == "inherit":
        owner = str(raw.get("billing_owner_id") or "").strip()
        if not owner or owner == factory_id:
            raise BillingConfigurationError(f"invalid billing owner for {factory_id}")
        owner_route = billing_route_for(owner, registry, policy, _seen=seen)
        return BillingRoute(
            factory_id=factory_id,
            billing_owner_id=owner_route.billing_owner_id,
            mode="inherit",
            payment_rail=owner_route.payment_rail,
            currency=owner_route.currency,
            collection_rails=owner_route.collection_rails,
            provider=owner_route.provider,
            entitlement=owner_route.entitlement,
            product_id=owner_route.product_id,
            grants_entitlement=owner_route.grants_entitlement,
            subscription_enabled=owner_route.subscription_enabled,
        )

    payment_rail = str(raw.get("payment_rail") or "").strip()
    if not mode or not payment_rail:
        raise BillingConfigurationError(f"incomplete billing policy for {factory_id}")
    collection_rails_raw = raw.get("collection_rails", [])
    if not isinstance(collection_rails_raw, list) or any(
        not str(item).strip() for item in collection_rails_raw
    ):
        raise BillingConfigurationError(f"invalid collection rails for {factory_id}")

    currency = str(raw.get("currency") or policy.get("currency_default") or "EUR")
    return BillingRoute(
        factory_id=factory_id,
        billing_owner_id=factory_id,
        mode=mode,
        payment_rail=payment_rail,
        currency=currency,
        collection_rails=tuple(str(item) for item in collection_rails_raw),
        provider=str(raw.get("provider")).strip() if raw.get("provider") else None,
        entitlement=raw.get("entitlement"),
        product_id=raw.get("product_id"),
        grants_entitlement=raw.get("grants_entitlement"),
        subscription_enabled=raw.get("subscription_enabled"),
    )


def billing_plan(
    registry: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    registry = dict(registry or load_switchboard(REGISTRY_PATH))
    policy = dict(policy or load_billing_policy(POLICY_PATH))
    routes = [
        billing_route_for(str(factory["id"]), registry, policy)
        for factory in registry.get("factories", [])
    ]
    owner_ids = {route.billing_owner_id for route in routes}
    return {
        "schema_version": policy.get("schema_version"),
        "registered_factories": len(routes),
        "billing_owners": len(owner_ids),
        "all_registered_factories_covered": True,
        "real_provider_calls_enabled": False,
        "bank_secret_embedded_in_repository": False,
        "provider_ids_embedded_in_repository": False,
        "provider_catalog_strategy": policy.get("provider_catalog_strategy"),
        "routes": [asdict(route) for route in routes],
    }


def normalize_iban(value: str) -> str:
    return "".join(str(value or "").upper().split())


def valid_iban(value: str) -> bool:
    compact = normalize_iban(value)
    if not (15 <= len(compact) <= 34):
        return False
    if not compact[:2].isalpha() or not compact[2:4].isdigit() or not compact[4:].isalnum():
        return False
    rearranged = compact[4:] + compact[:4]
    digits = "".join(str(ord(char) - 55) if char.isalpha() else char for char in rearranged)
    remainder = 0
    for char in digits:
        remainder = (remainder * 10 + int(char)) % 97
    return remainder == 1


def bank_destination_from_env(
    policy: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> BankDestination:
    policy = dict(policy or load_billing_policy())
    environ = environ or os.environ
    iban_key = str(policy.get("bank_destination_env") or "FACTORY_BILLING_IBAN")
    bic_key = str(policy.get("bank_bic_env") or "FACTORY_BILLING_BIC")
    iban = normalize_iban(environ.get(iban_key, ""))
    if not iban:
        raise BillingConfigurationError(f"bank destination is not configured in {iban_key}")
    if not valid_iban(iban):
        raise BillingConfigurationError(f"bank destination in {iban_key} is not a valid IBAN")
    bic = str(environ.get(bic_key) or "").strip().upper() or None
    return BankDestination(iban=iban, bic=bic)


def payment_instructions(
    factory_id: str,
    *,
    registry: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    include_full_bank_destination: bool = False,
) -> dict[str, Any]:
    registry = dict(registry or load_switchboard())
    policy = dict(policy or load_billing_policy())
    route = billing_route_for(factory_id, registry, policy)

    result: dict[str, Any] = {
        "factory_id": factory_id,
        "billing_owner_id": route.billing_owner_id,
        "mode": route.mode,
        "payment_rail": route.payment_rail,
        "collection_rails": list(route.collection_rails),
        "provider": route.provider,
        "currency": route.currency,
        "provider_call_performed": False,
    }
    if "direct_bank_transfer" in route.collection_rails:
        try:
            destination = bank_destination_from_env(policy, environ)
        except BillingConfigurationError:
            if include_full_bank_destination:
                raise
            result["direct_bank_transfer"] = {"configured": False}
        else:
            bank: dict[str, Any] = {
                "configured": True,
                "masked_iban": destination.masked_iban,
                "bic": destination.bic,
            }
            if include_full_bank_destination:
                bank["iban"] = destination.iban
            result["direct_bank_transfer"] = bank
    if route.payment_rail == "revenuecat_store":
        result["entitlement"] = route.entitlement
        result["product_id"] = route.product_id
    elif route.payment_rail == "supporter_checkout":
        result["grants_entitlement"] = bool(route.grants_entitlement)
        result["subscription_enabled"] = bool(route.subscription_enabled)
    return result


def money(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def success_fee(recovery_amount: Decimal | str | int | float, percentage: Decimal | str | int | float) -> Decimal:
    recovery = money(recovery_amount)
    pct = Decimal(str(percentage))
    if recovery < 0:
        raise BillingStateError("recovery amount cannot be negative")
    if pct < 0 or pct > 100:
        raise BillingStateError("success fee percentage must be between 0 and 100")
    return money(recovery * pct / Decimal("100"))


def create_revenue_record(
    *,
    factory_id: str,
    engagement_id: str,
    customer_id: str,
    platform_fee_amount: Decimal | str | int | float,
    currency: str = "EUR",
    recovery_amount: Decimal | str | int | float | None = None,
) -> RevenueRecord:
    fee = money(platform_fee_amount)
    if fee < 0:
        raise BillingStateError("platform fee cannot be negative")
    recovery = money(recovery_amount) if recovery_amount is not None else None
    return RevenueRecord(
        factory_id=str(factory_id),
        engagement_id=str(engagement_id),
        customer_id=str(customer_id),
        currency=str(currency).upper(),
        recovery_amount=recovery,
        platform_fee_amount=fee,
        state="NOT_BILLABLE",
    )


def advance_revenue_record(
    record: RevenueRecord,
    new_state: str,
    *,
    evidence_ref: str | None = None,
) -> RevenueRecord:
    target = str(new_state).upper()
    if target not in ALLOWED_STATES:
        raise BillingStateError(f"unknown billing state: {target}")
    if target not in ALLOWED_TRANSITIONS[record.state]:
        raise BillingStateError(f"invalid billing transition: {record.state} -> {target}")
    if target in {"PAID", "RECONCILED"} and not str(evidence_ref or "").strip():
        raise BillingStateError(f"{target} requires durable provider/bank evidence")
    return RevenueRecord(
        factory_id=record.factory_id,
        engagement_id=record.engagement_id,
        customer_id=record.customer_id,
        currency=record.currency,
        recovery_amount=record.recovery_amount,
        platform_fee_amount=record.platform_fee_amount,
        state=target,
        evidence_ref=str(evidence_ref).strip() if evidence_ref else record.evidence_ref,
    )


def main() -> int:
    print(json.dumps(billing_plan(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
