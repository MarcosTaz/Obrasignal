"""Authenticated HTTP adapter for Opportunity Readiness integration.

This module owns no readiness policy. It reads canonical opportunity/lifecycle,
tenant-private Company State, optional normalized Signal context, and legacy
Company Profile only for the separately owned Economic Fit calculation.

The route is intentionally not registered by this integration branch.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json

from flask import jsonify
from jwt import InvalidTokenError

from auth_context import configured_identity
from company_profile import load_profile
from company_state import CompanyState, TenantBoundaryError as CompanyTenantBoundaryError
from company_state_adapters import readiness_inputs
from company_state_store import CompanyStateService
from opportunity_lifecycle import ensure_lifecycle_table
from opportunity_readiness import evaluate_readiness
from readiness_requirements_adapter import STRUCTURED_REQUIREMENT_FIELDS, resolve_requirements
from signal_store import get_signal_record

_SIGNAL_CONTEXT_FIELDS = STRUCTURED_REQUIREMENT_FIELDS + (
    "currency", "jurisdiction", "deadline_precision", "deadline_timezone",
)


def _enrich_with_signal_context(opportunity, signal_record):
    """Copy approved rich context without overriding canonical identity/lifecycle/deadline."""
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


def _company_readiness_envelope(account_id: str, state: CompanyState | None) -> dict:
    if state is None:
        return {
            "contract_version": "company-state.v1",
            "account_id": account_id,
            "status": "UNAVAILABLE",
            "company_state_fingerprint": None,
            "unknowns": ["company_state"],
            "conflicts": [],
            "facts": [],
        }
    if state.account_id != account_id:
        raise CompanyTenantBoundaryError("company state belongs to a different account")
    envelope = readiness_inputs(state)
    envelope["status"] = "AVAILABLE"
    return envelope


def _economic_fit(account_id: str, opportunity: dict, profile_loader, *, now: datetime) -> dict | None:
    """Keep legacy profile-shaped economics separate from canonical Company State."""
    try:
        profile = profile_loader(account_id)
        if not profile:
            return None
        profile_account = str(profile.get("account_id") or account_id).strip()
        if profile_account != account_id:
            return None
        from economic_fit import evaluate_economic_fit
        return evaluate_economic_fit(opportunity.get("value"), profile, opportunity, today=now.date())
    except Exception:
        return None


def install_readiness_api(
    APP,
    db_factory,
    *,
    identity_provider=None,
    company_state_loader=None,
    profile_loader=None,
    requirements_resolver=None,
    signal_loader=None,
    clock=None,
):
    """Install the tenant-scoped read-only endpoint exactly once.

    Tenant identity comes only from trusted authentication. Company State storage
    failure degrades to explicit UNAVAILABLE/UNKNOWN. A mismatched Company State
    fails closed with no company facts in the response.
    """
    route = "/api/v1/opportunities/<int:opportunity_id>/readiness"
    if any(rule.rule == route for rule in APP.url_map.iter_rules()):
        return

    identity_provider = identity_provider or configured_identity
    profile_loader = profile_loader or load_profile
    requirements_resolver = requirements_resolver or resolve_requirements
    signal_loader = signal_loader or get_signal_record
    if company_state_loader is None:
        company_service = CompanyStateService(db_factory)
        company_state_loader = company_service.get

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
            state = company_state_loader(account_id)
            company_envelope = _company_readiness_envelope(account_id, state)
        except CompanyTenantBoundaryError:
            return jsonify({"error": "readiness_unavailable"}), 503
        except Exception:
            state = None
            company_envelope = _company_readiness_envelope(account_id, None)

        try:
            requirements = requirements_resolver(account_id, opportunity, state)
        except CompanyTenantBoundaryError:
            return jsonify({"error": "readiness_unavailable"}), 503
        except Exception:
            requirements = None

        now = clock() if callable(clock) else clock
        if now is None:
            now = datetime.now(timezone.utc)
        if now.tzinfo is None:
            return jsonify({"error": "readiness_unavailable"}), 503

        economic_result = _economic_fit(account_id, opportunity, profile_loader, now=now)
        assessment = evaluate_readiness(
            account_id,
            opportunity,
            company_envelope,
            requirements=requirements,
            economic_fit_result=economic_result,
            clock=now,
        )
        return jsonify(assessment)

    APP.add_url_rule(
        route,
        endpoint="opportunity_readiness_v1_integration",
        view_func=opportunity_readiness,
        methods=["GET"],
    )
