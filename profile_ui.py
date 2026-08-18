from html import escape


def _e(value):
    return escape(str(value if value is not None else ""), quote=True)


def _join(values):
    return ", ".join(str(v) for v in (values or []) if str(v).strip())


def render_profile_page(profile):
    """Render the company profile as an open, future-facing configuration workspace."""
    profile = profile or {}
    fields = {
        "name": profile.get("name") or "",
        "activity": profile.get("activity") or "",
        "countries": _join(profile.get("countries")),
        "regions": _join(profile.get("regions")),
        "radius": profile.get("geographic_radius_km") if profile.get("geographic_radius_km") is not None else "",
        "services": _join(profile.get("services")),
        "capabilities": _join(profile.get("capability_tags")),
        "scales": _join(profile.get("project_scales")),
        "certifications": _join(profile.get("certifications")),
        "cpvs": _join(profile.get("cpv_prefixes")),
        "min_value": profile.get("min_value") if profile.get("min_value") is not None else "",
        "max_value": profile.get("max_value") if profile.get("max_value") is not None else "",
        "economic_min_score": profile.get("economic_min_score") if profile.get("economic_min_score") is not None else "",
        "min_deadline_days": profile.get("min_deadline_days") if profile.get("min_deadline_days") is not None else "",
        "max_deadline_days": profile.get("max_deadline_days") if profile.get("max_deadline_days") is not None else "",
        "preferred": _join(profile.get("preferred_procedure_types")),
        "excluded": _join(profile.get("excluded_procedure_types")),
        "excluded_keywords": _join(profile.get("exclude_keywords")),
        "hard_exclusions": _join(profile.get("hard_exclusions")),
    }

    def input_text(key, label, help_text="", placeholder=""):
        return (
            f'<label class="field"><span>{_e(label)}</span>'
            f'<input name="{_e(key)}" value="{_e(fields[key])}" placeholder="{_e(placeholder)}">'
            f'<small>{_e(help_text)}</small></label>'
        )

    return f'''<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Perfil · ObraSignal</title>
<style>
:root{{--bg:#f5f8fc;--surface:#fff;--line:#e3eaf2;--ink:#142033;--muted:#66758a;--accent:#2f6fed;--accent-soft:#edf3ff;--good:#177245;--shadow:0 14px 40px rgba(20,32,51,.07)}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
.wrap{{max-width:1120px;margin:0 auto;padding:28px 20px 60px}}
.nav{{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px;gap:16px}}
a{{color:var(--accent);text-decoration:none}}a:hover{{text-decoration:underline}}
.kicker{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;font-weight:800;color:var(--muted)}}
h1{{font-size:clamp(30px,5vw,48px);line-height:1.02;letter-spacing:-.03em;margin:8px 0}}
.lead{{font-size:16px;color:var(--muted);max-width:760px;line-height:1.5}}
.section{{margin-top:18px;background:var(--surface);border:1px solid var(--line);border-radius:22px;padding:22px;box-shadow:var(--shadow)}}
.section h2{{margin:0 0 6px;font-size:21px;letter-spacing:-.02em}}
.section p{{margin:0 0 16px;color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}}
.field{{display:block}}
.field>span{{display:block;font-size:13px;font-weight:750;margin-bottom:7px}}
.field input{{width:100%;border:1px solid var(--line);background:#fbfdff;border-radius:13px;padding:12px 13px;font:inherit;color:var(--ink);outline:none}}
.field input:focus{{border-color:#b8caf3;box-shadow:0 0 0 4px rgba(47,111,237,.08)}}
.field small{{display:block;color:var(--muted);font-size:12px;margin-top:6px;line-height:1.4}}
.hint{{padding:13px 15px;border:1px solid #d7e5ff;background:var(--accent-soft);border-radius:15px;color:#35507e;font-size:13px;line-height:1.45;margin-bottom:14px}}
.actions{{display:flex;justify-content:flex-end;gap:10px;margin-top:18px}}
button{{border:0;background:var(--accent);color:#fff;border-radius:13px;padding:12px 18px;font:inherit;font-weight:800;cursor:pointer}}
button.secondary{{background:#eef2f7;color:#243248}}
.badges{{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}}
.badge{{padding:7px 10px;background:#f4f7fb;border:1px solid var(--line);border-radius:999px;font-size:12px;color:#41506a}}
@media(max-width:760px){{.grid{{grid-template-columns:1fr}}.nav{{align-items:flex-start;flex-direction:column}}.actions{{justify-content:stretch}}button{{width:100%}}}}
</style>
</head>
<body>
<div class="wrap">
  <div class="nav"><a href="/">← Voltar ao radar</a><div class="kicker">ObraSignal · configuração da empresa</div></div>
  <div class="kicker">Perfil comercial</div>
  <h1>Ensina o ObraSignal a pensar como a tua empresa.</h1>
  <div class="lead">Estas regras não inventam lucro nem substituem a tua decisão. Definem o que a empresa procura, onde trabalha, o que consegue executar e quais oportunidades devem ser filtradas antes de alguém perder tempo com uma proposta.</div>
  <form method="post" action="/profile">
    <section class="section">
      <h2>Identidade</h2><p>O contexto base usado para derivar keywords e famílias CPV.</p>
      <div class="grid">{input_text("name","Nome da empresa","Nome usado na interface e exportações.")}{input_text("activity","Actividade","Escreve a actividade em linguagem natural.","estruturas metálicas, coberturas…")}</div>
    </section>

    <section class="section">
      <h2>Mercado e geografia</h2><p>Define onde uma oportunidade faz sentido operacionalmente.</p>
      <div class="hint">Quanto mais precisa for esta camada, menos oportunidades irrelevantes chegam ao topo do radar.</div>
      <div class="grid">{input_text("countries","Países","ISO-3 separados por vírgulas.","PRT, ESP, FRA")}{input_text("regions","Regiões / cidades","Regiões ou cidades prioritárias.","Leiria, Coimbra")}{input_text("radius","Raio operacional (km)","Opcional. Usa coordenadas da empresa quando existirem.","100")}{input_text("cpvs","Famílias CPV","Prefixos separados por vírgulas.","45, 44, 42")}</div>
    </section>

    <section class="section">
      <h2>Capacidades</h2><p>O que a empresa realmente sabe executar e com que escala.</p>
      <div class="grid">{input_text("services","Serviços","Serviços que a empresa presta.","fabrico, montagem, cobertura")}{input_text("capabilities","Capabilities","Tags operacionais.","metalomecânica, aço, serralharia")}{input_text("scales","Escalas de projecto","Valores como small, medium, large.","medium, large")}{input_text("certifications","Certificações","Certificações relevantes.","ISO 9001")}</div>
    </section>

    <section class="section">
      <h2>Economia e capacidade de resposta</h2><p>Regras para decidir se uma oportunidade merece análise comercial.</p>
      <div class="grid">{input_text("min_value","Valor mínimo (€)","Abaixo disto, a oportunidade perde prioridade.","100000")}{input_text("max_value","Valor máximo (€)","Acima disto, pode sair do envelope operacional.","2000000")}{input_text("economic_min_score","Economic Fit mínimo","Score mínimo configurado pela empresa.","60")}{input_text("min_deadline_days","Prazo mínimo para preparar (dias)","Tempo mínimo de preparação desejado.","15")}{input_text("max_deadline_days","Prazo máximo considerado (dias)","Opcional.","90")}</div>
    </section>

    <section class="section">
      <h2>Regras e exclusões</h2><p>Controla procedimentos, palavras e condições que devem pesar contra a oportunidade.</p>
      <div class="grid">{input_text("preferred","Procedimentos preferidos","Tipos separados por vírgulas.","open")}{input_text("excluded","Procedimentos excluídos","Tipos separados por vírgulas.","negotiated")}{input_text("excluded_keywords","Palavras excluídas","Ex.: arquitetura, fiscalização, consultoria.","consultoria, fiscalização")}{input_text("hard_exclusions","Hard exclusions","Bloqueios determinísticos, usados com prudência.","serviço puramente intelectual")}</div>
    </section>

    <section class="section">
      <h2>O que isto muda</h2>
      <div class="badges"><span class="badge">Perfil</span><span class="badge">Lote</span><span class="badge">Geografia</span><span class="badge">Capacidade</span><span class="badge">Economic Fit</span><span class="badge">Decisão</span></div>
      <div class="hint" style="margin-top:14px">O radar continua explicável: estas definições não se transformam magicamente em “lucro previsto”. Elas tornam explícitas as regras comerciais da empresa e deixam o sistema mostrar porquê.</div>
      <div class="actions"><a href="/">Cancelar</a><button type="submit">Guardar perfil</button></div>
    </section>
  </form>
</div>
</body>
</html>'''
