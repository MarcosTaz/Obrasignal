from html import escape


def _esc(value):
    return escape(str(value if value is not None else ""), quote=True)


def render_opportunity_detail(item, decision):
    """Render the explainable opportunity detail using the open visual language."""
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
    title = _esc(item.get("title") or "Sem título")
    buyer = _esc(item.get("buyer") or "Entidade não identificada")
    source = _esc(item.get("source") or "—")
    country = _esc(item.get("country") or "—")
    score = _esc(item.get("score") or 0)
    value = _esc(item.get("value") or "não indicado")
    deadline = _esc(item.get("deadline") or "não indicado")
    url = _esc(item.get("url") or "#")
    reason = _esc(decision.get("reason") or "Sem razão registada.")
    rule_version = _esc(decision.get("rule_version") or "—")
    decided_at = _esc(decision.get("decided_at") or "—")

    return f'''<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Decisão · ObraSignal</title>
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
.score{{min-width:124px;padding:16px;border:1px solid var(--line);border-radius:18px;background:#fff;text-align:center}}
.score-label{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}}
.score-value{{font-size:34px;font-weight:850;color:var(--accent);line-height:1.1;margin-top:4px}}
.reason{{margin-top:20px;padding:16px 18px;border:1px solid #d7e5ff;background:var(--accent-soft);border-radius:16px;line-height:1.5}}
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
@media(max-width:760px){{.hero-grid{{grid-template-columns:1fr}}.score{{width:100%}.meta{{grid-template-columns:1fr 1fr}}.evidence-row{{grid-template-columns:1fr;gap:6px}}}}
@media(max-width:480px){{.wrap{{padding:18px 14px 40px}}.hero,.section{{padding:18px;border-radius:18px}}.meta{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="wrap">
  <div class="nav"><a class="back" href="/">← Voltar ao radar</a><div class="kicker">ObraSignal · decisão comercial</div></div>
  <section class="hero">
    <div class="hero-grid">
      <div>
        <div class="kicker">Oportunidade</div>
        <h1>{title}</h1>
        <div class="buyer">{buyer}</div>
        <div class="{status_class}">{status}</div>
      </div>
      <div class="score"><div class="score-label">Score comercial</div><div class="score-value">{score}<span style="font-size:16px;color:#64748b">/100</span></div></div>
    </div>
    <div class="reason">{reason}</div>
  </section>

  <section class="section">
    <h2>Porque esta oportunidade está aqui</h2>
    <div>{evidence_html}</div>
    <div class="footer-meta">Regra: {rule_version} · Decidido: {decided_at}</div>
  </section>

  <section class="section">
    <h2>Dados essenciais</h2>
    <div class="meta">
      <div class="meta-card"><div class="meta-label">Fonte</div><div class="meta-value">{source}</div></div>
      <div class="meta-card"><div class="meta-label">País</div><div class="meta-value">{country}</div></div>
      <div class="meta-card"><div class="meta-label">Valor</div><div class="meta-value">{value}</div></div>
      <div class="meta-card"><div class="meta-label">Prazo</div><div class="meta-value">{deadline}</div></div>
    </div>
    <a class="source" href="{url}" target="_blank" rel="noopener noreferrer">Abrir fonte original →</a>
  </section>
</div>
</body>
</html>'''
