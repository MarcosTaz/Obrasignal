import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRELOAD = ROOT / "preload.py"

# Existing compatibility debt. These are the only direct app monkeypatch seams
# currently required by the production composition shim. Adding another seam is
# an architectural change and must be reviewed rather than silently expanding
# preload's authority.
ALLOWED_APP_MUTATIONS = {"fetch_ted", "fetch_base", "sync_once"}


def _direct_app_mutations() -> set[str]:
    tree = ast.parse(PRELOAD.read_text(encoding="utf-8"))
    mutations = set()
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            if isinstance(node, ast.Assign):
                targets = node.targets
            else:
                targets = [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "_app"
            ):
                mutations.add(target.attr)
    return mutations


def test_preload_direct_app_monkeypatch_surface_is_bounded():
    """New app monkeypatch seams require explicit architecture review."""
    assert _direct_app_mutations() == ALLOWED_APP_MUTATIONS
