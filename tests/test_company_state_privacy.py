from pathlib import Path

FORBIDDEN_DEFAULT_REQUIREMENTS = {
    "bank account", "payroll", "continuous gps", "email inbox", "browser history",
    "phone monitoring", "employee productivity surveillance",
}


def test_company_state_modules_do_not_require_intrusive_integrations():
    root = Path(__file__).resolve().parents[1]
    text = "\n".join((root / name).read_text(encoding="utf-8").casefold() for name in (
        "company_state.py", "company_state_store.py", "company_state_profile_adapter.py", "company_state_adapters.py"
    ))
    # Names may appear only if explicitly discussed as forbidden; current modules
    # don't need to mention or connect any of them at all.
    for phrase in FORBIDDEN_DEFAULT_REQUIREMENTS:
        assert phrase not in text
    assert "requests." not in text
    assert "urlopen(" not in text
    assert "http://" not in text and "https://" not in text
