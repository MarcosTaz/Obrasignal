from html import escape


def _esc(value):
    return escape(str(value if value is not None else ""), quote=True)


def _is_missing(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _display(value, missing="Não indicado"):
    return missing if _is_missing(value) else _esc(value)


def _actionable(value):
    '''Preserve the tri-state product truth: True / False / UNKNOWN(None).'''
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized in ("false", "0"):
            return False
        if normalized in ("true", "1"):
            return True
    if value in (False, 0):
        return False
    if value in (True, 1):
        return True
    return bool(value)


def render_opportunity_detail(item, decision):
    '''Render explainable detail without manufacturing customer certainty.'''
    lines = []
    for line in decision.get("lines", []) or []:
        lines.append(
            '<div class="evidence-row">'
            f'<strong>{_esc(line.get("label"))}</strong>'
            f'<span class="evidence-value">{_esc(line.get("value"))}</span>'
            f'<span class="evidence-detail">{_esc(line.get("detail"))}</span>'
            '</div>'
        )
    evidence_html = "".join(lines) or '<div class="empty">Ainda não existe avaliação auditável para esta oportunidade.</div>'
    status = _esc(decision.get("status") or "SEM DECISÃO")
    status_class = {
        "QUALIFIED": "status-qualified",
        "REVIEW": "status-review",
        "REJECT": "status-rejected",
        "REJECTED": "status-rejected",
    }.get(decision.get("status"), "status-neutral")
    title = _display(item.get("title"), "Sem título")
    buyer = _display(item.get("buyer"), "Entidade não identificada")
    source = _display(item.get("source"), "Fonte não identificada")
    country = _display(item.get("country"), "País não indicado")
    decision_score = decision.get("score")
    score_value = "Não avaliada" if _is_missing(decision_score) else _esc(decision_score)
    score_suffix = "" if _is_missing(decision_score) else '<span style="font-size:16px;color:#64748b">/100</span>'
    value = _display(item.get("value"))
    deadline = _display(item.get("deadline"))
    raw_url = str(item.get("url") or "").strip()
    reason = _display(decision.get("reason"), "Sem razão registada.")
    rule_version = _display(decision.get("rule_version"), "—")
    decided_at = _display(decision.get("decided_at"), "—")

    current_actionable = _actionable(item.get("is_actionable"))
    lifecycle_reason = _display(
        item.get("lifecycle_reason"),
        "Esta oportunidade está marcada como não acionável nos dados atuais.",
    )
    lifecycle_observed_raw = item.get("lifecycle_last_observed") or item.get("lifecycle_source_updated_at")
    lifecycle_observed = _display(lifecycle_observed_raw, "Não indicada")
    lifecycle_banner = ""
    analysis_kicker = "Análise de compatibilidade"
    if current_actionable is False:
        analysis_kicker = "Decisão histórica"
        lifecycle_status = _display(item.get("lifecycle_status"), "Não acionável")
        lifecycle_banner = (
            '<section class="lifecycle-alert">'
            '<div class="kicker" style="color:#7f1d1d">ESTADO OFICIAL ATUAL</div>'
            f'<strong>Esta oportunidade já não está ativa · {_esc(str(lifecycle_status).upper())}</strong>'
            f'<div style="margin-top:6px;line-height:1.5">{lifecycle_reason}</div>'
            f'<div class="footer-meta" style="margin-top:8px">Última verificação registada: {lifecycle_observed}</div>'
            '</section>'
        )
    elif current_actionable is None:
        lifecycle_banner = (
            '<section class="lifecycle-unknown">'
            '<div class="kicker">ESTADO ATUAL</div>'
            '<strong>Estado atual não confirmado</strong>'
            '<div style="margin-top:6px;line-height:1.5">Os dados atuais não confirmam se esta oportunidade continua acionável. '
            'Confirma a situação na fonte antes de avançar.</div>'
            '</section>'
        )

    if raw_url:
        source_action = (
            f'<a class="source" href="{_esc(raw_url)}" target="_blank" rel="noopener noreferrer">'
            'Abrir fonte →</a>'
        )
    else:
        source_action = '<div class="source-unavailable">Ligação à fonte não disponível nos dados atuais.</div>'

    return f'''<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Análise · ObraSignal</title>
<style>
:root{{--bg:#f6f9fc;--surface:#fff;--line:#e4ebf3;--ink:#142033;--muted:#64748b;--accent:#2f6fed;--accent-soft:#eaf1ff;--good:#177245;--good-soft:#e9f8ef;--warn:#9a6700;--warn-soft:#fff6db;--bad:#b42318;--bad-soft:#fff0ee;--shadow:0 14px 40px rgba(20,32,51,.08)}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
a{{color:var(--accent);text-decoration:none}}
a:hover{{text-decoration:underline}}
.wrap{{max-width:1080px;margin:0 auto;padding:28px 20px 60px}}
.nav{{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:22px}}
.back{{font-weight:600}}
.kicker{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:700}}
.hero{{background:linear-gradient(135deg,#fff 0%,#f7fbff 100%);border:1px solid var(--line);border-radius:24px;padding:28px;box-shadow:var(--shadow)}}
.hero-grid{{display:grid;grid-template-columns:1fr auto;gap:24px;align-items:start}}
h1{{font-size:clamp(28px,4vw,46px);line-height:1.05;margin:8px 0 12px;letter-spacing:-.03em}}
.buyer{{font-size:16px;color:var(--muted)}}
.status{{display:inline-flex;align-items:center;padding:8px 12px;border-radius:999px;font-size:13px;font-weight:800;margin-top:14px}}
.status-qualified{{background:var(--good-soft);color:var(--good)}}
.status-review{{background:var(--warn-soft);color:var(--warn)}}
.status-rejected{{background:var(--bad-soft);color:var(--bad)}}
.status-neutral{{background:#eef2f6;color:#475569}}
.score{{min-width:150px;padding:16px;border:1px solid var(--line);border-radius:18px;background:#fff;text-align:center}}
.score-label{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}}
.score-value{{font-size:31px;font-weight:850;color:var(--accent);line-height:1.1;margin-top:4px}}
.reason{{margin-top:20px;padding:16px 18px;border:1px solid #d7e5ff;background:var(--accent-soft);border-radius:16px;line-height:1.5}}
.decision-note{{margin-top:10px;color:var(--muted);font-size:13px;line-height:1.45}}
.lifecycle-alert{{margin-bottom:18px;padding:18px 20px;border:1px solid #fecaca;background:#fff1f2;color:#7f1d1d;border-radius:18px}}
.lifecycle-unknown{{margin-bottom:18px;padding:18px 20px;border:1px solid #fde68a;background:#fffbeb;color:#713f12;border-radius:18px}}
.section{{margin-top:18px;background:var(--surface);border:1px solid var(--line);border-radius:20px;padding:22px;box-shadow:0 8px 28px rgba(20,32,51,.05)}}
.section h2{{margin:0 0 14px;font-size:20px;letter-spacing:-.02em}}
.evidence-row{{display:grid;grid-template-columns:190px 110px 1fr;gap:14px;align-items:start;padding:14px 0;border-top:1px solid var(--line)}}
.evidence-row:first-child{{border-top:0}}
.evidence-value{{font-weight:800}}
.evidence-detail{{color:var(--muted);line-height:1.45}}
.meta{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}}
.meta-card{{background:#fbfdff;border:1px solid var(--line);border-radius:16px;padding:14px}}
.meta-label{{font-size:12px;color:var(--muted);margin-bottom:5px}}
.meta-value{{font-weight:750}}
.footer-meta{{margin-top:16px;color:var(--muted);font-size:12px}}
.empty{{color:var(--muted);padding:12px 0}}
.source{{display:inline-flex;margin-top:16px;padding:10px 14px;border-radius:12px;background:var(--accent);color:white;font-weight:750;text-decoration:none}}
.source:hover{{text-decoration:none;filter:brightness(.97)}}
.source-unavailable{{margin-top:16px;padding:10px 14px;border:1px solid var(--line);border-radius:12px;color:var(--muted);background:#fbfdff}}
@media(max-width:760px){{.hero-grid{{grid-template-columns:1fr}}.score{{width:100%}}.meta{{grid-template-columns:1fr 1fr}}.evidence-row{{grid-template-columns:1fr;gap:6px}}}}
@media(max-width:480px){{.wrap{{padding:18px 14px 40px}}.hero,.section{{padding:18px;border-radius:18px}}.meta{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="wrap">
  <div class="nav"><a class="back" href="/radar">← Voltar ao radar</a><div class="kicker">ObraSignal · {analysis_kicker}</div></div>
  {lifecycle_banner}
  <section class="hero">
    <div class="hero-grid">
      <div>
        <div class="kicker">Oportunidade</div>
        <h1>{title}</h1>
        <div class="buyer">{buyer}</div>
        <div class="{status_class}">{status}</div>
      </div>
      <div class="score"><div class="score-label">Compatibilidade</div><div class="score-value">{score_value}{score_suffix}</div></div>
    </div>
    <div class="reason">{reason}</div>
    <div class="decision-note">Esta análise ajuda a ordenar e explicar a oportunidade; a decisão de concorrer é tua.</div>
  </section>

  <section class="section">
    <h2>Porque esta oportunidade está aqui</h2>
    <div>{evidence_html}</div>
    <div class="footer-meta">Regra: {rule_version} · Avaliada: {decided_at}</div>
  </section>

  <section class="section">
    <h2>Dados essenciais</h2>
    <div class="meta">
      <div class="meta-card"><div class="meta-label">Fonte</div><div class="meta-value">{source}</div></div>
      <div class="meta-card"><div class="meta-label">País</div><div class="meta-value">{country}</div></div>
      <div class="meta-card"><div class="meta-label">Valor</div><div class="meta-value">{value}</div></div>
      <div class="meta-card"><div class="meta-label">Prazo</div><div class="meta-value">{deadline}</div></div>
    </div>
    {source_action}
  </section>
</div>
</body>
</html>'''
