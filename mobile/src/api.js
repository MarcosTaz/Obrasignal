import { supabase } from '../lib/supabase';

const API_BASE = (process.env.EXPO_PUBLIC_API_URL || 'https://obrasignal.onrender.com/api/v1').replace(/\/$/, '');

const DEFAULT_TIMEOUT = 120000;
const PROFILE_TIMEOUT = 150000;
const MAX_ATTEMPTS = 2;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isRetryableNetworkError(error) {
  if (!error) return false;
  if (error.name === 'AbortError') return true;
  if (typeof error.status === 'number') return [502, 503, 504].includes(error.status);
  return !error.status;
}

function describeNetworkError(error, path) {
  const name = error?.name || 'NetworkError';
  const message = error?.message || String(error || 'unknown error');
  const hint = /load failed|failed to fetch|networkerror/i.test(message)
    ? 'O navegador não recebeu uma resposta HTTP. Verifica CORS, TLS, DNS ou se o endpoint está acessível.'
    : message;
  const diagnostic = new Error(`API ${path}: ${hint} [${name}]`);
  diagnostic.code = 'API_NETWORK_ERROR';
  diagnostic.causeMessage = message;
  diagnostic.path = path;
  diagnostic.apiBase = API_BASE;
  return diagnostic;
}

async function request(path, options = {}) {
  const timeout = options.timeout ?? DEFAULT_TIMEOUT;
  const maxAttempts = options.maxAttempts ?? MAX_ATTEMPTS;
  const fetchOptions = { ...options };
  delete fetchOptions.timeout;
  delete fetchOptions.maxAttempts;

  let lastError = null;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);

    try {
      const { data: { session } } = await supabase.auth.getSession();
      const authHeaders = session?.access_token
        ? { Authorization: `Bearer ${session.access_token}` }
        : {};

      const response = await fetch(`${API_BASE}${path}`, {
        ...fetchOptions,
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          ...authHeaders,
          ...(fetchOptions.headers || {}),
        },
        signal: controller.signal,
      });

      const text = await response.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch (_) {}

      if (!response.ok) {
        const message = data?.error || `HTTP ${response.status}`;
        const error = new Error(message);
        error.status = response.status;
        error.responseBody = data;
        throw error;
      }

      return data;
    } catch (error) {
      lastError = isRetryableNetworkError(error) ? describeNetworkError(error, path) : error;
      if (!isRetryableNetworkError(error) || attempt >= maxAttempts) {
        if (error?.name === 'AbortError') {
          throw new Error(`API ${path}: o servidor demorou demasiado tempo a responder. O Render pode estar a acordar.`);
        }
        throw lastError;
      }
      await sleep(1500 * attempt);
    } finally {
      clearTimeout(timer);
    }
  }

  throw lastError || new Error(`API ${path}: não foi possível concluir o pedido.`);
}

function normalizeOpportunity(item) {
  if (!item || typeof item !== 'object') return item;
  return {
    ...item,
    decision_score: item.decision_score ?? item.account_score ?? null,
    decision_reason: item.decision_reason ?? item.account_reason ?? null,
  };
}

export const api = {
  health: () => request('/health', { timeout: 90000 }),
  profile: () => request('/profile', { timeout: PROFILE_TIMEOUT }),
  saveProfile: (profile) => request('/profile', {
    method: 'POST',
    body: JSON.stringify(profile || {}),
    timeout: PROFILE_TIMEOUT,
  }),
  billingStatus: () => request('/billing/status'),
  stats: () => request('/stats'),
  workflowStats: () => request('/workflow/stats'),
  opportunities: async ({ q = '', minscore = 0, source = '', limit = 60, openOnly = false } = {}) => {
    const p = new URLSearchParams({ limit: String(limit), minscore: String(minscore) });
    if (q.trim()) p.set('q', q.trim());
    if (source) p.set('source', source);
    if (openOnly) p.set('open', '1');
    const data = await request(`/opportunities?${p.toString()}`);
    return data ? { ...data, items: (data.items || []).map(normalizeOpportunity) } : data;
  },
  opportunity: async (id) => normalizeOpportunity(await request(`/opportunities/${encodeURIComponent(id)}`)),
  workflow: (id) => request(`/opportunities/${encodeURIComponent(id)}/workflow`),
  setWorkflow: (id, status, note) => request(`/opportunities/${encodeURIComponent(id)}/workflow`, {
    method: 'POST',
    body: JSON.stringify({ status, note: note || null }),
  }),
};

export { API_BASE };
