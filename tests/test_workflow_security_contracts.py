import re
from pathlib import Path


WORKFLOW_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"
OWNED_WORKFLOWS = {
    "quality.yml",
    "web-preview.yml",
    "eas-preview.yml",
    "eas-production.yml",
    "mobile-release-preflight.yml",
    "codeql.yml",
    "dependency-review.yml",
}
PINNED_ACTION = re.compile(r"^\s*-?\s*uses:\s*[^\s@]+@[0-9a-f]{40}(?:\s+#.*)?$")


def test_no_workflow_uses_pull_request_target():
    for path in WORKFLOW_DIR.glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        assert "pull_request_target:" not in text, f"privileged untrusted PR trigger in {path.name}"


def test_owned_workflows_declare_permissions_and_pin_actions():
    for name in OWNED_WORKFLOWS:
        path = WORKFLOW_DIR / name
        text = path.read_text(encoding="utf-8")
        assert "permissions:" in text, f"missing explicit token permissions in {name}"
        for line in text.splitlines():
            if "uses:" in line:
                assert PINNED_ACTION.match(line), f"mutable action reference in {name}: {line.strip()}"


def test_checkout_credentials_are_not_persisted_in_owned_workflows():
    for name in OWNED_WORKFLOWS:
        text = (WORKFLOW_DIR / name).read_text(encoding="utf-8")
        if "actions/checkout@" in text:
            assert "persist-credentials: false" in text, f"checkout credentials persist in {name}"


def test_codeql_pr_analysis_is_limited_to_trusted_same_repo_heads():
    text = (WORKFLOW_DIR / "codeql.yml").read_text(encoding="utf-8")
    assert "pull_request:" in text
    assert "security-events: write" in text
    assert "github.event.pull_request.head.repo.full_name == github.repository" in text


def test_dependency_review_is_read_only_and_non_commenting():
    text = (WORKFLOW_DIR / "dependency-review.yml").read_text(encoding="utf-8")
    assert "contents: read" in text
    assert "pull-requests: write" not in text
    assert "comment-summary-in-pr: never" in text
    assert "fail-on-severity: high" in text
