"""Open, future-facing company profile UI."""
from __future__ import annotations

from html import escape


def _csv(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value or "")


def _field(name: str, label: str, value, placeholder: str = "", help_text: str = "", type_: str = "text") -> str:
    return (
        f'<label class="field"><span>{escape(label)}</span>'
        f'<input name="{escape(name)}" type="{type_}" value="{escape(str(value or ""), quote=True)}" placeholder="{escape(placeholder, quote=True)}">'
        f'<small>{escape(help_text)}</small></label>'
    )


def render_profile_page(profile: dict) -> str:
    profile = profile or {}
    return f'''<!doctype html>
<html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ObraSignal · Perfil da empresa</title>
<style>
:root{{--page:#f6f9fc;--surface:#fff;--ink:#14213d;--muted:#6d7a91;--line:#dfe7f2;--accent:#2b6df6;--accent-soft:#edf4ff;--good:#15845d;--warn:#a36a00;--danger:#c14a4a;--shadow:0 18px 45px rgba(26,48,84,.08)}}
*{{box-sizing:border-box}} body{{margin:0;background:linear-gradient(180deg,#f8fbff 0%,#f4f7fb 100%);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
.wrap{{max-width:1100px;margin:auto;padding:28px 20px 56px}} .hero{{display:flex;justify-content:space-between;gap:20px;align-items:end;flex-wrap:wrap;margin-bottom:20px}}
.eyebrow{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);font-weight:800}} h1{{font-size:40px;line-height:1.05;margin:8px 0}} .lead{{font-size:16px;color:var(--muted);max-width:680px}}
.panel{{background:rgba(255,255,255,.92);border:1px solid var(--line);border-radius:22px;box-shadow:var(--shadow);padding:22px;margin-top:16px}} .panel h2{{margin:0 0 6px;font-size:20px}} .panel p{{margin:0 0 16px;color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}} .field{{display:grid;gap:7px}} .field span{{font-weight:700;font-size:14px}} .field small{{color:var(--muted);font-size:12px;line-height:1.4}}
input{{width:100%;padding:12px 13px;border:1px solid var(--line);border-radius:12px;background:#fbfdff;color:var(--ink);font:inherit;outline:none}} input:focus{{border-color:var(--accent);box-shadow:0 0 0 4px rgba(43,109,246,.12)}}
.tagbox{{padding:12px;border:1px dashed #bfd0ec;background:var(--accent-soft);border-radius:14px;color:#335b9f;font-size:13px}} .actions{{display:flex;justify-content:flex-end;gap:10px;margin-top:20px;flex-wrap:wrap}}
button{{border:0;border-radius:12px;padding:12px 16px;background:var(--accent);color:white;font-weight:800;cursor:pointer}} .ghost{{background:white;color:var(--ink);border:1px solid var(--line)}}
.note{{display:flex;gap:10px;align-items:flex-start;padding:12px 14px;border-radius:14px;background:#f6f9fd;border:1px solid var(--line);color:var(--muted);font-size:13px}}
@media(max-width:760px){{.grid{{grid-template-columns:1fr}} h1{{font-size:32px}}}}
</style></head><body><div class="wrap">
<div class="hero"><div><div class="eyebrow">OBRASIGNAL · CONFIGURAÇÃO</div><h1>Ensina o sistema a conhecer a tua empresa.</h1><div class="lead">O ObraSignal não adivinha o que consegues executar. Define aqui as regras reais da empresa e o radar passa a trabalhar dentro delas.</div></div><a href="/radar"><button class="ghost">Voltar ao radar</button></a></div>
<form method="post" action="/profile">
<section class="panel"><h2>Identidade</h2><p>O contexto base que alimenta a interpretação comercial.</p><div class="grid">
{_field("name","Nome da empresa",profile.get("name"),"Ex.: Metalúrgica X","Nome usado na experiência.")}
{_field("activity","Actividade principal",profile.get("activity"),"Ex.: metalomecânica","A actividade pode gerar automaticamente keywords e famílias CPV.")}
</div></section>
<section class="panel"><h2>Onde queres trabalhar</h2><p>Define os mercados prioritários sem obrigar o sistema a inventar localizações.</p><div class="grid">
{_field("countries","Países",";".join(profile.get("countries") or []),"PRT;ESP","Códigos ISO-3 separados por ponto e vírgula.")}
{_field("regions","Regiões / cidades",_csv(profile.get("regions")),"Leiria, Pombal","Locais que devem receber prioridade.")}
{_field("geographic_radius_km","Raio máximo (km)",profile.get("geographic_radius_km"),"80","Só é aplicado quando existem coordenadas válidas.","number")}
{_field("profile_coordinates","Coordenadas da empresa",_csv([profile.get("profile_coordinates",{}).get("lat",""),profile.get("profile_coordinates",{}).get("lon","")]),"39.744,-8.807","Formato: latitude, longitude.")}
</div></section>
<section class="panel"><h2>O que a empresa executa</h2><p>Capacidade, serviços e escala operacional.</p><div class="grid">
{_field("services","Serviços",_csv(profile.get("services")),"estruturas metálicas, coberturas","Separados por vírgula.")}
{_field("capability_tags","Capabilities",_csv(profile.get("capability_tags")),"serralharia, montagem","Tags que ajudam a encontrar evidência de capacidade.")}
{_field("project_scales","Escalas de projecto",_csv(profile.get("project_scales")),"small, medium, large","Escalas suportadas pela empresa.")}
{_field("certifications","Certificações",_csv(profile.get("certifications")),"ISO 9001","Só entram se forem reais.")}
</div></section>
<section class="panel"><h2>Economia & prazo</h2><p>As regras vêm da própria empresa. O sistema não prevê lucro.</p><div class="grid">
{_field("min_value","Valor mínimo",profile.get("min_value"),"100000","Limite inferior da empresa.","number")}
{_field("max_value","Valor máximo",profile.get("max_value"),"1000000","Limite superior da empresa.","number")}
{_field("economic_min_score","Economic Fit mínimo",profile.get("economic_min_score"),"60","Pontuação mínima para considerar a oportunidade economicamente interessante.","number")}
{_field("min_deadline_days","Dias mínimos para preparar proposta",profile.get("min_deadline_days"),"10","Prazo mínimo aceitável.","number")}
{_field("max_deadline_days","Dias máximos",profile.get("max_deadline_days"),"90","Limite superior opcional.","number")}
</div></section>
<section class="panel"><h2>Procedimentos & exclusões</h2><p>Filtros claros para evitar desperdício comercial.</p><div class="grid">
{_field("preferred_procedure_types","Procedimentos preferidos",_csv(profile.get("preferred_procedure_types")),"OPEN","Separados por vírgula.")}
{_field("excluded_procedure_types","Procedimentos excluídos",_csv(profile.get("excluded_procedure_types")),"NEGOTIATED","Regras determinísticas.")}
{_field("exclude_keywords","Palavras excluídas",_csv(profile.get("exclude_keywords")),"ponte, estrada","Exclusões de texto.")}
{_field("hard_exclusions","Bloqueios rígidos",_csv(profile.get("hard_exclusions")),"certificação inexistente","Critérios que devem bloquear quando explicitamente comprovados.")}
</div></section>
<div class="note">💡 <span>Quanto mais concreta for esta configuração, melhor será a capacidade do ObraSignal de separar oportunidades interessantes de concursos que apenas parecem relevantes.</span></div>
<div class="actions"><a href="/radar"><button type="button" class="ghost">Cancelar</button></a><button type="submit">Guardar perfil</button></div>
</form></div></body></html>'''
