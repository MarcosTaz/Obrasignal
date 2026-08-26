"""Truth-preserving recovery boundary for partial profile onboarding.

The canonical profile owner persists the company profile before its bounded Radar
recalculation. If a later step fails, the customer must not be told that the
profile itself failed to save when durable account state already changed.

This module is deliberately narrow: it wraps only the registered mobile profile
view at the production WSGI boundary. It does not redefine profile validation,
matching, decisioning, ranking or bootstrap semantics.
"""
from __future__ import annotations

from flask import jsonify, request

import api as _api
from company_profile import load_profile

_INSTALLED = False


def install() -> bool:
    global _INSTALLED
    if _INSTALLED:
        return False

    endpoint = "mobile_api.profile"
    original = _api.APP.view_functions.get(endpoint)
    if original is None:
        # The production entrypoint registers the blueprint before installing
        # this boundary. Tests may register it explicitly first.
        return False
    if getattr(original, "_obrasignal_partial_profile_guard", False):
        _INSTALLED = True
        return False

    def guarded_profile(*args, **kwargs):
        if request.method != "POST":
            return original(*args, **kwargs)

        identity = request.obrasignal_identity
        before = load_profile(identity.account_id)
        try:
            return original(*args, **kwargs)
        except Exception:
            # Re-read durable authority after the exception. If account profile
            # truth changed, a generic 5xx would falsely imply that the save did
            # not happen. Do not expose exception text or guess Radar freshness.
            after = load_profile(identity.account_id)
            if after != before:
                return jsonify({
                    "ok": True,
                    "profile_saved": True,
                    "profile": after,
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
