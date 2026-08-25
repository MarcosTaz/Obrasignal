"""Read-only live GitHub collector for engineering_ops.py.

Only GitHub GET requests are implemented. Any collection failure degrades the
affected evidence to UNKNOWN and the process emits a bounded diagnostic report.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engineering_ops import (
    SCHEMA_VERSION,
    extract_dependency_refs,
    render_markdown,
    report_snapshot,
)
from engineering_ops_gate_attribution import (
    classify_gate_attribution,
    complete_required_gates,
    evaluate_owner_gate_state,
    extract_pull_request_paths,
    required_workflows_for_changed_paths,
)


class ReadOnlyGitHub:
    def __init__(self, *, repository: str, token: str | None, api_url: str) -> None:
        self.repository = repository
        self.token = token or ""
        self.api_url = api_url.rstrip("/")

    def get(self, path: str, *, params: dict[str, object] | None = None) -> Any:
        if not path.startswith("/"):
            raise ValueError("GitHub API path must start with /")
        query = urllib.parse.urlencode(
            {key: value for key, value in (params or {}).items() if value is not None}
        )
        url = f"{self.api_url}{path}"
        if query:
            url += "?" + query
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "obrasignal-engineering-ops-readonly",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    def repo(self) -> dict[str, Any]:
        return self.get(f"/repos/{self.repository}")

    def branch(self, name: str) -> dict[str, Any]:
        quoted = urllib.parse.quote(name, safe="")
        return self.get(f"/repos/{self.repository}/branches/{quoted}")

    def open_pull_numbers(self) -> list[int]:
        numbers: list[int] = []
        page = 1
        while True:
            payload = self.get(
                f"/repos/{self.repository}/pulls",
                params={"state": "open", "per_page": 100, "page": page},
            )
            if not isinstance(payload, list):
                raise RuntimeError("open pull request response is not a list")
            numbers.extend(int(item["number"]) for item in payload)
            if len(payload) < 100:
                return numbers
            page += 1
            if page > 20:
                raise RuntimeError("refusing unbounded PR pagination")

    def pull(self, number: int) -> dict[str, Any]:
        return self.get(f"/repos/{self.repository}/pulls/{number}")

    def pull_files(self, number: int) -> list[str]:
        paths: list[str] = []
        page = 1
        while True:
            payload = self.get(
                f"/repos/{self.repository}/pulls/{number}/files",
                params={"per_page": 100, "page": page},
            )
            if not isinstance(payload, list):
                raise RuntimeError("pull file response is not a list")
            paths.extend(str(item["filename"]) for item in payload if item.get("filename"))
            if len(payload) < 100:
                return paths
            page += 1
            if page > 20:
                raise RuntimeError("refusing unbounded PR file pagination")

    def workflow_runs(self, head_sha: str) -> list[dict[str, Any]]:
        payload = self.get(
            f"/repos/{self.repository}/actions/runs",
            params={"head_sha": head_sha, "per_page": 100},
        )
        runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
        if not isinstance(runs, list):
            raise RuntimeError("workflow run response is malformed")
        return runs

    def directory(self, path: str, *, ref: str) -> list[dict[str, Any]]:
        quoted = urllib.parse.quote(path, safe="/")
        payload = self.get(
            f"/repos/{self.repository}/contents/{quoted}", params={"ref": ref}
        )
        if not isinstance(payload, list):
            raise RuntimeError(f"directory response is malformed for {path}")
        return payload

    def text_file(self, path: str, *, ref: str) -> str:
        quoted = urllib.parse.quote(path, safe="/")
        payload = self.get(
            f"/repos/{self.repository}/contents/{quoted}", params={"ref": ref}
        )
        if not isinstance(payload, dict) or payload.get("encoding") != "base64":
            raise RuntimeError(f"file response is malformed for {path}")
        content = payload.get("content")
        if not isinstance(content, str):
            raise RuntimeError(f"file content unavailable for {path}")
        return base64.b64decode(content).decode("utf-8")


def _pr_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    head = payload.get("head") or {}
    base = payload.get("base") or {}
    return {
        "number": int(payload["number"]),
        "title": payload.get("title") or "",
        "body": payload.get("body") or "",
        "html_url": payload.get("html_url"),
        "head_sha": head.get("sha"),
        "head_ref": head.get("ref"),
        "base_sha": base.get("sha"),
        "base_ref": base.get("ref"),
        "draft": bool(payload.get("draft")),
        "mergeable": payload.get("mergeable"),
    }


def _run_snapshot(run: dict[str, Any]) -> dict[str, Any]:
    pull_requests = run.get("pull_requests") or []
    return {
        "id": run.get("id"),
        "run_number": run.get("run_number"),
        "name": run.get("name"),
        "path": run.get("path"),
        "head_sha": run.get("head_sha"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "event": run.get("event"),
        "created_at": run.get("created_at"),
        "updated_at": run.get("updated_at"),
        "html_url": run.get("html_url"),
        "trigger_pr": (
            int(pull_requests[0]["number"])
            if pull_requests and pull_requests[0].get("number") is not None
            else None
        ),
    }


def _raw_gate_state(run: dict[str, Any], *, candidate_head: str) -> str:
    run_sha = str(run.get("head_sha") or "")
    if not run_sha or not candidate_head.startswith(run_sha[:7]) and not run_sha.startswith(candidate_head[:7]):
        return "HISTORICAL"
    status = str(run.get("status") or "").lower()
    conclusion = str(run.get("conclusion") or "").lower()
    if status != "completed":
        return "IN_PROGRESS"
    if conclusion == "success":
        return "PASS"
    if conclusion in {"skipped", "neutral"}:
        return "NOT_RUN"
    if conclusion in {"failure", "cancelled", "timed_out", "action_required", "startup_failure"}:
        return "FAIL"
    return "UNKNOWN"


def _candidate_workflows(client: ReadOnlyGitHub, *, head_sha: str) -> tuple[set[str], dict[str, tuple[str, ...] | None]]:
    paths: set[str] = set()
    filters: dict[str, tuple[str, ...] | None] = {}
    try:
        entries = client.directory(".github/workflows", ref=head_sha)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return paths, filters
        raise
    for item in entries:
        path = item.get("path")
        if not isinstance(path, str) or item.get("type") != "file":
            continue
        paths.add(path)
        try:
            filters[path] = extract_pull_request_paths(client.text_file(path, ref=head_sha))
        except Exception:
            filters[path] = ()
    return paths, filters


def collect(client: ReadOnlyGitHub) -> dict[str, Any]:
    repo = client.repo()
    default_branch = repo.get("default_branch") or "main"
    branch = client.branch(default_branch)
    main_sha = ((branch.get("commit") or {}).get("sha"))

    pull_requests: list[dict[str, Any]] = []
    pull_errors: dict[str, str] = {}
    detail_by_number: dict[int, dict[str, Any]] = {}

    for number in client.open_pull_numbers():
        try:
            payload = client.pull(number)
            detail_by_number[number] = payload
            pull_requests.append(_pr_snapshot(payload))
        except Exception as exc:
            pull_errors[str(number)] = f"{type(exc).__name__}: {exc}"

    dependency_numbers: set[int] = set()
    for pr in pull_requests:
        for ref in extract_dependency_refs(pr.get("body") or "", self_pr=pr["number"]):
            dependency_numbers.add(int(ref["pr"]))

    dependency_heads: dict[str, str] = {}
    ignored_dependency_prs: set[int] = set()
    for number in sorted(dependency_numbers):
        payload = detail_by_number.get(number)
        if payload is None:
            try:
                payload = client.pull(number)
                detail_by_number[number] = payload
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    ignored_dependency_prs.add(number)
                continue
            except Exception:
                continue
        head_sha = ((payload.get("head") or {}).get("sha"))
        if head_sha:
            dependency_heads[str(number)] = str(head_sha)

    workflow_runs: dict[str, list[dict[str, Any]]] = {}
    gate_attribution: dict[str, dict[str, Any]] = {}
    collection_errors = dict(pull_errors)

    for pr in pull_requests:
        number = int(pr["number"])
        head_sha = pr.get("head_sha")
        if not head_sha:
            collection_errors[str(number)] = "PR head SHA unavailable"
            continue
        try:
            changed_paths = client.pull_files(number)
            candidate_workflow_paths, workflow_filters = _candidate_workflows(
                client, head_sha=str(head_sha)
            )
            raw_runs = client.workflow_runs(str(head_sha))
            run_rows = [_run_snapshot(run) for run in raw_runs]
            workflow_runs[str(number)] = run_rows

            required = required_workflows_for_changed_paths(changed_paths)
            attributed: list[dict[str, Any]] = []
            observed_states: dict[str, str] = {}
            for row in run_rows:
                workflow = str(row.get("name") or "UNKNOWN")
                gate_state = _raw_gate_state(row, candidate_head=str(head_sha))
                observed_states[workflow] = gate_state
                workflow_path = row.get("path")
                attribution = classify_gate_attribution(
                    workflow=workflow,
                    workflow_path=str(workflow_path) if workflow_path else None,
                    changed_paths=changed_paths,
                    explicit_required_workflows=required,
                    candidate_workflow_paths=candidate_workflow_paths,
                    path_filters=workflow_filters.get(str(workflow_path)) if workflow_path in candidate_workflow_paths else None,
                    run_trigger_pr=row.get("trigger_pr"),
                    candidate_pr=number,
                )
                attributed.append(
                    {
                        "workflow": workflow,
                        "run_id": row.get("id"),
                        "gate_state": gate_state,
                        "attribution": attribution.state,
                        "reason": attribution.reason,
                        "workflow_path": workflow_path,
                        "trigger_pr": row.get("trigger_pr"),
                    }
                )

            for missing in complete_required_gates(
                required_workflows=required,
                observed_gate_states=observed_states,
            ):
                if missing.state != "REQUIRED_NOT_RUN":
                    continue
                attributed.append(
                    {
                        "workflow": missing.workflow,
                        "run_id": None,
                        "gate_state": "NOT_RUN",
                        "attribution": missing.state,
                        "reason": missing.reason,
                        "workflow_path": None,
                        "trigger_pr": None,
                    }
                )

            owner_state, owner_reason = evaluate_owner_gate_state(attributed)
            gate_attribution[str(number)] = {
                "changed_paths": changed_paths,
                "required_workflows": sorted(required),
                "gates": attributed,
                "owner_gate_state": owner_state,
                "owner_gate_reason": owner_reason,
            }
        except Exception as exc:
            collection_errors[str(number)] = (
                f"workflow/gate collection failed: {type(exc).__name__}: {exc}"
            )
            gate_attribution[str(number)] = {
                "changed_paths": None,
                "required_workflows": [],
                "gates": [],
                "owner_gate_state": "NEEDS_RECHECK",
                "owner_gate_reason": "gate attribution collection failed",
            }

    return {
        "repository": client.repository,
        "default_branch": default_branch,
        "main_sha": main_sha,
        "pull_requests": pull_requests,
        "dependency_heads": dependency_heads,
        "ignored_dependency_prs": sorted(ignored_dependency_prs),
        "workflow_runs": workflow_runs,
        "gate_attribution": gate_attribution,
        "collection_errors": collection_errors,
    }


def enrich_report_with_gate_attribution(report: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    by_pr = snapshot.get("gate_attribution") or {}
    for candidate in report.get("candidates") or []:
        key = str(candidate.get("pr"))
        attribution = by_pr.get(key)
        if attribution is not None:
            candidate.setdefault("evidence", {})["gate_attribution"] = attribution
    return report


def _failure_report(repository: str, error: Exception) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "authority": "NON_AUTHORITATIVE_OPERATIONAL_METADATA",
        "overall": "UNKNOWN",
        "repository": repository,
        "main_sha": None,
        "candidate_count": 0,
        "stale_count": 0,
        "unknown_count": 1,
        "candidates": [],
        "failure_semantics": "tooling failure => UNKNOWN/NEEDS_RECHECK; never GREEN",
        "collector_state": "NEEDS_RECHECK",
        "collector_error": f"{type(error).__name__}: {error}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _write_outputs(report: dict[str, Any], *, json_out: Path, markdown_out: Path) -> None:
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"), help="owner/repository (defaults to GITHUB_REPOSITORY)")
    parser.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    parser.add_argument("--json-out", type=Path, default=Path("engineering-ops-status.json"))
    parser.add_argument("--markdown-out", type=Path, default=Path("engineering-ops-status.md"))
    args = parser.parse_args()

    if not args.repository or "/" not in args.repository:
        error = ValueError("repository must be supplied as owner/name")
        report = _failure_report(args.repository or "UNKNOWN", error)
        _write_outputs(report, json_out=args.json_out, markdown_out=args.markdown_out)
        print(report["collector_error"], file=sys.stderr)
        return 1

    client = ReadOnlyGitHub(
        repository=args.repository,
        token=os.environ.get("GITHUB_TOKEN"),
        api_url=args.api_url,
    )
    try:
        snapshot = collect(client)
        report = enrich_report_with_gate_attribution(report_snapshot(snapshot), snapshot)
        report.update(
            {
                "repository": args.repository,
                "default_branch": snapshot.get("default_branch"),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "collector_state": (
                    "NEEDS_RECHECK" if snapshot.get("collection_errors") else "COMPLETE"
                ),
            }
        )
        if snapshot.get("collection_errors"):
            report["collection_errors"] = snapshot["collection_errors"]
        _write_outputs(report, json_out=args.json_out, markdown_out=args.markdown_out)
        return 0
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
        report = _failure_report(args.repository, exc)
        _write_outputs(report, json_out=args.json_out, markdown_out=args.markdown_out)
        print(report["collector_error"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
