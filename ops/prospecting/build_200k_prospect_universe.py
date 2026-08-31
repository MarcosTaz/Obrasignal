#!/usr/bin/env python3
"""Build an evidence-first ObraSignal prospect universe across every active European market.

Uses public European Commission TED contract-award data only. The output is a company
universe for later business-contact enrichment; it does not collect personal contacts.
"""
from __future__ import annotations
import csv, io, json, math, os, re, sys, time, unicodedata, urllib.request, zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

OUT=Path(os.environ.get('OUT_DIR','prospect_output_200k')); OUT.mkdir(parents=True,exist_ok=True)
RAW=OUT/'raw'; RAW.mkdir(exist_ok=True)
YEARS=[2023,2022,2021,2020,2019]
URL='https://data.europa.eu/api/hub/store/data/ted-contract-award-notices-{year}.zip'
TARGET=int(os.environ.get('TARGET','200000'))

BUILD={'PT':20,'ES':18,'IT':18,'FR':18,'DE':18,'CH':17,'GB':17,'NL':15,'PL':15}
SHARED={'AT','BE','BG','HR','CY','CZ','DK','EE','FI','GR','HU','IS','IE','LV','LI','LT','LU','MT','NO','RO','SK','SI','SE'}
ACTIVE=set(BUILD)|SHARED

# ObraSignal-relevant public procurement families. Works stays strongest; adjacent
# technical categories materially expand the addressable buyer/supplier universe.
CPV_WEIGHT={'45':20,'71':16,'50':14,'31':13,'32':11,'43':11,'42':10,'44':10,'90':8,'65':7}
CPV_LABEL={'45':'construction works','71':'engineering/architecture','50':'repair/maintenance','31':'electrical equipment','32':'telecom/electronic equipment','43':'construction machinery','42':'industrial machinery','44':'construction materials','90':'environmental/waste services','65':'utilities'}
ALIASES={
'name':['WIN_NAME','WIN_NAME_1','CONTRACTOR_NAME'],'country':['WIN_COUNTRY_CODE','WIN_COUNTRY','CONTRACTOR_COUNTRY_CODE'],
'town':['WIN_TOWN','CONTRACTOR_TOWN'],'nuts':['WIN_NUTS','WIN_NUTS_CODE'],'national_id':['WIN_NATIONALID','WIN_NATIONAL_ID','CONTRACTOR_NATIONALID'],
'cpv':['CPV','CPV_MAIN','CPV_CODE'],'contract_type':['TYPE_OF_CONTRACT','CONTRACT_TYPE'],'buyer_country':['ISO_COUNTRY_CODE','CAE_COUNTRY_CODE','BUYER_COUNTRY_CODE'],
'buyer_name':['CAE_NAME','BUYER_NAME'],'value':['VALUE_EURO','AWARD_VALUE_EURO','VALUE'],'award_date':['DT_AWARD','AWARD_DATE'],
'dispatch_date':['DT_DISPATCH','PUBLICATION_DATE'],'sme':['B_CONTRACTOR_SME','WIN_SME','SME'],'url':['TED_NOTICE_URL','NOTICE_URL','URL'],'notice':['ID_NOTICE_CAN','NOTICE_ID','ID_NOTICE']}
LEGAL={'ltd','limited','llp','plc','sa','sas','sasu','sarl','gmbh','ag','kg','bv','nv','oy','oyj','ab','as','aps','srl','spa','snc','sc','sl','slu','lda','unipessoal','sp','zoo','kft','sro','doo'}

def norm(s):
 s=unicodedata.normalize('NFKD',(s or '').strip()); s=''.join(c for c in s if not unicodedata.combining(c)); s=s.casefold(); s=re.sub(r'[^a-z0-9]+',' ',s); return re.sub(r'\s+',' ',s).strip()
def loose(s):
 p=norm(s).split()
 while p and p[-1] in LEGAL: p.pop()
 return ' '.join(p)
def pick(r,f):
 for k in ALIASES[f]:
  v=r.get(k)
  if v is not None and str(v).strip(): return str(v).strip()
 return ''
def money(s):
 if not s:return 0.0
 s=s.strip().replace('\u00a0','').replace(' ','')
 if s.count(',')==1 and '.' not in s:s=s.replace(',','.')
 else:s=s.replace(',','')
 try:
  v=float(s); return v if 0<=v<=1e12 else 0.0
 except:return 0.0
def award_year(s,fallback):
 if not s:return fallback
 for fmt in ('%d/%m/%y','%d/%m/%Y','%Y-%m-%d','%Y-%m-%dT%H:%M:%S'):
  try:return datetime.strptime(s[:19],fmt).year
  except:pass
 m=re.search(r'(20\d{2})',s); return int(m.group(1)) if m else fallback
def download(y):
 dest=RAW/f'ted-contract-award-notices-{y}.zip'
 if dest.exists() and dest.stat().st_size>1_000_000:return dest
 req=urllib.request.Request(URL.format(year=y),headers={'User-Agent':'ObraSignal-prospect-research/2.0'})
 for a in range(4):
  try:
   with urllib.request.urlopen(req,timeout=120) as rr,open(dest,'wb') as f:
    while True:
     b=rr.read(1024*1024)
     if not b:break
     f.write(b)
   if dest.stat().st_size<1000:raise RuntimeError('small download')
   return dest
  except Exception as e:
   print(f'download {y} attempt {a+1}: {e}',file=sys.stderr)
   if dest.exists():dest.unlink()
   time.sleep(3*(a+1))
 return None
def rows(zp):
 with zipfile.ZipFile(zp) as zf:
  for m in [x for x in zf.namelist() if x.lower().endswith(('.csv','.txt'))]:
   with zf.open(m) as raw:
    t=io.TextIOWrapper(raw,encoding='utf-8-sig',errors='replace',newline=''); first=t.readline()
    if not first:continue
    d=';' if first.count(';')>first.count(',') else ','; t.seek(0); rd=csv.DictReader(t,delimiter=d)
    if not rd.fieldnames:continue
    rd.fieldnames=[(h or '').strip().upper() for h in rd.fieldnames]
    for r in rd:yield {str(k).strip().upper():(v or '') for k,v in r.items() if k is not None}
def category(r):
 cpv=re.sub(r'\D','',pick(r,'cpv'))
 pref=cpv[:2]
 if pref in CPV_WEIGHT:return pref,cpv[:8]
 # Preserve explicit works even when a legacy row lacks CPV.
 ct=norm(pick(r,'contract_type'))
 if ct in {'w','works','work'} or 'work' in ct:return '45',cpv[:8]
 return '',cpv[:8]
def score(p):
 market=BUILD.get(p['country'],9)
 wins=min(24,5*math.log2(p['award_count']+1)); buyers=min(12,3*math.log2(p['buyer_count']+1))
 rec={2023:19,2022:17,2021:13,2020:9,2019:5}.get(p['last_award_year'],2)
 val=min(12,max(0,math.log10(p['total_awarded_eur']+1)*1.7)); sme=5 if p['sme_evidence']=='yes' else 0; ident=4 if p['national_id'] else 0
 cat=max((CPV_WEIGHT.get(x,0) for x in p['category_prefixes']),default=0)
 return round(min(100,market+wins+buyers+rec+val+sme+ident+cat*0.45),1)
def tier(s):return 'A1' if s>=80 else 'A2' if s>=70 else 'B' if s>=57 else 'C'

def main():
 csv.field_size_limit(min(sys.maxsize,2_000_000_000)); P={}; st=defaultdict(int)
 for y in YEARS:
  zp=download(y)
  if not zp:continue
  for r in rows(zp):
   st['rows_seen']+=1; pref,cpv=category(r)
   if not pref:continue
   st['relevant_rows']+=1; name=pick(r,'name')
   if not name or len(name)<2:continue
   country=pick(r,'country').upper()[:2] or pick(r,'buyer_country').upper()[:2]
   if country not in ACTIVE:continue
   nid=norm(pick(r,'national_id')).replace(' ',''); nn=norm(name)
   if not nn or nn in {'unknown','not specified','n a','na'}:continue
   key=f'{country}|id|{nid}' if nid else f'{country}|name|{nn}'
   ay=award_year(pick(r,'award_date') or pick(r,'dispatch_date'),y); val=money(pick(r,'value')); buyer=pick(r,'buyer_name'); sm=norm(pick(r,'sme'))
   p=P.get(key)
   if p is None:
    p=P[key]={'company_name':name.strip(),'normalized_name':loose(name),'country':country,'town':pick(r,'town'),'nuts':pick(r,'nuts'),'national_id':pick(r,'national_id'),'award_count':0,'buyers':set(),'total_awarded_eur':0.0,'max_award_eur':0.0,'last_award_year':0,'last_award_date':'','last_cpv':'','sme_evidence':'unknown','evidence_url':'','notice_id':'','source_years':set(),'category_prefixes':set()}
   p['award_count']+=1; p['total_awarded_eur']+=val; p['max_award_eur']=max(p['max_award_eur'],val); p['source_years'].add(y); p['category_prefixes'].add(pref)
   if buyer:p['buyers'].add(norm(buyer))
   if sm in {'y','yes','true','1','oui','si'}:p['sme_evidence']='yes'
   if ay>=p['last_award_year']:
    p['last_award_year']=ay; p['last_award_date']=pick(r,'award_date') or pick(r,'dispatch_date'); p['last_cpv']=cpv; p['evidence_url']=pick(r,'url') or p['evidence_url']; p['notice_id']=pick(r,'notice') or p['notice_id']; p['town']=pick(r,'town') or p['town']; p['nuts']=pick(r,'nuts') or p['nuts']
  print(y,len(P),flush=True)
 out=[]
 for p in P.values():
  p['buyer_count']=len(p.pop('buyers')); p['source_years']=','.join(map(str,sorted(p['source_years']))); cats=sorted(p['category_prefixes']); p['procurement_categories']=';'.join(f'{x}:{CPV_LABEL[x]}' for x in cats); p['fit_score']=score(p); p['tier']=tier(p['fit_score']); p['why_fit']=f"Public-procurement winner: {p['award_count']} award record(s), {p['buyer_count']} buyer(s), latest {p['last_award_year']}; categories {p['procurement_categories']}."; p['outreach_angle']='Personalized tender radar and shortlist based on the company’s demonstrated procurement categories, geography and award history.'; p['recommended_offer']='30-day assisted pilot' if p['fit_score']>=80 else '21-day ObraSignal Evaluation'; p['contact_status']='needs_public_business_contact_enrichment'; p['source_dataset']='TED contract award notices; European Commission; public data'; p['category_prefixes']=';'.join(cats); out.append(p)
 out.sort(key=lambda r:(r['fit_score'],r['award_count'],r['buyer_count'],r['total_awarded_eur']),reverse=True)
 # Country representation pass, then global best-fill. This keeps all 32 markets represented.
 by=defaultdict(list)
 for r in out:by[r['country']].append(r)
 selected=[]; used=set(); floor=max(250,min(1000,TARGET//(len(ACTIVE)*10)))
 def uid(r):return (r['country'],norm(r['national_id']) or r['normalized_name'],norm(r['town']))
 for c in sorted(ACTIVE):
  for r in by.get(c,[])[:floor]:
   u=uid(r)
   if u not in used:selected.append(r);used.add(u)
 for r in out:
  if len(selected)>=TARGET:break
  u=uid(r)
  if u not in used:selected.append(r);used.add(u)
 fields=['rank','company_name','normalized_name','country','town','nuts','national_id','fit_score','tier','award_count','buyer_count','last_award_year','last_award_date','last_cpv','procurement_categories','total_awarded_eur','max_award_eur','sme_evidence','source_years','evidence_url','notice_id','why_fit','outreach_angle','recommended_offer','contact_status','source_dataset']
 csvp=OUT/f'obrasignal_prospects_{len(selected)}.csv'
 with open(csvp,'w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for i,r in enumerate(selected,1):r=dict(r);r['rank']=i;w.writerow({k:r.get(k,'') for k in fields})
 summary={'generated_utc':datetime.utcnow().isoformat()+'Z','target':TARGET,'selected':len(selected),'candidate_pool':len(out),'countries_configured':len(ACTIVE),'countries':{c:sum(1 for r in selected if r['country']==c) for c in sorted(ACTIVE)},'tiers':dict(defaultdict(int)),'years_attempted':YEARS,'rows_seen':st['rows_seen'],'relevant_rows':st['relevant_rows'],'cpv_families':CPV_LABEL,'privacy':'Public business/procurement data only; no private or personal contact data.'}
 tc=defaultdict(int)
 for r in selected:tc[r['tier']]+=1
 summary['tiers']=dict(tc)
 (OUT/'obrasignal_prospects_200k_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False,indent=2))
 if len(selected)<150000:raise SystemExit(f'Only {len(selected)} prospects; below 150k minimum')
if __name__=='__main__':main()
