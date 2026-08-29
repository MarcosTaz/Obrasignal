from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _analyze(service, *, tenant_id, event_ref, customer_ref="oem", program_ref="program", basis_ref="basis"):
    return service.analyze(
        tenant_id=tenant_id,
        actor_id="analyst",
        customer_ref=customer_ref,
        program_ref=program_ref,
        event_ref=event_ref,
        claim_family="TOOLING",
        commercial_basis_ref=basis_ref,
        cost_evidence_ref=f"cost-{event_ref}",
        gross_cost="10000",
        currency="EUR",
        commercial_basis_content="signed tooling agreement",
        event_evidence_content="documented cancellation event",
        cost_evidence_content="cost ledger supporting tooling exposure",
        notice_deadline_not_applicable=True,
    )


def _action(service, result):
    service.review(
        tenant_id=result.tenant_id,
        finding_id=result.finding.finding_id,
        reviewer="reviewer",
        approved=True,
        reason="reviewed",
    )
    service.action(
        tenant_id=result.tenant_id,
        finding_id=result.finding.finding_id,
        actor_id="operator",
    )


def test_structured_contract_reference_prevents_delimiter_collision(tmp_path):
    first_service = IndustrialClaimsService(tmp_path / "first.sqlite3")
    second_service = IndustrialClaimsService(tmp_path / "second.sqlite3")

    first = _analyze(
        first_service,
        tenant_id="alpha",
        event_ref="same-event",
        customer_ref="a:b",
        program_ref="c",
        basis_ref="d",
    )
    second = _analyze(
        second_service,
        tenant_id="alpha",
        event_ref="same-event",
        customer_ref="a",
        program_ref="b:c",
        basis_ref="d",
    )

    assert first.fingerprint.contract_ref != second.fingerprint.contract_ref
    assert first.fingerprint.fingerprint != second.fingerprint.fingerprint


def test_same_external_outcome_id_is_isolated_across_tenants(tmp_path):
    service = IndustrialClaimsService(tmp_path / "outcome-tenants.sqlite3")
    alpha = _analyze(service, tenant_id="alpha", event_ref="event-alpha")
    beta = _analyze(service, tenant_id="beta", event_ref="event-beta")
    _action(service, alpha)
    _action(service, beta)

    alpha_outcome = service.resolve(
        tenant_id="alpha",
        finding_id=alpha.finding.finding_id,
        outcome_id="settlement-1",
        recovered_amount="5000",
        currency="EUR",
        evidence_ref="bank-alpha",
        evidence_content="alpha settlement evidence",
        actor_id="operator",
    )
    beta_outcome = service.resolve(
        tenant_id="beta",
        finding_id=beta.finding.finding_id,
        outcome_id="settlement-1",
        recovered_amount="4000",
        currency="EUR",
        evidence_ref="bank-beta",
        evidence_content="beta settlement evidence",
        actor_id="operator",
    )

    assert alpha_outcome.outcome_id == "alpha:settlement-1"
    assert beta_outcome.outcome_id == "beta:settlement-1"
    assert alpha_outcome.outcome_id != beta_outcome.outcome_id
    assert len(service.ops.outcomes(tenant_id="alpha")) == 1
    assert len(service.ops.outcomes(tenant_id="beta")) == 1
