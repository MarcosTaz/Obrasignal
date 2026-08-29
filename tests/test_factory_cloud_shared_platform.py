import pytest

from factory_cloud.shared_platform import (
    AuditEvent,
    InMemoryOutbox,
    NotificationEvent,
    SharedPlatformError,
    TenantContext,
    assert_tenant_context,
)


def test_tenant_role_gate_fails_closed():
    context = TenantContext("tenant-a", "actor-1", ("reviewer",))
    context.require_role("reviewer")
    with pytest.raises(SharedPlatformError):
        context.require_role("admin")


def test_audit_payload_hash_is_deterministic():
    context = TenantContext("tenant-a", "actor-1")
    a = AuditEvent.create(event_id="1", context=context, event_type="finding.reviewed", subject_ref="f1", payload={"x": 1})
    b = AuditEvent.create(event_id="2", context=context, event_type="finding.reviewed", subject_ref="f1", payload={"x": 1})
    assert a.payload_hash == b.payload_hash


def test_notification_outbox_is_idempotent():
    event = NotificationEvent.create(event_id="n1", tenant_id="tenant-a", event_type="deadline", subject_ref="d1")
    outbox = InMemoryOutbox()
    assert outbox.add(event) is True
    assert outbox.add(event) is False
    assert outbox.pending("tenant-a") == (event,)


def test_cross_tenant_context_rejected():
    context = TenantContext("tenant-a", "actor-1")
    foreign = NotificationEvent.create(event_id="n1", tenant_id="tenant-b", event_type="deadline", subject_ref="d1")
    with pytest.raises(SharedPlatformError, match="cross-tenant"):
        assert_tenant_context(context, foreign)
