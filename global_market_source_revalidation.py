"""Deterministic source-contract drift detection for global market expansion.

Remote polling/retrieval belongs to the appropriate source/operations owner.
This module only evaluates observations and invalidates stale GREEN evidence.
Missing current evidence is never treated as unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

DriftState = Literal["UNCHANGED", "MATERIAL_DRIFT", "CURRENT_EVIDENCE_MISSING"]


@dataclass(frozen=True)
class SourceContractFingerprint:
    endpoint: str
    api_version: str
    schema: str
    pagination: str
    authentication: str
    identity: str
    update_identity: str
    lifecycle: str
    time_semantics: str
    taxonomy: str
    rate_limit: str

    def semantic_hash(self) -> str:
        material = "\n".join((
            self.endpoint,
            self.api_version,
            self.schema,
            self.pagination,
            self.authentication,
            self.identity,
            self.update_identity,
            self.lifecycle,
            self.time_semantics,
            self.taxonomy,
            self.rate_limit,
        ))
        return "sha256:" + sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourceObservation:
    country: str
    source_id: str
    observed_at: str
    fingerprint: SourceContractFingerprint | None
    reachable: bool | None
    response_semantics_valid: bool | None


def compare_source_contract(
    previous: SourceContractFingerprint | None,
    current: SourceContractFingerprint | None,
) -> DriftState:
    if previous is None or current is None:
        return "CURRENT_EVIDENCE_MISSING"
    if previous.semantic_hash() != current.semantic_hash():
        return "MATERIAL_DRIFT"
    return "UNCHANGED"


def source_revalidation_required(
    *,
    previous: SourceContractFingerprint | None,
    current: SourceContractFingerprint | None,
    reachable: bool | None,
    response_semantics_valid: bool | None,
) -> bool:
    """Invalidate prior technical confidence on drift, missing proof, or bad semantics."""
    if reachable is not True:
        return True
    if response_semantics_valid is not True:
        return True
    return compare_source_contract(previous, current) != "UNCHANGED"


def changed_dimensions(
    previous: SourceContractFingerprint | None,
    current: SourceContractFingerprint | None,
) -> tuple[str, ...]:
    if previous is None or current is None:
        return ("EVIDENCE_MISSING",)
    fields = SourceContractFingerprint.__dataclass_fields__
    return tuple(name for name in fields if getattr(previous, name) != getattr(current, name))


def validate_no_http_success_shortcut() -> None:
    baseline = SourceContractFingerprint(
        endpoint="official",
        api_version="v1",
        schema="schema-a",
        pagination="cursor-a",
        authentication="none",
        identity="id",
        update_identity="version",
        lifecycle="open/closed",
        time_semantics="UTC",
        taxonomy="native",
        rate_limit="documented",
    )
    drifted = SourceContractFingerprint(**{
        **baseline.__dict__,
        "schema": "schema-b",
    })
    if not source_revalidation_required(
        previous=baseline,
        current=drifted,
        reachable=True,
        response_semantics_valid=True,
    ):
        raise RuntimeError("HTTP/source reachability must not hide material schema drift")


validate_no_http_success_shortcut()
