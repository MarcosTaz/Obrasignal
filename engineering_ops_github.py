"""Read-only live GitHub collector for engineering_ops.py.

Only GitHub GET requests are implemented. Any collection failure degrades the
affected evidence to UNKNOWN and the process emits a bounded diagnostic report.
"""

from __future__ import annotations

import argparse
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

    def workflow_runs(self, head_sha: str) -> list[dict[str, Any]]:
        payload = self.get(
            f"/repos/{self.repository}/actions/runs",
            params={"head_sha": head_sha, "per_page": 100},
        )
        runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
        if not isinstance(runs, list):
            raise RuntimeError("workflow run response is malformed")
        return runs


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
    return {
        "id": run.get("id"),
        "run_number": run.get("run_number"),
        "name": run.get("name"),
        "head_sha": run.get("head_sha"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "event": run.get("event"),
        "created_at": run.get("created_at"),
        "updated_at": run.get("updated_at"),
        "html_url": run.get("html_url"),
    }


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
                    # Markdown bodies frequently use #NNNN for workflow/check
                    # numbers. A number that is not a PR is not a dependency.
                    ignored_dependency_prs.add(number)
                continue
            except Exception:
                # A transient lookup failure is not proof that the reference is
                # non-PR; leave it unresolved so normalization fails closed.
                continue
        head_sha = ((payload.get("head") or {}).get("sha"))
        if head_sha:
            dependency_heads[str(number)] = str(head_sha)

    workflow_runs: dict[str, list[dict[str, Any]]] = {}
    collection_errors = dict(pull_errors)
    for pr in pull_requests:
        head_sha = pr.get("head_sha")
        if not head_sha:
            collection_errors[str(pr["number"])] = "PR head SHA unavailable"
            continue
        try:
            workflow_runs[str(pr["number"])] = [
                _run_snapshot(run) for run in client.workflow_runs(str(head_sha))
            ]
        except Exception as exc:
            collection_errors[str(pr["number"])] = (
                f"workflow collection failed: {type(exc).__name__}: {exc}"
            )

    return {
        "repository": client.repository,
        "default_branch": default_branch,
        "main_sha": main_sha,
        "pull_requests": pull_requests,
        "dependency_heads": dependency_heads,
        "ignored_dependency_prs": sorted(ignored_dependency_prs),
        "workflow_runs": workflow_runs,
        "collection_errors": collection_errors,
    }


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


def _write_outputs(
    report: dict[str, Any],
    *,
    json_out: Path,
    markdown_out: Path,
) -> None:
    json_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_out.write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository",
        default=os.environ.get("GITHUB_REPOSITORY"),
        help="owner/repository (defaults to GITHUB_REPOSITORY)",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
    )
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
        report = report_snapshot(snapshot)
        report.update(
            {
                "repository": args.repository,
                "default_branch": snapshot.get("default_branch"),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "collector_state": (
                    "NEEDS_RECHECK"
                    if snapshot.get("collection_errors")
                    else "COMPLETE"
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
