#!/usr/bin/env python3
import csv, json, os, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_active45_non_europe_prospects as b
m=os.environ['MARKET'].upper(); out=Path(os.environ.get('OUT_DIR','market_output'));out.mkdir(parents=True,exist_ok=True)
if m in b.OCP:
    rows=b.ocp_market(m,*b.OCP[m])
elif m=='US': rows=b.us_market()
elif m=='CO': rows=b.colombia_market()
elif m=='CA': rows=b.canada_market()
else: raise SystemExit(f'unknown market {m}')
fields=['rank','company_name','country','company_id','id_scheme','city','fit_score','award_count','buyer_count','total_awarded','last_award_year','category','website','source','source_url']
p=out/f'obrasignal_candidates_{m}.csv'
with p.open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for i,r in enumerate(rows,1):q=dict(r);q['rank']=i;w.writerow({k:q.get(k,'') for k in fields})
(out/f'summary_{m}.json').write_text(json.dumps({'market':m,'selected':len(rows)},indent=2),encoding='utf-8')
print(m,len(rows),flush=True)
