from pathlib import Path
import re


def test_local_schedule_acceptance_is_not_persisted_as_delivery_completion_current_mobile():
    """Current-mobile revalidation: scheduling acceptance cannot authorize DELIVERED state."""
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
