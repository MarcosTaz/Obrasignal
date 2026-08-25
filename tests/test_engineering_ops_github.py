from engineering_ops_github import collect, enrich_report_with_gate_attribution
from engineering_ops import report_snapshot


MAIN = "66d43f6fd51cf9cea08016dad335aaa04b711a24"
ACTUAL_238 = "6519b9f368a229da2b2787caf178f8ef956bda5b"
STALE_238 = "2aa332112bf0497b698bfb8dabafcca4562ca1bd"
HEAD_319 = "52e3ba5474d3e388735715db051e87eafb14c90a"


class FakeGitHub:
    repository = "MarcosTaz/Obrasignal"

    def repo(self):
        return {"default_branch": "main"}

    def branch(self, name):
        assert name == "main"
        return {"commit": {"sha": MAIN}}

    def open_pull_numbers(self):
        return [238, 319]

    def pull(self, number):
        if number == 238:
            return {
                "number": 238,
                "title": "storage",
                "body": f"- canonical main `{MAIN}`\n- current owner HEAD `{ACTUAL_238}`",
                "html_url": "https://example/238",
                "head": {"sha": ACTUAL_238, "ref": "storage"},
                "base": {"sha": MAIN, "ref": "main"},
                "draft": True,
                "mergeable": True,
            }
        if number == 319:
            return {
                "number": 319,
                "title": "all-up",
                "body": (
                    f"- main `{MAIN}`\n"
                    f"- #238 CURRENT `{STALE_238}`\n"
                    f"- CURRENT ALL-UP C HEAD `{HEAD_319}`"
                ),
                "html_url": "https://example/319",
                "head": {"sha": HEAD_319, "ref": "lab"},
                "base": {"sha": MAIN, "ref": "main"},
                "draft": True,
                "mergeable": True,
            }
        raise AssertionError(number)

    def pull_files(self, number):
        return ["storage.py"] if number == 238 else ["lab_probe.py"]

    def directory(self, path, *, ref):
        assert path == ".github/workflows"
        return [{"type": "file", "path": ".github/workflows/quality.yml"}]

    def text_file(self, path, *, ref):
        assert path == ".github/workflows/quality.yml"
        return "name: ObraSignal Quality\non:\n  pull_request:\n"

    def workflow_runs(self, head_sha):
        return [
            {
                "id": 10,
                "run_number": 2,
                "run_attempt": 1,
                "name": "ObraSignal Quality",
                "path": ".github/workflows/quality.yml",
                "head_sha": head_sha,
                "status": "completed",
                "conclusion": "success",
                "event": "pull_request",
                "pull_requests": [],
            }
        ]


def test_collect_is_read_only_snapshot_and_resolves_dependency_heads():
    snapshot = collect(FakeGitHub())
    assert snapshot["main_sha"] == MAIN
    assert snapshot["dependency_heads"]["238"] == ACTUAL_238
    assert len(snapshot["pull_requests"]) == 2
    assert snapshot["workflow_runs"]["319"][0]["head_sha"] == HEAD_319
    assert snapshot["gate_attribution"]["319"]["owner_gate_state"] == "OWNER_CURRENT_GREEN"
    assert snapshot["collection_errors"] == {}


def test_gate_attribution_is_exposed_in_candidate_evidence():
    snapshot = collect(FakeGitHub())
    report = enrich_report_with_gate_attribution(report_snapshot(snapshot), snapshot)
    gate = report["candidates"][0]["evidence"]["gate_attribution"]
    assert gate["owner_gate_state"] == "OWNER_CURRENT_GREEN"
    assert gate["gates"][0]["attribution"] == "REQUIRED"
    assert gate["gates"][0]["owner_effect"] == "OWNER_PASS_INPUT"


class EngineeringOpsFake(FakeGitHub):
    def open_pull_numbers(self):
        return [407]

    def pull(self, number):
        assert number == 407
        return {
            "number": 407,
            "title": "ops",
            "body": f"- canonical main `{MAIN}`\n- current exact HEAD `{HEAD_319}`",
            "html_url": "https://example/407",
            "head": {"sha": HEAD_319, "ref": "ops"},
            "base": {"sha": MAIN, "ref": "main"},
            "draft": True,
            "mergeable": True,
        }

    def pull_files(self, number):
        return ["engineering_ops_github.py", "tests/test_engineering_ops_github.py"]

    def directory(self, path, *, ref):
        return [
            {"type": "file", "path": ".github/workflows/engineering-ops-drift.yml"},
            {"type": "file", "path": ".github/workflows/quality.yml"},
            {"type": "file", "path": ".github/workflows/codeql.yml"},
        ]

    def text_file(self, path, *, ref):
        if path.endswith("engineering-ops-drift.yml"):
            return (
                "name: Engineering Ops Drift\n"
                "on:\n"
                "  pull_request:\n"
                "    paths:\n"
                "      - engineering_ops_github.py\n"
                "      - 'tests/**'\n"
                "  workflow_dispatch:\n"
            )
        return f"name: {path}\non:\n  pull_request:\n"

    def workflow_runs(self, head_sha):
        return [
            {
                "id": 1,
                "run_number": 1,
                "run_attempt": 1,
                "name": "Engineering Ops Drift",
                "path": ".github/workflows/engineering-ops-drift.yml",
                "head_sha": head_sha,
                "status": "completed",
                "conclusion": "success",
                "event": "pull_request",
                "pull_requests": [{"number": 407}],
            },
            {
                "id": 2,
                "run_number": 2,
                "run_attempt": 1,
                "name": "ObraSignal Quality",
                "path": ".github/workflows/quality.yml",
                "head_sha": head_sha,
                "status": "completed",
                "conclusion": "success",
                "event": "pull_request",
                "pull_requests": [{"number": 407}],
            },
            {
                "id": 3,
                "run_number": 3,
                "run_attempt": 1,
                "name": "Golden GP03 Economic Operational Truth",
                "path": ".github/workflows/golden-gp03.yml",
                "head_sha": head_sha,
                "status": "completed",
                "conclusion": "failure",
                "event": "pull_request",
                "pull_requests": [{"number": 413}, {"number": 407}],
            },
        ]


def test_missing_required_codeql_is_required_not_run_and_incidental_gp03_is_not_red():
    snapshot = collect(EngineeringOpsFake())
    attribution = snapshot["gate_attribution"]["407"]
    by_name = {row["workflow"]: row for row in attribution["gates"]}
    gp03 = by_name["Golden GP03 Economic Operational Truth"]
    codeql = by_name["ObraSignal CodeQL"]
    assert gp03["attribution"] == "INCIDENTALLY_TRIGGERED"
    assert gp03["gate_state"] == "FAIL"
    assert gp03["owner_effect"] == "EXCLUDED_FROM_OWNER_PASS_RED"
    assert codeql["attribution"] == "REQUIRED_NOT_RUN"
    assert codeql["trigger_awareness"] == "WORKFLOW_MISSING"
    assert codeql["owner_effect"] == "OWNER_NEEDS_RECHECK"
    assert attribution["owner_gate_state"] == "NEEDS_RECHECK"


class DuplicateRunFake(EngineeringOpsFake):
    def workflow_runs(self, head_sha):
        rows = super().workflow_runs(head_sha)
        rows.extend(
            [
                {
                    "id": 11,
                    "run_number": 4,
                    "run_attempt": 1,
                    "name": "Engineering Ops Drift",
                    "path": ".github/workflows/engineering-ops-drift.yml",
                    "head_sha": head_sha,
                    "status": "in_progress",
                    "conclusion": None,
                    "event": "pull_request",
                    "pull_requests": [{"number": 407}],
                },
                {
                    "id": 12,
                    "run_number": 4,
                    "run_attempt": 2,
                    "name": "Engineering Ops Drift",
                    "path": ".github/workflows/engineering-ops-drift.yml",
                    "head_sha": head_sha,
                    "status": "completed",
                    "conclusion": "success",
                    "event": "pull_request",
                    "pull_requests": [{"number": 407}],
                },
            ]
        )
        return rows


def test_latest_run_attempt_is_used_for_owner_evidence():
    snapshot = collect(DuplicateRunFake())
    drift = next(
        row
        for row in snapshot["gate_attribution"]["407"]["gates"]
        if row["workflow"] == "Engineering Ops Drift"
    )
    assert drift["run_id"] == 12
    assert drift["run_attempt"] == 2
    assert drift["gate_state"] == "PASS"
    assert drift["trigger_awareness"] == "AUTO_TRIGGER_EXPECTED"
