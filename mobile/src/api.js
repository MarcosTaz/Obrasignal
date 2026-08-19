import { supabase } from '../lib/supabase';

const API_BASE = process.env.EXPO_PUBLIC_API_URL || 'https://obrasignal.onrender.com/api/v1';

async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeout ?? 15000);
  try {
    const { data: { session } } = await supabase.auth.getSession();
    const authHeaders = session?.access_token
      ? { Authorization: `Bearer ${session.access_token}` }
      : {};

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...authHeaders,
        ...(options.headers || {}),
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
      throw error;
    }
    return data;
  } finally {
    clearTimeout(timeout);
  }
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
  health: () => request('/health'),
  profile: () => request('/profile'),
  saveProfile: (profile) => request('/profile', {
    method: 'POST',
    body: JSON.stringify(profile || {}),
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
