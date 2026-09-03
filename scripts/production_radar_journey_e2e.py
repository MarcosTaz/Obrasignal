import sys

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

import production_browser_e2e as base


def fail(message):
    raise AssertionError(message)


def body_excerpt(page, limit=1800):
    try:
        return page.locator("body").inner_text(timeout=10_000)[:limit]
    except Exception:
        return "<body unavailable>"


def wait_or_fail(locator, message, page, timeout=60_000):
    try:
        locator.wait_for(timeout=timeout)
    except PlaywrightTimeoutError:
        fail(f"{message}. Body excerpt: {body_excerpt(page)}")


def login(page, browser_name):
    label = f"{browser_name}/radar-journey"
    failures = base.attach_failure_collectors(page, label)
    response = page.goto(base.ACTIVE_PUBLIC_URL, wait_until="domcontentloaded", timeout=45_000)
    if response is None or response.status >= 400:
        fail(f"{label} landing HTTP failure: {getattr(response, 'status', None)}")

    base.assert_browser_can_reach_api(page, label)
    base._discard_verified_webkit_health_noise(failures, browser_name)

    page.get_by_role("button", name="Entrar", exact=True).click()
    wait_or_fail(page.get_by_text("Bem-vindo de volta.", exact=True), f"{label} signin surface missing", page, 15_000)
    inputs = page.locator("input")
    if inputs.count() < 2:
        fail(f"{label} signin surface does not expose email/password inputs")
    inputs.nth(0).fill(base.E2E_EMAIL)
    inputs.nth(1).fill(base.E2E_PASSWORD)
    page.get_by_role("button", name="Entrar", exact=True).click()
    wait_or_fail(
        page.get_by_role("button", name="Terminar sessão", exact=True),
        f"{label} authenticated shell did not become ready",
        page,
        90_000,
    )
    return failures


def assert_profile_ready(page, browser_name):
    label = f"{browser_name}/radar-journey"
    onboarding = page.get_by_text("Conta-nos o que a tua empresa faz.", exact=True)
    if onboarding.count() and onboarding.first.is_visible():
        fail(f"{label} authenticated account lost its persisted commercial profile")

    wait_or_fail(
        page.get_by_text("Oportunidades que merecem atenção.", exact=True),
        f"{label} Radar shell missing despite authenticated session",
        page,
        60_000,
    )

    # Prove the profile is not merely present in browser storage: open the server-backed
    # profile surface and require non-empty company + activity fields.
    page.get_by_text("Perfil", exact=True).first.click()
    wait_or_fail(
        page.get_by_text("O teu perfil define o Radar.", exact=True),
        f"{label} profile surface did not load",
        page,
        30_000,
    )
    profile_inputs = page.locator("input")
    if profile_inputs.count() < 2:
        fail(f"{label} profile surface does not expose company/activity fields")
    name = profile_inputs.nth(0).input_value().strip()
    activity = profile_inputs.nth(1).input_value().strip()
    if not name or not activity:
        fail(f"{label} server-backed profile is incomplete: name={bool(name)} activity={bool(activity)}")

    page.get_by_text("Radar", exact=True).first.click()
    wait_or_fail(
        page.get_by_text("Oportunidades que merecem atenção.", exact=True),
        f"{label} could not return from profile to Radar",
        page,
        30_000,
    )


def assert_real_radar(page, browser_name):
    label = f"{browser_name}/radar-journey"

    # Returning accounts may have persisted a stricter 75/90 preference. Force the
    # product's supported baseline (60) through the actual UI; do not alter scoring.
    page.get_by_text("60+ relevância", exact=True).click()
    card_open = page.get_by_text("Ver oportunidade →", exact=True).first
    try:
        card_open.wait_for(timeout=90_000)
    except PlaywrightTimeoutError:
        body = body_excerpt(page)
        if "Sem resultados com estes filtros" in body:
            fail(f"{label} Radar is functionally empty at the supported 60+ open-opportunity baseline. Body excerpt: {body}")
        fail(f"{label} no usable opportunity card appeared. Body excerpt: {body}")

    # Exercise list -> detail, including the commercial workflow surface, without
    # mutating workflow state or notes on the shared production E2E account.
    card_open.click()
    wait_or_fail(
        page.get_by_text("← Voltar ao Radar", exact=True),
        f"{label} opportunity detail did not open",
        page,
        60_000,
    )
    wait_or_fail(
        page.get_by_text("ACOMPANHAMENTO COMERCIAL", exact=True),
        f"{label} commercial workflow surface missing from opportunity detail",
        page,
        60_000,
    )
    wait_or_fail(
        page.get_by_text("Objeto do contrato", exact=True),
        f"{label} opportunity detail never reached usable state",
        page,
        60_000,
    )
    page.get_by_text("← Voltar ao Radar", exact=True).click()
    wait_or_fail(
        page.get_by_text("Ver oportunidade →", exact=True).first,
        f"{label} could not return from detail to populated Radar",
        page,
        60_000,
    )

    # The exact failure class reported by a real returning user must survive reload:
    # session + profile + 60+ filter + usable results all remain coherent.
    page.reload(wait_until="domcontentloaded", timeout=45_000)
    wait_or_fail(
        page.get_by_role("button", name="Terminar sessão", exact=True),
        f"{label} session did not persist across reload",
        page,
        90_000,
    )
    wait_or_fail(
        page.get_by_text("Oportunidades que merecem atenção.", exact=True),
        f"{label} Radar disappeared after reload",
        page,
        60_000,
    )
    wait_or_fail(
        page.get_by_text("Ver oportunidade →", exact=True).first,
        f"{label} populated Radar did not persist/reload for the returning account",
        page,
        90_000,
    )


def run_browser(playwright, browser_name):
    browser_type = getattr(playwright, browser_name)
    browser = browser_type.launch(headless=True)
    try:
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        try:
            failures = login(page, browser_name)
            assert_profile_ready(page, browser_name)
            assert_real_radar(page, browser_name)
            base.assert_no_horizontal_overflow(page, f"{browser_name}/radar-journey")
            page.wait_for_timeout(250)
            base._discard_verified_webkit_health_noise(failures, browser_name)
            if failures:
                fail("\n".join(failures))
            print(f"PASS real Radar customer journey {browser_name}")
        finally:
            context.close()
    finally:
        browser.close()


def main():
    if not base.E2E_EMAIL or not base.E2E_PASSWORD:
        fail("E2E_EMAIL and E2E_PASSWORD are required")
    failures = []
    with sync_playwright() as playwright:
        probe = playwright.chromium.launch(headless=True)
        probe_page = probe.new_page()
        try:
            base.wait_for_exact_pages_build(probe_page)
        finally:
            probe.close()

        for browser_name in base.BROWSERS:
            try:
                run_browser(playwright, browser_name)
            except Exception as exc:
                failures.append(f"{browser_name}: {exc}")

    if failures:
        for item in failures:
            print(f"FAIL {item}", file=sys.stderr)
        raise SystemExit(1)
    print("Real production Radar customer journey PASS")


if __name__ == "__main__":
    main()
