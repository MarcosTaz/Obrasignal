from pathlib import Path
import re


GATE = Path('mobile/components/BillingGate.js').read_text(encoding='utf-8')


def test_server_billing_authority_failure_cannot_silently_fall_back_to_client_entitlement():
    assert not re.search(r"try\s*\{\s*server\s*=\s*await api\.billingStatus\(\);?\s*\}\s*catch\s*\([^)]*\)\s*\{\s*\}", GATE)
    assert not re.search(r"plan:\s*server\?\.plan\s*\|\|\s*\(hasProEntitlement\(info\)\s*\?\s*['\"]pro['\"]", GATE)
    assert re.search(r"authority:\s*['\"]loading['\"]", GATE)
    assert re.search(r"authority:\s*['\"]ready['\"]", GATE)
    assert re.search(r"billing\.authority\s*!==\s*['\"]ready['\"]", GATE)


def test_billing_authority_outage_is_visible_and_retryable():
    assert 'Não foi possível validar o estado da subscrição' in GATE
    assert 'Tentar novamente' in GATE
    assert re.search(r"onPress=\{refresh\}", GATE)


def test_server_plan_is_the_access_authority():
    assert re.search(r"plan:\s*server\.plan", GATE)
    assert re.search(r"pro:\s*server\.plan\s*===\s*['\"]pro['\"]", GATE)
