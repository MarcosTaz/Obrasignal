"""Executable PR-body drift classification for non-authoritative operations metadata."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

from engineering_ops import extract_declared_head, extract_dependency_refs, sha_matches

BODY_STATES = (
    "BODY_CURRENT",
    "BODY_STALE_HEAD",
    "BODY_STALE_EVIDENCE",
    "BODY_STALE_DEPENDENCY",
    "UNKNOWN",
)

_RUN_RE = re.compile(r"(?:run\s*[`#:]?\s*|run_id\s*[=:]\s*)(?P<id>\d{5,})", re.I)


@dataclass(frozen=True)
class BodyDrift:
    state: str
    reason: str
    reopen_condition: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def extract_evidence_run_ids(body: str) -> set[int]:
    return {int(match.group("id")) for match in _RUN_RE.finditer(body or "")}


def classify_body_drift(
    *,
    pr_number: int,
    body: str,
    actual_head: str | None,
    actual_dependency_heads: Mapping[int, str],
    current_evidence_run_ids: Iterable[int] | None = None,
) -> BodyDrift:
    if not actual_head:
        return BodyDrift("UNKNOWN", "live PR HEAD unavailable", "repository HEAD becomes observable")

    declared_head = extract_declared_head(body, self_pr=pr_number)
    if declared_head and not sha_matches(declared_head, actual_head):
        return BodyDrift(
            "BODY_STALE_HEAD",
            f"body HEAD {declared_head} differs from live HEAD {actual_head}",
            "body HEAD is refreshed to current exact HEAD",
        )

    dependencies = extract_dependency_refs(body, self_pr=pr_number)
    for dependency in dependencies:
        dep_pr = int(dependency["pr"])
        actual = actual_dependency_heads.get(dep_pr)
        if actual is None:
            return BodyDrift(
                "UNKNOWN",
                f"dependency #{dep_pr} current HEAD unavailable",
                "dependency HEAD becomes observable",
            )
        if not sha_matches(dependency.get("declared_sha"), actual):
            return BodyDrift(
                "BODY_STALE_DEPENDENCY",
                f"dependency #{dep_pr} body SHA differs from live HEAD",
                f"dependency #{dep_pr} evidence is refreshed or explicitly historical",
            )

    body_run_ids = extract_evidence_run_ids(body)
    if body_run_ids and current_evidence_run_ids is not None:
        current = {int(value) for value in current_evidence_run_ids}
        stale = sorted(body_run_ids - current)
        if stale:
            return BodyDrift(
                "BODY_STALE_EVIDENCE",
                "body references non-current evidence run IDs: " + ", ".join(map(str, stale)),
                "body evidence references current exact-head runs or marks old runs historical",
            )

    if declared_head is None:
        return BodyDrift(
            "UNKNOWN",
            "body has no unambiguous declared self HEAD",
            "body declares current exact HEAD",
        )

    return BodyDrift(
        "BODY_CURRENT",
        "body HEAD, dependencies, and supplied evidence references are current",
        "HEAD/dependency/evidence movement",
    )
