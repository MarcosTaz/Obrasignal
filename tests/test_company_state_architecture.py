import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNED = (
    "company_state.py",
    "company_state_store.py",
    "company_state_profile_adapter.py",
    "company_state_adapters.py",
)
FORBIDDEN_IMPORT_ROOTS = {
    "opportunity_readiness", "readiness_api", "opportunity_requirements",
    "bid_economics", "mobilize", "bangs", "bang_commands", "economic_fit",
}


def test_company_state_has_no_private_downstream_imports():
    imports = set()
    for name in OWNED:
        tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
    assert not (imports & FORBIDDEN_IMPORT_ROOTS)


def test_domain_contract_has_no_hidden_wall_clock_or_network_or_sql():
    text = (ROOT / "company_state.py").read_text(encoding="utf-8")
    assert "datetime.now(" not in text
    assert "sqlite3" not in text
    assert "requests" not in text
    assert "urlopen" not in text


def test_company_state_does_not_create_decision_vocabulary():
    text = "\n".join((ROOT / name).read_text(encoding="utf-8") for name in OWNED)
    for token in ("PURSUE", "NO_BID", "NOT_READY", "BID_SUBMITTED"):
        assert token not in text
