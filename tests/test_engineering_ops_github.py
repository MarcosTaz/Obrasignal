from engineering_ops_github import collect


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

    def workflow_runs(self, head_sha):
        return [
            {
                "id": 10,
                "run_number": 2,
                "name": "ObraSignal Quality",
                "head_sha": head_sha,
                "status": "completed",
                "conclusion": "success",
                "event": "pull_request",
            }
        ]


def test_collect_is_read_only_snapshot_and_resolves_dependency_heads():
    snapshot = collect(FakeGitHub())
    assert snapshot["main_sha"] == MAIN
    assert snapshot["dependency_heads"]["238"] == ACTUAL_238
    assert len(snapshot["pull_requests"]) == 2
    assert snapshot["workflow_runs"]["319"][0]["head_sha"] == HEAD_319
    assert snapshot["collection_errors"] == {}
