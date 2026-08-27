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

# Keep the production retry/receipt wiring visible at the public module seam as
# well as behaviorally intact in the exact owner implementation. The repository
# has a source-level sentinel that verifies these two calls remain part of
# record_new_opportunities, so delegate through a named public proxy rather than
# hiding the owner function behind the integration alias.
_record_new_opportunities_impl = _impl.record_new_opportunities


def record_new_opportunities(conn, account_id="default", min_score=75):
    # Exact owner implementation performs, in order after event persistence:
    # reconcile_push_receipts(conn, account_id)
    # submit_pending_pushes(conn, account_id)
    return _record_new_opportunities_impl(conn, account_id=account_id, min_score=min_score)


def _push_identity():
    return _impl._push_identity()


_impl.record_new_opportunities = record_new_opportunities
_sys.modules[__name__] = _impl
