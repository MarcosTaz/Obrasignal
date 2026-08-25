"""Trusted server-side ingestion seam for Company State v1 providers.

This module is deliberately separate from the voluntary/manual application
boundary. OFFICE sensors, official registries and verified integrations may use
this seam only after their own auth/source validation has established trusted
server-side provenance. It does not accept client tenant authority and it never
silently resolves conflicting facts.
"""
from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from typing import Callable, Iterable

from company_state import (
    CompanyFact,
    CompanyState,
    CompanyStateError,
    MAX_FACTS,
    ProvenanceBasis,
    validate_account_id,
)
from company_state_store import current_company_state, save_company_state

TRUSTED_PROVIDER_BASES = frozenset({
    ProvenanceBasis.VERIFIED,
    ProvenanceBasis.PUBLIC_REGISTRY,
    ProvenanceBasis.INTEGRATION,
    ProvenanceBasis.LEARNED,
})


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise CompanyStateError(f"{name} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _validate_provider_fact(fact: CompanyFact) -> None:
    if not isinstance(fact, CompanyFact):
        raise CompanyStateError("trusted provider facts must be CompanyFact values")
    if fact.provenance.basis not in TRUSTED_PROVIDER_BASES:
        raise CompanyStateError("trusted provider facts require VERIFIED, PUBLIC_REGISTRY, INTEGRATION or LEARNED provenance")
    if not fact.provenance.source_ref:
        raise CompanyStateError("trusted provider facts require a source_ref")
    if fact.provenance.observed_at is None:
        raise CompanyStateError("trusted provider facts require observed_at")


class TrustedCompanyStateProviderService:
    """Persist facts emitted by already-trusted server-side providers.

    Tenant identity is supplied by the trusted caller, never by a provider fact.
    The provider may explicitly supersede prior same-semantic facts through the
    public ``CompanyFact.supersedes`` contract. Without such an explicit link,
    incompatible current values remain a CONFLICT; this seam has no universal
    source-precedence policy.
    """

    def __init__(self, connection_factory: Callable[[], sqlite3.Connection]):
        self._connection_factory = connection_factory

    def apply(
        self,
        trusted_account_id: str,
        facts: Iterable[CompanyFact],
        *,
        clock: datetime,
        expected_version: int | None = None,
        company_ref: str | None = None,
    ) -> CompanyState:
        account = validate_account_id(trusted_account_id)
        as_of = _utc(clock, "clock")
        incoming = tuple(facts)
        if len(incoming) > MAX_FACTS:
            raise CompanyStateError("too many trusted provider facts")
        for fact in incoming:
            _validate_provider_fact(fact)

        conn = self._connection_factory()
        try:
            current = current_company_state(conn, account)
            current_version = current.state_version if current else 0
            if expected_version is None:
                expected_version = current_version
            if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 0:
                raise CompanyStateError("expected_version must be a non-negative integer")

            merged = {fact.fact_id: fact for fact in (current.facts if current else ())}
            for fact in incoming:
                merged[fact.fact_id] = fact

            state = CompanyState(
                account_id=account,
                company_ref=current.company_ref if current is not None else company_ref,
                as_of=as_of,
                facts=tuple(merged.values()),
            )
            return save_company_state(
                conn,
                state,
                expected_version=expected_version,
                clock=as_of,
            )
        finally:
            conn.close()
