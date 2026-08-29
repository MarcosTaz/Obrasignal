export class FounderControlClient {
  constructor({ apiBase = '' } = {}) {
    this.apiBase = String(apiBase || '').replace(/\/$/, '');
  }

  async dispatch(scope = 'all') {
    const response = await fetch(`${this.apiBase}/v1/dispatch`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ scope }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `dispatch failed: ${response.status}`);
    return payload;
  }

  async batch(batchId) {
    const id = encodeURIComponent(String(batchId || ''));
    if (!id) throw new Error('batchId required');
    const response = await fetch(`${this.apiBase}/v1/batches/${id}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `batch read failed: ${response.status}`);
    return payload;
  }

  ligarTodas() {
    return this.dispatch('all');
  }

  ligarObraSignal() {
    return this.dispatch('obrasignal');
  }

  ligarSubsObraSignal() {
    return this.dispatch('obrasignal-subs');
  }

  ligarNegocios() {
    return this.dispatch('business');
  }

  ligarDesenvolvimento() {
    return this.dispatch('development');
  }
}
