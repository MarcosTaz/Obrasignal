from __future__ import annotations

import pytest

from vertical_apps.industrial_claims.identity_release_gate import (
    IdentityReleaseGateError,
    MailIdentityEvidence,
    evaluate_identity_release,
)


def _evidence(**overrides):
    values = {
        "domain": "causledger.com",
        "mailbox": "marcos@causledger.com",
        "domain_owned": True,
        "mailbox_verified": True,
        "mx_records": ("10 mx.example-mail.test.",),
        "apex_txt_records": ("v=spf1 include:_spf.example-mail.test -all",),
        "dmarc_txt_records": ("v=DMARC1; p=none; rua=mailto:dmarc@causledger.com",),
        "dkim_records_by_selector": {"selector1": ("v=DKIM1; k=rsa; p=abc123",)},
    }
    values.update(overrides)
    return MailIdentityEvidence(**values)


def test_identity_release_requires_owned_domain_verified_mailbox_and_dns_authentication():
    decision = evaluate_identity_release(_evidence())
    assert decision.blockers == ()
    assert decision.mx_present is True
    assert decision.spf_valid is True
    assert decision.dkim_valid is True
    assert decision.dmarc_valid is True
    assert decision.dmarc_policy == "none"
    assert decision.dmarc_enforced is False
    assert decision.ready_for_brand_outbound is True
    assert decision.ready_for_public_contact_cta is True


@pytest.mark.parametrize(
    "override,blocker",
    [
        ({"domain_owned": False}, "DOMAIN_OWNERSHIP_UNVERIFIED"),
        ({"mailbox_verified": False}, "MAILBOX_UNVERIFIED"),
        ({"mx_records": ()}, "MX_MISSING"),
        ({"apex_txt_records": ()}, "SPF_MISSING"),
        ({"apex_txt_records": ("v=spf1 -all", "v=spf1 include:x -all")}, "SPF_MULTIPLE"),
        ({"dkim_records_by_selector": {}}, "DKIM_MISSING"),
        ({"dmarc_txt_records": ()}, "DMARC_MISSING"),
        ({"dmarc_txt_records": ("v=DMARC1; p=invalid",)}, "DMARC_POLICY_INVALID"),
    ],
)
def test_identity_release_blocks_each_missing_or_ambiguous_prerequisite(override, blocker):
    decision = evaluate_identity_release(_evidence(**override))
    assert blocker in decision.blockers
    assert decision.ready_for_brand_outbound is False
    assert decision.ready_for_public_contact_cta is False


def test_identity_release_recognizes_enforced_dmarc_without_requiring_it_for_initial_readiness():
    decision = evaluate_identity_release(
        _evidence(dmarc_txt_records=("v=DMARC1; p=reject; pct=100",))
    )
    assert decision.ready_for_brand_outbound is True
    assert decision.dmarc_enforced is True
    assert decision.dmarc_policy == "reject"


def test_identity_release_accepts_managed_provider_dkim_cname_binding():
    decision = evaluate_identity_release(
        _evidence(dkim_records_by_selector={"google": ("google.dkim.provider.example.",)})
    )
    assert decision.dkim_valid is True
    assert decision.ready_for_brand_outbound is True


def test_identity_release_rejects_mailbox_outside_canonical_domain():
    with pytest.raises(IdentityReleaseGateError, match="must belong to canonical domain"):
        evaluate_identity_release(_evidence(mailbox="marcos@obrasignal.com"))
