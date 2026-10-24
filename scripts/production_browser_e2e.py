import os
import sys
import time
from urllib.parse import urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

CANONICAL_PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://obrasignal.com/").rstrip("/") + "/"
FALLBACK_PUBLIC_URL = os.environ.get("FALLBACK_PUBLIC_URL", "").strip()
if FALLBACK_PUBLIC_URL:
    FALLBACK_PUBLIC_URL = FALLBACK_PUBLIC_URL.rstrip("/") + "/"
ACTIVE_PUBLIC_URL = CANONICAL_PUBLIC_URL
E2E_EMAIL = os.environ.get("E2E_EMAIL", "")
E2E_PASSWORD = os.environ.get("E2E_PASSWORD", "")
TARGET_BUILD = os.environ.get("TARGET_BUILD", "")
API_HEALTH_URL = "https://obrasignal.onrender.com/api/v1/health"

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
    """Wait for the exact web build on canonical origin or published fallback."""
    global ACTIVE_PUBLIC_URL
    if not TARGET_BUILD:
        fail("TARGET_BUILD is required")

    candidates = [("canonical", CANONICAL_PUBLIC_URL)]
    if FALLBACK_PUBLIC_URL and FALLBACK_PUBLIC_URL != CANONICAL_PUBLIC_URL:
        candidates.append(("fallback", FALLBACK_PUBLIC_URL))

    deadline = time.time() + 240
    last = {}
    while time.time() < deadline:
        for kind, origin in candidates:
            marker_url = urljoin(origin, "release-source.txt")
            try:
                response = page.request.get(marker_url, timeout=12_000)
                if not response.ok:
                    last[kind] = f"HTTP {response.status}"
                    continue
                marker = response.text().strip()
                last[kind] = marker
                if marker != TARGET_BUILD:
                    continue
                ACTIVE_PUBLIC_URL = origin
                if kind == "fallback":
                    print(
                        "PROVIDER_BLOCKED canonical DNS/origin; "
                        f"exercising exact published fallback {ACTIVE_PUBLIC_URL}"
                    )
                return
            except Exception as exc:
                last[kind] = f"network-error:{exc}"
        time.sleep(5)

    fail(
        f"no customer origin served exact target build {TARGET_BUILD}; "
        f"canonical={CANONICAL_PUBLIC_URL!r}; fallback={FALLBACK_PUBLIC_URL!r}; last={last!r}"
    )


def _ignorable_request_failure(request):
    """Ignore browser lifecycle cancellation, never connectivity/CORS failure."""
    failure = str(request.failure or "")
    lifecycle_markers = (
        "ERR_ABORTED",
        "NS_BINDING_ABORTED",
        "Load request cancelled",
    )
    return any(marker in failure for marker in lifecycle_markers)


def attach_failure_collectors(page, label):
    """Capture JavaScript, network and HTTP failures with actionable URLs."""
    failures = []

    def on_console(message):
        if message.type == "error":
            failures.append(f"{label} console error: {message.text}")

    def on_page_error(error):
        failures.append(f"{label} page error: {error}")

    def on_request_failed(request):
        if _ignorable_request_failure(request):
            return
        failures.append(f"{label} request failed: {request.method} {request.url} :: {request.failure}")

    def on_response(response):
        if response.status >= 400:
            request = response.request
            failures.append(
                f"{label} HTTP {response.status}: {request.method} {response.url}"
            )

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    page.on("requestfailed", on_request_failed)
    page.on("response", on_response)
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


def assert_browser_can_reach_api(page, label):
    """Prove CORS in the actual browser before treating later aborts as lifecycle."""
    result = page.evaluate(
        """async (url) => {
          try {
            const response = await fetch(url, {method: 'GET', cache: 'no-store'});
            const payload = await response.json();
            return {ok: response.ok, status: response.status, build: payload.build || null};
          } catch (error) {
            return {ok: false, status: 0, error: String(error)};
          }
        }""",
        API_HEALTH_URL,
    )
    if not result.get("ok"):
        fail(f"{label} browser API/CORS health probe failed: {result!r}")
    if result.get("build") != TARGET_BUILD:
        fail(f"{label} browser API served wrong build: {result!r}")
    return result


def _discard_verified_webkit_health_noise(failures, browser_name):
    """Discard only WebKit's duplicate pageerror after a successful real fetch.

    WebKit 26.5 can emit a pageerror string saying the exact health URL failed
    an access-control check even when the awaited `fetch()` above returned a
    readable 200 JSON response with the exact target build. That event is not
    allowed to stand in for the CORS verdict: the explicit browser fetch is the
    verdict. DNS/TLS/requestfailed/HTTP errors and every other pageerror remain.
    """
    if browser_name != "webkit":
        return
    marker = "/obrasignal.onrender.com/api/v1/health due to access control checks."
    failures[:] = [item for item in failures if marker not in item]


def assert_public_landing(page, browser_name, viewport_name, width, height):
    label = f"{browser_name}/{viewport_name}"
    page.set_viewport_size({"width": width, "height": height})
    failures = attach_failure_collectors(page, label)
    response = page.goto(ACTIVE_PUBLIC_URL, wait_until="domcontentloaded", timeout=45_000)
    if response is None or response.status >= 400:
        fail(f"{label} public landing HTTP failure: {getattr(response, 'status', None)}")
    page.get_by_text("Anticipate", exact=False).first.wait_for(timeout=30_000)
    page.get_by_role("button", name="Sign in →", exact=True).wait_for(timeout=10_000)
    page.get_by_role("button", name="Explore platform", exact=True).wait_for(timeout=10_000)
    page.get_by_text("Support contact pending verification", exact=False).first.wait_for(timeout=10_000)
    page.get_by_role("button", name="Privacy", exact=True).wait_for(timeout=10_000)
    page.get_by_role("button", name="Terms of use", exact=True).wait_for(timeout=10_000)
    page.get_by_text("Support contact pending verification", exact=False).first.wait_for(timeout=10_000)
    assert_no_horizontal_overflow(page, label)

    page.get_by_role("button", name="Privacy", exact=True).click()
    page.get_by_text("Account data", exact=True).wait_for(timeout=10_000)
    page.get_by_text("External providers", exact=True).wait_for(timeout=10_000)
    page.get_by_role("button", name="Close legal information", exact=True).click()

    page.get_by_role("button", name="Terms of use", exact=True).click()
    page.get_by_text("Authority of original notices", exact=True).wait_for(timeout=10_000)
    page.get_by_text("Subscriptions", exact=True).wait_for(timeout=10_000)
    page.get_by_role("button", name="Close legal information", exact=True).click()

    page.get_by_role("button", name="Explore platform", exact=True).click()
    page.get_by_text("Your procurement command centre.", exact=True).wait_for(timeout=10_000)
    page.get_by_text("INTERFACE PREVIEW · NOT LIVE DATA", exact=True).wait_for(timeout=10_000)
    page.get_by_role("button", name="Introduction", exact=True).click()
    page.get_by_text("Anticipate", exact=False).first.wait_for(timeout=10_000)

    if failures:
        fail("\n".join(failures))
    print(f"PASS public {label}")


def authenticated_roundtrip(page, browser_name):
    if not E2E_EMAIL or not E2E_PASSWORD:
        fail("E2E_EMAIL and E2E_PASSWORD are required for authenticated browser E2E")
    label = f"{browser_name}/authenticated"
    page.set_viewport_size({"width": 1280, "height": 900})
    failures = attach_failure_collectors(page, label)
    page.goto(ACTIVE_PUBLIC_URL, wait_until="domcontentloaded", timeout=45_000)
    assert_browser_can_reach_api(page, label)
    _discard_verified_webkit_health_noise(failures, browser_name)
    page.get_by_role("button", name="Sign in →", exact=True).click()
    page.get_by_text("Welcome back.", exact=True).wait_for(timeout=10_000)
    inputs = page.locator("input")
    if inputs.count() < 2:
        fail(f"{label} signin surface does not expose email/password inputs")
    inputs.nth(0).fill(E2E_EMAIL)
    inputs.nth(1).fill(E2E_PASSWORD)
    page.get_by_role("button", name="Sign in securely", exact=True).click()

    try:
        page.get_by_role("button", name="Sign out", exact=True).wait_for(timeout=90_000)
    except PlaywrightTimeoutError:
        body = page.locator("body").inner_text(timeout=10_000)
        fail(f"{label} authenticated shell did not become ready. Body excerpt: {body[:1200]}; failures={failures!r}")

    page.get_by_role("button", name="Account & privacy", exact=True).wait_for(timeout=30_000)
    assert_no_horizontal_overflow(page, label)

    page.reload(wait_until="domcontentloaded", timeout=45_000)
    page.get_by_role("button", name="Sign out", exact=True).wait_for(timeout=90_000)
    try:
        page.get_by_role("button", name="Account & privacy", exact=True).wait_for(timeout=30_000)
    except PlaywrightTimeoutError:
        body = page.locator("body").inner_text(timeout=10_000)
        fail(f"{label} privacy status did not become ready after reload. Body excerpt: {body[:1200]}; failures={failures!r}")

    page.get_by_role("button", name="Account & privacy", exact=True).click()
    page.get_by_text("Exportar os meus dados", exact=True).wait_for(timeout=30_000)
    page.get_by_text("Fechar", exact=True).last.click()

    page.get_by_role("button", name="Sign out", exact=True).click()
    page.get_by_text("Anticipate", exact=False).first.wait_for(timeout=30_000)
    page.get_by_role("button", name="Privacy", exact=True).wait_for(timeout=10_000)

    page.wait_for_timeout(250)
    # WebKit emits the duplicate access-control pageerror asynchronously, often
    # after the awaited health fetch has already returned the exact build. Apply
    # the narrow filter again at the final verdict, and only in a path where the
    # explicit browser fetch above succeeded. Every other failure remains fatal.
    _discard_verified_webkit_health_noise(failures, browser_name)
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
            print(f"PASS exact published build {TARGET_BUILD} at {ACTIVE_PUBLIC_URL}")
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
