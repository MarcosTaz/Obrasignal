"""Truth-preserving recovery boundary for partial profile onboarding.

The canonical profile owner persists the company profile before its bounded Radar
recalculation. If a later step fails, the customer must not be told that the
profile itself failed to save when durable account state already changed.

This module is deliberately narrow: it observes successful profile persistence
and wraps only the registered mobile profile view at the production WSGI
boundary. It does not redefine profile validation, matching, decisioning,
ranking or bootstrap semantics.
"""
from __future__ import annotations

from flask import g, has_request_context, jsonify, request

import api as _api

_INSTALLED = False


def install() -> bool:
    global _INSTALLED
    if _INSTALLED:
        return False

    endpoint = "mobile_api.profile"
    original_view = _api.APP.view_functions.get(endpoint)
    if original_view is None:
        # The production entrypoint registers the blueprint before installing
        # this boundary. Tests may register it explicitly first.
        return False
    if getattr(original_view, "_obrasignal_partial_profile_guard", False):
        _INSTALLED = True
        return False

    # Observe the canonical owner's successful return rather than comparing
    # before/after profile values. This remains correct when a retry saves the
    # exact same profile again and Radar bootstrap subsequently fails.
    original_save = _api.save_profile
    if not getattr(original_save, "_obrasignal_persistence_observer", False):
        def observed_save(*args, **kwargs):
            saved = original_save(*args, **kwargs)
            if has_request_context():
                g.obrasignal_profile_persisted = saved
            return saved
        observed_save._obrasignal_persistence_observer = True
        _api.save_profile = observed_save

    def guarded_profile(*args, **kwargs):
        if request.method != "POST":
            return original_view(*args, **kwargs)
        try:
            return original_view(*args, **kwargs)
        except Exception:
            saved = getattr(g, "obrasignal_profile_persisted", None)
            if saved is not None:
                identity = request.obrasignal_identity
                # Successful persistence is proven; Radar readiness is not. Do
                # not expose exception text and do not infer a fresh shortlist.
                return jsonify({
                    "ok": True,
                    "profile_saved": True,
                    "profile": saved,
                    "radar_state": "RECOVERY_REQUIRED",
                    "radar_recalculated": None,
                    "recovery_code": "radar_recalculation_incomplete",
                    "account_id": identity.account_id,
                    "authenticated": identity.authenticated,
                    "generated_at": _api._iso_now(),
                }), 202
            raise

    guarded_profile._obrasignal_partial_profile_guard = True
    _api.APP.view_functions[endpoint] = guarded_profile
    _INSTALLED = True
    return True
