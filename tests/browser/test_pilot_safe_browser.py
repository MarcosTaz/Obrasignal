from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager

import pytest
from werkzeug.serving import make_server

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

from factory_cloud.trusted_upstream_identity import TrustedUpstreamVerifier
from vertical_apps.aviation_recovery.web import create_app as create_aviation_app
from vertical_apps.contractcredit.web import create_app as create_contractcredit_app

SECRET = "browser-runtime-test-key-32-bytes-minimum"


class SignedIdentityProxy:
    """Test-only reverse-proxy simulation; browser never sees or computes the key."""

    def __init__(self, app, *, tenant_id: str, actor_id: str):
        self.app = app
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.verifier = TrustedUpstreamVerifier(SECRET)

    def __call__(self, environ, start_response):
        path = str(environ.get("PATH_INFO") or "/")
        method = str(environ.get("REQUEST_METHOD") or "GET")
        if path not in {"/", "/health", "/ready"}:
            timestamp = int(time.time())
            environ["HTTP_X_TENANT_ID"] = self.tenant_id
            environ["HTTP_X_ACTOR_ID"] = self.actor_id
            environ["HTTP_X_UPSTREAM_TIMESTAMP"] = str(timestamp)
            environ["HTTP_X_UPSTREAM_SIGNATURE"] = self.verifier.sign(
                timestamp=timestamp,
                method=method,
                path=path,
                tenant_id=self.tenant_id,
                actor_id=self.actor_id,
            )
        return self.app(environ, start_response)


@contextmanager
def running_app(flask_app, *, tenant_id: str):
    server = make_server("127.0.0.1", 0, SignedIdentityProxy(flask_app, tenant_id=tenant_id, actor_id="browser-operator"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _assert_browser_contract(page):
    assert page.locator("#analysis-form").is_visible()
    assert page.locator("#adjudication-form").is_hidden()
    assert page.locator("#review-form").is_hidden()
    assert page.locator("#action-form").is_hidden()
    assert page.locator("#resolve-form").is_hidden()
    assert page.locator("[aria-live='polite']").count() == 1
    assert page.locator("input[name='tenant_id']").count() == 0
    assert page.locator("input[name='actor_id']").count() == 0
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth") is True
    for button in page.locator("button:visible").all():
        assert button.bounding_box()["height"] >= 44


def _fill_contractcredit(page):
    page.get_by_label("Service contract evidence reference").fill("synthetic-msa.pdf")
    page.get_by_label("Service contract SHA-256").fill("a" * 64)
    page.get_by_label("Service contract provenance").fill("browser_synthetic_fixture")
    page.get_by_label("Evidence use is authorized").check()
    page.get_by_label("Incident evidence reference").fill("synthetic-incident.pdf")
    page.get_by_label("Incident evidence SHA-256").fill("b" * 64)
    page.get_by_label("Incident evidence provenance").fill("browser_synthetic_fixture")
    page.get_by_label("Incident evidence use is authorized").check()
    page.get_by_label("Monthly fee").fill("50000")
    page.get_by_label("Contractual credit rate").fill("0.10")
    page.get_by_label("Notice due").fill("2026-09-15")


def _fill_aviation(page):
    page.get_by_label("Lease contract evidence reference").fill("synthetic-lease.pdf")
    page.get_by_label("Lease contract SHA-256").fill("c" * 64)
    page.get_by_label("Lease contract provenance").fill("browser_synthetic_fixture")
    page.get_by_label("Lease evidence use is authorized").check()
    page.get_by_label("Maintenance event evidence reference").fill("synthetic-event.pdf")
    page.get_by_label("Maintenance event SHA-256").fill("d" * 64)
    page.get_by_label("Maintenance event provenance").fill("browser_synthetic_fixture")
    page.get_by_label("Maintenance evidence use is authorized").check()
    page.get_by_label("Eligible cost").fill("100000")
    page.get_by_label("Already reimbursed amount").fill("25000")
    page.get_by_label("Notice due").fill("2026-09-30")


def _complete_browser_flow(page, *, requires_breach: bool, recovered_amount: str):
    page.get_by_role("button", name="Analyze evidence packet").click()
    page.locator("#status").get_by_text("Human adjudication", exact=False).wait_for()
    assert page.locator("#adjudication-form").is_visible()
    assert page.locator("#review-form").is_hidden()

    page.get_by_label("Entitlement established by reviewed evidence").check()
    if requires_breach:
        page.get_by_label("Contractual breach established by reviewed evidence").check()
    page.get_by_label("Decision evidence reference").fill("synthetic-decision-evidence")
    page.get_by_label("Decision reason").fill("bounded synthetic evidence establishes the test entitlement")
    page.get_by_role("button", name="Record adjudication").click()
    page.locator("#status").get_by_text("Review may proceed", exact=False).wait_for()
    assert page.locator("#review-form").is_visible()
    assert page.locator("#approve-button").is_visible()

    page.get_by_label("Review reason").fill("synthetic adjudication reviewed")
    page.get_by_role("button", name="Approve finding").click()
    page.locator("#action-form").wait_for(state="visible")
    page.get_by_role("button", name="Mark adjudicated finding as actioned").click()
    page.locator("#resolve-form").wait_for(state="visible")
    page.get_by_label("Outcome ID").fill("browser-outcome")
    page.get_by_label("Recovered amount").fill(recovered_amount)
    page.get_by_label("Currency").fill("EUR")
    page.get_by_label("Outcome evidence reference").fill("browser-outcome-evidence")
    page.get_by_role("button", name="Record outcome").click()
    page.locator("#result").get_by_text('"state": "RECOVERED"', exact=False).wait_for()


@pytest.mark.parametrize("viewport", [{"width": 390, "height": 844}, {"width": 1280, "height": 800}])
def test_contractcredit_real_browser_evidence_adjudication_outcome(tmp_path, viewport):
    os.environ["ASSISTED_UPSTREAM_HMAC_KEY"] = SECRET
    app = create_contractcredit_app(tmp_path / "contractcredit.sqlite3")
    with running_app(app, tenant_id="browser-contractcredit") as base_url, sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=viewport)
        page.goto(base_url, wait_until="networkidle")
        _assert_browser_contract(page)
        _fill_contractcredit(page)
        _complete_browser_flow(page, requires_breach=True, recovered_amount="5000")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth") is True
        browser.close()


@pytest.mark.parametrize("viewport", [{"width": 390, "height": 844}, {"width": 1280, "height": 800}])
def test_aviation_real_browser_evidence_adjudication_outcome(tmp_path, viewport):
    os.environ["ASSISTED_UPSTREAM_HMAC_KEY"] = SECRET
    app = create_aviation_app(tmp_path / "aviation.sqlite3")
    with running_app(app, tenant_id="browser-aviation") as base_url, sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=viewport)
        page.goto(base_url, wait_until="networkidle")
        _assert_browser_contract(page)
        _fill_aviation(page)
        _complete_browser_flow(page, requires_breach=False, recovered_amount="75000")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth") is True
        browser.close()
