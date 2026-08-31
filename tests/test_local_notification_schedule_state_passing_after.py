from pathlib import Path


def test_local_sync_uses_tenant_scheduled_dedupe_without_marking_delivered():
    source = Path("mobile/src/notifications.js").read_text(encoding="utf-8")
    start = source.index("export async function syncUnreadOpportunityAlerts")
    end = source.index("export async function notificationOpportunityTarget", start)
    sync = source[start:end]

    assert "getLocalNotificationScheduled" in sync
    assert "rememberLocalScheduledEvent" in sync
    assert "markAlertDelivered" not in sync
    assert "return { status: 'ready', scheduled }" in sync


def test_user_response_is_the_completion_authority_and_failed_ack_keeps_dedupe():
    source = Path("mobile/src/notifications.js").read_text(encoding="utf-8")
    start = source.index("export async function notificationOpportunityTarget")
    end = source.index("export function listenForOpportunityNotificationResponses", start)
    target = source[start:end]

    assert "await api.markAlertDelivered(eventId)" in target
    assert "await forgetLocalScheduledEvent(eventId)" in target
    assert target.index("await api.markAlertDelivered(eventId)") < target.index("await forgetLocalScheduledEvent(eventId)")


def test_scheduled_dedupe_is_tenant_private_and_purged_with_tenant_state():
    tenant_storage = Path("mobile/src/tenantStorage.js").read_text(encoding="utf-8")
    storage = Path("mobile/src/storage.js").read_text(encoding="utf-8")

    assert "'local-notification-scheduled'" in tenant_storage
    assert "PRIVATE_KINDS.map" in tenant_storage
    assert "getLocalNotificationScheduled" in tenant_storage
    assert "setLocalNotificationScheduled" in tenant_storage
    assert "getLocalNotificationScheduled" in storage
    assert "setLocalNotificationScheduled" in storage
