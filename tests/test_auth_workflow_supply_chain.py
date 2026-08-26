from pathlib import Path
import re


WORKFLOW = Path('.github/workflows/auth-forged-signature-e2e.yml')
IMMUTABLE_CHECKOUT = re.compile(r"actions/checkout@[0-9a-f]{40}(?:\s+#.*)?$")


def test_auth_forged_signature_checkout_is_immutable_and_does_not_persist_credentials():
    text = WORKFLOW.read_text(encoding='utf-8')
    checkout_lines = [line.strip().removeprefix('- uses: ').strip() for line in text.splitlines() if 'uses: actions/checkout@' in line]

    assert checkout_lines, 'auth forged-signature workflow must declare checkout explicitly'
    assert all(IMMUTABLE_CHECKOUT.fullmatch(line) for line in checkout_lines), checkout_lines

    lines = text.splitlines()
    for index, line in enumerate(lines):
        if 'uses: actions/checkout@' not in line:
            continue
        window = '\n'.join(lines[index:index + 5])
        assert re.search(r"persist-credentials:\s*false", window), window


def test_auth_forged_signature_workflow_keeps_minimum_declared_repository_permission():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert re.search(r"(?m)^permissions:\s*$\n\s+contents:\s*read\s*$", text)
