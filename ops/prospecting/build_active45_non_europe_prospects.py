#!/usr/bin/env python3
from __future__ import annotations
import csv, gzip, io, json, math, os, re, time, unicodedata, urllib.parse, urllib.request, urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

OUT=Path(os.environ.get('OUT_DIR','active45_non_europe')); OUT.mkdir(parents=True,exist_ok=True)
YEARS=[2026,2025]
OCP={
 'BR':(157,3500,'Brazil federal procurement / Compras.gov.br'),
 'CL':(144,2000,'Chile MercadoPublico OCDS'),
 'DO':(22,800,'Dominican Republic DGCP'),
 'EC':(110,1500,'Ecuador SERCOP'),
 'GT':(142,1200,'Guatemala Guatecompras'),
 'HN':(122,800,'Honduras ONCAE'),
 'PY':(63,1000,'Paraguay DNCP'),
 'PE':(135,2500,'Peru OECE'),
 'ZA':(143,900,'South Africa National Treasury'),
 'UY':(43,1000,'Uruguay ARCE'),
}
SOURCE_URL={c:f'https://data.open-contracting.org/en/publication/{pid}' for c,(pid,_,_) in OCP.items()}
CORP=re.compile(r'\b(sa|s a|sas|s a s|ltda|limitada|srl|eirl|spa|inc|llc|ltd|corp|corporation|company|cooperativa|consorcio|union temporal|empresa|constructora|construtora|engenharia|ingenieria|ingeniería|engineering|servicios|serviços|services|comercial|industrial|infraestructura|infraestrutura|obras|solutions|group|grupo)\b',re.I)
KEYWORDS=('construction','construccion','construcción','construcao','construção','obra','obras','engenharia','ingenieria','ingeniería','engineering','infrastructure','infraestructura','infraestrutura','civil','road','roads','carretera','estrada','electrical','electric','electrica','eléctrica','eletrica','elétrica','hvac','avac','plumbing','climatizacion','climatização','maintenance','mantenimiento','manutencao','manutenção','facility','facilities','roof','roofing','paviment','asfalt','water','sewer','saneamento','telecom','energy','energia','renewable','solar','building','edificio','edifício')
CPV=('45','71','50','31','32','43','42','44','90','65')
UNSPSC=('72','81','95','30','39','40','26')

def norm(s):
 s=unicodedata.normalize('NFKD',str(s or ''));s=''.join(c for c in s if not unicodedata.combining(c));s=s.casefold();s=re.sub(r'[^a-z0-9]+',' ',s);return re.sub(r'\s+',' ',s).strip()
def likely_company(name):
 n=norm(name)
 if len(n)<3:return False
 if CORP.search(n):return True
 if any(k in n for k in KEYWORDS):return True
 toks=n.split()
 # Reject likely natural persons, but keep longer branded/organizational names.
 if 2<=len(toks)<=4 and all(t.isalpha() for t in toks):return False
 return True
def money(v):
 try:
  if isinstance(v,dict):v=v.get('amount') or v.get('value') or 0
  return float(str(v or 0).replace(',',''))
 except:return 0.0
def date_year(s):
 m=re.search(r'(20\d{2})',str(s or ''));return int(m.group(1)) if m else 0
def relevant_release(r):
 t=r.get('tender') or {}
 if str(t.get('mainProcurementCategory','')).lower()=='works':return True,'works'
 codes=[];texts=[t.get('title',''),t.get('description','')]
 def scan_item(it):
  c=it.get('classification') or {};codes.append(str(c.get('id','')))
  for c2 in it.get('additionalClassifications') or []:codes.append(str((c2 or {}).get('id','')))
  texts.append(it.get('description',''))
 for it in t.get('items') or []:scan_item(it)
 for a in r.get('awards') or []:
  for it in a.get('items') or []:scan_item(it)
 digits=[re.sub(r'\D','',c) for c in codes]
 for c in digits:
  if c.startswith(CPV) or c.startswith(UNSPSC):return True,c[:8]
 txt=norm(' '.join(map(str,texts)))
 if any(norm(k) in txt for k in KEYWORDS):return True,'keyword'
 return False,''
def extract_suppliers(r):
 parties={str(p.get('id','')):p for p in (r.get('parties') or []) if p.get('id')}
 out=[]
 for a in r.get('awards') or []:
  st=str(a.get('status','')).lower()
  if st not in ('','active','pending'):continue
  val=money(a.get('value'))
  adate=a.get('date') or r.get('date') or ''
  for s in a.get('suppliers') or []:
   sid=str((s or {}).get('id') or '')
   p=parties.get(sid) or s or {}
   name=(p.get('name') or s.get('name') or '').strip()
   if not likely_company(name):continue
   ident=p.get('identifier') or {}
   iid=str(ident.get('id') or sid or '')
   scheme=str(ident.get('scheme') or '')
   addr=p.get('address') or {};cp=p.get('contactPoint') or {}
   out.append((name,iid,scheme,addr.get('locality','') or addr.get('region','') or '',val,adate,cp.get('url','') or ''))
 return out

def ocp_market(country,pid,quota,label):
 agg={};seen=0;rel=0
 for year in YEARS:
  url=f'https://data.open-contracting.org/en/publication/{pid}/download?name={year}.jsonl.gz'
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'ObraSignal-market-research/3.0'})
   with urllib.request.urlopen(req,timeout=120) as resp, gzip.GzipFile(fileobj=resp) as gz:
    for raw in gz:
     seen+=1
     try:r=json.loads(raw)
     except:continue
     ok,cat=relevant_release(r)
     if not ok:continue
     rel+=1; buyer=norm((r.get('buyer') or {}).get('name',''))
     for name,iid,scheme,city,val,adate,site in extract_suppliers(r):
      k=(iid or norm(name),norm(name))
      p=agg.get(k)
      if p is None:p=agg[k]={'company_name':name,'country':country,'company_id':iid,'id_scheme':scheme,'city':city,'award_count':0,'buyers':set(),'total_awarded':0.0,'last_award_year':0,'category':cat,'website':site}
      p['award_count']+=1;p['total_awarded']+=val;p['last_award_year']=max(p['last_award_year'],date_year(adate));
      if buyer:p['buyers'].add(buyer)
      if cat and p['category'] in ('','keyword'):p['category']=cat
      if site and not p['website']:p['website']=site
     if seen>=150000 or (len(agg)>=quota*6 and seen>=30000):break
  except Exception as e:
   print(country,year,'ERROR',repr(e),flush=True)
  if len(agg)>=quota*2:break
 rows=[]
 for p in agg.values():
  p['buyer_count']=len(p.pop('buyers'));p['source']=label;p['source_url']=SOURCE_URL[country]
  p['fit_score']=round(min(100,48+8*math.log2(p['award_count']+1)+5*math.log2(p['buyer_count']+1)+min(18,2.2*math.log10(p['total_awarded']+1))+(8 if p['last_award_year']>=2026 else 5)),1)
  rows.append(p)
 rows.sort(key=lambda x:(x['fit_score'],x['award_count'],x['buyer_count'],x['total_awarded']),reverse=True)
 print(country,'seen',seen,'relevant',rel,'unique',len(rows),'selected',min(quota,len(rows)),flush=True)
 return rows[:quota]

def us_market(quota=3500):
 url='https://api.usaspending.gov/api/v2/search/spending_by_award/'
 agg={};page=1
 while page<=350 and len(agg)<quota*3:
  body={'subawards':False,'limit':100,'page':page,'filters':{'award_type_codes':['A','B','C','D'],'time_period':[{'start_date':'2024-01-01','end_date':'2026-08-31'}],'naics_codes':{'require':['23','5413']}},'fields':['Award ID','Recipient Name','Recipient UEI','Award Amount','NAICS','Recipient Location','Start Date'],'sort':'Award Amount','order':'desc','spending_level':'awards'}
  req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','User-Agent':'ObraSignal-market-research/3.0'})
  try:
   with urllib.request.urlopen(req,timeout=90) as r:d=json.load(r)
  except Exception as e:print('US page',page,'ERROR',e,flush=True);break
  res=d.get('results') or []
  if not res:break
  for x in res:
   name=(x.get('Recipient Name') or '').strip()
   if not likely_company(name):continue
   uei=str(x.get('Recipient UEI') or '')
   k=uei or norm(name);loc=x.get('Recipient Location') or {};na=x.get('NAICS') or {}
   p=agg.get(k)
   if p is None:p=agg[k]={'company_name':name,'country':'US','company_id':uei,'id_scheme':'UEI','city':loc.get('city_name','') if isinstance(loc,dict) else '','award_count':0,'buyers':set(),'total_awarded':0.0,'last_award_year':0,'category':str(na.get('code','')) if isinstance(na,dict) else str(na),'website':''}
   p['award_count']+=1;p['total_awarded']+=money(x.get('Award Amount'));p['last_award_year']=max(p['last_award_year'],date_year(x.get('Start Date')))
  page+=1
 for p in agg.values():p['buyer_count']=0;p['source']='USAspending federal contracts';p['source_url']='https://api.usaspending.gov/';p['fit_score']=round(min(100,52+9*math.log2(p['award_count']+1)+min(22,2.4*math.log10(p['total_awarded']+1))),1)
 rows=sorted(agg.values(),key=lambda x:(x['fit_score'],x['award_count'],x['total_awarded']),reverse=True)[:quota]
 print('US pages',page-1,'unique',len(agg),'selected',len(rows),flush=True);return rows

def colombia_market(quota=2500):
 base='https://www.datos.gov.co/resource/jbjy-vk9h.json';agg={};offset=0
 select='proveedor_adjudicado,documento_proveedor,tipo_de_contrato,objeto_del_contrato,valor_del_contrato,fecha_de_firma,urlproceso'
 while offset<250000 and len(agg)<quota*4:
  q={'$limit':'50000','$offset':str(offset),'$select':select,'$where':"fecha_de_firma >= '2024-01-01T00:00:00.000'",'$order':'fecha_de_firma DESC'}
  url=base+'?'+urllib.parse.urlencode(q,safe="',><=()")
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'ObraSignal-market-research/3.0'})
   with urllib.request.urlopen(req,timeout=120) as r:rows=json.load(r)
  except Exception as e:print('CO ERROR',e,flush=True);break
  if not rows:break
  for x in rows:
   text=norm((x.get('tipo_de_contrato') or '')+' '+(x.get('objeto_del_contrato') or ''))
   if 'obra' not in text and not any(norm(k) in text for k in KEYWORDS):continue
   name=(x.get('proveedor_adjudicado') or '').strip()
   if not likely_company(name):continue
   iid=str(x.get('documento_proveedor') or '');k=iid or norm(name)
   p=agg.get(k)
   if p is None:p=agg[k]={'company_name':name,'country':'CO','company_id':iid,'id_scheme':'NIT/documento proveedor','city':'','award_count':0,'buyers':set(),'total_awarded':0.0,'last_award_year':0,'category':x.get('tipo_de_contrato') or 'contract','website':''}
   p['award_count']+=1;p['total_awarded']+=money(x.get('valor_del_contrato'));p['last_award_year']=max(p['last_award_year'],date_year(x.get('fecha_de_firma')))
  offset+=len(rows)
  if len(rows)<50000:break
 for p in agg.values():p['buyer_count']=0;p['source']='Colombia SECOP II contratos electrónicos';p['source_url']='https://www.datos.gov.co/resource/jbjy-vk9h.json';p['fit_score']=round(min(100,52+8*math.log2(p['award_count']+1)+min(20,2.1*math.log10(p['total_awarded']+1))+(8 if p['last_award_year']>=2026 else 5)),1)
 rows=sorted(agg.values(),key=lambda x:(x['fit_score'],x['award_count'],x['total_awarded']),reverse=True)[:quota]
 print('CO rows',offset,'unique',len(agg),'selected',len(rows),flush=True);return rows

def canada_market(quota=1500):
 url='https://canadabuys.canada.ca/opendata/pub/contractHistoryComplete-contratsOctroyesComplet.csv';agg={};seen=0
 req=urllib.request.Request(url,headers={'User-Agent':'ObraSignal-market-research/3.0'})
 try:
  with urllib.request.urlopen(req,timeout=180) as resp:
   t=io.TextIOWrapper(resp,encoding='utf-8-sig',errors='replace',newline='');rd=csv.DictReader(t)
   for row in rd:
    seen+=1
    vals=' '.join(str(v or '') for v in row.values());txt=norm(vals)
    if not any(norm(k) in txt for k in KEYWORDS):continue
    # resilient bilingual header lookup
    name='';value=0.0;date='';city='';ident=''
    for k,v in row.items():
     nk=norm(k)
     if not name and v and ('supplier' in nk or 'fournisseur' in nk or 'vendor' in nk):name=str(v).strip()
     if not date and v and ('award date' in nk or 'date attribution' in nk):date=str(v)
     if not city and v and ('supplier city' in nk or 'ville fournisseur' in nk):city=str(v)
     if not ident and v and ('supplier number' in nk or 'numero fournisseur' in nk):ident=str(v)
     if v and ('contract value' in nk or 'valeur contrat' in nk):value=max(value,money(v))
    if not likely_company(name):continue
    k=ident or norm(name);p=agg.get(k)
    if p is None:p=agg[k]={'company_name':name,'country':'CA','company_id':ident,'id_scheme':'CanadaBuys supplier id','city':city,'award_count':0,'buyers':set(),'total_awarded':0.0,'last_award_year':0,'category':'construction/engineering keyword match','website':''}
    p['award_count']+=1;p['total_awarded']+=value;p['last_award_year']=max(p['last_award_year'],date_year(date))
    if seen>=300000 or len(agg)>=quota*5:break
 except Exception as e:print('CA ERROR',e,flush=True)
 for p in agg.values():p['buyer_count']=0;p['source']='CanadaBuys contract history';p['source_url']='https://canadabuys.canada.ca/en/procurement-and-contracting-data';p['fit_score']=round(min(100,50+8*math.log2(p['award_count']+1)+min(20,2.0*math.log10(p['total_awarded']+1))+(8 if p['last_award_year']>=2026 else 4)),1)
 rows=sorted(agg.values(),key=lambda x:(x['fit_score'],x['award_count'],x['total_awarded']),reverse=True)[:quota]
 print('CA seen',seen,'unique',len(agg),'selected',len(rows),flush=True);return rows

def main():
 allrows=[]
 with ThreadPoolExecutor(max_workers=6) as ex:
  fut={ex.submit(ocp_market,c,*cfg):c for c,cfg in OCP.items()}
  for f in as_completed(fut):
   try:allrows.extend(f.result())
   except Exception as e:print('market failure',fut[f],e,flush=True)
 for fn in (us_market,colombia_market,canada_market):
  try:allrows.extend(fn())
  except Exception as e:print(fn.__name__,'FAIL',e,flush=True)
 # Cross-market conservative dedupe (same country + identifier/name).
 ded={}
 for r in allrows:
  k=(r['country'],norm(r.get('company_id')) or norm(r['company_name']))
  if k not in ded or r['fit_score']>ded[k]['fit_score']:ded[k]=r
 rows=sorted(ded.values(),key=lambda x:(x['fit_score'],x['award_count'],x['total_awarded']),reverse=True)
 fields=['rank','company_name','country','company_id','id_scheme','city','fit_score','award_count','buyer_count','total_awarded','last_award_year','category','website','source','source_url']
 with open(OUT/'obrasignal_non_europe_active45_candidates.csv','w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for i,r in enumerate(rows,1):q=dict(r);q['rank']=i;w.writerow({k:q.get(k,'') for k in fields})
 by=defaultdict(int)
 for r in rows:by[r['country']]+=1
 summary={'generated_utc':datetime.now(timezone.utc).isoformat(),'selected':len(rows),'countries':dict(sorted(by.items())),'sources':'official/public procurement award datasets only','privacy':'business/entity data only; no personal outreach contacts collected','target_role':'supplement Europe universe so final 100k spans all 45 active ObraSignal markets'}
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
