from vertical_apps.industrial_claims.zero_touch_journey import ZeroTouchJourneyInput, evaluate_zero_touch_journey


def state(**kwargs):
    return evaluate_zero_touch_journey(ZeroTouchJourneyInput(**kwargs))


def qualified_base(**extra):
    data = dict(metadata_qualification="METADATA_QUALIFIED", account_created=True, case_metadata_complete=True)
    data.update(extra)
    return data


def test_zero_touch_requires_triage_then_account():
    assert state().state == "TRIAGE_REQUIRED"
    assert state(metadata_qualification="METADATA_QUALIFIED").state == "ACCOUNT_REQUIRED"


def test_secure_intake_fails_closed_before_evidence_upload():
    result = state(**qualified_base())
    assert result.state == "SECURE_INTAKE_BLOCKED"
    assert result.confidential_upload_allowed is False
    assert result.operator_intervention_required is False


def test_evidence_gaps_are_resolved_by_customer_not_operator():
    result = state(**qualified_base(secure_intake_ready=True, evidence_uploaded=True, evidence_gap_count=2))
    assert result.state == "EVIDENCE_GAPS"
    assert result.operator_intervention_required is False


def test_payment_is_required_and_only_verified_active_state_unlocks_paid_access():
    unpaid = state(**qualified_base(secure_intake_ready=True, evidence_uploaded=True))
    assert unpaid.state == "PAYMENT_REQUIRED"
    assert unpaid.paid_access_granted is False
    pending = state(**qualified_base(secure_intake_ready=True, evidence_uploaded=True, verified_payment_state="PENDING_PAYMENT_CONFIRMATION"))
    assert pending.paid_access_granted is False
    active = state(**qualified_base(secure_intake_ready=True, evidence_uploaded=True, verified_payment_state="ACTIVE"))
    assert active.state == "ANALYSIS_PENDING"
    assert active.paid_access_granted is True


def test_analysis_requires_customer_confirmation_then_dossier():
    base = qualified_base(secure_intake_ready=True, evidence_uploaded=True, verified_payment_state="ACTIVE", automated_analysis_complete=True)
    assert state(**base).state == "CUSTOMER_CONFIRMATION_REQUIRED"
    base["customer_confirmed_facts"] = True
    assert state(**base).state == "DOSSIER_PENDING"
    base["dossier_ready"] = True
    assert state(**base).state == "DOSSIER_READY"
    base["claim_workspace_enabled"] = True
    assert state(**base).state == "CLAIM_WORKSPACE"
    base["portfolio_monitoring_enabled"] = True
    assert state(**base).state == "PORTFOLIO_MONITORING"


def test_normal_customer_path_never_requires_operator_intervention():
    scenarios = [
        ZeroTouchJourneyInput(),
        ZeroTouchJourneyInput(metadata_qualification="METADATA_QUALIFIED"),
        ZeroTouchJourneyInput(**qualified_base()),
        ZeroTouchJourneyInput(**qualified_base(secure_intake_ready=True, evidence_uploaded=True, evidence_gap_count=1)),
    ]
    assert all(not evaluate_zero_touch_journey(x).operator_intervention_required for x in scenarios)
