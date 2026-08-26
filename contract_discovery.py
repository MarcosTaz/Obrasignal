"""Repository-derived contract discovery outside the enrolled registry.

Discovery is observation-only. A discovered boundary is not compatible merely
because its producer or consumer exists, and nothing in this module defines
business semantics. `contracts/public_contract_registry.json` remains the only
enrolled registry and remains intentionally narrow.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def observe_account_profile(root: Path = Path(".")) -> dict[str, Any]:
    api = _read(root, "api.py")
    mobile_api = _read(root, "mobile/src/api.js")
    mobile_app = _read(root, "mobile/App.js")

    get_envelope = (
        'return jsonify({"profile": current, "account_id": identity.account_id, "authenticated": identity.authenticated, "generated_at": _iso_now()})'
        in api
    )
    post_envelope = (
        'return jsonify({"ok": True, "profile": saved, "radar_recalculated": recalculated, "account_id": identity.account_id, "authenticated": identity.authenticated, "generated_at": _iso_now()})'
        in api
    )
    truthy_dual_shape = "function unwrapProfile(data){return data?.profile||data||null;}" in mobile_api
    consumer_requires_profile_fields = (
        "!profile?.name?.trim()||!profile?.activity?.trim()" in mobile_app
    )

    return {
        "contract": "account_profile.v1",
        "status": "DISCOVERED_UNKNOWN",
        "producer": {
            "get": "profile_envelope" if get_envelope else "UNKNOWN",
            "post": "save_profile_envelope" if post_envelope else "UNKNOWN",
        },
        "consumer": {
            "parser": "truthy_envelope_or_flat" if truthy_dual_shape else "UNKNOWN",
            "required_fields": "name_activity" if consumer_requires_profile_fields else "UNKNOWN",
        },
        "risk": (
            "PROFILE_CONTRACT_REVIEW_REQUIRED"
            if get_envelope and post_envelope and truthy_dual_shape
            else "UNKNOWN"
        ),
    }


def account_profile_mutation_matrix() -> dict[str, str]:
    """Classify the current Mobile truthiness parser under bounded shapes.

    This models JavaScript truthiness only; it deliberately does not assert
    domain behavior for shapes the canonical producer does not currently emit.
    """
    return {
        "normal_envelope": "PROFILE_OBJECT",
        "profile_empty_object": "PROFILE_OBJECT",
        "profile_null": "ENVELOPE_MISINTERPRETED_AS_PROFILE",
        "profile_absent": "ENVELOPE_MISINTERPRETED_AS_PROFILE",
        "legacy_flat_profile": "FLAT_PROFILE_ACCEPTED",
        "future_additive_envelope": "PROFILE_OBJECT",
        "malformed_truthy_profile": "MALFORMED_PROFILE_ACCEPTED_BY_UNWRAP",
    }


def observe_mobile_unknown_coercions(root: Path = Path(".")) -> list[dict[str, str]]:
    app = _read(root, "mobile/App.js")
    findings: list[dict[str, str]] = []

    patterns = [
        (
            "mobile.stats.rejected_to_zero",
            "stats_partial_failure.v1",
            "BREAKING",
            "UNKNOWN_TO_ZERO",
            "const[stats,setStats]=useState({})" in app
            and "statsResult.status==='fulfilled'?(statsResult.value||{}):stats" in app
            and "{v??0}" in app,
        ),
        (
            "mobile.opportunity.missing_source_to_ted",
            "opportunity_card.v1",
            "BREAKING",
            "UNKNOWN_TO_TED",
            "item.source||'TED'" in app,
        ),
        (
            "mobile.opportunity.missing_score_to_zero",
            "opportunity_card.v1",
            "BREAKING",
            "UNKNOWN_TO_ZERO",
            "item.decision_score??item.score??0" in app,
        ),
        (
            "mobile.opportunity.missing_reason_fabricated",
            "opportunity_card.v1",
            "BREAKING",
            "UNKNOWN_TO_POSITIVE_EXPLANATION",
            "item.decision_reason||item.match_reason||'Correspondência com o perfil'" in app,
        ),
        (
            "mobile.workflow.missing_status_to_new",
            "opportunity_workflow.v1",
            "BREAKING",
            "UNKNOWN_TO_NEW",
            "current.workflow?.status||'NEW'" in app,
        ),
    ]

    for finding_id, contract, classification, coercion, present in patterns:
        if present:
            findings.append(
                {
                    "id": finding_id,
                    "contract": contract,
                    "classification": classification,
                    "coercion": coercion,
                    "status": "DISCOVERED_BREAKING",
                }
            )
    return findings
