export class FounderControlClient {
  constructor({ apiBase = '' } = {}) {
    this.apiBase = String(apiBase || '').replace(/\/$/, '');
  }
  async _json(path, options = {}) {
    const response = await fetch(`${this.apiBase}${path}`, options);
    let payload = {};
    try { payload = await response.json(); } catch {}
    if (!response.ok) throw new Error(payload.error || `Control Tower HTTP ${response.status}`);
    return payload;
  }
  routes() { return this._json('/v1/routes'); }
  readiness() { return this._json('/ready'); }
  dispatch(scope = 'all') {
    return this._json('/v1/dispatch', {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({scope})});
  }
  batch(batchId) {
    const id = encodeURIComponent(String(batchId || ''));
    if (!id) throw new Error('batchId required');
    return this._json(`/v1/batches/${id}`);
  }
  ligarTodas(){ return this.dispatch('all'); }
  ligarObraSignal(){ return this.dispatch('obrasignal'); }
  ligarSubsObraSignal(){ return this.dispatch('obrasignal-subs'); }
  ligarNegocios(){ return this.dispatch('business'); }
  ligarDesenvolvimento(){ return this.dispatch('development'); }
}
