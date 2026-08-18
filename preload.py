"""Production preload layer for ObraSignal.
Loaded by Gunicorn before exposing app.APP.
"""
import re
from datetime import datetime, timezone, timedelta
import app as _app

# ---------- Better TED deadline extraction ----------
def _deadline_from_notice(n):
    dates = n.get("deadline-receipt-tender-date-lot") or n.get("deadline-date-lot") or []
    times = n.get("deadline-receipt-tender-time-lot") or n.get("deadline-time-lot") or []
    if isinstance(dates, (str, dict)): dates=[dates]
    if isinstance(times, (str, dict)): times=[times]
    out=[]
    for i, raw in enumerate(dates or []):
        if isinstance(raw, dict): raw=raw.get("value") or raw.get("date") or raw.get("deadline") or ""
        raw=str(raw).strip()
        if not raw: continue
        d=raw[:10]
        tm=""
        if i < len(times or []):
            tv=times[i]
            if isinstance(tv, dict): tv=tv.get("value") or tv.get("time") or ""
            tm=str(tv).strip()
        out.append(f"{d}T{tm}" if tm else d)
    return max(out) if out else ""


def _fetch_ted():
    since=(datetime.now(timezone.utc)-timedelta(days=_app.TED_DAYS)).strftime("%Y%m%d")
    fields=["publication-number","notice-title","description-proc","buyer-name","buyer-country",
            "classification-cpv","estimated-value-proc","estimated-value-cur-proc",
            "deadline-receipt-tender-date-lot","deadline-receipt-tender-time-lot",
            "deadline-date-lot","deadline-time-lot","publication-date","notice-type","form-type",
            "main-classification-type-proc"]
    payload={"query":f"buyer-country=PRT AND publication-date>={since}","fields":fields,
             "limit":250,"scope":"ACTIVE","checkQuerySyntax":False,"paginationMode":"ITERATION"}
    rows=[]; token=None
    for _ in range(_app.TED_MAX_PAGES):
        body=dict(payload)
        if token: body["iterationNextToken"]=token
        r=_app.requests.post(_app.TED_URL,json=body,timeout=45); r.raise_for_status()
        data=r.json(); batch=data.get("notices") or data.get("results") or data.get("content") or []
        rows.extend(batch)
        token=data.get("iterationNextToken") or data.get("nextToken") or data.get("nextIterationToken")
        if not token or not batch: break
    return rows

_ORIGINAL_NORMALIZE_TED=_app.normalize_ted

def _normalize_ted(n):
    x=_ORIGINAL_NORMALIZE_TED(n)
    deadline=_deadline_from_notice(n)
    if deadline: x["deadline"]=deadline
    # TED /html is the downloadable HTML representation. The notice-view URL
    # is the browser page intended for normal human navigation.
    ext=x.get("external_id")
    if ext:
        x["url"]=f"https://ted.europa.eu/en/notice/-/detail/{ext}"
    return x

_app.fetch_ted=_fetch_ted
_app.normalize_ted=_normalize_ted

# ---------- Calibrated commercial score ----------
STRONG={
    "metalomecânica":26,"metalomecanica":26,"estruturas metálicas":27,"estruturas metalicas":27,
    "estrutura metálica":25,"estrutura metalica":25,"serralharia":23,"serralheiro":20,
    "pavilhão":19,"pavilhoes":19,"pavilhao":19,"armazém":18,"armazem":18,"warehouse":17,
    "cobertura":17,"coberturas":17,"fachada":15,"fachadas":15,"steel":17,"aço":17,"aco":17,
    "montagem":14,"montagem de estruturas":18}
MEDIUM={"empreitada":11,"empreitadas":11,"execução":8,"execucao":8,"construção":8,"construcao":8,
        "construction":8,"obra":6,"obras":6,"reabilitação":8,"reabilitacao":8,"remodelação":7,
        "remodelacao":7,"renovação":6,"renovacao":6,"engenharia":3,"engineering":3}
NEG={"arquitetura":-18,"arquitectura":-18,"architecture":-18,"fiscalização":-20,"fiscalizacao":-20,
     "consultoria":-18,"consulting":-18,"topografia":-18,"topographic":-18,"geologia":-18,
     "geotechnical":-18,"estudo":-12,"estudos":-12,"study":-12,"auditoria":-12,"audit":-12,
     "formação":-15,"formacao":-15,"training":-15}

def _deadline_dt(value):
    if not value: return None
    s=str(value).strip().replace("Z","+00:00").replace(" ","T")
    if len(s)>=13 and s[10] in "+-" and "T" not in s: s=s[:10]
    for fn in (lambda:datetime.fromisoformat(s).astimezone(timezone.utc),
               lambda:datetime.strptime(s[:10],"%Y-%m-%d").replace(tzinfo=timezone.utc),
               lambda:datetime.strptime(s[:8],"%Y%m%d").replace(tzinfo=timezone.utc)):
        try: return fn()
        except Exception: pass
    return None

def _score(title, desc, cpv, deadline=None):
    text=re.sub(r"\s+"," ",f"{title or ''} {desc or ''}".lower()); cpvtext=(cpv or "").replace(" ","")
    score=24; strong_hits=[]; medium_hits=[]; penalties=[]
    for k,v in STRONG.items():
        if k in text: score+=v; strong_hits.append(k)
    for k,v in MEDIUM.items():
        if k in text: score+=v; medium_hits.append(k)
    for k,v in NEG.items():
        if k in text: score+=v; penalties.append(k)
    if cpvtext.startswith("45"): score+=9
    elif cpvtext.startswith("44"): score+=5
    elif cpvtext.startswith(("42","43")): score+=3
    elif cpvtext.startswith("71"): score-=2
    execution=any(k in text for k in ("execução","execucao","empreitada","empreitadas","montagem","construção","construcao","construction","works"))
    if execution: score+=7
    pure_intellectual=any(k in text for k in ("serviços de arquitetura","servicos de arquitetura","architecture services","serviços de fiscalização","servicos de fiscalizacao","consultoria")) and not execution and not strong_hits
    if pure_intellectual: score-=16; penalties.append("serviço predominantemente intelectual")
    dd=_deadline_dt(deadline); days=None
    if dd:
        days=(dd-datetime.now(timezone.utc)).total_seconds()/86400
        if days<0: score-=35
        elif days<=2: score+=10
        elif days<=7: score+=7
        elif days<=21: score+=4
        elif days<=60: score+=1
    score=max(0,min(99,int(round(score))))
    if score>=80: label,cls="PRIORIDADE MÁXIMA","hot"
    elif score>=62: label,cls="BOA OPORTUNIDADE","good"
    elif score>=45: label,cls="ANALISAR","good"
    else: label,cls="BAIXA PRIORIDADE","low"
    hits=list(dict.fromkeys(strong_hits+medium_hits))
    reason=("forte correspondência com "+", ".join(hits[:5])) if hits else "correspondência geral com obra"
    if days is not None:
        if days<0: reason+=f"; prazo expirado há {max(1,int(-days))} dias"
        elif days<=7: reason+=f"; prazo curto ({max(0,int(days))} dias)"
    if penalties: reason+="; penalizado por "+", ".join(dict.fromkeys(penalties[:2]))
    return score,label,cls,reason

_app.commercial_score=_score

def _recalibrate_database():
    c=_app.db(); rows=c.execute("SELECT id,title,description,cpv,deadline FROM tenders").fetchall()
    for r in rows:
        sc,label,cls,reason=_score(r["title"],r["description"],r["cpv"],r["deadline"])
        c.execute("UPDATE tenders SET score=?,match_reason=?,priority_label=?,priority_class=? WHERE id=?",(sc,reason,label,cls,r["id"]))
    c.commit(); c.close()

# ---------- Deadline-aware dashboard ----------
DEADLINE_HELP='<style>.state{display:inline-block;padding:5px 9px;border-radius:999px;font-size:12px;font-weight:800;margin:5px 0}.state-open{background:#123b2a;color:#7ee787}.state-urgent{background:#4b3410;color:#ffd866}.state-closed{background:#3a1c24;color:#ff9aa8}.state-none{background:#30384d;color:#c7d0e2}.days{font-size:12px;color:#9aa5bd;margin-left:6px}</style>'

def _deadline_html(value):
    dt=_deadline_dt(value)
    if not dt: return '<span class="state state-none">PRAZO NÃO INDICADO</span>'
    days=(dt-datetime.now(timezone.utc)).total_seconds()/86400
    if days<0: return f'<span class="state state-closed">TERMINADO</span><span class="days">há {max(1,int(-days))} dias</span>'
    if days<=2: return f'<span class="state state-urgent">URGENTE</span><span class="days">{max(0,int(days))} dias restantes</span>'
    if days<=7: return f'<span class="state state-urgent">PRAZO CURTO</span><span class="days">{int(days)} dias restantes</span>'
    return f'<span class="state state-open">ABERTO</span><span class="days">{int(days)} dias restantes</span>'

_original_html=_app.HTML.replace('</style></head>',DEADLINE_HELP+'</style></head>')
_old_top='<div class="small deadline">Prazo: {{t.deadline or \'não indicado\'}}</div>'
_new_top='<div class="small deadline">Prazo: {{t.deadline or \'não indicado\'}}</div><div>{{deadline_badges(t.deadline) | safe}}</div>'
_original_html=_original_html.replace(_old_top,_new_top)
_old_list='<div class="muted small">{{t.value or \'Valor não indicado\'}} · {{t.deadline or \'Prazo não indicado\'}}</div>'
_new_list='<div class="muted small">{{t.value or \'Valor não indicado\'}} · {{t.deadline or \'Prazo não indicado\'}}</div><div>{{deadline_badges(t.deadline) | safe}}</div>'
_original_html=_original_html.replace(_old_list,_new_list)
_app.HTML=_original_html
_orig_render=_app.render_template_string

def _render(template,*args,**kwargs):
    if template is _app.HTML or (isinstance(template,str) and "TOP OPORTUNIDADES DE HOJE" in template): kwargs["deadline_badges"]=_deadline_html
    return _orig_render(template,*args,**kwargs)
_app.render_template_string=_render

_recalibrate_database()
APP=_app.APP
