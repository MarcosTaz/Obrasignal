import { supabase } from '../lib/supabase';

const API_BASE = 'https://obrasignal.onrender.com/api/v1';

async function authHeaders() {
  const { data } = await supabase.auth.getSession();
  const token = data?.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeout ?? 15000);
  try {
    const tokenHeaders = await authHeaders();
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { Accept: 'application/json', ...tokenHeaders, ...(options.headers || {}) },
      signal: controller.signal,
    });
    const text = await response.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (_) {}
    if (!response.ok) {
      const message = data?.error || `HTTP ${response.status}`;
      const error = new Error(message);
      error.status = response.status;
      if (response.status === 401) error.code = 'AUTH_REQUIRED';
      throw error;
    }
    return data;
  } finally {
    clearTimeout(timeout);
  }
}

export const api = {
  health: () => request('/health'),
  stats: () => request('/stats'),
  opportunities: ({ q = '', minscore = 0, source = '', limit = 60, openOnly = false } = {}) => {
    const p = new URLSearchParams({ limit: String(limit), minscore: String(minscore) });
    if (q.trim()) p.set('q', q.trim());
    if (source) p.set('source', source);
    if (openOnly) p.set('open', '1');
    return request(`/opportunities?${p.toString()}`);
  },
  opportunity: (id) => request(`/opportunities/${encodeURIComponent(id)}`),
};

export { API_BASE };
