from __future__ import annotations

from datetime import date

from flask import g, jsonify, request

from .exception_queue import build_exception_queue


def register_exception_queue_routes(app, repository):
    @app.route("/api/capacity/exceptions", methods=["GET"])
    def exception_queue():
        raw_as_of = request.args.get("as_of")
        if not raw_as_of:
            raise ValueError("as_of query parameter is required")
        try:
            as_of = date.fromisoformat(raw_as_of)
        except ValueError as exc:
            raise ValueError("as_of must be YYYY-MM-DD") from exc
        include_no_action = request.args.get("include_no_action", "false")
        if include_no_action not in {"true", "false"}:
            raise ValueError("include_no_action must be true or false")
        items = build_exception_queue(
            repository,
            tenant_id=g.capacity_tenant_id,
            as_of=as_of,
            include_no_action=include_no_action == "true",
        )
        return jsonify(
            {
                "as_of": as_of.isoformat(),
                "items": [
                    {
                        "monitor_id": item.monitor_id,
                        "engagement_id": item.engagement_id,
                        "case_id": item.case_id,
                        "exception_type": item.exception_type.value,
                        "priority": item.priority,
                        "next_check_on": item.next_check_on,
                        "deadline": item.deadline,
                        "days_to_deadline": item.days_to_deadline,
                        "days_to_monitor": item.days_to_monitor,
                        "recoverability_state": item.recoverability_state.value,
                        "net_exposure": format(item.net_exposure, "f"),
                        "claimable_amount": format(item.claimable_amount, "f"),
                        "reasons": list(item.reasons),
                        "missing_evidence": list(item.missing_evidence),
                    }
                    for item in items
                ],
                "count": len(items),
                "truth_rule": "priority is operational triage; UNKNOWN exposure is not a recovery claim",
            }
        )

    return app
