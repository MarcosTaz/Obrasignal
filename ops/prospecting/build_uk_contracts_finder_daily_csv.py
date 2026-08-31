#!/usr/bin/env python3
"""Build recent UK ObraSignal prospects from official Contracts Finder daily OCDS CSVs.

Source: Crown Commercial Service / National Data Library daily flattened OCDS exports.
Retains only generic/role business emails; person-like emails are excluded from outreach data.
"""
from __future__ import annotations
import csv, io, json, os, re, urllib.request, urllib.error
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

OUT=Path(os.environ.get('OUT_DIR','uk_cf_daily_output')); OUT.mkdir(parents=True,exist_ok=True)
START=date.fromisoformat(os.environ.get('CF_START_DATE','2026-08-01'))
END=date.fromisoformat(os.environ.get('CF_END_DATE','2026-08-29'))
BASE='https://cdp-sirsi-production-cfs-471112843276.s3.eu-west-2.amazonaws.com/Harvester-new/{ym}/Contracts%20Finder%20OCDS%20{d}.csv'
CPV={'45':'construction works','71':'engineering/architecture','50':'repair/maintenance','31':'electrical equipment','32':'telecom/electronic equipment','43':'construction machinery','42':'industrial machinery','44':'construction materials','90':'environmental/waste services','65':'utilities'}
ROLE_WORDS={'info','sales','office','enquiries','enquiry','admin','commercial','tenders','tender','contracts','contract','contact','business','bids','bid','quotes','estimating','estimates','reception','hello','mail','support','projects','project','marketing','accounts','procurement','customerservice','service','general','uk','operations','work','works'}

def norm(s):return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9]+',' ',(s or '').casefold())).strip()
def role_email(e):
 e=(e or '').strip().lower()
 if '@' not in e:return ''
 local=e.split('@',1)[0]
 toks=set(re.split(r'[^a-z]+',local))
 return e if toks & ROLE_WORDS or any(local.startswith(x) for x in ROLE_WORDS) else ''
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'ObraSignal-prospect-research/2.3','Accept':'text/csv,*/*'})
 try:
  with urllib.request.urlopen(req,timeout=120) as r:return r.read()
 except urllib.error.HTTPError as e:
  if e.code==404:return b''
  raise

def field(row,suffix):
 # flattened export normally has releases/0/ prefix; make lookup suffix-based for resilience
 for k,v in row.items():
  if k.endswith(suffix) and v:return v
 return ''
def party_indexes(row):
 out=set()
 for k in row:
  m=re.search(r'/parties/(\d+)/',k)
  if m:out.add(int(m.group(1)))
 return sorted(out)
def award_supplier_ids(row):
 ids=set(); names=set()
 for k,v in row.items():
  if not v:continue
  if re.search(r'/awards/\d+/suppliers/\d+/id$',k):ids.add(v.strip())
  elif re.search(r'/awards/\d+/suppliers/\d+/name$',k):names.add(norm(v))
 return ids,names
def category(row):
 codes=[]
 for k,v in row.items():
  if not v:continue
  if k.endswith('/tender/classification/id') or re.search(r'/tender/additionalClassifications/\d+/id$',k):
   c=re.sub(r'\D','',v); codes.append(c)
 for c in codes:
  if c[:2] in CPV:return c[:2],c[:8]
 main=norm(field(row,'/tender/mainProcurementCategory'))
 if main=='works':return '45',''
 return '',''

def main():
 P={}; days=rows_seen=relevant=awarded=0; cur=START
 while cur<=END:
  ds=cur.isoformat();url=BASE.format(ym=ds[:7],d=ds)
  raw=get(url);cur+=timedelta(days=1)
  if not raw:continue
  days+=1
  text=io.StringIO(raw.decode('utf-8-sig',errors='replace'))
  rd=csv.DictReader(text)
  for row in rd:
   rows_seen+=1; pref,cpv=category(row)
   if not pref:continue
   relevant+=1
   supplier_ids,supplier_names=award_supplier_ids(row)
   if not supplier_ids and not supplier_names:continue
   awarded+=1
   buyer=field(row,'/buyer/name')
   award_date=''
   for k,v in row.items():
    if v and re.search(r'/awards/\d+/date$',k):award_date=v;break
   year=int(award_date[:4]) if award_date[:4].isdigit() else int(ds[:4])
   for i in party_indexes(row):
    pre=f'releases/0/parties/{i}/'
    pid=row.get(pre+'id','').strip(); name=(row.get(pre+'identifier/legalName') or row.get(pre+'name') or '').strip()
    roles=[v.strip().lower() for k,v in row.items() if k.startswith(pre+'roles/') and v]
    if not name:continue
    if pid not in supplier_ids and norm(name) not in supplier_names and 'supplier' not in roles:continue
    ident_id=(row.get(pre+'identifier/id') or '').strip(); scheme=(row.get(pre+'identifier/scheme') or '').strip()
    key=(scheme,ident_id) if ident_id else ('name',norm(name))
    p=P.get(key)
    if p is None:
     em=role_email(row.get(pre+'contactPoint/email',''))
     p=P[key]={'company_name':name,'country':'GB','company_identifier':ident_id,'identifier_scheme':scheme,'address':row.get(pre+'address/streetAddress',''),'locality':row.get(pre+'address/locality',''),'postal_code':row.get(pre+'address/postalCode',''),'region':row.get(pre+'address/region',''),'business_email':em,'telephone':row.get(pre+'contactPoint/telephone',''),'website':row.get(pre+'details/url',''),'award_count':0,'buyers':set(),'last_award_year':0,'categories':set(),'source_notice':field(row,'/uri') or row.get('uri','')}
    p['award_count']+=1;p['last_award_year']=max(p['last_award_year'],year);p['categories'].add(pref)
    if buyer:p['buyers'].add(norm(buyer))
    em=role_email(row.get(pre+'contactPoint/email',''))
    if em and not p['business_email']:p['business_email']=em
    if row.get(pre+'contactPoint/telephone') and not p['telephone']:p['telephone']=row[pre+'contactPoint/telephone']
    if row.get(pre+'details/url') and not p['website']:p['website']=row[pre+'details/url']
  print(ds,'unique suppliers',len(P),flush=True)
 rows=[]
 for p in P.values():
  p['buyer_count']=len(p.pop('buyers'));p['procurement_categories']=';'.join(f'{c}:{CPV[c]}' for c in sorted(p.pop('categories')));rows.append(p)
 rows.sort(key=lambda x:(x['award_count'],x['buyer_count'],bool(x['business_email']),x['last_award_year']),reverse=True)
 fields=['rank','company_name','country','company_identifier','identifier_scheme','address','locality','postal_code','region','business_email','telephone','website','award_count','buyer_count','last_award_year','procurement_categories','source_notice']
 with open(OUT/'obrasignal_uk_contracts_finder_recent.csv','w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for i,p in enumerate(rows,1):q=dict(p);q['rank']=i;w.writerow(q)
 summary={'generated_utc':datetime.now(timezone.utc).isoformat(),'source':'UK Contracts Finder daily OCDS CSV / National Data Library','start':START.isoformat(),'end':END.isoformat(),'days_loaded':days,'rows_seen':rows_seen,'relevant_rows':relevant,'award_rows':awarded,'unique_suppliers':len(rows),'role_based_business_emails':sum(bool(r['business_email']) for r in rows),'phones':sum(bool(r['telephone']) for r in rows),'websites':sum(bool(r['website']) for r in rows),'privacy':'Public procurement/business data. Person-like supplier emails are excluded from outreach data.'}
 (OUT/'obrasignal_uk_contracts_finder_recent_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
