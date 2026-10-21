"""Selective evidence provenance and invalidation for Engineering Operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

from engineering_ops import sha_matches

HANDOFF_STATES = ("CURRENT", "HISTORICAL", "STALE", "NEEDS_RECHECK")


@dataclass(frozen=True)
class EvidenceDependency:
    kind: str
    key: str
    sha: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceClaim:
    claim_id: str
    exact_tree_sha: str | None
    dependencies: tuple[EvidenceDependency, ...]
    gate_run_ids: tuple[int, ...] = ()
    golden_evidence: str | None = None
    assembly_evidence: str | None = None


@dataclass(frozen=True)
class InvalidationResult:
    claim_id: str
    state: str
    invalidated_by: tuple[str, ...]
    preserved_dependencies: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def classify_claim(
    claim: EvidenceClaim,
    *,
    current_dependencies: Mapping[tuple[str, str], str],
    exact_tree_observable: bool = True,
) -> InvalidationResult:
    if not claim.exact_tree_sha or not exact_tree_observable:
        return InvalidationResult(
            claim.claim_id,
            "NEEDS_RECHECK",
            (),
            (),
            "exact-tree lineage is unavailable",
        )

    invalidated: list[str] = []
    preserved: list[str] = []
    unresolved: list[str] = []
    for dependency in claim.dependencies:
        label = f"{dependency.kind}:{dependency.key}@{dependency.sha[:8]}"
        current = current_dependencies.get((dependency.kind, dependency.key))
        if current is None:
            unresolved.append(label)
        elif sha_matches(dependency.sha, current):
            preserved.append(label)
        else:
            invalidated.append(label)

    if unresolved:
        return InvalidationResult(
            claim.claim_id,
            "NEEDS_RECHECK",
            tuple(invalidated),
            tuple(preserved),
            "dependency lineage unresolved: " + ", ".join(unresolved),
        )
    if invalidated:
        return InvalidationResult(
            claim.claim_id,
            "STALE",
            tuple(invalidated),
            tuple(preserved),
            "one or more material dependency HEADs moved",
        )
    return InvalidationResult(
        claim.claim_id,
        "CURRENT",
        (),
        tuple(preserved),
        "all declared material dependencies remain current",
    )


def invalidate_graph(
    claims: Iterable[EvidenceClaim],
    *,
    current_dependencies: Mapping[tuple[str, str], str],
) -> list[InvalidationResult]:
    return [
        classify_claim(claim, current_dependencies=current_dependencies)
        for claim in claims
    ]
