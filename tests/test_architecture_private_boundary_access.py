import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api.py"

# Existing debt only. Any additional private preload symbol consumed by the API
# is a new architecture violation and must not be silently normalized.
ALLOWED_PRIVATE_PRELOAD_IMPORTS = {"_deadline_dt"}
ALLOWED_PRIVATE_PRELOAD_ATTRIBUTES = {"_app"}


def test_api_private_preload_dependency_surface_does_not_expand():
    tree = ast.parse(API.read_text(encoding="utf-8"))

    private_imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "preload"
        for alias in node.names
        if alias.name.startswith("_")
    }
    private_attributes = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "_preload"
        and node.attr.startswith("_")
    }

    assert private_imports == ALLOWED_PRIVATE_PRELOAD_IMPORTS
    assert private_attributes == ALLOWED_PRIVATE_PRELOAD_ATTRIBUTES
