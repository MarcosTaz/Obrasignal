import os,sqlite3,threading,time,json,re
from pathlib import Path
from datetime import datetime,timezone,timedelta
from flask import Flask,request,redirect,url_for,render_template_string,jsonify
import requests

APP=Flask(__name__)
DB=os.getenv('OBRASIGNAL_DB',str(Path(__file__).with_name('obrasignal.db')))
TED_URL='https://api.ted.europa.eu/v3/notices/search'
BASE_URL='https://www.base.gov.pt/APIBase2'
POLL_SECONDS=int(os.getenv('POLL_SECONDS','300')); TED_DAYS=int(os.getenv('TED_DAYS','30')); TED_MAX_PAGES=int(os.getenv('TED_MAX_PAGES','60'))

HTML='''<!doctype html><html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ObraSignal</title><style>
body{font-family:Arial,sans-serif;background:#0b1020;color:#eef2ff;margin:0}.wrap{max-width:1200px;margin:auto;padding:24px}.top{display:flex;justify-content:space-between;align-items:center;gap:20px}.muted{color:#9aa5bd}.card{background:#151d33;border:1px solid #293553;border-radius:14px;padding:16px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.stat{font-size:28px;font-weight:700}.row{display:flex;gap:10px;flex-wrap:wrap}input,button{background:#0f1629;color:#eef2ff;border:1px solid #354364;border-radius:9px;padding:10px}button{cursor:pointer;background:#2a5bd7;border:0}.tag{display:inline-block;padding:4px 8px;border-radius:999px;background:#26324e;margin:3px;font-size:12px}a{color:#8db4ff}.score{font-size:22px;font-weight:700}.small{font-size:13px}.title{margin:6px 0 8px}.reason{margin-top:10px;padding:9px;border-radius:9px;background:#10182b;color:#b9c6df;font-size:13px}.hot{color:#7ee787}.good{color:#8db4ff}.low{color:#9aa5bd}.hero{border:1px solid #3d5f9d;background:#111b31}.hero h2{margin-top:4px}.rank{font-size:13px;font-weight:700;letter-spacing:.5px;color:#9fb9ff}.deadline{font-weight:700}.topgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.topcard{margin:0}.topmeta{display:flex;justify-content:space-between;gap:10px;align-items:center}.pill{padding:5px 9px;border-radius:999px;background:#22304e;font-size:12px}.empty{color:#9aa5bd;padding:12px 0}.market{margin-bottom:12px}.market button{background:#22304e}.market button.active{background:#2a5bd7}@media(max-width:800px){.grid,.topgrid{grid-template-columns:1fr 1fr}.top{flex-direction:column;align-items:flex-start}}@media(max-width:560px){.grid,.topgrid{grid-template-columns:1fr}}
</style></head><body><div class="wrap"><div class="top"><div><h1>OBRASIGNAL</h1><div class="muted">Radar automático de concursos e oportunidades de obra</div></div><form method="post" action="/sync"><button>Sincronizar agora</button></form></div>
<div class="card market"><div class="rank">MERCADO</div><div class="row"><a href="/?market=PT"><button class="{{'active' if market=='PT' else ''}}">🇵🇹 Portugal</button></a><a href="/?market=EU"><button class="{{'active' if market=='EU' else ''}}">🇪🇺 Europa</button></a><a href="/?market=ALL"><button class="{{'active' if market=='ALL' else ''}}">🌍 Todos</button></a></div><div class="small muted">Europa usa TED; Portugal acrescenta a fonte BASE quando configurada.</div></div>
<div class="grid"><div class="card"><div class="muted">Oportunidades</div><div class="stat">{{stats.total}}</div></div><div class="card"><div class="muted">Novas 24h</div><div class="stat">{{stats.new24}}</div></div><div class="card"><div class="muted">Alta relevância</div><div class="stat">{{stats.high}}</div></div><div class="card"><div class="muted">Última sincronização</div><div class="small">{{stats.last}}</div></div></div>
<div class="card hero"><div class="topmeta"><div><div class="rank">TOP OPORTUNIDADES DE HOJE</div><h2>{{'Europa' if market=='EU' else 'Portugal' if market=='PT' else 'Todos os mercados'}}</h2></div><span class="pill">{{top|length}} selecionadas</span></div><div class="topgrid">{% for t in top %}<div class="card topcard"><div class="topmeta"><span class="pill">#{{loop.index}} · {{t.source}} · {{t.country or '—'}}</span><span class="score">{{t.score}}/100</span></div><h3 class="title">{{t.title or 'Sem título'}}</h3><div>{{t.buyer or 'Entidade não identificada'}}</div><div class="small muted">Publicada: {{t.publication_date or 'sem data'}}</div><div class="small deadline">Prazo: {{t.deadline or 'não indicado'}}</div>{% if t.value %}<div class="small">Valor: {{t.value}}</div>{% endif %}<div class="reason"><span class="{{t.priority_class}}">{{t.priority_label}}</span> — {{t.match_reason}}</div><p><a href="{{t.url}}" target="_blank">Abrir oportunidade →</a></p></div>{% endfor %}</div>{% if not top %}<div class="empty">Ainda não há oportunidades classificadas.</div>{% endif %}</div>
<div class="card"><h2>Filtro</h2><form method="get" class="row"><input type="hidden" name="market" value="{{market}}"><input name="q" placeholder="palavra-chave" value="{{q}}"><input name="country" placeholder="país ISO-3" value="{{country}}"><input name="minscore" type="number" min="0" max="100" placeholder="score mínimo" value="{{minscore}}"><button>Filtrar</button><a href="/?market={{market}}">Limpar</a></form></div>
{% for t in tenders %}<div class="card"><div class="row" style="justify-content:space-between"><div><span class="tag">{{t.source}}</span><span class="tag">{{t.publication_date or 'sem data'}}</span>{% if t.country %}<span class="tag">{{t.country}}</span>{% endif %}</div><div class="score">{{t.score}}/100</div></div><h2 class="title">{{t.title or 'Sem título'}}</h2><div>{{t.buyer or 'Entidade não identificada'}}</div><div class="muted small">{{t.value or 'Valor não indicado'}} · {{t.deadline or 'Prazo não indicado'}}</div><p class="small">{{t.description[:900] if t.description else ''}}</p>{% if t.match_reason %}<div class="reason"><span class="{{t.priority_class}}">{{t.priority_label}}</span> — {{t.match_reason}}</div>{% endif %}{% if t.cpv %}<div>{% for x in t.cpv.split('|')[:10] %}<span class="tag">{{x}}</span>{% endfor %}</div>{% endif %}<p><a href="{{t.url}}" target="_blank">Abrir fonte</a></p></div>{% endfor %}</div></body></html>'''

def db():
 c=sqlite3.connect(DB,check_same_thread=False);c.row_factory=sqlite3.Row
 c.execute('''CREATE TABLE IF NOT EXISTS tenders(id INTEGER PRIMARY KEY AUTOINCREMENT,source TEXT NOT NULL,external_id TEXT NOT NULL,title TEXT,description TEXT,buyer TEXT,country TEXT,cpv TEXT,value TEXT,deadline TEXT,publication_date TEXT,url TEXT,score INTEGER DEFAULT 0,first_seen TEXT,last_seen TEXT,UNIQUE(source,external_id))''')
 c.execute('''CREATE TABLE IF NOT EXISTS sync_runs(id INTEGER PRIMARY KEY AUTOINCREMENT,started_at TEXT NOT NULL,finished_at TEXT,found INTEGER DEFAULT 0,new_items INTEGER DEFAULT 0)''')
 cols=[r['name'] for r in c.execute('PRAGMA table_info(tenders)').fetchall()]
 for col in ['published_at','match_reason','priority_label','priority_class','market']:
  if col not in cols:c.execute(f'ALTER TABLE tenders ADD COLUMN {col} TEXT')
 c.commit();return c

def pick(o,*ks):
 if not isinstance(o,dict):return None
 for k in ks:
  v=o.get(k)
  if v not in (None,'',[],{}):return v

def lang_value(v):
 if isinstance(v,str):
  s=v.strip()
  if s.startswith('{') and s.endswith('}'):
   try:return lang_value(json.loads(s))
   except Exception:return v
  return v
 if isinstance(v,dict):
  for k in ('pt','pt-PT','por','en','en-GB','eng'):
   if k in v and v[k] not in (None,''):return lang_value(v[k])
  for k,val in v.items():
   if isinstance(k,str) and k.lower().startswith(('pt','por')) and val not in (None,''):return lang_value(val)
  for val in v.values():
   if isinstance(val,(str,dict)) and val not in (None,''):return lang_value(val)
  return ''
 if isinstance(v,list):return ' | '.join(x for x in (lang_value(i) for i in v) if x)
 return str(v) if v is not None else ''

def flat(v):
 if isinstance(v,list):return ' | '.join(x for x in (lang_value(pick(i,'label','name','value','code') or i) if isinstance(i,dict) else lang_value(i) for i in v) if x)
 return lang_value(v)

def parse_date(v):
 if not v:return None
 s=str(v).strip().replace('Z','+00:00')
 for fn in (lambda:datetime.fromisoformat(s).astimezone(timezone.utc),lambda:datetime.strptime(s[:10],'%Y-%m-%d').replace(tzinfo=timezone.utc),lambda:datetime.strptime(s[:8],'%Y%m%d').replace(tzinfo=timezone.utc)):
  try:return fn().isoformat()
  except Exception:pass
 return None

def deadline_dt(v):
 if not v:return None
 s=str(v).strip().replace('Z','+00:00')
 for fn in (lambda:datetime.fromisoformat(s).astimezone(timezone.utc),lambda:datetime.strptime(s[:10],'%Y-%m-%d').replace(tzinfo=timezone.utc),lambda:datetime.strptime(s[:8],'%Y%m%d').replace(tzinfo=timezone.utc)):
  try:return fn()
  except Exception:pass
 return None

POS={'metalomecânica':28,'metalomecanica':28,'estrutura metálica':30,'estruturas metálicas':30,'estrutura metalica':30,'estruturas metalicas':30,'serralharia':26,'steel':22,'aço':22,'aco':22,'metal':18,'metálica':24,'metalica':24,'metálico':24,'metalico':24,'pavilhão':24,'pavilhões':24,'pavilhao':24,'armazém':22,'armazem':22,'warehouse':22,'cobertura':20,'coberturas':20,'fachada':18,'fachadas':18,'montagem':16,'empreitada':16,'empreitadas':16,'construção':12,'construcao':12,'construction':12,'obra':12,'obras':12,'reabilitação':14,'reabilitacao':14,'renovação':12,'renovacao':12,'engenharia':6,'engineering':6}
NEG={'arquitetura':-18,'arquitectura':-18,'architecture':-18,'fiscalização':-22,'fiscalizacao':-22,'consultoria':-20,'consulting':-20,'estudo':-18,'estudos':-18,'study':-18,'topografia':-20,'topographic':-20,'geologia':-20,'geotechnical':-20,'auditoria':-15,'audit':-15,'formação':-18,'formacao':-18,'training':-18}

def commercial_score(t,d,c,deadline=None):
 text=re.sub(r'\s+',' ',(t+' '+d+' '+c).lower());score=18;hits=[];pen=[]
 for k,v in POS.items():
  if k in text:score+=v;hits.append(k)
 for k,v in NEG.items():
  if k in text:score+=v;pen.append(k)
 cpv=(c or '').replace(' ','')
 if cpv.startswith('45'):score+=18
 elif cpv.startswith('44'):score+=12
 elif cpv.startswith(('42','43')):score+=5
 elif cpv.startswith('71'):score+=2
 execution=any(k in text for k in ('execução','execucao','empreitada','montagem','construção','construcao','works','construction'))
 if any(k in text for k in ('serviços de arquitetura','servicos de arquitetura','architecture services','fiscalização','fiscalizacao','consultoria')) and not execution:score-=18;pen.append('serviço predominantemente intelectual')
 dd=deadline_dt(deadline)
 if dd:
  days=(dd-datetime.now(timezone.utc)).total_seconds()/86400
  if 0<=days<=7:score+=10
  elif 7<days<=21:score+=5
  elif days<0:score-=30
 score=max(0,min(100,score))
 label,cls=('PRIORIDADE MÁXIMA','hot') if score>=75 else ('BOA OPORTUNIDADE','good') if score>=55 else ('BAIXA PRIORIDADE','low')
 reason='forte correspondência com '+', '.join(dict.fromkeys(hits[:5])) if hits else 'correspondência geral com obra'
 if dd:
  days=(dd-datetime.now(timezone.utc)).total_seconds()/86400
  if 0<=days<=7:reason+=f'; prazo em {max(0,int(days))} dias'
 if pen:reason+='; penalizado por '+', '.join(pen[:2])
 return score,label,cls,reason

TED_NOTICE_TYPES=('cn-standard','cn-social','cn-desg','subco','qu-sy')

def fetch_ted():
 since=(datetime.now(timezone.utc)-timedelta(days=TED_DAYS)).strftime('%Y%m%d')
 query=f'publication-date>={since} AND (notice-type=cn-standard OR notice-type=cn-social OR notice-type=cn-desg OR notice-type=subco OR notice-type=qu-sy)'
 fields=['publication-number','notice-title','description-proc','buyer-name','buyer-country','classification-cpv','estimated-value-proc','estimated-value-cur-proc','deadline-receipt-tender-date-lot','deadline-receipt-tender-time-lot','deadline-date-lot','deadline-time-lot','publication-date','notice-type','form-type','main-classification-type-proc','place-of-performance-country-proc','place-of-performance-city-proc','place-of-performance-subdiv-proc','place-of-performance-post-code-proc','place-of-performance-country-lot','place-of-performance-city-lot','place-of-performance-subdiv-lot']
 payload={'query':query,'fields':fields,'limit':250,'scope':'ACTIVE','checkQuerySyntax':False,'paginationMode':'ITERATION'};rows=[];token=None
 for _ in range(TED_MAX_PAGES):
  body=dict(payload)
  if token:body['iterationNextToken']=token
  r=requests.post(TED_URL,json=body,timeout=45);r.raise_for_status();data=r.json();batch=data.get('notices') or data.get('results') or data.get('content') or [];rows+=batch;token=data.get('iterationNextToken') or data.get('nextToken') or data.get('nextIterationToken')
  if not token or not batch:break
 return rows

def normalize_ted(n):
 ext=flat(pick(n,'publication-number','publicationNumber','id'));title=flat(pick(n,'notice-title','noticeTitle','title'));desc=flat(pick(n,'description-proc','descriptionProc','description'));buyer=flat(pick(n,'buyer-name','buyerName','buyer'));country=flat(pick(n,'buyer-country','buyerCountry','country'));cpv=flat(pick(n,'classification-cpv','cpvCodes','cpv'));value=flat(pick(n,'estimated-value-proc','estimatedValue','value'));deadline=flat(pick(n,'deadline-receipt-tender-date-lot','deadline-date-lot','deadlineDate'));pub=flat(pick(n,'publication-date','publicationDate'));place_country=flat(pick(n,'place-of-performance-country-proc','place-of-performance-country-lot'));place_city=flat(pick(n,'place-of-performance-city-proc','place-of-performance-city-lot'));place_region=flat(pick(n,'place-of-performance-subdiv-proc','place-of-performance-subdiv-lot'));place=flat(' | '.join(x for x in [place_city,place_region,place_country] if x));desc=(desc+' '+place).strip();market='PT' if country=='PRT' or place_country=='PRT' else 'EU';return dict(source='TED',external_id=ext,title=title,description=desc,buyer=buyer,country=country,cpv=cpv,value=value,deadline=deadline,publication_date=pub,published_at=parse_date(pub),url=f'https://ted.europa.eu/en/notice/-/detail/{ext}' if ext else 'https://ted.europa.eu/',market=market,place=place)

def fetch_base():
 token=os.getenv('BASE_ACCESS_TOKEN','').strip()
 if not token:return []
 r=requests.get(BASE_URL+'/GetInfoAnuncio',params={'numDias':90},headers={'_AcessToken':token},timeout=45);r.raise_for_status();data=r.json();data=data if isinstance(data,list) else [data];out=[]
 for n in data:
  ext=str(pick(n,'nAnuncio','idAnuncio','idprocedimento') or '');pub=flat(pick(n,'dataPublicacao'));out.append(dict(source='BASE',external_id=ext,title=flat(pick(n,'objectoContrato','descricao','descContrato')),description=flat(pick(n,'descContrato','descricao')),buyer=flat(pick(n,'adjudicante','entidadeAdjudicante')),country='PRT',cpv=flat(pick(n,'cpv')),value=flat(pick(n,'precoBaseProcedimento','precoContratual')),deadline=flat(pick(n,'dataApresentacaoPropostas','dataLimite')),publication_date=pub,published_at=parse_date(pub),url=flat(pick(n,'url','link')) or 'https://www.base.gov.pt/',market='PT',place=''))
 return out

def sync_once():
 started=datetime.now(timezone.utc).isoformat();rows=fetch_ted();norm=[normalize_ted(n) for n in rows if normalize_ted(n).get('external_id')]
 try:norm+=fetch_base()
 except Exception:pass
 c=db();new=0;seen=datetime.now(timezone.utc).isoformat()
 for x in norm:
  sc,label,cls,reason=commercial_score(x.get('title',''),x.get('description',''),x.get('cpv',''),x.get('deadline'));x['score']=sc;x['priority_label']=label;x['priority_class']=cls;x['match_reason']=reason
  old=c.execute('SELECT id FROM tenders WHERE source=? AND external_id=?',(x['source'],x['external_id'])).fetchone()
  vals=(x.get('title'),x.get('description'),x.get('buyer'),x.get('country'),x.get('cpv'),x.get('value'),x.get('deadline'),x.get('publication_date'),x.get('url'),x.get('score'),seen,x.get('published_at'),x.get('match_reason'),x.get('priority_label'),x.get('priority_class'),x.get('market'))
  if old:c.execute('''UPDATE tenders SET title=?,description=?,buyer=?,country=?,cpv=?,value=?,deadline=?,publication_date=?,url=?,score=?,last_seen=?,published_at=?,match_reason=?,priority_label=?,priority_class=?,market=? WHERE id=?''',vals+(old['id'],))
  else:c.execute('''INSERT INTO tenders(title,description,buyer,country,cpv,value,deadline,publication_date,url,score,last_seen,published_at,match_reason,priority_label,priority_class,market,source,external_id,first_seen) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',vals+(x['source'],x['external_id'],seen));new+=1
 c.execute('INSERT INTO sync_runs(started_at,finished_at,found,new_items) VALUES(?,?,?,?)',(started,seen,len(norm),new));c.commit();c.close();return len(norm),new

def stats_for(market):
 c=db();where='';params=[]
 if market in ('PT','EU'):where=' WHERE market=?';params=[market]
 total=c.execute('SELECT COUNT(*) n FROM tenders'+where,params).fetchone()['n'];high=c.execute('SELECT COUNT(*) n FROM tenders'+where+(' AND ' if where else ' WHERE ')+'score>=75',params).fetchone()['n'];new24=c.execute('SELECT COUNT(*) n FROM tenders'+where+(' AND ' if where else ' WHERE ')+'first_seen>=?',params+[(datetime.now(timezone.utc)-timedelta(hours=24)).isoformat()]).fetchone()['n'];last=c.execute('SELECT MAX(finished_at) v FROM sync_runs').fetchone()['v'];c.close();return dict(total=total,new24=new24,high=high,last=last or 'nunca')

def query_tenders(market,q,country,minscore,limit=60):
 c=db();where=[];params=[]
 if market in ('PT','EU'):where.append('market=?');params.append(market)
 if q:where.append('(title LIKE ? OR description LIKE ? OR buyer LIKE ? OR cpv LIKE ?)');params += [f'%{q}%']*4
 if country:where.append('country=?');params.append(country.upper())
 if minscore:where.append('score>=?');params.append(int(minscore))
 sql='SELECT * FROM tenders'+((' WHERE '+' AND '.join(where)) if where else '')+' ORDER BY score DESC, publication_date DESC LIMIT ?';params.append(limit);rows=c.execute(sql,params).fetchall();c.close();return [dict(r) for r in rows]

@APP.get('/')
def home():
 market=request.args.get('market','PT').upper();market=market if market in ('PT','EU','ALL') else 'PT';q=request.args.get('q','').strip();country=request.args.get('country','').strip().upper();minscore=request.args.get('minscore','').strip();tenders=query_tenders(market,q,country,minscore);top=tenders[:6];return render_template_string(HTML,stats=stats_for(market),tenders=tenders,top=top,q=q,country=country,minscore=minscore,market=market)

@APP.post('/sync')
def sync_route():
 sync_once();return redirect(url_for('home',market=request.args.get('market','PT')))

@APP.get('/api/v1/health')
def health():return jsonify(ok=True,service='obrasignal')

@APP.get('/api/v1/tenders')
def api_tenders():
 market=request.args.get('market','PT').upper();market=market if market in ('PT','EU','ALL') else 'PT';return jsonify(market=market,items=query_tenders(market,request.args.get('q','').strip(),request.args.get('country','').strip().upper(),request.args.get('minscore','').strip(),min(200,max(1,int(request.args.get('limit','60'))))))

def worker():
 while True:
  try:sync_once()
  except Exception:pass
  time.sleep(POLL_SECONDS)

threading.Thread(target=worker,daemon=True).start()
