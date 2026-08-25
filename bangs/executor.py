from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from .contracts import BangExecutionContext, BangObserver, BangResult, BangStatus, ProviderAvailability, ProviderResult, utc_now_iso
from .parser import BangParseError, parse_bang
from .providers import ProviderRegistry
from .registry import ArgumentError, BangDefinition, BangRegistry, DEFAULT_REGISTRY


class NullObserver:
    def record(self, event):
        return None


class BangExecutor:
    def __init__(self, providers: ProviderRegistry | None = None, registry: BangRegistry = DEFAULT_REGISTRY, observer: BangObserver | None = None, clock: Callable[[], str] = utc_now_iso, id_factory: Callable[[], str] | None = None) -> None:
        self.providers = providers or ProviderRegistry()
        self.registry = registry
        self.observer = observer or NullObserver()
        self.clock = clock
        self.id_factory = id_factory or (lambda: str(uuid.uuid4()))

    def execute(self, text: str, context: BangExecutionContext) -> BangResult:
        started = time.perf_counter(); execution_id = self.id_factory(); command = ""; capability = None; provider_name = None
        try:
            invocation = parse_bang(text)
            definition = self.registry.resolve(invocation.command)
            command = definition.name if definition else invocation.command
            if definition is None:
                return self._finish(command, BangStatus.INVALID, "unknown command", None, (), (), None, execution_id, started, None)
            capability = definition.required_capability
            try:
                definition.validator(invocation)
            except ArgumentError as exc:
                return self._finish(command, BangStatus.INVALID, str(exc), None, (), (), capability, execution_id, started, None)
            if not definition.required_permissions.issubset(context.principal.permissions):
                return self._finish(command, BangStatus.FORBIDDEN, "permission denied", None, (), (), capability, execution_id, started, None)
            if definition.built_in:
                return self._execute_builtin(definition, context, execution_id, started)
            provider = self.providers.get(capability or "")
            if provider is None:
                return self._finish(command, BangStatus.UNAVAILABLE, "capability not integrated", None, ("NOT_INTEGRATED",), (), capability, execution_id, started, None)
            provider_name = getattr(provider, "name", provider.__class__.__name__)
            try:
                availability = provider.availability()
            except Exception:
                return self._finish(command, BangStatus.UNAVAILABLE, "capability availability check failed", None, (), (), capability, execution_id, started, provider_name)
            if not isinstance(availability, ProviderAvailability):
                return self._finish(command, BangStatus.FAILED, "provider returned invalid availability contract", None, (), (), capability, execution_id, started, provider_name)
            if not availability.present:
                return self._finish(command, BangStatus.UNAVAILABLE, availability.reason or "capability unavailable", None, (), (), capability, execution_id, started, provider_name)
            if availability.gated or not availability.enabled:
                return self._finish(command, BangStatus.GATED, availability.reason or "capability gated", None, (), (), capability, execution_id, started, provider_name)
            try:
                response = provider.execute(invocation, context)
            except Exception:
                return self._finish(command, BangStatus.FAILED, "provider execution failed", None, (), (), capability, execution_id, started, provider_name)
            if not isinstance(response, ProviderResult):
                return self._finish(command, BangStatus.FAILED, "provider returned invalid contract", None, (), (), capability, execution_id, started, provider_name)
            return self._finish(command, response.status, response.message, response.data, response.warnings, response.evidence_refs, capability, execution_id, started, provider_name)
        except BangParseError as exc:
            return self._finish(command, BangStatus.INVALID, str(exc), None, (), (), capability, execution_id, started, provider_name)

    def _execute_builtin(self, definition: BangDefinition, context: BangExecutionContext, execution_id: str, started: float) -> BangResult:
        available = []
        for item in self.registry.definitions():
            if not item.required_permissions.issubset(context.principal.permissions):
                continue
            if item.built_in:
                available.append(self._help_row(item)); continue
            provider = self.providers.get(item.required_capability or "")
            if provider is None:
                continue
            try:
                state = provider.availability()
                if isinstance(state, ProviderAvailability) and state.present and state.enabled and not state.gated:
                    available.append(self._help_row(item))
            except Exception:
                continue
        return self._finish(definition.name, BangStatus.SUCCESS, "available commands", available, (), (), None, execution_id, started, "bangs-core")

    @staticmethod
    def _help_row(definition: BangDefinition) -> dict[str, object]:
        return {"name": f"!{definition.name}", "aliases": [f"!{alias}" for alias in definition.aliases], "description": definition.description, "side_effect_class": definition.side_effect_class.value}

    def _finish(self, command, status, message, data, warnings, evidence_refs, capability, execution_id, started, provider_name):
        result = BangResult(command=command, status=status, message=message, data=data, warnings=tuple(warnings), evidence_refs=tuple(evidence_refs), capability=capability, execution_id=execution_id, generated_at=self.clock())
        try:
            self.observer.record({"command": command, "status": status.value, "capability": capability, "provider": provider_name, "latency_ms": round((time.perf_counter() - started) * 1000, 3)})
        except Exception:
            pass
        return result
