from __future__ import annotations

from vertical_apps.industrial_claims.outbound_preflight import (
    PreflightChecks,
    SenderIdentity,
    evaluate_outbound_preflight,
)


def _record(**overrides):
    data = {
        "account_id": "hfa-electronics-pt",
        "status": "PREPARED_NOT_SENDABLE",
        "role_recheck_required": False,
        "route_recheck_required": False,
    }
    data.update(overrides)
    return data


def _route(**overrides):
    data = {
        "account_id": "hfa-electronics-pt",
        "outbound_authorized": False,
    }
    data.update(overrides)
    return data


def _sender(**overrides):
    values = {
        "product": "Supplier Recovery",
        "from_address": "Marcos <marcos@supplierrecovery.co>",
        "dedicated_to_product": True,
        "reply_capable": True,
        "outbound_auth_verified": True,
        "suppression_ready": True,
    }
    values.update(overrides)
    return SenderIdentity(**values)


def test_missing_sender_fails_closed():
    decision = evaluate_outbound_preflight(
        record=_record(), route=_route(), sender=None, checks=PreflightChecks()
    )
    assert decision.ready_to_send is False
    assert decision.next_state == "PREPARED_NOT_SENDABLE"
    assert "dedicated_sender_missing" in decision.blockers


def test_other_project_or_generic_primitive_sender_is_rejected():
    for address in (
        "marcos@certactum.com",
        "marcos@obrasignal.com",
        "agent@rapid-ox.primitive.email",
    ):
        decision = evaluate_outbound_preflight(
            record=_record(),
            route=_route(),
            sender=_sender(from_address=address),
            checks=PreflightChecks(),
        )
        assert decision.ready_to_send is False
        assert "cross_project_or_generic_sender_forbidden" in decision.blockers


def test_medium_route_recheck_is_mandatory():
    decision = evaluate_outbound_preflight(
        record=_record(route_recheck_required=True),
        route=_route(),
        sender=_sender(),
        checks=PreflightChecks(founder_authorized=True, route_recheck_passed=False),
    )
    assert decision.ready_to_send is False
    assert "route_recheck_required" in decision.blockers


def test_role_recheck_is_mandatory_for_mold_tech_like_record():
    decision = evaluate_outbound_preflight(
        record=_record(role_recheck_required=True),
        route=_route(),
        sender=_sender(),
        checks=PreflightChecks(founder_authorized=True, role_recheck_passed=False),
    )
    assert decision.ready_to_send is False
    assert "role_recheck_required" in decision.blockers


def test_confidential_document_request_blocks_first_contact():
    decision = evaluate_outbound_preflight(
        record=_record(),
        route=_route(),
        sender=_sender(),
        checks=PreflightChecks(
            founder_authorized=True,
            confidential_documents_requested=True,
        ),
    )
    assert decision.ready_to_send is False
    assert "confidential_documents_not_allowed_in_first_contact" in decision.blockers


def test_complete_technical_preflight_still_waits_for_founder_authorization():
    decision = evaluate_outbound_preflight(
        record=_record(),
        route=_route(),
        sender=_sender(),
        checks=PreflightChecks(founder_authorized=False),
    )
    assert decision.ready_to_send is False
    assert decision.next_state == "READY_FOR_FOUNDER_AUTHORIZATION"
    assert decision.blockers == ("founder_send_authorization_required",)


def test_full_preflight_can_only_reach_authorized_not_sent():
    decision = evaluate_outbound_preflight(
        record=_record(),
        route=_route(),
        sender=_sender(),
        checks=PreflightChecks(founder_authorized=True),
    )
    assert decision.ready_to_send is True
    assert decision.next_state == "AUTHORIZED_NOT_SENT"
    assert decision.blockers == ()
