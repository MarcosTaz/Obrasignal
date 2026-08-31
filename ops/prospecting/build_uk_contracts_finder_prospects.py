#!/usr/bin/env python3
"""Extract ObraSignal-relevant UK award suppliers from the official Contracts Finder OCDS API."""
from __future__ import annotations
import csv, json, os, re, time, urllib.parse, urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

OUT=Path(os.environ.get('OUT_DIR','uk_prospect_output')); OUT.mkdir(parents=True,exist_ok=True)
START=os.environ.get('CF_START','2024-01-01T00:00:00Z')
END=os.environ.get('CF_END','2026-08-31T23:59:59Z')
BASE='https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search'
CPV={'45':'construction works','71':'engineering/architecture','50':'repair/maintenance','31':'electrical equipment','32':'telecom/electronic equipment','43':'construction machinery','42':'industrial machinery','44':'construction materials','90':'environmental/waste services','65':'utilities'}

def norm(s): return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9]+',' ',(s or '').casefold())).strip()
def cpvs(release):
 out=set()
 def scan(x):
  if isinstance(x,dict):
   c=x.get('classification')
   if isinstance(c,dict):
    code=re.sub(r'\D','',str(c.get('id','')))
    if code[:2] in CPV: out.add(code[:2])
   for v in x.values(): scan(v)
  elif isinstance(x,list):
   for v in x: scan(v)
 scan(release.get('tender',{}))
 for a in release.get('awards',[]) or []: scan(a)
 return out

def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'ObraSignal-prospect-research/2.0','Accept':'application/json'})
 for attempt in range(6):
  try:
   with urllib.request.urlopen(req,timeout=90) as r:
    return json.load(r)
  except urllib.error.HTTPError as e:
   if e.code==403:
    time.sleep(300); continue
   if e.code in {429,500,502,503,504}:
    time.sleep(min(60,5*(attempt+1))); continue
   raise
  except Exception:
   time.sleep(min(30,3*(attempt+1)))
 raise RuntimeError('Contracts Finder request failed after retries')

def main():
 q={'publishedFrom':START,'publishedTo':END,'stages':'award','limit':'100'}
 url=BASE+'?'+urllib.parse.urlencode(q)
 P={}; pages=0; releases=0; relevant=0
 while url:
  data=get(url); pages+=1
  batch=data.get('releases',[]) or []; releases+=len(batch)
  for r in batch:
   cats=cpvs(r)
   if not cats: continue
   relevant+=1
   buyer=(r.get('buyer') or {}).get('name','')
   date=r.get('date') or data.get('publishedDate') or ''
   year=int(date[:4]) if str(date)[:4].isdigit() else 0
   awards=r.get('awards',[]) or []
   for a in awards:
    status=str(a.get('status','')).lower()
    if status and status not in {'active','pending'}: continue
    value=(a.get('value') or {}).get('amount') or 0
    for s in a.get('suppliers',[]) or []:
     name=(s.get('name') or '').strip()
     if not name: continue
     sid=str((s.get('identifier') or {}).get('id') or s.get('id') or '').strip()
     scheme=str((s.get('identifier') or {}).get('scheme') or '').strip()
     key=('id',scheme,sid) if sid else ('name',norm(name))
     p=P.get(key)
     if p is None:
      addr=s.get('address') or {}
      p=P[key]={'company_name':name,'country':'GB','company_identifier':sid,'identifier_scheme':scheme,'address':addr.get('streetAddress',''),'locality':addr.get('locality',''),'postal_code':addr.get('postalCode',''),'award_count':0,'buyer_names':set(),'total_awarded_gbp':0.0,'last_award_year':0,'categories':set(),'evidence_url':''}
     p['award_count']+=1
     if buyer:p['buyer_names'].add(norm(buyer))
     try:p['total_awarded_gbp']+=float(value or 0)
     except:pass
     p['categories'].update(cats); p['last_award_year']=max(p['last_award_year'],year)
     docs=r.get('documents',[]) or []
     for d in docs:
      if d.get('url'):p['evidence_url']=d['url'];break
  links=data.get('links') or {}
  nxt=links.get('next')
  if nxt and not str(nxt).startswith('http'):
   nxt=urllib.parse.urljoin(BASE,nxt)
  url=nxt or None
  if pages%25==0: print('pages',pages,'releases',releases,'unique',len(P),flush=True)
  if url: time.sleep(3.2)
 rows=[]
 for p in P.values():
  p['buyer_count']=len(p.pop('buyer_names')); p['procurement_categories']=';'.join(f'{c}:{CPV[c]}' for c in sorted(p.pop('categories'))); rows.append(p)
 rows.sort(key=lambda x:(x['award_count'],x['buyer_count'],x['total_awarded_gbp']),reverse=True)
 fields=['rank','company_name','country','company_identifier','identifier_scheme','address','locality','postal_code','award_count','buyer_count','total_awarded_gbp','last_award_year','procurement_categories','evidence_url']
 with open(OUT/'obrasignal_uk_contracts_finder_prospects.csv','w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for i,p in enumerate(rows,1):p=dict(p);p['rank']=i;w.writerow(p)
 summary={'generated_utc':datetime.utcnow().isoformat()+'Z','source':'UK Contracts Finder OCDS','start':START,'end':END,'pages':pages,'releases_seen':releases,'relevant_releases':relevant,'unique_suppliers':len(rows),'privacy':'Public business/procurement data only; no private or personal contact data.'}
 (OUT/'obrasignal_uk_contracts_finder_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
