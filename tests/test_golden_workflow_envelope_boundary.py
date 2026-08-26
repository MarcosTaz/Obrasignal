from pathlib import Path

VALID_STATUSES={"NEW","REVIEWING","PREPARING","SUBMITTED","WON","LOST"}


def classify(payload, expected_account_id):
    if not isinstance(payload, dict):
        return "MALFORMED_FAIL_CLOSED"
    if str(payload.get("account_id")) != str(expected_account_id):
        return "TENANT_BINDING_FAILURE"
    if "workflow" not in payload:
        return "AUTH_CONSUMER_BREAKING"
    workflow=payload.get("workflow")
    if workflow is None:
        return "UNKNOWN_COERCION"
    if not isinstance(workflow, dict):
        return "MALFORMED_FAIL_CLOSED"
    if not workflow:
        return "UNKNOWN_COERCION"
    status=workflow.get("status")
    if status not in VALID_STATUSES:
        return "MALFORMED_FAIL_CLOSED"
    return "COMPATIBLE"


def test_canonical_producer_shape_is_nested_and_tenant_bound():
    source=Path("api.py").read_text(encoding="utf-8")
    assert 'jsonify({"workflow": workflow, "account_id": identity.account_id, "generated_at": _iso_now()})' in source


def test_authenticated_consumer_must_parse_nested_workflow_not_root_metadata():
    workflow=Path(".github/workflows/authenticated-e2e.yml").read_text(encoding="utf-8")
    assert "actual.get('workflow')" in workflow
    assert "restored.get('workflow')" in workflow
    assert "workflow.get('status')" not in workflow
    assert "actual.get('status')" not in workflow
    assert "restored.get('status')" not in workflow


def test_workflow_envelope_adversarial_matrix():
    account="acct-a"
    matrix=[
        ({"workflow":{"status":"REVIEWING","note":"x"},"account_id":account,"generated_at":"t"},"COMPATIBLE"),
        ({"workflow":None,"account_id":account,"generated_at":"t"},"UNKNOWN_COERCION"),
        ({"account_id":account,"generated_at":"t"},"AUTH_CONSUMER_BREAKING"),
        ({"workflow":{},"account_id":account,"generated_at":"t"},"UNKNOWN_COERCION"),
        ({"workflow":"REVIEWING","account_id":account,"generated_at":"t"},"MALFORMED_FAIL_CLOSED"),
        ({"workflow":{"status":"NEW"},"account_id":account,"generated_at":"t","extra":{"x":1}},"COMPATIBLE"),
        ({"workflow":{"status":"NEW"},"account_id":"acct-b","generated_at":"t"},"TENANT_BINDING_FAILURE"),
    ]
    assert [(classify(payload, account), expected) for payload,expected in matrix] == [(expected,expected) for _,expected in matrix]
