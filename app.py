import os,sqlite3,threading,time,json,re
from datetime import datetime,timezone,timedelta
from flask import Flask,request,redirect,url_for,render_template_string,jsonify
import requests
APP=Flask(__name__); DB=os.getenv('OBRASIGNAL_DB','obrasignal.db'); TED_URL='https://api.ted.europa.eu/v3/notices/search'; BASE_URL='https://www.base.gov.pt/APIBase2'; POLL_SECONDS=int(os.getenv('POLL_SECONDS','300')); TED_DAYS=int(os.getenv('TED_DAYS','30')); TED_MAX_PAGES=int(os.getenv('TED_MAX_PAGES','60'))
HTML='''<!doctype html><html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ObraSignal</title><style>body{font-family:Arial;background:#0b1020;color:#eef2ff;margin:0}.wrap{max-width:1200px;margin:auto;padding:24px}.top,.row{display:flex;gap:10px;flex-wrap:wrap}.top{justify-content:space-between}.muted{color:#9aa5bd}.card{background:#151d33;border:1px solid #293553;border-radius:14px;padding:16px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.stat{font-size:28px;font-weight:700}input,button{background:#0f1629;color:#eef2ff;border:1px solid #354364;border-radius:9px;padding:10px}button{cursor:pointer;background:#2a5bd7;border:0}.tag{display:inline-block;padding:4px 8px;border-radius:999px;background:#26324e;margin:3px;font-size:12px}a{color:#8db4ff}.score{font-size:22px;font-weight:700}.small{font-size:13px}.reason{margin-top:10px;padding:9px;border-radius:9px;background:#10182b;color:#b9c6df;font-size:13px}.hot{color:#7ee787}.good{color:#8db4ff}.low{color:#9aa5bd}@media(max-width:800px){.grid{grid-template-columns:1fr 1fr}}</style></head><body><div class="wrap"><div class="top"><div><h1>OBRASIGNAL</h1><div class="muted">Radar automático de concursos e oportunidades de obra</div></div><form method="post" action="/sync"><button>Sincronizar agora</button></form></div><div class="grid"><div class="card"><div class="muted">Oportunidades</div><div class="stat">{{stats.total}}</div></div><div class="card"><div class="muted">Novas 24h</div><div class="stat">{{stats.new24}}</div></div><div class="card"><div class="muted">Alta relevância</div><div class="stat">{{stats.high}}</div></div><div class="card"><div class="muted">Última sincronização</div><div class="small">{{stats.last}}</div></div></div><div class="card"><h2>Filtro</h2><form method="get" class="row"><input name="q" placeholder="palavra-chave" value="{{q}}"><input name="country" placeholder="país ISO-3" value="{{country}}"><input name="minscore" type="number" min="0" max="100" placeholder="score mínimo" value="{{minscore}}"><button>Filtrar</button><a href="/">Limpar</a></form></div>{% for t in tenders %}<div class="card"><div class="top"><div><span class="tag">{{t.source}}</span><span class="tag">{{t.publication_date or 'sem data'}}</span>{% if t.country %}<span class="tag">{{t.country}}</span>{% endif %}</div><div class="score">{{t.score}}/100</div></div><h2>{{t.title or 'Sem título'}}</h2><div>{{t.buyer or 'Entidade não identificada'}}</div><div class="muted small">{{t.value or 'Valor não indicado'}} · {{t.deadline or 'Prazo não indicado'}}</div><p class="small">{{t.description[:900] if t.description else ''}}</p>{% if t.match_reason %}<div class="reason"><b class="{{t.priority_class}}">{{t.priority_label}}</b> — {{t.match_reason}}</div>{% endif %}{% if t.cpv %}<div>{% for x in t.cpv.split('|')[:10] %}<span class="tag">{{x}}</span>{% endfor %}</div>{% endif %}<p><a href="{{t.url}}" target="_blank">Abrir fonte</a></p></div>{% endfor %}</div></body></html>'''

def db():
 c=sqlite3.connect(DB,check_same_thread=False);c.row_factory=sqlite3.Row;c.execute('''CREATE TABLE IF NOT EXISTS tenders(id INTEGER PRIMARY KEY AUTOINCREMENT,source TEXT,external_id TEXT,title TEXT,description TEXT,buyer TEXT,country TEXT,cpv TEXT,value TEXT,deadline TEXT,publication_date TEXT,url TEXT,score INTEGER DEFAULT 0,first_seen TEXT,last_seen TEXT,UNIQUE(source,external_id))''');c.execute('''CREATE TABLE IF NOT EXISTS sync_runs(id INTEGER PRIMARY KEY AUTOINCREMENT,started_at TEXT,finished_at TEXT,found INTEGER DEFAULT 0,new_items INTEGER DEFAULT 0)''');cols=[x['name'] for x in c.execute('PRAGMA table_info(tenders)')];
 for col in ['published_at','match_reason','priority_label','priority_class']:
  if col not in cols:c.execute('ALTER TABLE tenders ADD COLUMN '+col+' TEXT')
 c.commit();return c

def pick(o,*ks):
 if not isinstance(o,dict):return None
 for k in ks:
  if o.get(k) not in (None,'',[],{}):return o[k]

def lang(v):
 if isinstance(v,str):
  s=v.strip()
  if s.startswith('{'):
   try:return lang(json.loads(s))
   except:pass
  return v
 if isinstance(v,dict):
  for k in ('pt','pt-PT','por','en','en-GB','eng'):
   if v.get(k):return lang(v[k])
  return next((lang(x) for x in v.values() if x), '')
 if isinstance(v,list):return ' | '.join(filter(None,(lang(x) for x in v)))
 return '' if v is None else str(v)

def flat(v):
 if isinstance(v,list):return ' | '.join(filter(None,(lang(pick(x,'label','name','value','code') or x) if isinstance(x,dict) else lang(x) for x in v)))
 return lang(v)

def date(v):
 if not v:return None
 s=str(v).replace('Z','+00:00')
 try:return datetime.fromisoformat(s).astimezone(timezone.utc).isoformat()
 except:
  try:return datetime.strptime(s[:10],'%Y-%m-%d').replace(tzinfo=timezone.utc).isoformat()
  except:return None

POS={'metalomecânica':30,'metalomecanica':30,'estruturas metálicas':32,'estruturas metalicas':32,'estrutura metálica':30,'estrutura metalica':30,'serralharia':28,'steel':24,'aço':24,'aco':24,'pavilhão':24,'pavilhões':24,'armazém':22,'armazem':22,'warehouse':22,'cobertura':20,'fachada':18,'montagem':16,'empreitada':16,'construção':12,'construcao':12,'construction':12,'obra':10,'obras':10,'reabilitação':14,'reabilitacao':14,'remodelação':12,'remodelacao':12,'engenharia':5,'engineering':5}
NEG={'arquitetura':-20,'arquitectura':-20,'architecture':-20,'fiscalização':-24,'fiscalizacao':-24,'consultoria':-22,'consulting':-22,'topografia':-20,'topographic':-20,'geologia':-20,'geotechnical':-20,'estudo':-18,'estudos':-18,'auditoria':-15,'audit':-15,'formação':-18,'formacao':-18,'training':-18,'software':-12}

def commercial_score(t,d,c):
 text=re.sub(r'\s+',' ',(t+' '+d+' '+c).lower());score=15;hits=[];bad=[]
 for k,v in POS.items():
  if k in text:score+=v;hits.append(k)
 for k,v in NEG.items():
  if k in text:score+=v;bad.append(k)
 cpv=(c or '').replace(' ','')
 if cpv.startswith('45'):score+=18
 elif cpv.startswith('44'):score+=12
 elif cpv.startswith(('42','43')):score+=5
 elif cpv.startswith('71'):score+=2
 execution=any(k in text for k in ('execução','execucao','empreitada','montagem','construção','construcao','works','construction'))
 if any(k in text for k in ('serviços de arquitetura','servicos de arquitetura','architecture services')) and not execution:score-=18;bad.append('arquitetura sem execução')
 score=max(0,min(100,score));label='PRIORIDADE MÁXIMA' if score>=75 else 'BOA OPORTUNIDADE' if score>=55 else 'BAIXA PRIORIDADE';cls='hot' if score>=75 else 'good' if score>=55 else 'low'
 reason=('forte correspondência com '+', '.join(dict.fromkeys(hits)[:5])) if hits else 'correspondência geral com obra';
 if bad:reason+='; penalizado por '+', '.join(dict.fromkeys(bad)[:3])
 return score,label,cls,reason

def fetch_ted():
 since=(datetime.now(timezone.utc)-timedelta(days=TED_DAYS)).strftime('%Y%m%d');p={'query':f'buyer-country=PRT AND publication-date>={since}','fields':['publication-number','notice-title','description-proc','buyer-name','buyer-country','classification-cpv','estimated-value-proc','estimated-value-cur-proc','deadline-date-lot','publication-date'],'limit':250,'scope':'ACTIVE','checkQuerySyntax':False,'paginationMode':'ITERATION'};rows=[];token=None
 for _ in range(TED_MAX_PAGES):
  b=dict(p)
  if token:b['iterationNextToken']=token
  r=requests.post(TED_URL,json=b,timeout=45);r.raise_for_status();j=r.json();batch=j.get('notices') or j.get('results') or j.get('content') or [];rows+=batch;token=j.get('iterationNextToken') or j.get('nextToken') or j.get('nextIterationToken')
  if not token or not batch:break
 return rows

def norm(n):
 e=flat(pick(n,'publication-number','publicationNumber','id'));t=flat(pick(n,'notice-title','noticeTitle','title'));d=flat(pick(n,'description-proc','descriptionProc','description'));b=flat(pick(n,'buyer-name','buyerName','buyer'));co=flat(pick(n,'buyer-country','buyerCountry','country'));c=flat(pick(n,'classification-cpv','cpvCodes','cpv'));v=flat(pick(n,'estimated-value-proc','estimatedValue','value'));dl=flat(pick(n,'deadline-date-lot','deadlineDate'));p=flat(pick(n,'publication-date','publicationDate'));return dict(source='TED',external_id=e,title=t,description=d,buyer=b,country=co,cpv=c,value=v,deadline=dl,publication_date=p,published_at=date(p),url=f'https://ted.europa.eu/en/notice/{e}/html' if e else 'https://ted.europa.eu/')

def fetch_base():
 tok=os.getenv('BASE_ACCESS_TOKEN','').strip()
 if not tok:return []
 r=requests.get(BASE_URL+'/GetInfoAnuncio',params={'numDias':90},headers={'_AcessToken':tok},timeout=45);r.raise_for_status();data=r.json();data=data if isinstance(data,list) else [data];out=[]
 for n in data:
  e=str(pick(n,'nAnuncio','idAnuncio','idprocedimento') or '');p=flat(pick(n,'dataPublicacao'));out.append(dict(source='BASE',external_id=e,title=flat(pick(n,'objectoContrato','descricao','descContrato')),description=flat(pick(n,'descContrato','descricao')),buyer=flat(pick(n,'adjudicante','entidadeAdjudicante')),country='PRT',cpv=flat(pick(n,'cpv')),value=flat(pick(n,'precoBaseProcedimento','precoContratual')),deadline=flat(pick(n,'dataLimiteApresentacaoPropostas','prazo')),publication_date=p,published_at=date(p),url='https://www.base.gov.pt/Base4/pt/pesquisa/'))
 return out

def save(rows):
 c=db();now=datetime.now(timezone.utc).isoformat();new=0
 for x in rows:
  if not x['external_id']:continue
  sc,lab,cls,why=commercial_score(x['title'],x['description'],x['cpv']);old=c.execute('SELECT id FROM tenders WHERE source=? AND external_id=?',(x['source'],x['external_id'])).fetchone()
  vals=(x['title'],x['description'],x['buyer'],x['country'],x['cpv'],x['value'],x['deadline'],x['publication_date'],x['published_at'],x['url'],sc,why,lab,cls,now)
  if old:c.execute('UPDATE tenders SET title=?,description=?,buyer=?,country=?,cpv=?,value=?,deadline=?,publication_date=?,published_at=?,url=?,score=?,match_reason=?,priority_label=?,priority_class=?,last_seen=? WHERE id=?',vals+(old['id'],))
  else:c.execute('INSERT INTO tenders(source,external_id,title,description,buyer,country,cpv,value,deadline,publication_date,published_at,url,score,match_reason,priority_label,priority_class,first_seen,last_seen) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(x['source'],x['external_id'])+vals+(now,));new+=1
 c.commit();return new

def sync():
 c=db();start=datetime.now(timezone.utc).isoformat();rows=[]
 try:rows=[norm(x) for x in fetch_ted()]
 except Exception as e:print('TED',e)
 try:rows+=fetch_base()
 except Exception as e:print('BASE',e)
 new=save(rows);c.execute('INSERT INTO sync_runs(started_at,finished_at,found,new_items) VALUES(?,?,?,?)',(start,datetime.now(timezone.utc).isoformat(),len(rows),new));c.commit()

def index():
 c=db();q=request.args.get('q','').strip().lower();co=request.args.get('country','').strip().upper();
 try:ms=int(request.args.get('minscore','0') or 0)
 except:ms=0
 sql='SELECT * FROM tenders WHERE score>=?';a=[ms]
 if q:sql+=' AND lower(title||" "||description||" "||buyer||" "||cpv) LIKE ?';a+=['%'+q+'%']
 if co:sql+=' AND upper(country)=?';a+=[co]
 rows=c.execute(sql+' ORDER BY score DESC,published_at DESC,first_seen DESC LIMIT 500',a).fetchall();total=c.execute('SELECT COUNT(*) FROM tenders').fetchone()[0];cut=(datetime.now(timezone.utc)-timedelta(hours=24)).isoformat();new24=c.execute('SELECT COUNT(*) FROM tenders WHERE published_at>=?',(cut,)).fetchone()[0];high=c.execute('SELECT COUNT(*) FROM tenders WHERE score>=75').fetchone()[0];last=c.execute('SELECT MAX(finished_at) FROM sync_runs').fetchone()[0] or '—';return render_template_string(HTML,tenders=rows,stats={'total':total,'new24':new24,'high':high,'last':last},q=q,country=co,minscore=ms)
APP.add_url_rule('/','index',index)
@APP.post('/sync')
def do_sync():sync();return redirect(url_for('index'))
@APP.get('/health')
def health():return jsonify(ok=True)
@APP.get('/api/tenders')
def api():
 c=db();return jsonify([dict(x) for x in c.execute('SELECT * FROM tenders ORDER BY score DESC,published_at DESC,first_seen DESC LIMIT 500')])
def worker():
 while True:
  try:sync()
  except Exception as e:print('worker',e)
  time.sleep(POLL_SECONDS)
if __name__=='__main__':db();threading.Thread(target=worker,daemon=True).start();APP.run(host='0.0.0.0',port=int(os.getenv('PORT','8080')))
