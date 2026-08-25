from pathlib import Path
import re


def test_local_schedule_acceptance_is_not_persisted_as_delivery_completion():
    """Failing-before: scheduling acceptance cannot authorize DELIVERED state.

    Expo scheduleNotificationAsync resolves with a scheduled-notification
    identifier.  It does not prove presentation/delivery.  The current owner
    path immediately persists delivered_at after that scheduling call resolves.
    """
    source = Path("mobile/src/notifications.js").read_text(encoding="utf-8")
    schedule_then_delivered = re.compile(
        r"await\s+showLocalOpportunityAlert\(item\);"
        r"[\s\S]{0,240}?"
        r"await\s+api\.markAlertDelivered\(item\.event_id\)"
    )
    assert not schedule_then_delivered.search(source), (
        "FALSE_COMPLETION: local notification scheduling acceptance is persisted "
        "as delivered_at before presentation/delivery authority exists"
    )
