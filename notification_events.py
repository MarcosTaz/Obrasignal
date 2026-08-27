"""Integration overlay for Notification owner semantics.

The exact #607 Notification module is preserved byte-for-byte as
``notification_events_base.py``. This wrapper installs only the provider-ticket
parentage fail-closed guard, then aliases the implementation module so existing
imports/monkeypatches continue to operate on one module object.

DRAFT / INTEGRATION EVIDENCE ONLY / NOT OWNER OR CANONICAL ARCHITECTURE.
"""
import sys as _sys

import notification_events_base as _impl
from provider_ticket_parentage_guard import install as _install_provider_ticket_parentage_guard

_install_provider_ticket_parentage_guard(_impl)
_sys.modules[__name__] = _impl
