#!/usr/bin/env python3
"""Extract historical UK supplier candidates from TED awards for ObraSignal expansion.

TED legacy data commonly uses country code UK while ObraSignal canonicalises the market
as GB. This pass exists to guarantee real UK representation in the +100k expansion.
"""
from __future__ import annotations
import csv, io, json, math, os, re, sys, time, unicodedata, urllib.request, zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

OUT=Path(os.environ.get('OUT_DIR','uk_historical_output')); OUT.mkdir(parents=True,exist_ok=True)
RAW=OUT/'raw'; RAW.mkdir(exist_ok=True)
YEARS=[2018,2017,2016,2015,2014]
URL='https://data.europa.eu/api/hub/store/data/ted-contract-award-notices-{year}.zip'
TARGET=int(os.environ.get('TARGET','40000'))
CPV={'45':24,'71':21,'50':19,'51':18,'31':17,'32':15,'43':15,'42':14,'44':14,'90':13,'65':11,'34':11,'35':11,'38':10,'39':9,'60':9,'63':9,'72':10,'79':8}
ALIASES={
'name':['WIN_NAME','WIN_NAME_1','CONTRACTOR_NAME'],'country':['WIN_COUNTRY_CODE','WIN_COUNTRY','CONTRACTOR_COUNTRY_CODE'],
'town':['WIN_TOWN','CONTRACTOR_TOWN'],'national_id':['WIN_NATIONALID','WIN_NATIONAL_ID','CONTRACTOR_NATIONALID'],
'cpv':['CPV','CPV_MAIN','CPV_CODE','MAIN_CPV_CODE'],'contract_type':['TYPE_OF_CONTRACT','CONTRACT_TYPE'],
'buyer_name':['CAE_NAME','BUYER_NAME'],'value':['VALUE_EURO','AWARD_VALUE_EURO','VALUE','VALUE_EURO_FIN_1'],
'award_date':['DT_AWARD','AWARD_DATE'],'dispatch_date':['DT_DISPATCH','PUBLICATION_DATE'],'sme':['B_CONTRACTOR_SME','WIN_SME','SME'],
'url':['TED_NOTICE_URL','NOTICE_URL','URL'],'notice':['ID_NOTICE_CAN','NOTICE_ID','ID_NOTICE']}
LEGAL={'ltd','limited','llp','plc','inc','co'}

def norm(s):
 s=unicodedata.normalize('NFKD',(s or '').strip()); s=''.join(c for c in s if not unicodedata.combining(c)); s=s.casefold(); s=re.sub(r'[^a-z0-9]+',' ',s); return re.sub(r'\s+',' ',s).strip()
def loose(s):
 p=norm(s).split()
 while p and p[-1] in LEGAL:p.pop()
 return ' '.join(p)
def pick(r,f):
 for k in ALIASES[f]:
  v=r.get(k)
  if v is not None and str(v).strip():return str(v).strip()
 return ''
def money(s):
 if not s:return 0.0
 s=s.strip().replace('\u00a0','').replace(' ','')
 if s.count(',')==1 and '.' not in s:s=s.replace(',','.')
 else:s=s.replace(',','')
 try:
  v=float(s);return v if 0<=v<=1e12 else 0.0
 except:return 0.0
def yearof(s,f):
 if not s:return f
 m=re.search(r'(20\d{2})',s);return int(m.group(1)) if m else f
def download(y):
 p=RAW/f'ted-{y}.zip'
 if p.exists() and p.stat().st_size>100000:return p
 req=urllib.request.Request(URL.format(year=y),headers={'User-Agent':'ObraSignal-prospect-research/3.1'})
 for a in range(4):
  try:
   with urllib.request.urlopen(req,timeout=180) as rr,open(p,'wb') as f:
    while True:
     b=rr.read(1024*1024)
     if not b:break
     f.write(b)
   return p
  except Exception as e:
   print('download',y,'retry',a+1,e,file=sys.stderr)
   if p.exists():p.unlink()
   time.sleep(3*(a+1))
 return None
def rows(zp):
 with zipfile.ZipFile(zp) as z:
  for n in [x for x in z.namelist() if x.lower().endswith(('.csv','.txt'))]:
   with z.open(n) as raw:
    t=io.TextIOWrapper(raw,encoding='utf-8-sig',errors='replace',newline=''); first=t.readline()
    if not first:continue
    d=';' if first.count(';')>first.count(',') else ',';t.seek(0);rd=csv.DictReader(t,delimiter=d)
    if not rd.fieldnames:continue
    rd.fieldnames=[(h or '').strip().upper() for h in rd.fieldnames]
    for r in rd:yield {str(k).strip().upper():(v or '') for k,v in r.items() if k is not None}
def cat(r):
 c=re.sub(r'\D','',pick(r,'cpv'));p=c[:2]
 if p in CPV:return p,c[:8]
 ct=norm(pick(r,'contract_type'))
 if ct in {'w','works','work'} or 'work' in ct:return '45',c[:8]
 return '',c[:8]
def main():
 csv.field_size_limit(min(sys.maxsize,2_000_000_000));P={};seen=rel=0
 for y in YEARS:
  zp=download(y)
  if not zp:continue
  for r in rows(zp):
   seen+=1;pref,cpv=cat(r)
   if not pref:continue
   rawc=pick(r,'country').upper()[:2]
   if rawc not in {'UK','GB'}:continue
   rel+=1;name=pick(r,'name')
   if not name:continue
   nid=norm(pick(r,'national_id')).replace(' ','');nn=norm(name)
   if not nn:continue
   key=('id',nid) if nid and nid not in {'0','1','uk','gb','n/a','na'} and len(nid)>=4 else ('name',nn)
   p=P.get(key)
   if p is None:p=P[key]={'company_name':name,'normalized_name':loose(name),'country':'GB','town':pick(r,'town'),'national_id':pick(r,'national_id'),'award_count':0,'buyers':set(),'total_awarded_eur':0.0,'last_award_year':0,'last_cpv':'','categories':set(),'sme_evidence':'unknown','evidence_url':'','notice_id':''}
   p['award_count']+=1;p['total_awarded_eur']+=money(pick(r,'value'));p['categories'].add(pref)
   b=pick(r,'buyer_name')
   if b:p['buyers'].add(norm(b))
   if norm(pick(r,'sme')) in {'y','yes','true','1'}:p['sme_evidence']='yes'
   ay=yearof(pick(r,'award_date') or pick(r,'dispatch_date'),y)
   if ay>=p['last_award_year']:
    p['last_award_year']=ay;p['last_cpv']=cpv;p['town']=pick(r,'town') or p['town'];p['evidence_url']=pick(r,'url') or p['evidence_url'];p['notice_id']=pick(r,'notice') or p['notice_id']
  print(y,'UK unique',len(P),flush=True)
 out=[]
 for p in P.values():
  p['buyer_count']=len(p.pop('buyers'));cats=sorted(p.pop('categories'));p['procurement_categories']=';'.join(cats);rec=max(0,19-(2018-p['last_award_year'])*2);p['fit_score']=round(min(100,rec+min(24,5*math.log2(p['award_count']+1))+min(12,3*math.log2(p['buyer_count']+1))+max((CPV[x] for x in cats),default=0)+(5 if p['sme_evidence']=='yes' else 0)),1);p['tier']='A1' if p['fit_score']>=78 else 'A2' if p['fit_score']>=68 else 'B' if p['fit_score']>=54 else 'C';p['source_dataset']='TED contract award notices 2014-2018; UK/GB legacy mapping; European Commission';p['contact_status']='needs_current_business_verification';out.append(p)
 out.sort(key=lambda x:(x['fit_score'],x['last_award_year'],x['award_count'],x['buyer_count']),reverse=True);out=out[:TARGET]
 fields=['rank','company_name','normalized_name','country','town','national_id','fit_score','tier','award_count','buyer_count','last_award_year','last_cpv','procurement_categories','total_awarded_eur','sme_evidence','evidence_url','notice_id','contact_status','source_dataset']
 with open(OUT/'obrasignal_uk_historical_candidates.csv','w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for i,r in enumerate(out,1):q=dict(r);q['rank']=i;w.writerow({k:q.get(k,'') for k in fields})
 s={'generated_utc':datetime.now(timezone.utc).isoformat(),'years':YEARS,'rows_seen':seen,'relevant_uk_rows':rel,'unique_uk_suppliers':len(P),'selected':len(out)};(OUT/'summary.json').write_text(json.dumps(s,indent=2),encoding='utf-8');print(json.dumps(s,indent=2))
if __name__=='__main__':main()
