"""Web UI for configuring the ObraSignal company profile."""
from __future__ import annotations

from flask import Blueprint, redirect, render_template_string, request, url_for

from company_profile import derive_profile, load_profile, normalize_profile, save_profile


PROFILE_UI = Blueprint("profile_ui", __name__)

_TEMPLATE = r'''
<!doctype html>
<html lang="pt">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Perfil da empresa · ObraSignal</title>
  <style>
    body{font-family:Arial,sans-serif;background:#0b1020;color:#eef2ff;margin:0}
    .wrap{max-width:1050px;margin:auto;padding:24px}
    .top{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:18px}
    .muted{color:#9aa5bd}.card{background:#151d33;border:1px solid #293553;border-radius:14px;padding:18px;margin:14px 0}
    .grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
    label{display:block;font-size:13px;color:#b9c6df;margin-bottom:6px}
    input,textarea{box-sizing:border-box;width:100%;background:#0f1629;color:#eef2ff;border:1px solid #354364;border-radius:9px;padding:10px}
    textarea{min-height:80px;resize:vertical}button,a.button{background:#2a5bd7;color:#fff;border:0;border-radius:9px;padding:10px 14px;text-decoration:none;cursor:pointer}
    .help{font-size:12px;color:#7f8ca6;margin-top:5px}.error{padding:12px;border-radius:9px;background:#4b1d29;border:1px solid #7c3041;color:#ffd6df}
    .success{padding:12px;border-radius:9px;background:#173a2b;border:1px solid #2b6d4d;color:#d7ffe8}.section{margin-top:8px}.row{display:flex;gap:10px;flex-wrap:wrap}
    @media(max-width:760px){.grid{grid-template-columns:1fr}.top{flex-direction:column;align-items:flex-start}}
  </style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div><h1>Perfil comercial</h1><div class="muted">Configura as regras que o ObraSignal usa para decidir o que merece atenção.</div></div>
    <a class="button" href="/">← Voltar ao radar</a>
  </div>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
  {% if saved %}<div class="success">Perfil guardado. As próximas classificações usarão estas regras.</div>{% endif %}
  <form method="post">
    <div class="card">
      <div class="section"><h2>Empresa</h2></div>
      <div class="grid">
        <div><label for="name">Nome</label><input id="name" name="name" value="{{ p.name }}"></div>
        <div><label for="activity">Actividade</label><input id="activity" name="activity" value="{{ p.activity }}"><div class="help">A actividade pode gerar keywords e famílias CPV automaticamente.</div></div>
      </div>
    </div>

    <div class="card">
      <h2>Geografia e capacidade</h2>
      <div class="grid">
        <div><label for="countries">Países</label><input id="countries" name="countries" value="{{ p.countries|join(', ') }}"></div>
        <div><label for="regions">Regiões prioritárias</label><input id="regions" name="regions" value="{{ p.regions|join(', ') }}"></div>
        <div><label for="geographic_radius_km">Raio geográfico (km)</label><input id="geographic_radius_km" name="geographic_radius_km" value="{{ p.geographic_radius_km if p.geographic_radius_km is not none else '' }}" type="number" min="0" step="0.1"></div>
        <div><label for="cpv_prefixes">Famílias CPV</label><input id="cpv_prefixes" name="cpv_prefixes" value="{{ p.cpv_prefixes|join(', ') }}"><div class="help">Ex.: 45, 44, 4522.</div></div>
      </div>
      <div class="grid">
        <div><label for="services">Serviços</label><textarea id="services" name="services">{{ p.services|join(', ') }}</textarea></div>
        <div><label for="capability_tags">Capacidades / tags</label><textarea id="capability_tags" name="capability_tags">{{ p.capability_tags|join(', ') }}</textarea></div>
        <div><label for="project_scales">Escalas de projecto</label><input id="project_scales" name="project_scales" value="{{ p.project_scales|join(', ') }}"></div>
        <div><label for="certifications">Certificações</label><input id="certifications" name="certifications" value="{{ p.certifications|join(', ') }}"></div>
      </div>
    </div>

    <div class="card">
      <h2>Critérios económicos</h2>
      <div class="grid">
        <div><label for="min_value">Valor mínimo (€)</label><input id="min_value" name="min_value" type="number" min="0" step="0.01" value="{{ p.min_value if p.min_value is not none else '' }}"></div>
        <div><label for="max_value">Valor máximo (€)</label><input id="max_value" name="max_value" type="number" min="0" step="0.01" value="{{ p.max_value if p.max_value is not none else '' }}"></div>
        <div><label for="economic_min_score">Score económico mínimo</label><input id="economic_min_score" name="economic_min_score" type="number" min="0" max="100" step="1" value="{{ p.economic_min_score if p.economic_min_score is not none else '' }}"></div>
        <div><label for="min_deadline_days">Prazo mínimo para preparar proposta (dias)</label><input id="min_deadline_days" name="min_deadline_days" type="number" min="0" step="1" value="{{ p.min_deadline_days if p.min_deadline_days is not none else '' }}"></div>
        <div><label for="max_deadline_days">Prazo máximo de preparação desejado (dias)</label><input id="max_deadline_days" name="max_deadline_days" type="number" min="0" step="1" value="{{ p.max_deadline_days if p.max_deadline_days is not none else '' }}"></div>
      </div>
    </div>

    <div class="card">
      <h2>Procedimentos e exclusões</h2>
      <div class="grid">
        <div><label for="preferred_procedure_types">Procedimentos preferidos</label><input id="preferred_procedure_types" name="preferred_procedure_types" value="{{ p.preferred_procedure_types|join(', ') }}"></div>
        <div><label for="excluded_procedure_types">Procedimentos excluídos</label><input id="excluded_procedure_types" name="excluded_procedure_types" value="{{ p.excluded_procedure_types|join(', ') }}"></div>
        <div><label for="exclude_keywords">Palavras penalizadas</label><textarea id="exclude_keywords" name="exclude_keywords">{{ p.exclude_keywords|join(', ') }}</textarea></div>
        <div><label for="hard_exclusions">Exclusões rígidas</label><textarea id="hard_exclusions" name="hard_exclusions">{{ p.hard_exclusions|join(', ') }}</textarea><div class="help">Qualquer ocorrência destas palavras pode bloquear a oportunidade.</div></div>
      </div>
    </div>

    <div class="row"><button type="submit">Guardar perfil</button><a class="button" href="/api/v1/profile" target="_blank">Ver JSON</a></div>
  </form>
</div>
</body>
</html>
'''


@PROFILE_UI.route("/profile", methods=["GET", "POST"])
def profile_page():
    if request.method == "GET":
        return render_template_string(_TEMPLATE, p=load_profile(), error=None, saved=False)

    current = load_profile()
    payload = dict(current)
    list_fields = {
        "countries", "regions", "cpv_prefixes", "services", "capability_tags",
        "project_scales", "certifications", "preferred_procedure_types",
        "excluded_procedure_types", "exclude_keywords", "hard_exclusions",
    }
    number_fields = {
        "geographic_radius_km", "min_value", "max_value", "economic_min_score",
        "min_deadline_days", "max_deadline_days",
    }
    text_fields = {"name", "activity"}

    try:
        for field in text_fields:
            payload[field] = request.form.get(field, "").strip()
        for field in list_fields:
            payload[field] = [item.strip() for item in request.form.get(field, "").split(",") if item.strip()]
        for field in number_fields:
            raw = request.form.get(field, "").strip()
            payload[field] = None if raw == "" else raw
        normalized = normalize_profile(payload)
        normalized = derive_profile(normalized.get("activity", ""), normalized)
        save_profile(normalized)
        return redirect(url_for("profile_ui.profile_page", saved="1"))
    except ValueError as exc:
        return render_template_string(_TEMPLATE, p=payload, error=str(exc), saved=False), 400
