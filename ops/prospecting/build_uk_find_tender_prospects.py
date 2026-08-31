#!/usr/bin/env python3
"""Build recent UK ObraSignal prospects from the official Find a Tender OCDS API.

Only role/business supplier emails are retained for outreach enrichment. Person-like
emails are deliberately not stored in the contact output.
"""
from __future__ import annotations
import csv,json,os,re,time,urllib.parse,urllib.request,urllib.error
from datetime import datetime, timezone
from pathlib import Path

OUT=Path(os.environ.get('OUT_DIR','uk_fts_output')); OUT.mkdir(parents=True,exist_ok=True)
START=os.environ.get('FTS_START','2025-01-01T00:00:00')
END=os.environ.get('FTS_END','2026-08-31T23:59:59')
MAX_PAGES=int(os.environ.get('FTS_MAX_PAGES','500'))
BASE='https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages'
CPV={'45':'construction works','71':'engineering/architecture','50':'repair/maintenance','31':'electrical equipment','32':'telecom/electronic equipment','43':'construction machinery','42':'industrial machinery','44':'construction materials','90':'environmental/waste services','65':'utilities'}
ROLE_WORDS={'info','sales','office','enquiries','enquiry','admin','commercial','tenders','tender','contracts','contract','contact','business','bids','bid','quotes','estimating','estimates','reception','hello','mail','support','projects','project','marketing','accounts','procurement','customerservice','service','general','uk'}

def norm(s):return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9]+',' ',(s or '').casefold())).strip()
def role_email(e):
 e=(e or '').strip().lower()
 if '@' not in e:return ''
 local=e.split('@',1)[0]
 toks=set(re.split(r'[^a-z]+',local))
 if toks & ROLE_WORDS:return e
 if any(local.startswith(x) for x in ROLE_WORDS):return e
 return ''
def cpv_codes(rel):
 out=set()
 def walk(x):
  if isinstance(x,dict):
   c=x.get('classification')
   if isinstance(c,dict):
    code=re.sub(r'\D','',str(c.get('id','')))
    if code[:2] in CPV:out.add(code[:2])
   ac=x.get('additionalClassifications')
   if isinstance(ac,list):
    for c in ac:
     if isinstance(c,dict):
      code=re.sub(r'\D','',str(c.get('id','')))
      if code[:2] in CPV:out.add(code[:2])
   for v in x.values():walk(v)
  elif isinstance(x,list):
   for v in x:walk(v)
 walk(rel.get('tender',{}))
 for a in rel.get('awards',[]) or []:walk(a)
 for c in rel.get('contracts',[]) or []:walk(c)
 return out

def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'ObraSignal-prospect-research/2.2','Accept':'application/json'})
 for attempt in range(8):
  try:
   with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)
  except urllib.error.HTTPError as e:
   if e.code in {429,503}:
    wait=int(e.headers.get('Retry-After') or 15);time.sleep(min(120,max(5,wait)));continue
   if e.code in {500,502,504}:
    time.sleep(min(60,5*(attempt+1)));continue
   raise
  except Exception as e:
   print('request retry',attempt+1,type(e).__name__,flush=True);time.sleep(min(45,4*(attempt+1)))
 raise RuntimeError('Find a Tender request failed after retries')

def main():
 q={'updatedFrom':START,'updatedTo':END,'stages':'award','limit':'100'}
 url=BASE+'?'+urllib.parse.urlencode(q); P={}; pages=releases=relevant=0
 while url and pages < MAX_PAGES:
  d=get(url);pages+=1
  batch=d.get('releases',[]) or [];releases+=len(batch)
  for rel in batch:
   cats=cpv_codes(rel)
   if not cats:continue
   relevant+=1
   buyer=(rel.get('buyer') or {}).get('name','')
   date=str(rel.get('date') or d.get('publishedDate') or '')
   year=int(date[:4]) if date[:4].isdigit() else 0
   parties={str(p.get('id','')):p for p in (rel.get('parties',[]) or []) if p.get('id')}
   supplier_ids=set()
   for a in rel.get('awards',[]) or []:
    if str(a.get('status','')).lower() not in {'','active','pending'}:continue
    for s in a.get('suppliers',[]) or []:
     if s.get('id'):supplier_ids.add(str(s['id']))
     else:
      sid=str((s.get('identifier') or {}).get('id') or '')
      name=(s.get('name') or '').strip()
      if name:
       parties['inline:'+norm(name)]={**s,'id':'inline:'+norm(name),'identifier':s.get('identifier') or {'id':sid},'roles':['supplier']}
       supplier_ids.add('inline:'+norm(name))
   if not supplier_ids:
    for pid,p in parties.items():
     if 'supplier' in [str(x).lower() for x in p.get('roles',[]) or []]:supplier_ids.add(pid)
   for pid in supplier_ids:
    pty=parties.get(pid) or {}
    name=(pty.get('name') or '').strip()
    if not name:continue
    ident=pty.get('identifier') or {}; scheme=str(ident.get('scheme') or ''); ident_id=str(ident.get('id') or '')
    key=(scheme,ident_id) if ident_id else ('name',norm(name))
    p=P.get(key)
    if p is None:
     addr=pty.get('address') or {}; cp=pty.get('contactPoint') or {}; em=role_email(cp.get('email'))
     p=P[key]={'company_name':name,'country':'GB','company_identifier':ident_id,'identifier_scheme':scheme,'address':addr.get('streetAddress',''),'locality':addr.get('locality',''),'postal_code':addr.get('postalCode',''),'region':addr.get('region',''),'business_email':em,'telephone':cp.get('telephone','') or '','award_count':0,'buyers':set(),'last_award_year':0,'categories':set(),'source_notice':''}
    p['award_count']+=1;p['last_award_year']=max(p['last_award_year'],year);p['categories'].update(cats)
    if buyer:p['buyers'].add(norm(buyer))
    cp=pty.get('contactPoint') or {}; em=role_email(cp.get('email'))
    if em and not p['business_email']:p['business_email']=em
    if cp.get('telephone') and not p['telephone']:p['telephone']=cp['telephone']
    docs=rel.get('documents',[]) or []
    for doc in docs:
     u=doc.get('url')
     if u and 'find-tender.service.gov.uk' in str(u):p['source_notice']=u;break
  links=d.get('links') or {};nxt=links.get('next')
  if nxt and not str(nxt).startswith('http'):nxt=urllib.parse.urljoin(BASE,str(nxt))
  url=nxt or None
  if pages%25==0:print('pages',pages,'releases',releases,'unique',len(P),flush=True)
  if url:time.sleep(0.20)
 rows=[]
 for p in P.values():
  p['buyer_count']=len(p.pop('buyers'));p['procurement_categories']=';'.join(f'{c}:{CPV[c]}' for c in sorted(p.pop('categories')));rows.append(p)
 rows.sort(key=lambda x:(x['award_count'],x['buyer_count'],x['last_award_year'],bool(x['business_email'])),reverse=True)
 fields=['rank','company_name','country','company_identifier','identifier_scheme','address','locality','postal_code','region','business_email','telephone','award_count','buyer_count','last_award_year','procurement_categories','source_notice']
 with open(OUT/'obrasignal_uk_fts_prospects.csv','w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for i,p in enumerate(rows,1):q=dict(p);q['rank']=i;w.writerow(q)
 summary={'generated_utc':datetime.now(timezone.utc).isoformat(),'source':'UK Find a Tender OCDS','start':START,'end':END,'max_pages':MAX_PAGES,'pages':pages,'releases_seen':releases,'relevant_releases':relevant,'unique_suppliers':len(rows),'role_based_business_emails':sum(bool(r['business_email']) for r in rows),'privacy':'Public procurement/business data. Person-like supplier emails are not retained for outreach.'}
 (OUT/'obrasignal_uk_fts_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
