from __future__ import annotations

from dataclasses import dataclass

from .adapters import GitHubAdapter, HealthAdapter
from .models import ActionLevel, TruthState
from .registry import append_audit, get_company, mutate_company
from .sources import company_api_view


@dataclass(frozen=True)
class ActionDefinition:
    id: str
    label: str
    level: ActionLevel
    description: str


ACTIONS = {
    "refresh_diagnostics": ActionDefinition("refresh_diagnostics", "Refresh diagnostics", ActionLevel.GREEN, "Refresh read-only repository/application diagnostic sources."),
    "update_factory_state": ActionDefinition("update_factory_state", "Update ACTIVE / NEXT / WAIT", ActionLevel.GREEN, "Update internal control-plane state only."),
    "prepare_deployment": ActionDefinition("prepare_deployment", "Deployment approval gate", ActionLevel.YELLOW, "Record that deployment requires founder approval; this control does not create or execute a deployment."),
    "send_outreach": ActionDefinition("send_outreach", "Customer outreach approval gate", ActionLevel.YELLOW, "Record that external communication requires founder approval; this control does not send outreach."),
    "delete_customer_data": ActionDefinition("delete_customer_data", "Delete customer data", ActionLevel.RED, "Owner-only destructive action; never executed here."),
}


class NoStateChange(ValueError):
    pass


def list_actions() -> list[dict]:
    return [{"id": x.id, "label": x.label, "level": x.level.value, "description": x.description} for x in ACTIONS.values()]


def _audit_payload_shape(payload: dict) -> dict:
    """Audit action intent without persisting arbitrary potentially-sensitive values."""
    return {"payload_keys": sorted(str(key)[:120] for key in payload.keys())[:50]}


def execute(action_id: str, company_id: str, payload: dict | None = None) -> tuple[dict, int]:
    payload = payload or {}
    action = ACTIONS.get(action_id)
    if not action:
        return {"ok": False, "error": "unknown_action"}, 404
    company = get_company(company_id)
    if not company:
        return {"ok": False, "error": "unknown_company"}, 404
    if action.level == ActionLevel.RED:
        append_audit(actor="founder_control_center", action=action_id, level="RED", company_id=company_id, result="blocked_owner_only", source_data=_audit_payload_shape(payload))
        return {"ok": False, "state": "OWNER_ONLY", "message": "This action can never be executed autonomously."}, 403
    if action.level == ActionLevel.YELLOW:
        append_audit(actor="founder_control_center", action=action_id, level="YELLOW", company_id=company_id, result="approval_required_no_execution", source_data=_audit_payload_shape(payload))
        return {
            "ok": False,
            "state": "APPROVAL_REQUIRED",
            "prepared": False,
            "executed": False,
            "message": "Approval is required. No external action or preparation artifact was executed by this request.",
        }, 202
    if action_id == "update_factory_state":
        candidates: dict[str, str] = {}
        for field in ("active", "next", "wait"):
            if field not in payload:
                continue
            value = payload[field]
            if not isinstance(value, str) or not value.strip():
                append_audit(
                    actor="founder_control_center",
                    action=action_id,
                    level="GREEN",
                    company_id=company_id,
                    result="rejected_invalid_state_field",
                    source_data={"invalid_field": field, **_audit_payload_shape(payload)},
                    failure_state=f"{field} must be a non-empty string",
                )
                return {"ok": False, "error": "invalid_state_field", "field": field}, 400
            normalized = value.strip()
            if len(normalized) > 500:
                append_audit(
                    actor="founder_control_center",
                    action=action_id,
                    level="GREEN",
                    company_id=company_id,
                    result="rejected_oversized_state_field",
                    source_data={"invalid_field": field, **_audit_payload_shape(payload)},
                    failure_state=f"{field} must be at most 500 characters",
                )
                return {"ok": False, "error": "state_field_too_long", "field": field, "max_length": 500}, 400
            candidates[field] = normalized

        if not candidates:
            append_audit(
                actor="founder_control_center",
                action=action_id,
                level="GREEN",
                company_id=company_id,
                result="rejected_state_fields_required",
                source_data=_audit_payload_shape(payload),
                failure_state="active, next or wait is required",
            )
            return {"ok": False, "error": "state_fields_required"}, 400

        def apply(latest):
            changed_fields = [field for field, value in candidates.items() if getattr(latest, field) != value]
            if not changed_fields:
                raise NoStateChange("submitted state matches current state")
            for field in changed_fields:
                setattr(latest, field, candidates[field])
            return changed_fields

        try:
            updated, changed_fields = mutate_company(company_id, apply)
        except NoStateChange:
            append_audit(
                actor="founder_control_center",
                action=action_id,
                level="GREEN",
                company_id=company_id,
                result="rejected_no_state_change",
                source_data={"candidate_fields": sorted(candidates), **_audit_payload_shape(payload)},
                failure_state="submitted state matches current state",
            )
            return {"ok": False, "error": "no_state_change"}, 409
        append_audit(
            actor="founder_control_center",
            action=action_id,
            level="GREEN",
            company_id=company_id,
            result="state_updated",
            source_data={"changed_fields": changed_fields, **_audit_payload_shape(payload)},
        )
        return {"ok": True, "state": "UPDATED", "changed_fields": changed_fields, "company": company_api_view(updated)}, 200
    if action_id == "refresh_diagnostics":
        changes = []
        repository_state = None
        deployment_state = None
        deployment_evidence = None
        environment_url = None
        health_state = None
        health_evidence = None

        if company.repository.full_name:
            github = GitHubAdapter()
            repository_state = github.refresh_repo(company.repository.full_name)
            changes.append("repository")
            deployment_state, deployment_evidence, environment_url = github.refresh_deployment(company.repository.full_name)
            changes.append("deployment")

        health_url = company.application.url or environment_url
        if health_url:
            health_state, health_evidence = HealthAdapter().refresh(health_url.rstrip("/") + "/health")
            changes.append("application_health")

        def apply(latest):
            if repository_state is not None:
                latest.repository = repository_state
            if deployment_state is not None:
                latest.application.deployment = deployment_state
                latest.application.deployment_evidence = deployment_evidence
            if environment_url and not latest.application.url:
                latest.application.url = environment_url
            if health_state is not None:
                latest.application.health = health_state
                latest.application.health_evidence = health_evidence
            if not changes:
                latest.data_freshness = TruthState.UNKNOWN
            return changes

        updated, _ = mutate_company(company_id, apply)
        append_audit(actor="founder_control_center", action=action_id, level="GREEN", company_id=company_id, result="diagnostics_refreshed", source_data={"changes": changes})
        return {"ok": True, "changes": changes, "company": company_api_view(updated)}, 200
    return {"ok": False, "error": "not_implemented"}, 501
