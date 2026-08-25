import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"

# Existing legacy schema-composition dependencies in app.init_db. This is a
# baseline, not an endorsement: new domain schema owners must not be added to
# the application module without explicit architecture/persistence review.
ALLOWED_SCHEMA_OWNER_MODULES = {
    "account_registry",
    "company_profile",
    "decision_log",
    "latency_metrics",
    "notification_events",
    "opportunity_workflow",
    "source_health",
}


def _init_db_schema_owner_imports() -> set[str]:
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    init_db = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "init_db"
    )
    return {
        node.module
        for node in ast.walk(init_db)
        if isinstance(node, ast.ImportFrom) and node.module
    }


def test_app_schema_composition_dependency_surface_is_bounded():
    """New domain schema-owner edges from app.py require explicit review."""
    assert _init_db_schema_owner_imports() == ALLOWED_SCHEMA_OWNER_MODULES
