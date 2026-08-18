"""Small UI compatibility layer for ObraSignal.

It adds an explicit deadline state to the existing dashboard without touching
its ingestion/ranking code. Python loads sitecustomize during normal startup,
so the existing Flask app keeps its current routes and data pipeline.
"""
from datetime import datetime, timezone

import flask

_ORIGINAL_RENDER = flask.render_template_string


def _deadline_state(value):
    if not value:
        return ("SEM PRAZO", "neutral", None)
    s = str(value).strip().replace("Z", "+00:00")
    dt = None
    for parser in (
        lambda: datetime.fromisoformat(s),
        lambda: datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc),
        lambda: datetime.strptime(s[:8], "%Y%m%d").replace(tzinfo=timezone.utc),
    ):
        try:
            dt = parser()
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            break
        except Exception:
            pass
    if dt is None:
        return ("PRAZO NÃO CONFIRMADO", "neutral", None)
    seconds = (dt - datetime.now(timezone.utc)).total_seconds()
    days = int(seconds // 86400) if seconds >= 0 else -int((-seconds + 86399) // 86400)
    if seconds < 0:
        return ("TERMINADO", "closed", days)
    if seconds <= 48 * 3600:
        return ("URGENTE", "urgent", max(0, days))
    return ("ABERTO", "open", days)


DASHBOARD = r'''<!doctype html>
<html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ObraSignal</title>
<style>
body{font-family:Arial,sans-serif;background:#0b1020;color:#eef2ff;margin:0}.wrap{max-width:1200px;margin:auto;padding:24px}.top{display:flex;justify-content:space-between;align-items:center;gap:20px}.muted{color:#9aa5bd}.card{background:#151d33;border:1px solid #293553;border-radius:14px;padding:16px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.stat{font-size:28px;font-weight:700}.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}input,button{background:#0f1629;color:#eef2ff;border:1px solid #354364;border-radius:9px;padding:10px}button{cursor:pointer;background:#2a5bd7;border:0}.tag{display:inline-block;padding:4px 8px;border-radius:999px;background:#26324e;margin:3px;font-size:12px}a{color:#8db4ff}.score{font-size:22px;font-weight:700}.small{font-size:13px}.title{margin:6px 0 8px}.reason{margin-top:10px;padding:9px;border-radius:9px;background:#10182b;color:#b9c6df;font-size:13px}.hot{color:#7ee787}.good{color:#8db4ff}.low{color:#9aa5bd}.hero{border:1px solid #3d5f9d;background:#111b31}.rank{font-size:13px;font-weight:700;letter-spacing:.5px;color:#9fb9ff}.deadline{font-weight:700}.topgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.topcard{margin:0}.topmeta{display:flex;justify-content:space-between;gap:10px;align-items:center}.pill{padding:5px 9px;border-radius:999px;background:#22304e;font-size:12px}.state{font-weight:800;font-size:12px;letter-spacing:.3px;padding:5px 9px;border-radius:999px}.open{background:#123b2a;color:#7ee787}.urgent{background:#4b3410;color:#ffd866}.closed{background:#3a1c24;color:#ff9aa8}.neutral{background:#30384d;color:#c7d0e2}.empty{color:#9aa5bd;padding:12px 0}@media(max-width:800px){.grid,.topgrid{grid-template-columns:1fr 1fr}.top{flex-direction:column;align-items:flex-start}}@media(max-width:560px){.grid,.topgrid{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<div class="top"><div><h1>OBRASIGNAL</h1><div class="muted">Radar automático de concursos e oportunidades de obra</div></div><form method="post" action="/sync"><button>Sincronizar agora</button></form></div>
<div class="grid"><div class="card"><div class="muted">Oportunidades</div><div class="stat">{{stats.total}}</div></div><div class="card"><div class="muted">Novas 24h</div><div class="stat">{{stats.new24}}</div></div><div class="card"><div class="muted">Alta relevância</div><div class="stat">{{stats.high}}</div></div><div class="card"><div class="muted">Última sincronização</div><div class="small">{{stats.last}}</div></div></div>
<div class="card hero"><div class="topmeta"><div><div class="rank">TOP OPORTUNIDADES DE HOJE</div><h2>As oportunidades que merecem atenção primeiro</h2></div><span class="pill">{{top|length}} selecionadas</span></div><div class="topgrid">{% for t in top %}{% set st=deadline_state(t.deadline) %}<div class="card topcard"><div class="topmeta"><span class="pill">#{{loop.index}} · {{t.source}}</span><span class="score">{{t.score}}/100</span></div><div class="row"><span class="state {{st[1]}}">{{st[0]}}</span>{% if st[2] is not none %}<span class="small muted">{% if st[2] >= 0 %}{{st[2]}} dias restantes{% else %}{{-st[2]}} dias após o prazo{% endif %}</span>{% endif %}</div><h3 class="title">{{t.title or 'Sem título'}}</h3><div>{{t.buyer or 'Entidade não identificada'}}</div><div class="small muted">Publicada: {{t.publication_date or 'sem data'}}</div><div class="small deadline">Prazo: {{t.deadline or 'não indicado'}}</div>{% if t.value %}<div class="small">Valor: {{t.value}}</div>{% endif %}<div class="reason"><span class="{{t.priority_class}}">{{t.priority_label}}</span> — {{t.match_reason}}</div><p><a href="{{t.url}}" target="_blank">Abrir oportunidade →</a></p></div>{% endfor %}</div>{% if not top %}<div class="empty">Ainda não há oportunidades classificadas.</div>{% endif %}</div>
<div class="card"><h2>Filtro</h2><form method="get" class="row"><input name="q" placeholder="palavra-chave" value="{{q}}"><input name="country" placeholder="país ISO-3" value="{{country}}"><input name="minscore" type="number" min="0" max="100" placeholder="score mínimo" value="{{minscore}}"><button>Filtrar</button><a href="/">Limpar</a></form></div>
{% for t in tenders %}{% set st=deadline_state(t.deadline) %}<div class="card"><div class="row" style="justify-content:space-between"><div><span class="tag">{{t.source}}</span><span class="tag">{{t.publication_date or 'sem data'}}</span>{% if t.country %}<span class="tag">{{t.country}}</span>{% endif %}</div><div class="row"><span class="state {{st[1]}}">{{st[0]}}</span><div class="score">{{t.score}}/100</div></div></div><div class="small muted">{% if st[2] is not none %}{% if st[2] >= 0 %}{{st[2]}} dias restantes{% else %}{{-st[2]}} dias após o prazo{% endif %}{% else %}Estado do prazo não confirmável{% endif %}</div><h2 class="title">{{t.title or 'Sem título'}}</h2><div>{{t.buyer or 'Entidade não identificada'}}</div><div class="muted small">{{t.value or 'Valor não indicado'}} · Prazo: {{t.deadline or 'não indicado'}}</div><p class="small">{{t.description[:900] if t.description else ''}}</p>{% if t.match_reason %}<div class="reason"><span class="{{t.priority_class}}">{{t.priority_label}}</span> — {{t.match_reason}}</div>{% endif %}{% if t.cpv %}<div>{% for x in t.cpv.split('|')[:10] %}<span class="tag">{{x}}</span>{% endfor %}</div>{% endif %}<p><a href="{{t.url}}" target="_blank">Abrir fonte</a></p></div>{% endfor %}
</div></body></html>'''


def _render_template_string(template, **context):
    if isinstance(template, str) and "OBRASIGNAL" in template and "stats.total" in template:
        context["deadline_state"] = _deadline_state
        return _ORIGINAL_RENDER(DASHBOARD, **context)
    return _ORIGINAL_RENDER(template, **context)


flask.render_template_string = _render_template_string

# Install the funnel hook after the existing UI compatibility patch. The hook
# wraps the existing sync function at worker startup, preserving the pipeline.
try:
    import sync_funnel_hook  # noqa: F401
except Exception:
    pass
