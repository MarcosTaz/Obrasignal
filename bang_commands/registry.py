from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .contracts import BangInvocation, SideEffectClass


class ArgumentError(ValueError):
    pass

Validator = Callable[[BangInvocation], None]


def _reject_flags(invocation: BangInvocation) -> None:
    if any(arg.startswith("--") for arg in invocation.args):
        raise ArgumentError("flags are not supported in v0")


def arity(min_args: int, max_args: int | None = None) -> Validator:
    upper = min_args if max_args is None else max_args
    def validate(invocation: BangInvocation) -> None:
        _reject_flags(invocation)
        count = len(invocation.args)
        if count < min_args or count > upper:
            expected = str(min_args) if min_args == upper else f"{min_args}..{upper}"
            raise ArgumentError(f"expected {expected} argument(s), got {count}")
    return validate


def nonempty_query(invocation: BangInvocation) -> None:
    _reject_flags(invocation)
    if not invocation.args:
        raise ArgumentError("search query is required")


@dataclass(frozen=True)
class BangDefinition:
    name: str
    aliases: tuple[str, ...]
    description: str
    required_capability: str | None
    required_permissions: frozenset[str]
    validator: Validator
    side_effect_class: SideEffectClass
    built_in: bool = False


class BangRegistry:
    def __init__(self, definitions: Iterable[BangDefinition]):
        by_name: dict[str, BangDefinition] = {}
        aliases: dict[str, str] = {}
        for definition in definitions:
            if definition.name in by_name or definition.name in aliases:
                raise ValueError(f"duplicate bang name: {definition.name}")
            by_name[definition.name] = definition
            for alias in definition.aliases:
                if alias in by_name or alias in aliases:
                    raise ValueError(f"duplicate bang alias: {alias}")
                aliases[alias] = definition.name
        self._by_name = by_name
        self._aliases = aliases

    def resolve(self, name: str) -> BangDefinition | None:
        canonical = self._aliases.get(name, name)
        return self._by_name.get(canonical)

    def definitions(self) -> tuple[BangDefinition, ...]:
        return tuple(self._by_name[name] for name in sorted(self._by_name))


DEFAULT_REGISTRY = BangRegistry([
    BangDefinition("help", ("commands",), "List commands available to this caller/runtime.", None, frozenset(), arity(0), SideEffectClass.READ_ONLY, True),
    BangDefinition("search", ("hunt",), "Search opportunities through the canonical search provider.", "SEARCH", frozenset({"opportunities:read"}), nonempty_query, SideEffectClass.READ_ONLY),
    BangDefinition("watch", (), "Add an opportunity to the tenant watchlist through its public provider.", "WATCHLIST", frozenset({"watchlist:write"}), arity(1), SideEffectClass.TENANT_WRITE),
    BangDefinition("compare", (), "Compare opportunities through the comparison provider.", "OPPORTUNITY_COMPARE", frozenset({"opportunities:read"}), arity(2, 8), SideEffectClass.READ_ONLY),
    BangDefinition("requirements", (), "Read extracted opportunity requirements.", "OPPORTUNITY_REQUIREMENTS", frozenset({"opportunities:read"}), arity(1), SideEffectClass.READ_ONLY),
    BangDefinition("readiness", (), "Read opportunity readiness.", "OPPORTUNITY_READINESS", frozenset({"opportunities:read"}), arity(1), SideEffectClass.READ_ONLY),
    BangDefinition("economics", (), "Read bid economics from the economics provider.", "BID_ECONOMICS", frozenset({"opportunities:read"}), arity(1), SideEffectClass.READ_ONLY),
    BangDefinition("workspace", (), "Read pursuit workspace state.", "PURSUIT_WORKSPACE", frozenset({"workspace:read"}), arity(0, 1), SideEffectClass.READ_ONLY),
    BangDefinition("buyer", (), "Read buyer intelligence.", "BUYER_PROFILE", frozenset({"opportunities:read"}), arity(1), SideEffectClass.READ_ONLY),
    BangDefinition("documents", (), "Read opportunity document inventory.", "OPPORTUNITY_DOCUMENTS", frozenset({"opportunities:read"}), arity(1), SideEffectClass.READ_ONLY),
    BangDefinition("history", (), "Read opportunity change history.", "OPPORTUNITY_HISTORY", frozenset({"opportunities:read"}), arity(1), SideEffectClass.READ_ONLY),
    BangDefinition("country", ("coverage",), "Read country coverage from an international registry provider.", "COUNTRY_COVERAGE", frozenset({"coverage:read"}), arity(1), SideEffectClass.READ_ONLY),
    BangDefinition("source", ("sources",), "Read one source registry entry.", "SOURCE_REGISTRY", frozenset({"coverage:read"}), arity(1), SideEffectClass.READ_ONLY),
])
