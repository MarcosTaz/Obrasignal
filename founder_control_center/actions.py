from __future__ import annotations

from dataclasses import dataclass

from .adapters import GitHubAdapter, HealthAdapter
from .models import ActionLevel, TruthState
from .registry import append_audit, get_company, save_company


@dataclass(frozen=True)
class ActionDefinition:
    id: str
    label: str
    level: ActionLevel
    description: str


ACTIONS = {
    "refresh_diagnostics": ActionDefinition("refresh_diagnostics", "Refresh diagnostics", ActionLevel.GREEN, "Refresh read-only repository/application diagnostic sources."),
    "update_factory_state": ActionDefinition("update_factory_state", "Update ACTIVE / NEXT / WAIT", ActionLevel.GREEN, "Update internal control-plane state only."),
    "prepare_deployment": ActionDefinition("prepare_deployment", "Prepare deployment", ActionLevel.YELLOW, "Prepare a deployment plan but do not deploy to production."),
    "send_outreach": ActionDefinition("send_outreach", "Send customer outreach", ActionLevel.YELLOW, "External communication requires founder approval."),
    "delete_customer_data": ActionDefinition("delete_customer_data", "Delete customer data", ActionLevel.RED, "Owner-only destructive action; never executed here."),
}


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
        append_audit(actor="founder_control_center", action=action_id, level="YELLOW", company_id=company_id, result="approval_required", source_data=_audit_payload_shape(payload))
        return {"ok": False, "state": "APPROVAL_REQUIRED", "prepared": True}, 202
    if action_id == "update_factory_state":
        for field in ("active", "next", "wait"):
            if field in payload and isinstance(payload[field], str) and payload[field].strip():
                setattr(company, field, payload[field].strip()[:500])
        save_company(company)
        append_audit(actor="founder_control_center", action=action_id, level="GREEN", company_id=company_id, result="state_updated", source_data={k: payload.get(k) for k in ("active", "next", "wait")})
        return {"ok": True, "state": "UPDATED", "company": company.to_dict()}, 200
    if action_id == "refresh_diagnostics":
        changes = []
        if company.repository.full_name:
            github = GitHubAdapter()
            company.repository = github.refresh_repo(company.repository.full_name)
            changes.append("repository")
            deployment, deployment_evidence, environment_url = github.refresh_deployment(company.repository.full_name)
            company.application.deployment = deployment
            company.application.deployment_evidence = deployment_evidence
            if environment_url and not company.application.url:
                company.application.url = environment_url
            changes.append("deployment")
        if company.application.url:
            health, health_evidence = HealthAdapter().refresh(company.application.url.rstrip("/") + "/health")
            company.application.health = health
            company.application.health_evidence = health_evidence
            changes.append("application_health")
        if not changes:
            company.data_freshness = TruthState.UNKNOWN
        save_company(company)
        append_audit(actor="founder_control_center", action=action_id, level="GREEN", company_id=company_id, result="diagnostics_refreshed", source_data={"changes": changes})
        return {"ok": True, "changes": changes, "company": company.to_dict()}, 200
    return {"ok": False, "error": "not_implemented"}, 501
