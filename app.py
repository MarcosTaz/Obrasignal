import os, sqlite3, threading, time, json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from flask import Flask, request, redirect, url_for, render_template_string, jsonify
import requests
APP=Flask(__name__); DB=os.getenv('OBRASIGNAL_DB',str(Path(__file__).with_name('obrasignal.db'))); TED_URL='https://api.ted.europa.eu/v3/notices/search'; BASE_URL='https://www.base.gov.pt/APIBase2'; POLL_SECONDS=int(os.getenv('POLL_SECONDS','300'))
HTML='''<!doctype html><html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ObraSignal</title><style>body{font-family:Arial;background:#0b1020;color:#eef2ff;margin:0}.wrap{max-width:1200px;margin:auto;padding:24px}.top{display:flex;justify-content:space-between;align-items:center}.muted{color:#9aa5bd}.card{background:#151d33;border:1px solid #293553;border-radius:14px;padding:16px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.stat{font-size:28px;font-weight:700}.row{display:flex;gap:10px;flex-wrap:wrap}input,button{background:#0f1629;color:#eef2ff;border:1px solid #354364;border-radius:9px;padding:10px}button{cursor:pointer;background:#2a5bd7;border:0}.tag{display:inline-block;padding:4px 8px;border-radius:999px;background:#26324e;margin:3px;font-size:12px}a{color:#8db4ff}.score{font-size:22px;font-weight:700}.small{font-size:13px}@media(max-width:800px){.grid{grid-template-columns:1fr 1fr}.top{flex-direction:column;align-items:flex-start}}</style></head><body><div class="wrap"><div class="top"><div><h1>OBRASIGNAL</h1><div class="muted">Radar automático de concursos e oportunidades de obra</div></div><form method="post" action="/sync"><button>Sincronizar agora</button></form></div><div class="grid"><div class="card"><div class="muted">Oportunidades</div><div class="stat">{{stats.total}}</div></div><div class="card"><div class="muted">Novas 24h</div><div class="stat">{{stats.new24}}</div></div><div class="card"><div class="muted">Alta relevância</div><div class="stat">{{stats.high}}</div></div><div class="card"><div class="muted">Última sincronização</div><div class="small">{{stats.last}}</div></div></div><div class="card"><h2>Filtro</h2><form method="get" class="row"><input name="q" placeholder="palavra-chave" value="{{q}}"><input name="country" placeholder="país ISO-3" value="{{country}}"><input name="minscore" type="number" min="0" max="100" placeholder="score mínimo" value="{{minscore}}"><button>Filtrar</button><a href="/">Limpar</a></form></div>{% for t in tenders %}<div class="card"><div class="row" style="justify-content:space-between"><div><span class="tag">{{t.source}}</span><span class="tag">{{t.publication_date or 'sem data'}}</span>{% if t.country %}<span class="tag">{{t.country}}</span>{% endif %}</div><div class="score">{{t.score}}/100</div></div><h2>{{t.title or 'Sem título'}}</h2><div>{{t.buyer or 'Entidade não identificada'}}</div><div class="muted small">{{t.value or 'Valor não indicado'}} · {{t.deadline or 'Prazo não indicado'}}</div><p class="small">{{t.description[:700] if t.description else ''}}</p><p><a href="{{t.url}}" target="_blank">Abrir fonte</a></p></div>{% endfor %}</div></body></html>'''
def db():
 c=sqlite3.connect(DB,check_same_thread=False); c.row_factory=sqlite3.Row; c.execute('''CREATE TABLE IF NOT EXISTS tenders(id INTEGER PRIMARY KEY AUTOINCREMENT,source TEXT NOT NULL,external_id TEXT NOT NULL,title TEXT,description TEXT,buyer TEXT,country TEXT,cpv TEXT,value TEXT,deadline TEXT,publication_date TEXT,url TEXT,score INTEGER DEFAULT 0,first_seen TEXT,last_seen TEXT,UNIQUE(source,external_id))'''); c.commit(); return c
def pick(o,*ks):
 for k in ks:
  v=o.get(k)
  if v not in (None,'',[],{}): return v
def flat(v):
 if v is None:return ''
 if isinstance(v,str):return v
 if isinstance(v,list):return ' | '.join(str(pick(x,'label','name','value','code') or x) if isinstance(x,dict) else str(x) for x in v)
 if isinstance(v,dict):return str(pick(v,'label','name','value','code') or json.dumps(v,ensure_ascii=False))
 return str(v)
def score(t,d,c):
 x=(t+' '+d+' '+c).lower(); s=30
 if any(k in x for k in ['construction','construção','obra','works','building','edifício','renovação','reabilitação','empreitada']):s+=25
 if any(k in x for k in ['metal','metallic','metálica','metálico','steel','aço','serralharia','structure','estrutura','pavilhão','warehouse','armazém']):s+=25
 if any(k in x for k in ['engineering','engenharia','project','projeto','design']):s+=8
 if c.startswith(('45','44','71')):s+=10
 return min(s,100)
def fetch_ted():
 p={'query':'buyer-country=PRT AND publication-date>=20260801','fields':['publication-number','notice-title','description-proc','buyer-name','buyer-country','classification-cpv','estimated-value-proc','deadline-date-lot','publication-date'],'limit':100,'scope':'ACTIVE','checkQuerySyntax':False,'paginationMode':'ITERATION'}
 r=requests.post(TED_URL,json=p,timeout=30); r.raise_for_status(); return r.json().get('notices',[])
def norm(n):
 e=flat(pick(n,'publication-number','publicationNumber','id')); t=flat(pick(n,'notice-title','noticeTitle','title')); d=flat(pick(n,'description-proc','descriptionProc','description')); b=flat(pick(n,'buyer-name','buyerName','buyer')); co=flat(pick(n,'buyer-country','buyerCountry','country')); c=flat(pick(n,'classification-cpv','cpvCodes','cpv')); v=flat(pick(n,'estimated-value-proc','estimatedValue','value')); dl=flat(pick(n,'deadline-date-lot','deadlineDate')); pu=flat(pick(n,'publication-date','publicationDate')); return dict(source='TED',external_id=e,title=t,description=d,buyer=b,country=co,cpv=c,value=v,deadline=dl,publication_date=pu,url=f'https://ted.europa.eu/en/notice/{e}/html' if e else 'https://ted.europa.eu/')
def fetch_base():
 tok=os.getenv('BASE_ACCESS_TOKEN','').strip()
 if not tok:return []
 r=requests.get(BASE_URL+'/GetInfoAnuncio',params={'numDias':90},headers={'_AcessToken':tok},timeout=30); r.raise_for_status(); data=r.json(); data=data if isinstance(data,list) else [data]; out=[]
 for n in data:
  e=str(pick(n,'nAnuncio','idAnuncio','idprocedimento') or ''); out.append(dict(source='BASE',external_id=e,title=flat(pick(n,'objectoContrato','descricao','descContrato')),description=flat(pick(n,'descContrato','descricao')),buyer=flat(pick(n,'adjudicante','entidadeAdjudicante')),country='PRT',cpv=flat(pick(n,'cpv')),value=flat(pick(n,'precoBaseProcedimento','precoContratual')),deadline=flat(pick(n,'dataLimiteApresentacaoPropostas','prazo')),publication_date=flat(pick(n,'dataPublicacao')),url='https://www.base.gov.pt/Base4/pt/pesquisa/'))
 return out
def save(rows):
 c=db(); now=datetime.now(timezone.utc).isoformat()
 for x in rows:
  if not x['external_id']:continue
  sc=score(x['title'],x['description'],x['cpv']); c.execute('''INSERT INTO tenders(source,external_id,title,description,buyer,country,cpv,value,deadline,publication_date,url,score,first_seen,last_seen) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source,external_id) DO UPDATE SET title=excluded.title,description=excluded.description,buyer=excluded.buyer,country=excluded.country,cpv=excluded.cpv,value=excluded.value,deadline=excluded.deadline,publication_date=excluded.publication_date,url=excluded.url,score=excluded.score,last_seen=excluded.last_seen''',(x['source'],x['external_id'],x['title'],x['description'],x['buyer'],x['country'],x['cpv'],x['value'],x['deadline'],x['publication_date'],x['url'],sc,now,now))
 c.commit()
def sync():
 rows=[]
 try:rows += [norm(x) for x in fetch_ted()]
 except Exception as e:print('TED:',e)
 try:rows += fetch_base()
 except Exception as e:print('BASE:',e)
 save(rows)
@APP.route('/')
def index():
 c=db(); q=request.args.get('q','').strip().lower(); country=request.args.get('country','').strip().upper()
 try:ms=int(request.args.get('minscore','0') or 0)
 except:ms=0
 sql='SELECT * FROM tenders WHERE score>=?'; args=[ms]
 if q:sql+=' AND lower(title||" "||description||" "||buyer||" "||cpv) LIKE ?'; args.append('%'+q+'%')
 if country:sql+=' AND upper(country)=?'; args.append(country)
 rows=c.execute(sql+' ORDER BY score DESC,first_seen DESC LIMIT 200',args).fetchall(); total=c.execute('SELECT COUNT(*) FROM tenders').fetchone()[0]; new24=c.execute('SELECT COUNT(*) FROM tenders WHERE first_seen>=?',((datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),)).fetchone()[0]; high=c.execute('SELECT COUNT(*) FROM tenders WHERE score>=70').fetchone()[0]; last=c.execute('SELECT MAX(last_seen) FROM tenders').fetchone()[0] or '—'; return render_template_string(HTML,tenders=rows,stats={'total':total,'new24':new24,'high':high,'last':last},q=q,country=country,minscore=ms)
@APP.post('/sync')
def do_sync():sync(); return redirect(url_for('index'))
@APP.get('/health')
def health():return jsonify(ok=True)
@APP.get('/api/tenders')
def api():
 c=db(); return jsonify([dict(x) for x in c.execute('SELECT * FROM tenders ORDER BY score DESC,first_seen DESC LIMIT 200').fetchall()])
def worker():
 while True:
  try:sync()
  except Exception as e:print('worker:',e)
  time.sleep(POLL_SECONDS)
if __name__=='__main__':
 db(); threading.Thread(target=worker,daemon=True).start(); APP.run(host='0.0.0.0',port=int(os.getenv('PORT','8080')))
