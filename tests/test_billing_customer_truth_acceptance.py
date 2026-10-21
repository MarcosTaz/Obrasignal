from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BILLING_GATE = ROOT / "mobile" / "components" / "BillingGate.js"


def _source():
    return BILLING_GATE.read_text(encoding="utf-8")


def test_billing_status_failure_is_not_silently_swallowed():
    source = _source()
    assert "try { server = await api.billingStatus(); } catch (_) {}" not in source, (
        "BUG-GP-014: the authoritative server billing/evaluation status can fail and "
        "the failure is silently discarded. Verification failure must remain visible "
        "as UNKNOWN/UNAVAILABLE, not flow into a normal plan state."
    )


def test_absence_of_local_pro_does_not_infer_active_evaluation():
    source = _source()
    assert "plan: server?.plan || (hasProEntitlement(info) ? 'pro' : 'evaluation')" not in source, (
        "BUG-GP-014: when server billing status is unavailable, absence of a local Pro "
        "entitlement is interpreted as active Evaluation. Missing Pro is not evidence "
        "that the server has granted Evaluation access."
    )
