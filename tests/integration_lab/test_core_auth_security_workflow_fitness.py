import re
from pathlib import Path


AUTH_WORKFLOWS = (
    Path('.github/workflows/authenticated-e2e.yml'),
    Path('.github/workflows/auth-forged-signature-e2e.yml'),
)

IMMUTABLE_CHECKOUT = re.compile(r'uses:\s*actions/checkout@[0-9a-f]{40}\b')


def test_authoritative_auth_workflows_close_security_immutable_action_handoff():
    for workflow in AUTH_WORKFLOWS:
        text = workflow.read_text(encoding='utf-8')
        assert 'actions/checkout@v4' not in text, f'{workflow} still uses mutable checkout@v4'
        assert IMMUTABLE_CHECKOUT.search(text), f'{workflow} must pin actions/checkout to an immutable commit SHA'
