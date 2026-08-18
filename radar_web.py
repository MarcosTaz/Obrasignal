"""Web presentation for the decision-aware radar feed."""
from __future__ import annotations

from html import escape

from visual_system import render_status_pill, visual_css


def _render_layers(layers: list[dict] | None) -> str:
    if not layers:
        return '<div class="os-muted">Sem detalhe de decisão registado.</div>'

    items = []
    for layer in layers:
        label = escape(str(layer.get("label") or "Camada"))
        kind = layer.get("kind") or "score"
        detail = escape(str(layer.get("detail") or ""))
        if kind == "score":
            score = layer.get("score")
            scale = layer.get("scale")
            value = "—" if score is None else (f"{score}/{scale}" if scale else f"{score}/100")
        elif kind == "evidence":
            value = f"{layer.get('evidence_count', 0)} evidência(s)"
        elif kind == "blocker":
            value = f"{layer.get('evidence_count', 0)} bloqueio(s)"
        else:
            value = "—"
        items.append(
            f'<div class="os-card" style="padding:12px;box-shadow:none;background:var(--os-surface-alt);">'
            f'<div style="display:flex;justify-content:space-between;gap:10px;"><strong>{label}</strong><span>{escape(value)}</span></div>'
            f'<div class="os-muted" style="font-size:12px;margin-top:5px;">{detail}</div>'
            f'</div>'
        )
    return "".join(items)


def render_radar_page(items: list[dict], minscore: int = 0) -> str:
    cards = []
    for item in items:
        summary = item.get("decision_summary") or {}
        status_raw = str(summary.get("status") or "SEM DECISÃO")
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
            f'<article class="os-card">'
            f'<div style="display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;">'
            f'<div><span class="os-pill">{source}</span> <span class="os-pill">{country}</span></div>'
            f'{render_status_pill(status_raw)}</div>'
            f'<h2 style="margin:14px 0 5px;font-size:23px;letter-spacing:-.02em;">{title}</h2>'
            f'<div class="os-muted">{buyer}</div>'
            f'<div style="display:flex;justify-content:space-between;gap:12px;align-items:end;margin:18px 0 10px;">'
            f'<div><div class="os-muted" style="font-size:12px;">DECISÃO</div><div class="os-stat" style="font-size:27px;">{score_text}</div></div>'
            f'<div class="os-muted" style="font-size:13px;max-width:55%;text-align:right;">{reason}</div></div>'
            f'<div class="os-grid" style="grid-template-columns:repeat(2,minmax(0,1fr));margin-bottom:14px;">{layers}</div>'
            f'<a class="os-button os-button--primary" href="{url}" target="_blank" rel="noopener">Abrir oportunidade →</a>'
            f'</article>'
        )

    body = "".join(cards) or '<div class="os-card">Nenhuma oportunidade encontrada.</div>'
    return f'''<!doctype html>
<html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ObraSignal · Radar</title><style>{visual_css()}</style></head>
<body><main class="os-shell">
<section class="os-card os-card--hero os-future" style="margin-bottom:20px;">
  <div class="os-kicker">OBRASIGNAL · RADAR</div>
  <div style="display:flex;justify-content:space-between;gap:24px;align-items:end;flex-wrap:wrap;">
    <div><h1 class="os-title">Encontra primeiro o que merece atenção.</h1>
    <div class="os-muted" style="max-width:680px;font-size:16px;line-height:1.5;">Um radar comercial que explica cada oportunidade através do perfil da empresa, lote, geografia, capacidade e Economic Fit.</div></div>
    <form method="get" style="display:flex;gap:8px;align-items:end;"><label class="os-muted" style="font-size:12px;">Score mínimo<br><input style="margin-top:5px;border:1px solid var(--os-line);border-radius:12px;padding:10px 12px;background:white;color:var(--os-text);" type="number" name="minscore" min="0" max="100" value="{minscore}"></label><button class="os-button os-button--primary" type="submit">Filtrar</button></form>
  </div>
</section>
<section style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;">{body}</section>
</main></body></html>'''
