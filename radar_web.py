"""Web presentation for the decision-aware radar feed."""
from __future__ import annotations

from html import escape


def _render_layers(layers: list[dict] | None) -> str:
    if not layers:
        return '<div class="layers-empty">Sem detalhe de decisão registado.</div>'

    items = []
    for layer in layers:
        label = escape(str(layer.get("label") or "Camada"))
        kind = layer.get("kind") or "score"
        detail = escape(str(layer.get("detail") or ""))
        if kind == "score":
            score = layer.get("score")
            value = f"{score}/100" if score is not None else "—"
        elif kind == "evidence":
            value = f"{layer.get('evidence_count', 0)} evidência(s)"
        elif kind == "blocker":
            value = f"{layer.get('evidence_count', 0)} bloqueio(s)"
        else:
            value = "—"
        items.append(
            f'<div class="layer"><strong>{label}</strong><span>{escape(value)}</span><small>{detail}</small></div>'
        )
    return "".join(items)


def render_radar_page(items: list[dict], minscore: int = 0) -> str:
    cards = []
    for item in items:
        summary = item.get("decision_summary") or {}
        status = escape(str(summary.get("status") or "SEM DECISÃO"))
        reason = escape(str(summary.get("reason") or "Ainda não existe decisão comercial auditável."))
        score = summary.get("score")
        score_text = f"{score}/100" if score is not None else "—"
        title = escape(str(item.get("title") or "Sem título"))
        buyer = escape(str(item.get("buyer") or "Entidade não identificada"))
        source = escape(str(item.get("source") or "—"))
        country = escape(str(item.get("country") or "—"))
        url = escape(str(item.get("url") or "#"), quote=True)
        layers = _render_layers(summary.get("layers"))
        cards.append(
            f'<article class="card">'
            f'<div class="meta"><span class="tag">{source}</span><span class="tag">{country}</span>'
            f'<span class="decision">{status}</span></div>'
            f'<h2>{title}</h2><div class="buyer">{buyer}</div>'
            f'<div class="score">Score comercial: {score_text}</div>'
            f'<div class="reason">{reason}</div>'
            f'<div class="layers">{layers}</div>'
            f'<a href="{url}" target="_blank" rel="noopener">Abrir oportunidade →</a>'
            f'</article>'
        )

    return f'''<!doctype html>
<html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ObraSignal · Radar</title>
<style>
body{{font-family:Arial,sans-serif;background:#0b1020;color:#eef2ff;margin:0}}
.wrap{{max-width:1100px;margin:auto;padding:24px}}
.top{{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:18px}}
.card{{background:#151d33;border:1px solid #293553;border-radius:14px;padding:18px}}
.meta{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.tag,.decision{{display:inline-block;padding:5px 9px;border-radius:999px;background:#22304e;font-size:12px}}
.decision{{font-weight:700}}
h1,h2{{margin:8px 0}}
.muted,.buyer{{color:#9aa5bd}}
.score{{margin-top:12px;font-weight:700}}
.reason{{margin:12px 0;padding:10px;border-radius:9px;background:#10182b;color:#b9c6df}}
.layers{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:12px 0}}
.layer{{display:grid;grid-template-columns:1fr auto;gap:4px;padding:9px;border-radius:9px;background:#111a2d;border:1px solid #24314e}}
.layer small{{grid-column:1/-1;color:#9aa5bd}}
.layers-empty{{color:#9aa5bd;font-size:13px;margin:12px 0}}
a{{color:#8db4ff}}
form{{display:flex;gap:8px;flex-wrap:wrap}}
input,button{{background:#0f1629;color:#eef2ff;border:1px solid #354364;border-radius:9px;padding:10px}}
button{{cursor:pointer;background:#2a5bd7;border:0}}
@media(max-width:760px){{.grid,.layers{{grid-template-columns:1fr}}}}
</style></head>
<body><div class="wrap">
<div class="top"><div><div class="muted">OBRASIGNAL</div><h1>Radar comercial</h1><div class="muted">Oportunidades explicadas pela decisão real da empresa.</div></div>
<form method="get"><input type="number" name="minscore" min="0" max="100" value="{minscore}" placeholder="Score mínimo"><button>Filtrar</button></form></div>
<div class="grid">{''.join(cards) or '<div class="card">Nenhuma oportunidade encontrada.</div>'}</div>
</div></body></html>'''
