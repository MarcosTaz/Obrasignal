const ALLOWED_SCOPES = new Set(['all','obrasignal','obrasignal-subs','business','development']);

function config() {
  const origin = String(process.env.CONTROL_TOWER_ORIGIN || '').replace(/\/$/, '');
  const token = String(process.env.CONTROL_TOWER_TOKEN || '');
  if (!origin.startsWith('https://')) throw new Error('CONTROL_TOWER_ORIGIN must be HTTPS');
  if (!token) throw new Error('CONTROL_TOWER_TOKEN required');
  return { origin, token };
}

async function upstream(path, init = {}) {
  const { origin, token } = config();
  const response = await fetch(`${origin}${path}`, {
    ...init,
    redirect: 'manual',
    headers: {
      ...(init.headers || {}),
      authorization: `Bearer ${token}`,
      accept: 'application/json',
    },
  });
  const text = await response.text();
  let body = {};
  try { body = text ? JSON.parse(text) : {}; } catch { body = { error: 'invalid_upstream_json' }; }
  return { status: response.status, body };
}

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  try {
    if (req.method === 'POST') {
      const scope = String(req.body?.scope || 'all');
      if (!ALLOWED_SCOPES.has(scope) && !/^[a-z0-9][a-z0-9-]{0,79}$/.test(scope)) {
        return res.status(400).json({ error: 'invalid_scope' });
      }
      const result = await upstream('/v1/dispatch', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ scope }),
      });
      return res.status(result.status).json(result.body);
    }
    if (req.method === 'GET') {
      const batchId = String(req.query?.batch_id || '');
      if (!/^[0-9a-f-]{36}$/.test(batchId)) return res.status(400).json({ error: 'invalid_batch_id' });
      const result = await upstream(`/v1/batches/${encodeURIComponent(batchId)}`);
      return res.status(result.status).json(result.body);
    }
    res.setHeader('Allow', 'GET, POST');
    return res.status(405).json({ error: 'method_not_allowed' });
  } catch (error) {
    return res.status(503).json({ error: 'control_tower_unavailable' });
  }
}
