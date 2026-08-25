"""Non-authoritative engineering-operations status normalization for ObraSignal.

This module automates the flow of repository evidence. It never decides product
truth, priority, merge, release, deployment, source activation, capability
promotion, or specialist ownership.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "engineering-ops.v1"

STATUS_VALUES = (
    "ACTIVE",
    "NEXT",
    "WAIT",
    "GREEN",
    "RED",
    "STALE",
    "BLOCKED_EXTERNAL",
    "BLOCKED_OWNER",
    "READY",
    "HANDOFF_READY",
    "CANONICAL_NEXT",
    "SUPERSEDED",
    "UNKNOWN",
)
EVIDENCE_STATES = ("CURRENT", "STALE", "SUPERSEDED", "UNKNOWN")
GATE_STATES = ("PASS", "FAIL", "NOT_RUN", "IN_PROGRESS", "UNKNOWN", "HISTORICAL")
REQUIRED_STATUS_FIELDS = (
    "owner",
    "exact_head",
    "base",
    "main_sha",
    "evidence",
    "reason",
    "reopen_condition",
)

_FULL_SHA_RE = re.compile(r"(?<![0-9a-f])([0-9a-f]{40})(?![0-9a-f])", re.I)
_SHORT_SHA_RE = re.compile(r"(?<![0-9a-f])([0-9a-f]{7,12})(?![0-9a-f])", re.I)
_PR_AT_SHA_RE = re.compile(
    r"#(?P<pr>\d+)\s*@\s*`?(?P<sha>[0-9a-f]{7,40})`?",
    re.I,
)
_PR_TOKEN_RE = re.compile(r"#(?P<pr>\d+)")
_SHA_TOKEN_RE = re.compile(r"`?(?P<sha>[0-9a-f]{7,40})`?", re.I)

_CURRENT_REFERENCE_TOKENS = (
    "current",
    "exact",
    "input",
    "head",
    "base",
    "compose",
    "stacked",
    "must use",
    "depends",
    "dependency",
    "handoff",
)
_DIAGNOSTIC_REFERENCE_TOKENS = (
    "historical",
    "prior",
    "earlier",
    "older",
    "previous",
    "superseded",
    "diagnostic",
    "example",
    "observed as",
    "motivated",
    "motivation",
)

_HEAD_LABELS = (
    "current owner head",
    "current pr head",
    "candidate head",
    "exact candidate head",
    "exact head",
    "final candidate head",
    "current candidate head",
    "head",
)
_MAIN_LABELS = (
    "canonical main",
    "current main",
    "main",
)


@dataclass(frozen=True)
class ReferenceState:
    declared: str | None
    actual: str | None
    state: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalized_sha(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{7,40}", candidate):
        return None
    return candidate


def sha_matches(declared: object, actual: object) -> bool:
    left = _normalized_sha(declared)
    right = _normalized_sha(actual)
    if not left or not right:
        return False
    shortest = min(len(left), len(right))
    if shortest < 7:
        return False
    return left[:shortest] == right[:shortest]


def classify_reference(
    declared: object,
    actual: object,
    *,
    subject: str,
) -> ReferenceState:
    declared_sha = _normalized_sha(declared)
    actual_sha = _normalized_sha(actual)
    if not declared_sha:
        return ReferenceState(
            declared=None,
            actual=actual_sha,
            state="UNKNOWN",
            reason=f"{subject}: no valid declared SHA",
        )
    if not actual_sha:
        return ReferenceState(
            declared=declared_sha,
            actual=None,
            state="UNKNOWN",
            reason=f"{subject}: current SHA unavailable",
        )
    if sha_matches(declared_sha, actual_sha):
        return ReferenceState(
            declared=declared_sha,
            actual=actual_sha,
            state="CURRENT",
            reason=f"{subject}: declared SHA matches current SHA",
        )
    return ReferenceState(
        declared=declared_sha,
        actual=actual_sha,
        state="STALE",
        reason=f"{subject}: declared SHA differs from current SHA",
    )


def _extract_labeled_sha(body: str, labels: Sequence[str]) -> str | None:
    if not body:
        return None
    for line in body.splitlines():
        lowered = line.lower()
        if not any(re.search(rf"\b{re.escape(label)}\b", lowered) for label in labels):
            continue
        matches = _FULL_SHA_RE.findall(line) or _SHORT_SHA_RE.findall(line)
        if matches:
            return matches[-1].lower()
    return None


def extract_declared_head(body: str, *, self_pr: int | None = None) -> str | None:
    """Return a declared self HEAD, ignoring HEAD statements about another PR."""
    if not body:
        return None
    for line in body.splitlines():
        lowered = line.lower()
        if not any(re.search(rf"\b{re.escape(label)}\b", lowered) for label in _HEAD_LABELS):
            continue
        referenced_prs = {int(match.group("pr")) for match in _PR_TOKEN_RE.finditer(line)}
        if self_pr is not None and referenced_prs and self_pr not in referenced_prs:
            continue
        matches = _FULL_SHA_RE.findall(line) or _SHORT_SHA_RE.findall(line)
        if matches:
            return matches[-1].lower()
    return None


def extract_declared_main(body: str) -> str | None:
    return _extract_labeled_sha(body, _MAIN_LABELS)


def _dependency_reference_role(line: str, section: str) -> str:
    context = f"{section} {line}".lower()
    if any(token in context for token in _DIAGNOSTIC_REFERENCE_TOKENS):
        return "HISTORICAL_OR_DIAGNOSTIC"
    if any(token in context for token in _CURRENT_REFERENCE_TOKENS):
        return "CURRENT_PIN"
    return "UNCLASSIFIED"


def extract_dependency_refs(body: str, *, self_pr: int | None = None) -> list[dict[str, Any]]:
    """Extract only explicit current PR->SHA pins.

    References in historical/diagnostic prose are preserved in the PR body but
    are not allowed to invalidate downstream current proof. On a line with
    multiple PR numbers, a SHA belongs only to the PR segment before the next
    PR token; this prevents "#319 ... current #329 input <sha>" from falsely
    pinning #319 to #329's SHA.
    """
    found: dict[tuple[int, str], dict[str, Any]] = {}
    section = ""

    for raw_line in (body or "").splitlines():
        line = raw_line.strip()
        if re.match(r"^#{1,6}\s+", line):
            section = line
            continue

        role = _dependency_reference_role(line, section)
        if role != "CURRENT_PIN":
            continue

        # Direct #PR@SHA form is unambiguous within a current-intent line/section.
        for match in _PR_AT_SHA_RE.finditer(line):
            pr = int(match.group("pr"))
            if self_pr is not None and pr == self_pr:
                continue
            sha = match.group("sha").lower()
            found[(pr, sha)] = {
                "pr": pr,
                "declared_sha": sha,
                "source": "pr_at_sha",
                "role": role,
            }

        pr_matches = list(_PR_TOKEN_RE.finditer(line))
        for index, match in enumerate(pr_matches):
            pr = int(match.group("pr"))
            if self_pr is not None and pr == self_pr:
                continue
            start = match.end()
            end = pr_matches[index + 1].start() if index + 1 < len(pr_matches) else len(line)
            segment = line[start:end]
            sha_match = _SHA_TOKEN_RE.search(segment)
            if not sha_match:
                continue
            sha = sha_match.group("sha").lower()
            found.setdefault(
                (pr, sha),
                {
                    "pr": pr,
                    "declared_sha": sha,
                    "source": "pr_segment_sha",
                    "role": role,
                },
            )

    return sorted(found.values(), key=lambda item: (item["pr"], item["declared_sha"]))


def classify_dependencies(
    refs: Iterable[Mapping[str, Any]],
    actual_heads: Mapping[int, str],
) -> list[dict[str, Any]]:
    classified: list[dict[str, Any]] = []
    for ref in refs:
        pr = int(ref["pr"])
        declared = ref.get("declared_sha")
        state = classify_reference(
            declared,
            actual_heads.get(pr),
            subject=f"dependency #{pr}",
        )
        classified.append(
            {
                "pr": pr,
                "source": ref.get("source"),
                **state.to_dict(),
            }
        )
    return classified


def normalize_workflow_runs(
    runs: Iterable[Mapping[str, Any]],
    *,
    candidate_head: str | None,
) -> list[dict[str, Any]]:
    """Normalize runs without promoting a workflow result into product readiness."""
    current_head = _normalized_sha(candidate_head)
    normalized: list[dict[str, Any]] = []

    for run in runs:
        run_sha = _normalized_sha(run.get("head_sha"))
        status = str(run.get("status") or "").lower()
        conclusion = str(run.get("conclusion") or "").lower() or None
        exact = bool(current_head and run_sha and sha_matches(run_sha, current_head))

        if not exact:
            gate_state = "HISTORICAL"
            evidence_state = "STALE" if run_sha else "UNKNOWN"
        elif status != "completed":
            gate_state = "IN_PROGRESS"
            evidence_state = "CURRENT"
        elif conclusion == "success":
            gate_state = "PASS"
            evidence_state = "CURRENT"
        elif conclusion in {"skipped", "neutral"}:
            gate_state = "NOT_RUN"
            evidence_state = "CURRENT"
        elif conclusion in {"failure", "cancelled", "timed_out", "action_required", "startup_failure"}:
            gate_state = "FAIL"
            evidence_state = "CURRENT"
        else:
            gate_state = "UNKNOWN"
            evidence_state = "CURRENT" if run_sha else "UNKNOWN"

        normalized.append(
            {
                "workflow": run.get("name") or run.get("workflow_name") or "UNKNOWN",
                "run_id": run.get("id"),
                "run_number": run.get("run_number"),
                "head_sha": run_sha,
                "status": status or None,
                "conclusion": conclusion,
                "event": run.get("event"),
                "created_at": run.get("created_at"),
                "updated_at": run.get("updated_at"),
                "gate_state": gate_state,
                "evidence_state": evidence_state,
                "exact_head": exact,
                "proves": "workflow execution only; no product/readiness authority",
            }
        )

    normalized.sort(
        key=lambda item: (
            str(item.get("workflow")),
            str(item.get("updated_at") or ""),
            int(item.get("run_id") or 0),
        ),
        reverse=True,
    )
    return normalized


def _record_state(
    *,
    self_head: ReferenceState,
    main_ref: ReferenceState,
    dependencies: Sequence[Mapping[str, Any]],
    collection_error: str | None,
) -> tuple[str, str, str]:
    if collection_error:
        return (
            "UNKNOWN",
            f"collector failure: {collection_error}",
            "successful repository recheck",
        )

    stale = []
    unknown = []
    if self_head.state == "STALE":
        stale.append("PR body HEAD")
    elif self_head.state == "UNKNOWN":
        unknown.append("PR body HEAD")
    if main_ref.state == "STALE":
        stale.append("PR body main")
    elif main_ref.state == "UNKNOWN":
        # Main may legitimately be omitted from a small PR body. Keep this as
        # evidence uncertainty, but do not invent stale.
        unknown.append("PR body main")

    for dep in dependencies:
        label = f"dependency #{dep['pr']}"
        if dep["state"] == "STALE":
            stale.append(label)
        elif dep["state"] == "UNKNOWN":
            unknown.append(label)

    if stale:
        return (
            "STALE",
            "stale exact-reference evidence: " + ", ".join(stale),
            "referenced HEAD/main changes reconciled and affected proof rerun",
        )
    if unknown:
        return (
            "UNKNOWN",
            "exact-reference evidence incomplete: " + ", ".join(unknown),
            "missing exact references/evidence resolved from repository truth",
        )
    return (
        "ACTIVE",
        "operational references are current; readiness is intentionally not inferred",
        "material PR/main/dependency movement or owner handoff",
    )


def candidate_record(
    pr: Mapping[str, Any],
    *,
    main_sha: str | None,
    actual_heads: Mapping[int, str],
    workflow_runs: Iterable[Mapping[str, Any]] = (),
    collection_error: str | None = None,
    ignored_dependency_prs: Iterable[int] = (),
) -> dict[str, Any]:
    number = int(pr["number"])
    body = str(pr.get("body") or "")
    actual_head = _normalized_sha(pr.get("head_sha"))
    base_sha = _normalized_sha(pr.get("base_sha"))

    self_ref = classify_reference(
        extract_declared_head(body, self_pr=number),
        actual_head,
        subject=f"PR #{number} body HEAD",
    )
    main_ref = classify_reference(
        extract_declared_main(body),
        main_sha,
        subject=f"PR #{number} body main",
    )
    ignored = {int(value) for value in ignored_dependency_prs}
    dependency_refs = [
        ref
        for ref in extract_dependency_refs(body, self_pr=number)
        if int(ref["pr"]) not in ignored
    ]
    dependencies = classify_dependencies(dependency_refs, actual_heads)
    workflows = normalize_workflow_runs(workflow_runs, candidate_head=actual_head)
    state, reason, reopen = _record_state(
        self_head=self_ref,
        main_ref=main_ref,
        dependencies=dependencies,
        collection_error=collection_error,
    )

    owner = pr.get("owner") or "UNKNOWN"

    evidence = {
        "self_head": self_ref.to_dict(),
        "main": main_ref.to_dict(),
        "dependencies": dependencies,
        "workflow_runs": workflows,
    }

    record = {
        "pr": number,
        "title": pr.get("title") or "",
        "url": pr.get("html_url") or pr.get("url"),
        "owner": owner,
        "exact_head": actual_head,
        "base": pr.get("base_ref") or pr.get("base") or "UNKNOWN",
        "base_sha": base_sha,
        "main_sha": _normalized_sha(main_sha),
        "draft": bool(pr.get("draft")),
        "mergeable": pr.get("mergeable"),
        "status": state,
        "evidence": evidence,
        "reason": reason,
        "reopen_condition": reopen,
        "authority": "NON_AUTHORITATIVE_OPERATIONAL_METADATA",
    }
    missing = [field for field in REQUIRED_STATUS_FIELDS if field not in record]
    if missing:
        raise RuntimeError(f"internal status record missing fields: {missing}")
    return record


def report_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a deterministic offline snapshot used by tests and tooling."""
    main_sha = _normalized_sha(snapshot.get("main_sha"))
    pulls = list(snapshot.get("pull_requests") or [])
    actual_heads: dict[int, str] = {}
    for pr in pulls:
        sha = _normalized_sha(pr.get("head_sha"))
        if sha:
            actual_heads[int(pr["number"])] = sha
    for key, value in (snapshot.get("dependency_heads") or {}).items():
        sha = _normalized_sha(value)
        if sha:
            actual_heads[int(key)] = sha

    runs_by_pr = snapshot.get("workflow_runs") or {}
    ignored_dependency_prs = {
        int(value) for value in (snapshot.get("ignored_dependency_prs") or ())
    }
    records = [
        candidate_record(
            pr,
            main_sha=main_sha,
            actual_heads=actual_heads,
            workflow_runs=runs_by_pr.get(str(pr["number"]), runs_by_pr.get(int(pr["number"]), ())),
            collection_error=(snapshot.get("collection_errors") or {}).get(str(pr["number"])),
            ignored_dependency_prs=ignored_dependency_prs,
        )
        for pr in pulls
    ]

    if any(record["status"] == "STALE" for record in records):
        overall = "STALE"
    elif not main_sha or any(record["status"] == "UNKNOWN" for record in records):
        overall = "UNKNOWN"
    else:
        overall = "CURRENT"

    return {
        "schema_version": SCHEMA_VERSION,
        "authority": "NON_AUTHORITATIVE_OPERATIONAL_METADATA",
        "overall": overall,
        "main_sha": main_sha,
        "candidate_count": len(records),
        "stale_count": sum(record["status"] == "STALE" for record in records),
        "unknown_count": sum(record["status"] == "UNKNOWN" for record in records),
        "candidates": records,
        "failure_semantics": "tooling failure => UNKNOWN/NEEDS_RECHECK; never GREEN",
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Engineering Operations Drift Report",
        "",
        f"- schema: `{report.get('schema_version')}`",
        f"- authority: `{report.get('authority')}`",
        f"- main: `{report.get('main_sha') or 'UNKNOWN'}`",
        f"- overall operational evidence state: **{report.get('overall', 'UNKNOWN')}**",
        f"- candidates: {report.get('candidate_count', 0)}",
        f"- stale: {report.get('stale_count', 0)}",
        f"- unknown: {report.get('unknown_count', 0)}",
        "",
        "> Operational metadata only. CURRENT is not GREEN, READY, merge authorization, release authorization, or product truth.",
        "",
        "| PR | Status | Actual HEAD | Reason |",
        "|---:|:---|:---|:---|",
    ]
    for record in report.get("candidates") or []:
        head = (record.get("exact_head") or "UNKNOWN")[:8]
        reason = str(record.get("reason") or "").replace("|", "\\|")
        lines.append(
            f"| #{record.get('pr')} | {record.get('status')} | `{head}` | {reason} |"
        )

    stale = [r for r in report.get("candidates") or [] if r.get("status") == "STALE"]
    if stale:
        lines.extend(["", "## Stale handoff/evidence inputs"])
        for record in stale:
            lines.append(
                f"- #{record['pr']} `{(record.get('exact_head') or 'UNKNOWN')[:8]}`: "
                f"{record.get('reason')}; reopen when {record.get('reopen_condition')}."
            )

    return "\n".join(lines) + "\n"


def _cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    report = report_snapshot(snapshot)
    if args.format == "markdown":
        print(render_markdown(report), end="")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
