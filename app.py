import os, sqlite3, threading, time, json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from flask import Flask, request, redirect, url_for, render_template_string, jsonify
import requests

APP = Flask(__name__)
DB = os.getenv('OBRASIGNAL_DB', str(Path(__file__).with_name('obrasignal.db')))
TED_URL = 'https://api.ted.europa.eu/v3/notices/search'
BASE_URL = 'https://www.base.gov.pt/APIBase2'
POLL_SECONDS = int(os.getenv('POLL_SECONDS', '300'))
TED_DAYS = int(os.getenv('TED_DAYS', '30'))
TED_MAX_PAGES = int(os.getenv('TED_MAX_PAGES', '60'))

HTML = '''<!doctype html><html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ObraSignal</title><style>
body{font-family:Arial,sans-serif;background:#0b1020;color:#eef2ff;margin:0}.wrap{max-width:1200px;margin:auto;padding:24px}.top{display:flex;justify-content:space-between;align-items:center;gap:20px}.muted{color:#9aa5bd}.card{background:#151d33;border:1px solid #293553;border-radius:14px;padding:16px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.stat{font-size:28px;font-weight:700}.row{display:flex;gap:10px;flex-wrap:wrap}input,button{background:#0f1629;color:#eef2ff;border:1px solid #354364;border-radius:9px;padding:10px}button{cursor:pointer;background:#2a5bd7;border:0}.tag{display:inline-block;padding:4px 8px;border-radius:999px;background:#26324e;margin:3px;font-size:12px}a{color:#8db4ff}.score{font-size:22px;font-weight:700}.small{font-size:13px}.title{margin-bottom:8px}@media(max-width:800px){.grid{grid-template-columns:1fr 1fr}.top{flex-direction:column;align-items:flex-start}}
</style></head><body><div class="wrap"><div class="top"><div><h1>OBRASIGNAL</h1><div class="muted">Radar automático de concursos e oportunidades de obra</div></div><form method="post" action="/sync"><button>Sincronizar agora</button></form></div>
<div class="grid"><div class="card"><div class="muted">Oportunidades</div><div class="stat">{{stats.total}}</div></div><div class="card"><div class="muted">Novas 24h</div><div class="stat">{{stats.new24}}</div></div><div class="card"><div class="muted">Alta relevância</div><div class="stat">{{stats.high}}</div></div><div class="card"><div class="muted">Última sincronização</div><div class="small">{{stats.last}}</div></div></div>
<div class="card"><h2>Filtro</h2><form method="get" class="row"><input name="q" placeholder="palavra-chave" value="{{q}}"><input name="country" placeholder="país ISO-3" value="{{country}}"><input name="minscore" type="number" min="0" max="100" placeholder="score mínimo" value="{{minscore}}"><button>Filtrar</button><a href="/">Limpar</a></form></div>
{% for t in tenders %}<div class="card"><div class="row" style="justify-content:space-between"><div><span class="tag">{{t.source}}</span><span class="tag">{{t.publication_date or 'sem data'}}</span>{% if t.country %}<span class="tag">{{t.country}}</span>{% endif %}</div><div class="score">{{t.score}}/100</div></div><h2 class="title">{{t.title or 'Sem título'}}</h2><div>{{t.buyer or 'Entidade não identificada'}}</div><div class="muted small">{{t.value or 'Valor não indicado'}} · {{t.deadline or 'Prazo não indicado'}}</div><p class="small">{{t.description[:900] if t.description else ''}}</p>{% if t.cpv %}<div>{% for x in t.cpv.split('|')[:10] %}<span class="tag">{{x}}</span>{% endfor %}</div>{% endif %}<p><a href="{{t.url}}" target="_blank">Abrir fonte</a></p></div>{% endfor %}
</div></body></html>'''

def db():
    c=sqlite3.connect(DB, check_same_thread=False); c.row_factory=sqlite3.Row
    c.execute('''CREATE TABLE IF NOT EXISTS tenders(id INTEGER PRIMARY KEY AUTOINCREMENT,source TEXT NOT NULL,external_id TEXT NOT NULL,title TEXT,description TEXT,buyer TEXT,country TEXT,cpv TEXT,value TEXT,deadline TEXT,publication_date TEXT,url TEXT,score INTEGER DEFAULT 0,first_seen TEXT,last_seen TEXT,UNIQUE(source,external_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS sync_runs(id INTEGER PRIMARY KEY AUTOINCREMENT,started_at TEXT NOT NULL,finished_at TEXT,found INTEGER DEFAULT 0,new_items INTEGER DEFAULT 0)''')
    c.commit(); return c

def pick(o,*ks):
    if not isinstance(o,dict): return None
    for k in ks:
        v=o.get(k)
        if v not in (None,'',[],{}): return v
    return None

def lang_value(v):
    if isinstance(v,str):
        s=v.strip()
        if s.startswith('{') and s.endswith('}'):
            try: return lang_value(json.loads(s))
            except Exception: return v
        return v
    if isinstance(v,dict):
        preferred=['pt','pt-PT','por','en','en-GB','eng']
        for key in preferred:
            if key in v and v[key] not in (None,''): return lang_value(v[key])
        for key,val in v.items():
            if isinstance(key,str) and (key.lower().startswith('pt') or key.lower().startswith('por')) and val not in (None,''): return lang_value(val)
        for val in v.values():
            if isinstance(val,(str,dict)) and val not in (None,''): return lang_value(val)
        return ''
    if isinstance(v,list):
        vals=[lang_value(x) for x in v]
        return ' | '.join(x for x in vals if x)
    return str(v) if v is not None else ''

def flat(v):
    if isinstance(v,list):
        vals=[]
        for x in v:
            if isinstance(x,dict): vals.append(lang_value(pick(x,'label','name','value','code') or x))
            else: vals.append(lang_value(x))
        return ' | '.join(x for x in vals if x)
    return lang_value(v)

def score(t,d,c):
    x=(t+' '+d+' '+c).lower(); s=20
    if any(k in x for k in ['construction','construção','obra','works','building','edifício','renovação','reabilitação','empreitada']): s+=25
    if any(k in x for k in ['metal','metallic','metálica','metálico','steel','aço','serralharia','structure','estrutura','pavilhão','warehouse','armazém']): s+=25
    if any(k in x for k in ['engineering','engenharia','project','projeto','design']): s+=10
    if c.startswith(('45','44','71')): s+=10
    return min(s,100)

def fetch_ted():
    since=(datetime.now(timezone.utc)-timedelta(days=TED_DAYS)).strftime('%Y%m%d')
    payload={'query':f'buyer-country=PRT AND publication-date>={since}','fields':['publication-number','notice-title','description-proc','buyer-name','buyer-country','classification-cpv','estimated-value-proc','estimated-value-cur-proc','deadline-date-lot','publication-date'],'limit':250,'scope':'ACTIVE','checkQuerySyntax':False,'paginationMode':'ITERATION'}
    rows=[]; token=None
    for _ in range(TED_MAX_PAGES):
        body=dict(payload)
        if token: body['iterationNextToken']=token
        r=requests.post(TED_URL,json=body,timeout=45); r.raise_for_status(); data=r.json()
        batch=data.get('notices') or data.get('results') or data.get('content') or []
        rows.extend(batch)
        token=data.get('iterationNextToken') or data.get('nextToken') or data.get('nextIterationToken')
        if not token or not batch: break
    return rows

def normalize_ted(n):
    ext=flat(pick(n,'publication-number','publicationNumber','id'))
    title=flat(pick(n,'notice-title','noticeTitle','title'))
    desc=flat(pick(n,'description-proc','descriptionProc','description'))
    buyer=flat(pick(n,'buyer-name','buyerName','buyer'))
    country=flat(pick(n,'buyer-country','buyerCountry','country'))
    cpv=flat(pick(n,'classification-cpv','cpvCodes','cpv'))
    value=flat(pick(n,'estimated-value-proc','estimatedValue','value'))
    deadline=flat(pick(n,'deadline-date-lot','deadlineDate'))
    pub=flat(pick(n,'publication-date','publicationDate'))
    url=f'https://ted.europa.eu/en/notice/{ext}/html' if ext else 'https://ted.europa.eu/'
    return dict(source='TED',external_id=ext,title=title,description=desc,buyer=buyer,country=country,cpv=cpv,value=value,deadline=deadline,publication_date=pub,url=url)

def fetch_base():
    token=os.getenv('BASE_ACCESS_TOKEN','').strip()
    if not token:return []
    r=requests.get(BASE_URL+'/GetInfoAnuncio',params={'numDias':90},headers={'_AcessToken':token},timeout=45); r.raise_for_status()
    data=r.json(); data=data if isinstance(data,list) else [data]; out=[]
    for n in data:
        ext=str(pick(n,'nAnuncio','idAnuncio','idprocedimento') or '')
        out.append(dict(source='BASE',external_id=ext,title=flat(pick(n,'objectoContrato','descricao','descContrato')),description=flat(pick(n,'descContrato','descricao')),buyer=flat(pick(n,'adjudicante','entidadeAdjudicante')),country='PRT',cpv=flat(pick(n,'cpv')),value=flat(pick(n,'precoBaseProcedimento','precoContratual')),deadline=flat(pick(n,'dataLimiteApresentacaoPropostas','prazo')),publication_date=flat(pick(n,'dataPublicacao')),url='https://www.base.gov.pt/Base4/pt/pesquisa/'))
    return out

def save(rows):
    c=db(); now=datetime.now(timezone.utc).isoformat(); new_items=0
    for x in rows:
        if not x['external_id']: continue
        exists=c.execute('SELECT id FROM tenders WHERE source=? AND external_id=?',(x['source'],x['external_id'])).fetchone()
        sc=score(x['title'],x['description'],x['cpv'])
        if exists:
            c.execute('''UPDATE tenders SET title=?,description=?,buyer=?,country=?,cpv=?,value=?,deadline=?,publication_date=?,url=?,score=?,last_seen=? WHERE id=?''',(x['title'],x['description'],x['buyer'],x['country'],x['cpv'],x['value'],x['deadline'],x['publication_date'],x['url'],sc,now,exists['id']))
        else:
            c.execute('''INSERT INTO tenders(source,external_id,title,description,buyer,country,cpv,value,deadline,publication_date,url,score,first_seen,last_seen) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(x['source'],x['external_id'],x['title'],x['description'],x['buyer'],x['country'],x['cpv'],x['value'],x['deadline'],x['publication_date'],x['url'],sc,now,now)); new_items+=1
    c.commit(); return new_items

def sync():
    c=db(); started=datetime.now(timezone.utc).isoformat(); rows=[]
    try: rows += [normalize_ted(x) for x in fetch_ted()]
    except Exception as e: print('TED sync error:',e)
    try: rows += fetch_base()
    except Exception as e: print('BASE sync error:',e)
    new_items=save(rows)
    c.execute('INSERT INTO sync_runs(started_at,finished_at,found,new_items) VALUES(?,?,?,?)',(started,datetime.now(timezone.utc).isoformat(),len(rows),new_items)); c.commit(); return len(rows),new_items

@APP.route('/')
def index():
    c=db(); q=request.args.get('q','').strip().lower(); country=request.args.get('country','').strip().upper()
    try: ms=int(request.args.get('minscore','0') or 0)
    except: ms=0
    sql='SELECT * FROM tenders WHERE score>=?'; args=[ms]
    if q: sql+=' AND lower(title||" "||description||" "||buyer||" "||cpv) LIKE ?'; args.append('%'+q+'%')
    if country: sql+=' AND upper(country)=?'; args.append(country)
    rows=c.execute(sql+' ORDER BY score DESC, first_seen DESC LIMIT 500',args).fetchall()
    total=c.execute('SELECT COUNT(*) FROM tenders').fetchone()[0]
    new24=c.execute('SELECT COUNT(*) FROM tenders WHERE first_seen>=?',((datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),)).fetchone()[0]
    high=c.execute('SELECT COUNT(*) FROM tenders WHERE score>=70').fetchone()[0]
    last=c.execute('SELECT MAX(finished_at) FROM sync_runs').fetchone()[0] or '—'
    return render_template_string(HTML,tenders=rows,stats={'total':total,'new24':new24,'high':high,'last':last},q=q,country=country,minscore=ms)

@APP.post('/sync')
def do_sync(): sync(); return redirect(url_for('index'))
@APP.get('/health')
def health(): return jsonify(ok=True)
@APP.get('/api/tenders')
def api():
    c=db(); return jsonify([dict(x) for x in c.execute('SELECT * FROM tenders ORDER BY score DESC,first_seen DESC LIMIT 500').fetchall()])

def worker():
    while True:
        try: sync()
        except Exception as e: print('worker:',e)
        time.sleep(POLL_SECONDS)

if __name__=='__main__':
    db(); threading.Thread(target=worker,daemon=True).start(); APP.run(host='0.0.0.0',port=int(os.getenv('PORT','8080')))
