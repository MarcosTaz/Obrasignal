from __future__ import annotations

from market_scope_registry import market_scope
from source_registry import production_gate_reasons, source_status

from .contracts import BangExecutionContext, BangInvocation, BangStatus, ProviderAvailability, ProviderResult
from .providers import ProviderRegistry


class CanonicalCountryCoverageProvider:
    """Read the existing canonical market-scope registry without duplicating its policy."""

    name = "canonical-market-scope"

    def availability(self) -> ProviderAvailability:
        return ProviderAvailability(True)

    def execute(self, invocation: BangInvocation, context: BangExecutionContext) -> ProviderResult:
        country = invocation.args[0].strip()
        try:
            scope = market_scope(country)
        except KeyError:
            return ProviderResult(BangStatus.NOT_FOUND, "country not found in canonical market scope")
        return ProviderResult(
            BangStatus.SUCCESS,
            "canonical market scope",
            {
                "country": country,
                "status": scope.status,
                "reason": scope.reason,
                "infrastructure": scope.infrastructure or None,
                "reopen_condition": scope.reopen_condition or None,
                "priority": scope.priority,
            },
            evidence_refs=("registry:market_scope",),
        )


class CanonicalSourceRegistryProvider:
    """Read canonical source metadata and its existing production-gate explanation."""

    name = "canonical-source-registry"

    def availability(self) -> ProviderAvailability:
        return ProviderAvailability(True)

    def execute(self, invocation: BangInvocation, context: BangExecutionContext) -> ProviderResult:
        key = invocation.args[0].strip().upper()
        meta = source_status(key)
        if meta.get("status") == "unknown" and not meta.get("official"):
            return ProviderResult(BangStatus.NOT_FOUND, "source not found in canonical source registry")

        gates = production_gate_reasons(key)
        data = {"registry_key": key, **dict(meta)}
        for field in ("capabilities", "signal_types"):
            if field in data:
                data[field] = list(data[field])
        data["production_gate_reasons"] = list(gates)
        data["production_ready"] = not gates
        return ProviderResult(
            BangStatus.SUCCESS,
            "canonical source registry entry",
            data,
            evidence_refs=(f"registry:source_registry:{key}",),
        )


def canonical_read_provider_registry() -> ProviderRegistry:
    """Return only providers backed by public contracts already present on main."""

    registry = ProviderRegistry()
    registry.register("COUNTRY_COVERAGE", CanonicalCountryCoverageProvider())
    registry.register("SOURCE_REGISTRY", CanonicalSourceRegistryProvider())
    return registry
