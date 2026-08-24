const { chromium } = require('playwright');

const HOME = 'https://www.g2b.go.kr/';

function redactHeaders(headers = {}) {
  const out = {};
  for (const [key, value] of Object.entries(headers)) {
    const lower = key.toLowerCase();
    if (['cookie', 'set-cookie', 'authorization', 'proxy-authorization'].includes(lower)) continue;
    out[key] = value;
  }
  return out;
}

function compact(value, limit = 12000) {
  const text = String(value || '');
  return text.length <= limit ? text : text.slice(0, limit) + `... [truncated ${text.length - limit}]`;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    locale: 'ko-KR',
    timezoneId: 'Asia/Seoul',
  });
  const page = await context.newPage();
  const observed = [];

  page.on('response', async (response) => {
    if (!response.url().includes('srchBidPbanc.do')) return;
    const request = response.request();
    let bodyText = '';
    let parsed = null;
    try {
      bodyText = await response.text();
      parsed = JSON.parse(bodyText);
    } catch (_) {}
    observed.push({
      url: response.url(),
      status: response.status(),
      request: {
        method: request.method(),
        postData: compact(request.postData(), 16000),
        headers: redactHeaders(await request.allHeaders()),
      },
      response: {
        headers: redactHeaders(await response.allHeaders()),
        jsonTopLevelKeys: parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? Object.keys(parsed) : null,
        jsonPreview: parsed ? compact(JSON.stringify(parsed), 30000) : null,
        textPreview: parsed ? null : compact(bodyText, 12000),
      },
    });
  });

  const result = {
    startedAt: new Date().toISOString(),
    requestedUrl: HOME,
    finalUrl: null,
    title: null,
    searchInputVisible: false,
    dateInputsVisible: 0,
    searchSubmitted: false,
    observedSearchCalls: observed,
    classification: null,
    error: null,
  };

  try {
    await page.goto(HOME, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(5000);
    result.finalUrl = page.url();
    result.title = await page.title().catch(() => null);

    if (/sso\.g2b\.go\.kr\/oidc\//i.test(result.finalUrl)) {
      result.classification = 'SSO_REDIRECT_FROM_ANONYMOUS_HOME';
    } else {
      const input = page.locator('input[placeholder="입찰공고"]:visible').first();
      result.searchInputVisible = (await input.count()) > 0;
      result.dateInputsVisible = await page.locator('input.udcDateReadOnly:visible').count();

      if (!result.searchInputVisible) {
        result.classification = 'PUBLIC_HOME_BUT_SEARCH_UI_NOT_FOUND';
      } else {
        // Use a harmless construction keyword solely to let the official frontend
        // reveal its own search request contract. Do not log cookies or auth data.
        await input.fill('공사');
        const buttons = page.locator('a.main-srch:has-text("검색하기"):visible');
        if ((await buttons.count()) === 0) {
          result.classification = 'SEARCH_INPUT_PRESENT_BUT_BUTTON_NOT_FOUND';
        } else {
          const responsePromise = page.waitForResponse(
            r => r.url().includes('srchBidPbanc.do'),
            { timeout: 40000 }
          ).catch(() => null);
          await buttons.first().click({ force: true, timeout: 10000 });
          result.searchSubmitted = true;
          const response = await responsePromise;
          await page.waitForTimeout(3000);
          result.finalUrl = page.url();
          if (response && response.status() === 200 && observed.length > 0) {
            result.classification = 'ANONYMOUS_SEARCH_CALL_OBSERVED';
          } else if (/sso\.g2b\.go\.kr\/oidc\//i.test(result.finalUrl)) {
            result.classification = 'SSO_REQUIRED_AT_SEARCH';
          } else {
            result.classification = 'SEARCH_CALL_NOT_OBSERVED';
          }
        }
      }
    }
  } catch (error) {
    result.error = String(error && error.stack ? error.stack : error);
    result.finalUrl = page.url();
    result.classification = result.classification || 'PROBE_ERROR';
  } finally {
    result.observedSearchCalls = observed;
    console.log('KOREA_G2B_ANONYMOUS_PROBE=' + JSON.stringify(result, null, 2));
    await browser.close();
  }
})();
