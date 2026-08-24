const { chromium } = require('playwright');

const HOME = 'https://www.g2b.go.kr/';
const SEARCH = 'https://www.g2b.go.kr/pn/pnp/pnpd/searchBidNtce.do';

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
        postData: compact(request.postData(), 20000),
        headers: redactHeaders(await request.allHeaders()),
      },
      response: {
        headers: redactHeaders(await response.allHeaders()),
        jsonTopLevelKeys: parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? Object.keys(parsed) : null,
        jsonPreview: parsed ? compact(JSON.stringify(parsed), 40000) : null,
        textPreview: parsed ? null : compact(bodyText, 15000),
      },
    });
  });

  const result = {
    startedAt: new Date().toISOString(),
    home: {},
    directSearch: {},
    observedSearchCalls: observed,
    classification: null,
    error: null,
  };

  async function snapshot(label) {
    const inputs = await page.locator('input:visible').evaluateAll(nodes => nodes.slice(0, 80).map(el => ({
      id: el.id || '', name: el.name || '', type: el.type || '',
      placeholder: el.getAttribute('placeholder') || '',
      value: el.value || '', className: String(el.className || ''),
      ariaLabel: el.getAttribute('aria-label') || '', title: el.getAttribute('title') || '',
    }))).catch(() => []);
    const actions = await page.locator('a:visible,button:visible').evaluateAll(nodes => nodes.slice(0, 120).map(el => ({
      tag: el.tagName, id: el.id || '', text: String(el.innerText || '').trim().slice(0, 160),
      title: el.getAttribute('title') || '', className: String(el.className || ''),
    })).filter(x => /검색|조회|입찰|공고/.test(`${x.text} ${x.title}`))).catch(() => []);
    const body = await page.locator('body').innerText().catch(() => '');
    return {
      label,
      url: page.url(),
      title: await page.title().catch(() => null),
      inputs,
      actions,
      bodyPreview: compact(body, 10000),
    };
  }

  try {
    await page.goto(HOME, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(4000);
    result.home = await snapshot('home');

    await page.goto(SEARCH, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(6000);
    result.directSearch = await snapshot('direct-search');

    if (/sso\.g2b\.go\.kr\/oidc\//i.test(page.url())) {
      result.classification = 'SSO_REDIRECT_FROM_DIRECT_SEARCH';
    } else {
      const candidate = page.locator('input:visible').filter({ has: page.locator('xpath=..') });
      const allInputs = page.locator('input:visible');
      const count = await allInputs.count();
      let filled = false;
      for (let i = 0; i < Math.min(count, 80); i++) {
        const el = allInputs.nth(i);
        const meta = await el.evaluate(node => `${node.id} ${node.name} ${node.placeholder || ''} ${node.title || ''}`).catch(() => '');
        if (/공고명|입찰공고|bid.*name|bid.*ntce/i.test(meta)) {
          await el.fill('공사').catch(() => {});
          filled = true;
          break;
        }
      }

      const actionCandidates = page.locator('a:visible,button:visible');
      const actionCount = await actionCandidates.count();
      let clicked = false;
      for (let i = 0; i < Math.min(actionCount, 200); i++) {
        const el = actionCandidates.nth(i);
        const meta = await el.evaluate(node => `${node.id} ${node.innerText || ''} ${node.title || ''} ${node.className || ''}`).catch(() => '');
        if (/검색하기|검색|조회/.test(meta)) {
          const responsePromise = page.waitForResponse(r => r.url().includes('srchBidPbanc.do'), { timeout: 30000 }).catch(() => null);
          await el.click({ force: true, timeout: 10000 }).catch(() => null);
          clicked = true;
          await responsePromise;
          await page.waitForTimeout(3000);
          break;
        }
      }

      result.directSearch.filledConstructionKeyword = filled;
      result.directSearch.clickedSearchAction = clicked;
      result.directSearch.afterAttemptUrl = page.url();

      if (observed.length > 0 && observed.some(x => x.status === 200)) {
        result.classification = 'ANONYMOUS_SEARCH_CALL_OBSERVED';
      } else if (/sso\.g2b\.go\.kr\/oidc\//i.test(page.url())) {
        result.classification = 'SSO_REQUIRED_AT_SEARCH';
      } else if (result.directSearch.bodyPreview && /페이지를 찾을 수|요청하신 페이지|접근.*권한/.test(result.directSearch.bodyPreview)) {
        result.classification = 'DIRECT_SEARCH_ROUTE_NOT_PUBLICLY_USABLE';
      } else {
        result.classification = 'DIRECT_SEARCH_PUBLIC_BUT_CALL_NOT_OBSERVED';
      }
    }
  } catch (error) {
    result.error = String(error && error.stack ? error.stack : error);
    result.classification = result.classification || 'PROBE_ERROR';
  } finally {
    result.observedSearchCalls = observed;
    console.log('KOREA_G2B_ANONYMOUS_PROBE=' + JSON.stringify(result, null, 2));
    await browser.close();
  }
})();
