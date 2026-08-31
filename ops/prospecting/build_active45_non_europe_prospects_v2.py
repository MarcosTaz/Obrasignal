#!/usr/bin/env python3
from __future__ import annotations
import csv,gzip,io,json,math,os,re,unicodedata,urllib.parse,urllib.request
from collections import defaultdict
from pathlib import Path

# Strict sector taxonomy for ObraSignal prospecting. Numeric codes are interpreted
# ONLY when their source scheme is known, preventing CPV/UNSPSC collisions.
CPV_PREFIX=('45','71','50','31','32','43','42','44','90','65')
UNSPSC_SEGMENT=('72','81','95','30','39','40','26')
STRONG_TERMS=(
 'construction','constructora','constructor','construccion','construcción','construtora','construcao','construção',
 'obra civil','obras civiles','obras publicas','obras públicas','civil works','public works',
 'engineering','engenharia','ingenieria','ingeniería','infraestructura','infraestrutura','infrastructure',
 'electrical installation','instalacion electrica','instalación eléctrica','instalacao eletrica','instalação elétrica',
 'hvac','avac','climatizacion','climatización','climatizacao','climatização','air conditioning',
 'road construction','road maintenance','carretera','pavimentacion','pavimentación','pavimentacao','pavimentação','asphalt','asfalto',
 'water network','water works','sewer','sewerage','saneamento','alcantarillado','plumbing',
 'building maintenance','facility maintenance','mantenimiento de edificios','manutencao predial','manutenção predial',
 'roofing','cubierta','telhado','telecommunications installation','telecom installation',
 'renewable energy','energia renovable','energia renovável','solar installation','instalacion solar','instalação solar'
)
COMPANY_TERMS=(
 'construction','construct','constructora','construtora','engenharia','engineering','ingenieria','ingeniería',
 'infraestructura','infraestrutura','infrastructure','obras','civil','electrical','electrica','eléctrica','eletrica','elétrica',
 'instalaciones','instalacoes','instalações','hvac','avac','climat','paviment','asfalt','road','roads','saneamento',
 'plumbing','telecom','energia','energy','solar','roof','facility','facilities'
)
NEGATIVE_COMPANY=(
 'farmaceut','pharma','medical','medico','médico','hospital','drogueria','drug','laboratorio','laboratório',
 'papeleria','papelaria','stationery','alimentos','food','catering','restaurant','supermerc','grocery',
 'aseguradora','seguros','insurance','banco','bank','financiera','financial','courier','mensajeria','mensajería',
 'automovil','automóvil','automotive dealer','vehicle dealer','repuestos','tires','neumatic','neumátic',
 'software','cloud','cyber','it services','tecnologia de informacion','tecnología de información'
)
CORP=re.compile(r'\b(sa|s a|sas|s a s|ltda|limitada|srl|eirl|spa|inc|llc|ltd|corp|corporation|company|cooperativa|consorcio|union temporal|empresa|sociedad anonima|sociedad anónima|cia|saci|sacia|bv|gmbh|ag)\b',re.I)

def norm(s):
 s=unicodedata.normalize('NFKD',str(s or ''));s=''.join(c for c in s if not unicodedata.combining(c));s=s.casefold();s=re.sub(r'[^a-z0-9]+',' ',s);return re.sub(r'\s+',' ',s).strip()
def has_terms(text,terms):
 t=norm(text);return any(norm(x) in t for x in terms)
def company_relevant(name):return has_terms(name,COMPANY_TERMS) and not has_terms(name,NEGATIVE_COMPANY)
def likely_company(name):
 n=norm(name)
 if len(n)<3 or has_terms(n,NEGATIVE_COMPANY):return False
 if CORP.search(n) or company_relevant(n):return True
 toks=n.split()
 return len(toks)>=5 or any(any(ch.isdigit() for ch in t) for t in toks)
def money(v):
 try:
  if isinstance(v,dict):v=v.get('amount') or v.get('value') or 0
  return float(str(v or 0).replace(',',''))
 except:return 0.0
def date_year(s):
 m=re.search(r'(20\d{2})',str(s or ''));return int(m.group(1)) if m else 0

def class_hits(obj):
 hits=[]
 def one(c):
  if not isinstance(c,dict):return
  code=re.sub(r'\D','',str(c.get('id') or '')); scheme=norm(c.get('scheme') or '')
  if not code:return
  if 'cpv' in scheme and code.startswith(CPV_PREFIX):hits.append(('cpv',code[:8]))
  elif 'unspsc' in scheme and code[:2] in UNSPSC_SEGMENT:hits.append(('unspsc',code[:8]))
 def walk_item(it):
  if not isinstance(it,dict):return
  one(it.get('classification') or {})
  for c in it.get('additionalClassifications') or []:one(c)
 t=obj.get('tender') or {}
 one(t.get('classification') or {})
 for c in t.get('additionalClassifications') or []:one(c)
 for it in t.get('items') or []:walk_item(it)
 for a in obj.get('awards') or []:
  for it in a.get('items') or []:walk_item(it)
 return hits

def release_relevance(r):
 t=r.get('tender') or {}
 if str(t.get('mainProcurementCategory','')).lower()=='works':return True,'works'
 hits=class_hits(r)
 if hits:return True,':'.join(hits[0])
 texts=[t.get('title',''),t.get('description','')]
 for it in t.get('items') or []:texts.append((it or {}).get('description',''))
 for a in r.get('awards') or []:
  texts += [a.get('title',''),a.get('description','')]
  for it in a.get('items') or []:texts.append((it or {}).get('description',''))
 if has_terms(' '.join(map(str,texts)),STRONG_TERMS):return True,'strong-keyword'
 return False,''

def suppliers(r):
 parties={str(p.get('id','')):p for p in (r.get('parties') or []) if p.get('id')}
 out=[]
 for a in r.get('awards') or []:
  if str(a.get('status','')).lower() not in ('','active','pending'):continue
  val=money(a.get('value'));adate=a.get('date') or r.get('date') or ''
  for s in a.get('suppliers') or []:
   sid=str((s or {}).get('id') or '');p=parties.get(sid) or s or {};name=(p.get('name') or s.get('name') or '').strip()
   if not likely_company(name):continue
   ident=p.get('identifier') or {};iid=str(ident.get('id') or sid or '');scheme=str(ident.get('scheme') or '')
   addr=p.get('address') or {};cp=p.get('contactPoint') or {}
   out.append((name,iid,scheme,addr.get('locality','') or addr.get('region','') or '',val,adate,cp.get('url','') or ''))
 return out

def ocp_market(country,pid,quota,label,max_seen=55000):
 agg={};seen=rel=0
 for year in (2026,2025):
  url=f'https://data.open-contracting.org/en/publication/{pid}/download?name={year}.jsonl.gz'
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'ObraSignal-market-research/4.0'})
   with urllib.request.urlopen(req,timeout=120) as resp,gzip.GzipFile(fileobj=resp) as gz:
    for raw in gz:
     seen+=1
     try:r=json.loads(raw)
     except:continue
     ok,cat=release_relevance(r); ss=suppliers(r) if ok else []
     # If procurement metadata is weak, a clearly sector-specific supplier name is enough
     # to keep the entity as a candidate, but never negative-sector suppliers.
     if not ok:
      ss=suppliers(r)
      ss=[x for x in ss if company_relevant(x[0])]
      if ss:ok=True;cat='supplier-sector-name'
     if not ok:continue
     rel+=1;buyer=norm((r.get('buyer') or {}).get('name',''))
     for name,iid,scheme,city,val,adate,site in ss:
      k=(iid or norm(name),norm(name));p=agg.get(k)
      if p is None:p=agg[k]={'company_name':name,'country':country,'company_id':iid,'id_scheme':scheme,'city':city,'award_count':0,'buyers':set(),'total_awarded':0.0,'last_award_year':0,'category':cat,'website':site}
      p['award_count']+=1;p['total_awarded']+=val;p['last_award_year']=max(p['last_award_year'],date_year(adate));
      if buyer:p['buyers'].add(buyer)
      if cat and p['category']=='supplier-sector-name':p['category']=cat
      if site and not p['website']:p['website']=site
     if seen>=max_seen or (len(agg)>=quota*3 and seen>=12000):break
  except Exception as e:print(country,year,'ERROR',repr(e),flush=True)
  if len(agg)>=quota*2:break
 rows=[]
 for p in agg.values():
  p['buyer_count']=len(p.pop('buyers'));p['source']=label;p['source_url']=f'https://data.open-contracting.org/en/publication/{pid}'
  p['fit_score']=round(min(100,44+9*math.log2(p['award_count']+1)+6*math.log2(p['buyer_count']+1)+min(16,1.9*math.log10(p['total_awarded']+1))+(9 if p['last_award_year']>=2026 else 5)+(6 if p['category']!='supplier-sector-name' else 0)),1)
  rows.append(p)
 rows.sort(key=lambda x:(x['fit_score'],x['award_count'],x['buyer_count'],x['total_awarded']),reverse=True)
 print(country,'seen',seen,'relevant',rel,'unique',len(rows),'selected',min(quota,len(rows)),flush=True);return rows[:quota]

def us_market(quota=3500):
 url='https://api.usaspending.gov/api/v2/search/spending_by_award/';agg={}
 # Construction + architectural/engineering services. Keep 5413, but reject known unrelated names by NEGATIVE_COMPANY.
 for page in range(1,121):
  body={'subawards':False,'limit':100,'page':page,'filters':{'award_type_codes':['A','B','C','D'],'time_period':[{'start_date':'2024-01-01','end_date':'2026-08-31'}],'naics_codes':{'require':['23','5413']}},'fields':['Award ID','Recipient Name','Recipient UEI','Award Amount','NAICS','Recipient Location','Start Date'],'sort':'Award Amount','order':'desc','spending_level':'awards'}
  req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','User-Agent':'ObraSignal-market-research/4.0'})
  try:
   with urllib.request.urlopen(req,timeout=90) as rr:d=json.load(rr)
  except Exception as e:print('US',page,'ERROR',e,flush=True);break
  xs=d.get('results') or []
  if not xs:break
  for x in xs:
   name=(x.get('Recipient Name') or '').strip()
   if not likely_company(name):continue
   uei=str(x.get('Recipient UEI') or '');k=uei or norm(name);loc=x.get('Recipient Location') or {};na=x.get('NAICS') or {};code=str(na.get('code','')) if isinstance(na,dict) else str(na)
   p=agg.get(k)
   if p is None:p=agg[k]={'company_name':name,'country':'US','company_id':uei,'id_scheme':'UEI','city':loc.get('city_name','') if isinstance(loc,dict) else '','award_count':0,'buyers':set(),'total_awarded':0.0,'last_award_year':0,'category':code,'website':''}
   p['award_count']+=1;p['total_awarded']+=money(x.get('Award Amount'));p['last_award_year']=max(p['last_award_year'],date_year(x.get('Start Date')))
  if len(agg)>=quota*2:break
 for p in agg.values():p['buyer_count']=0;p['source']='USAspending federal contracts';p['source_url']='https://api.usaspending.gov/';p['fit_score']=round(min(100,50+9*math.log2(p['award_count']+1)+min(20,2.2*math.log10(p['total_awarded']+1))),1)
 return sorted(agg.values(),key=lambda x:(x['fit_score'],x['award_count'],x['total_awarded']),reverse=True)[:quota]

def colombia_market(quota=2500):
 base='https://www.datos.gov.co/resource/jbjy-vk9h.json';agg={};offset=0
 select='proveedor_adjudicado,documento_proveedor,tipo_de_contrato,objeto_del_contrato,valor_del_contrato,fecha_de_firma,urlproceso'
 while offset<100000 and len(agg)<quota*3:
  q={'$limit':'50000','$offset':str(offset),'$select':select,'$where':"fecha_de_firma >= '2024-01-01T00:00:00.000'",'$order':'fecha_de_firma DESC'}
  req=urllib.request.Request(base+'?'+urllib.parse.urlencode(q,safe="',><=()"),headers={'User-Agent':'ObraSignal-market-research/4.0'})
  try:
   with urllib.request.urlopen(req,timeout=120) as rr:rows=json.load(rr)
  except Exception as e:print('CO ERROR',e,flush=True);break
  if not rows:break
  for x in rows:
   name=(x.get('proveedor_adjudicado') or '').strip();typ=norm(x.get('tipo_de_contrato') or '');obj=x.get('objeto_del_contrato') or ''
   if not likely_company(name):continue
   is_work=('obra' in typ and 'segu' not in typ)
   is_sector_name=company_relevant(name)
   is_eng_service=(('consult' in typ or 'servicio' in typ) and has_terms(obj,STRONG_TERMS))
   if not (is_work or is_sector_name or is_eng_service):continue
   iid=str(x.get('documento_proveedor') or '');k=iid or norm(name);p=agg.get(k)
   if p is None:p=agg[k]={'company_name':name,'country':'CO','company_id':iid,'id_scheme':'NIT/documento proveedor','city':'','award_count':0,'buyers':set(),'total_awarded':0.0,'last_award_year':0,'category':x.get('tipo_de_contrato') or 'contract','website':''}
   p['award_count']+=1;p['total_awarded']+=money(x.get('valor_del_contrato'));p['last_award_year']=max(p['last_award_year'],date_year(x.get('fecha_de_firma')))
  offset+=len(rows)
  if len(rows)<50000:break
 for p in agg.values():p['buyer_count']=0;p['source']='Colombia SECOP II contratos electrónicos';p['source_url']='https://www.datos.gov.co/resource/jbjy-vk9h.json';p['fit_score']=round(min(100,50+9*math.log2(p['award_count']+1)+min(18,1.9*math.log10(p['total_awarded']+1))+(9 if p['last_award_year']>=2026 else 5)),1)
 return sorted(agg.values(),key=lambda x:(x['fit_score'],x['award_count'],x['total_awarded']),reverse=True)[:quota]

def canada_market(quota=1500):
 url='https://canadabuys.canada.ca/opendata/pub/contractHistoryComplete-contratsOctroyesComplet.csv';agg={};seen=0
 req=urllib.request.Request(url,headers={'User-Agent':'ObraSignal-market-research/4.0'})
 try:
  with urllib.request.urlopen(req,timeout=180) as resp:
   rd=csv.DictReader(io.TextIOWrapper(resp,encoding='utf-8-sig',errors='replace',newline=''))
   for row in rd:
    seen+=1;subject=[];name='';value=0.0;date='';city='';ident=''
    for k,v in row.items():
     nk=norm(k);v=str(v or '')
     if not name and v and ('supplier name' in nk or 'nom fournisseur' in nk or nk=='supplier'):name=v.strip()
     if not date and v and ('award date' in nk or 'date attribution' in nk):date=v
     if not city and v and ('supplier city' in nk or 'ville fournisseur' in nk):city=v
     if not ident and v and ('supplier number' in nk or 'numero fournisseur' in nk):ident=v
     if v and ('contract value' in nk or 'valeur contrat' in nk):value=max(value,money(v))
     if any(x in nk for x in ('description','commodity','category','gsin','objet','produit','service')):subject.append(v)
    if not likely_company(name):continue
    if not (has_terms(' '.join(subject),STRONG_TERMS) or company_relevant(name)):continue
    k=ident or norm(name);p=agg.get(k)
    if p is None:p=agg[k]={'company_name':name,'country':'CA','company_id':ident,'id_scheme':'CanadaBuys supplier id','city':city,'award_count':0,'buyers':set(),'total_awarded':0.0,'last_award_year':0,'category':'construction/engineering evidence','website':''}
    p['award_count']+=1;p['total_awarded']+=value;p['last_award_year']=max(p['last_award_year'],date_year(date))
    if seen>=120000 or len(agg)>=quota*3:break
 except Exception as e:print('CA ERROR',e,flush=True)
 for p in agg.values():p['buyer_count']=0;p['source']='CanadaBuys contract history';p['source_url']='https://canadabuys.canada.ca/en/procurement-and-contracting-data';p['fit_score']=round(min(100,48+9*math.log2(p['award_count']+1)+min(18,1.9*math.log10(p['total_awarded']+1))+(8 if p['last_award_year']>=2026 else 4)),1)
 return sorted(agg.values(),key=lambda x:(x['fit_score'],x['award_count'],x['total_awarded']),reverse=True)[:quota]

OCP={'BR':(157,3500,'Brazil Compras.gov.br'),'CL':(144,2000,'Chile MercadoPublico'),'DO':(22,800,'Dominican Republic DGCP'),'EC':(110,1500,'Ecuador SERCOP'),'GT':(142,1200,'Guatemala Guatecompras'),'HN':(122,800,'Honduras ONCAE'),'PY':(63,1000,'Paraguay DNCP'),'PE':(135,2500,'Peru OECE'),'ZA':(143,900,'South Africa National Treasury'),'UY':(43,1000,'Uruguay ARCE')}
