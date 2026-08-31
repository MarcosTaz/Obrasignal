import os
import sys
import time
from urllib.parse import urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://marcostaz.github.io/Obrasignal/").rstrip("/") + "/"
E2E_EMAIL = os.environ.get("E2E_EMAIL", "")
E2E_PASSWORD = os.environ.get("E2E_PASSWORD", "")
TARGET_BUILD = os.environ.get("TARGET_BUILD", "")

VIEWPORTS = [
    ("mobile-320", 320, 844),
    ("mobile-375", 375, 812),
    ("mobile-390", 390, 844),
    ("tablet", 768, 1024),
    ("desktop", 1440, 1000),
]
BROWSERS = ("chromium", "firefox", "webkit")


def fail(message):
    raise AssertionError(message)


def wait_for_exact_pages_build(page):
    if not TARGET_BUILD:
        fail("TARGET_BUILD is required")
    marker_url = urljoin(PUBLIC_URL, "release-source.txt")
    deadline = time.time() + 180
    last = ""
    while time.time() < deadline:
        response = page.request.get(marker_url, timeout=15_000)
        if response.ok:
            last = response.text().strip()
            if last == TARGET_BUILD:
                return
        time.sleep(5)
    fail(f"GitHub Pages never served exact target build {TARGET_BUILD}; last marker={last!r}")


def attach_failure_collectors(page, label):
    failures = []

    def on_console(message):
        if message.type == "error":
            failures.append(f"{label} console error: {message.text}")

    def on_page_error(error):
        failures.append(f"{label} page error: {error}")

    def on_request_failed(request):
        failures.append(f"{label} request failed: {request.method} {request.url} :: {request.failure}")

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("requestfailed", on_request_failed)
    return failures


def assert_no_horizontal_overflow(page, label):
    metrics = page.evaluate(
        """() => ({
          innerWidth: window.innerWidth,
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          bodyScrollWidth: document.body ? document.body.scrollWidth : 0
        })"""
    )
    allowed = max(metrics["innerWidth"], metrics["clientWidth"]) + 2
    actual = max(metrics["scrollWidth"], metrics["bodyScrollWidth"])
    if actual > allowed:
        fail(f"{label} horizontal overflow: viewport={allowed}, content={actual}, metrics={metrics}")


def assert_public_landing(page, browser_name, viewport_name, width, height):
    label = f"{browser_name}/{viewport_name}"
    page.set_viewport_size({"width": width, "height": height})
    failures = attach_failure_collectors(page, label)
    response = page.goto(PUBLIC_URL, wait_until="domcontentloaded", timeout=45_000)
    if response is None or response.status >= 400:
        fail(f"{label} public landing HTTP failure: {getattr(response, 'status', None)}")
    page.get_by_text("Encontra os concursos que merecem o teu tempo.", exact=True).wait_for(timeout=30_000)
    page.get_by_role("button", name="Entrar", exact=True).wait_for(timeout=10_000)
    page.get_by_role("button", name="Criar conta", exact=True).wait_for(timeout=10_000)
    page.get_by_text("obrasignal.pt@gmail.com", exact=True).wait_for(timeout=10_000)
    assert_no_horizontal_overflow(page, label)

    page.get_by_role("button", name="Criar conta", exact=True).click()
    page.get_by_text("Cria o teu radar.", exact=True).wait_for(timeout=10_000)
    inputs = page.locator("input")
    if inputs.count() < 2:
        fail(f"{label} signup surface does not expose email/password inputs")
    page.get_by_role("button", name="← Voltar ao site", exact=True).click()
    page.get_by_text("Encontra os concursos que merecem o teu tempo.", exact=True).wait_for(timeout=10_000)

    if failures:
        fail("\n".join(failures))
    print(f"PASS public {label}")


def authenticated_roundtrip(page, browser_name):
    if not E2E_EMAIL or not E2E_PASSWORD:
        fail("E2E_EMAIL and E2E_PASSWORD are required for authenticated browser E2E")
    label = f"{browser_name}/authenticated"
    page.set_viewport_size({"width": 1280, "height": 900})
    failures = attach_failure_collectors(page, label)
    page.goto(PUBLIC_URL, wait_until="domcontentloaded", timeout=45_000)
    page.get_by_role("button", name="Entrar", exact=True).click()
    page.get_by_text("Bem-vindo de volta.", exact=True).wait_for(timeout=10_000)
    inputs = page.locator("input")
    if inputs.count() < 2:
        fail(f"{label} signin surface does not expose email/password inputs")
    inputs.nth(0).fill(E2E_EMAIL)
    inputs.nth(1).fill(E2E_PASSWORD)
    page.get_by_role("button", name="Entrar", exact=True).click()

    try:
        page.get_by_role("button", name="Terminar sessão", exact=True).wait_for(timeout=90_000)
    except PlaywrightTimeoutError:
        body = page.locator("body").inner_text(timeout=10_000)
        fail(f"{label} authenticated shell did not become ready. Body excerpt: {body[:1200]}")

    page.get_by_role("button", name="Conta e privacidade", exact=True).wait_for(timeout=30_000)
    assert_no_horizontal_overflow(page, label)

    page.reload(wait_until="domcontentloaded", timeout=45_000)
    page.get_by_role("button", name="Terminar sessão", exact=True).wait_for(timeout=90_000)
    page.get_by_role("button", name="Conta e privacidade", exact=True).wait_for(timeout=30_000)

    page.get_by_role("button", name="Conta e privacidade", exact=True).click()
    page.get_by_text("Exportar os meus dados", exact=True).wait_for(timeout=30_000)
    page.get_by_role("button", name="Fechar", exact=True).click()

    page.get_by_role("button", name="Terminar sessão", exact=True).click()
    page.get_by_text("Encontra os concursos que merecem o teu tempo.", exact=True).wait_for(timeout=30_000)

    if failures:
        fail("\n".join(failures))
    print(f"PASS authenticated {browser_name}")


def main():
    all_failures = []
    with sync_playwright() as playwright:
        probe = playwright.chromium.launch(headless=True)
        probe_page = probe.new_page()
        try:
            wait_for_exact_pages_build(probe_page)
            print(f"PASS exact Pages build {TARGET_BUILD}")
        finally:
            probe.close()

        for browser_name in BROWSERS:
            browser_type = getattr(playwright, browser_name)
            browser = browser_type.launch(headless=True)
            try:
                for viewport_name, width, height in VIEWPORTS:
                    context = browser.new_context(viewport={"width": width, "height": height})
                    page = context.new_page()
                    try:
                        assert_public_landing(page, browser_name, viewport_name, width, height)
                    except Exception as exc:
                        all_failures.append(f"{browser_name}/{viewport_name}: {exc}")
                    finally:
                        context.close()

                context = browser.new_context(viewport={"width": 1280, "height": 900})
                page = context.new_page()
                try:
                    authenticated_roundtrip(page, browser_name)
                except Exception as exc:
                    all_failures.append(f"{browser_name}/authenticated: {exc}")
                finally:
                    context.close()
            finally:
                browser.close()

    if all_failures:
        for item in all_failures:
            print(f"FAIL {item}", file=sys.stderr)
        raise SystemExit(1)
    print("Production browser matrix PASS")


if __name__ == "__main__":
    main()
