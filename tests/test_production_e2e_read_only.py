"""Regression gate: production authenticated E2E must never write customer workflows.

This check is intentionally dependency-free and runs in the repository Python
quality job. Persistence writes belong in isolated staging/fixture tests.
"""
from pathlib import Path
import re

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/authenticated-e2e.yml"


def test_production_auth_e2e_is_read_only():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "Verify authenticated production contract" in source
    assert '"$API_URL/opportunities/$ID/workflow"' in source
    assert '"$API_URL/opportunities/$ID"' in source
    assert not re.search(r"(?m)^\s*curl\b[^\n]*\s-X\s+(?:POST|PUT|PATCH|DELETE)\b[^\n]*\$API_URL", source)
    assert not re.search(r"(?m)^\s*trap\s+cleanup\s+EXIT", source)
    assert "/tmp/workflow-write.json" not in source
    assert "/tmp/workflow-restore.json" not in source


def test_authenticated_e2e_requires_exact_deployed_revision():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "TARGET_BUILD" in source
    assert "health.get('build') == os.environ['TARGET_BUILD']" in source
