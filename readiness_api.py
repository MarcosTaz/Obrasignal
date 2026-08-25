"""Authenticated HTTP adapter for Opportunity Readiness v0.

This module owns no readiness policy. It adapts canonical opportunity/lifecycle,
tenant-scoped company-profile, canonical Signal context and optional Opportunity
Requirements inputs to ``evaluate_readiness``.
"""
from __future__ import annotations

import json

from flask import jsonify
from jwt import InvalidTokenError

from auth_context import configured_identity
from company_profile import load_profile
from opportunity_lifecycle import ensure_lifecycle_table
from opportunity_readiness import evaluate_readiness
from readiness_requirements_adapter import STRUCTURED_REQUIREMENT_FIELDS, resolve_requirements
from signal_store import get_signal_record

_SIGNAL_CONTEXT_FIELDS = STRUCTURED_REQUIREMENT_FIELDS + ("currency", "jurisdiction")


def _enrich_with_signal_context(opportunity, signal_record):
    """Copy only approved rich-context fields from the canonical Signal envelope.

    Identity, lifecycle and deadline remain owned by the current tender/lifecycle
    read model. Malformed or unavailable normalized snapshots simply contribute no
    optional context.
    """
    if not signal_record:
        return opportunity
    raw = signal_record.get("normalized_json")
    try:
        normalized = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError):
        return opportunity
    if not isinstance(normalized, dict):
        return opportunity
    enriched = dict(opportunity)
    for field in _SIGNAL_CONTEXT_FIELDS:
        if field in normalized:
            enriched[field] = normalized.get(field)
    if not enriched.get("currency") and signal_record.get("currency"):
        enriched["currency"] = signal_record.get("currency")
    if not enriched.get("source_updated_at") and signal_record.get("source_updated_at"):
        enriched["source_updated_at"] = signal_record.get("source_updated_at")
    return enriched


def install_readiness_api(
    APP,
    db_factory,
    *,
    identity_provider=None,
    profile_loader=None,
    requirements_resolver=None,
    signal_loader=None,
):
    """Install the tenant-scoped readiness endpoint exactly once.

    Account identity is always derived from the trusted authentication provider;
    there is deliberately no client supplied ``account_id`` parameter. Optional
    profile/signal/requirements failures degrade to UNKNOWN rather than failing
    the entire opportunity detail surface.
    """
    route = "/api/v1/opportunities/<int:opportunity_id>/readiness"
    if any(rule.rule == route for rule in APP.url_map.iter_rules()):
        return

    identity_provider = identity_provider or configured_identity
    profile_loader = profile_loader or load_profile
    requirements_resolver = requirements_resolver or resolve_requirements
    signal_loader = signal_loader or get_signal_record

    def opportunity_readiness(opportunity_id):
        try:
            identity = identity_provider()
        except (RuntimeError, InvalidTokenError):
            return jsonify({"error": "authentication_required"}), 401
        account_id = str(getattr(identity, "account_id", "") or "").strip()
        if not account_id:
            return jsonify({"error": "authentication_required"}), 401

        conn = db_factory()
        try:
            ensure_lifecycle_table(conn)
            row = conn.execute(
                """SELECT t.*, COALESCE(lc.is_actionable,1) AS is_actionable,
                          lc.lifecycle_status, lc.lifecycle_reason,
                          lc.source_updated_at AS lifecycle_source_updated_at,
                          lc.last_observed AS lifecycle_last_observed
                   FROM tenders t
                   LEFT JOIN opportunity_lifecycle lc
                     ON lc.source=t.source AND lc.external_id=t.external_id
                   WHERE t.id=?""",
                (opportunity_id,),
            ).fetchone()
            if row is None:
                return jsonify({"error": "not_found"}), 404
            opportunity = dict(row)
            try:
                signal_record = signal_loader(
                    conn,
                    opportunity.get("source"),
                    opportunity.get("external_id"),
                    "TENDER",
                )
            except Exception:
                signal_record = None
            opportunity = _enrich_with_signal_context(opportunity, signal_record)
        finally:
            conn.close()

        try:
            company_state = profile_loader(account_id) or {"account_id": account_id}
        except Exception:
            company_state = {"account_id": account_id}

        try:
            requirements = requirements_resolver(account_id, opportunity, company_state)
        except Exception:
            requirements = None

        assessment = evaluate_readiness(
            account_id,
            opportunity,
            company_state,
            requirements=requirements,
        )
        return jsonify(assessment)

    APP.add_url_rule(
        route,
        endpoint="opportunity_readiness_v0",
        view_func=opportunity_readiness,
        methods=["GET"],
    )
