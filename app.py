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

HTML='''<!doctype html><html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ObraSignal</title></head><body><h1>OBRASIGNAL</h1></body></html>'''

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
 payload={'query':query,'fields':fields,'limit':250,'scope':'ACTIVE','checkQuerySyntax':False,'paginationMode':'ITERATION'};rows=[];token=None;seen_tokens=set();pages=0
 while True:
  body=dict(payload)
  if token:body['iterationNextToken']=token
  r=requests.post(TED_URL,json=body,timeout=45);r.raise_for_status();data=r.json();batch=data.get('notices') or data.get('results') or data.get('content') or [];rows+=batch;pages+=1
  next_token=data.get('iterationNextToken') or data.get('nextToken') or data.get('nextIterationToken')
  if not next_token or not batch:break
  if next_token in seen_tokens:raise RuntimeError('TED iteration token repeated; aborting sync without advancing watermark')
  seen_tokens.add(next_token);token=next_token
 return rows
