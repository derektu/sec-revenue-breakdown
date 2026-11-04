"""Curated scope validation. A sum check is not evidence of semantic correctness."""
from pathlib import Path
import json
ROOT=Path(__file__).parent
REVENUE='us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'
AXES={'product_service':'srt:ProductOrServiceAxis','operating_segment':'us-gaap:StatementBusinessSegmentsAxis','geography':'srt:StatementGeographicalAxis'}
# Explicit analyst-selected memberships, NOT an automatically learned taxonomy.
EXCLUDE={'aapl_2024_10k':{'us-gaap:ProductMember'},'amzn_2024_10k':{'us-gaap:ProductMember','us-gaap:ServiceMember'},'amzn_2024q3_10q':{'us-gaap:ProductMember','us-gaap:ServiceMember'}}

def unique(fs):
 out={}
 for f in fs:
  key=(f['concept'],f.get('startdate'),f.get('enddate'),f['unit'],json.dumps(f['dimensions'],sort_keys=True))
  if key in out and out[key]['value']!=f['value']: raise AssertionError('conflicting duplicate facts')
  out[key]=f
 return list(out.values())

def run():
 results=[];normalized=[]
 for p in sorted((ROOT/'outputs').glob('*_facts.json')):
  data=json.loads(p.read_text());fs=unique([f for f in data['facts'] if f['concept']==REVENUE]); filing=data['filing']
  periods=sorted(set((f.get('startdate'),f.get('enddate')) for f in fs))
  for start,end in periods:
   period=[f for f in fs if f.get('startdate')==start and f.get('enddate')==end]
   totals=[f for f in period if not f['dimensions'] and f['unit']=='iso4217:USD']
   if not totals: continue
   assert len(totals)==1
   total=totals[0]['value']
   for kind,axis in AXES.items():
    parts=[f for f in period if len(f['dimensions'])==1 and axis in f['dimensions'] and f['dimensions'][axis] not in EXCLUDE[filing]]
    if not parts:continue
    value=sum(f['value'] for f in parts)
    check={'filing':filing,'dimension_type':kind,'start':start,'end':end,'components':len(parts),'sum_usd':value,'consolidated_revenue_usd':total,'difference_usd':value-total,'pass':value==total}
    results.append(check)
    for f in parts: normalized.append({**f,'filing':filing,'dimension_type':kind,'revenue_share':f['value']/total,'selection_method':'curated membership exclusions + exact XBRL period/axis'})
 (ROOT/'outputs'/'validation.json').write_text(json.dumps(results,indent=2));(ROOT/'outputs'/'normalized.json').write_text(json.dumps(normalized,indent=2))
 print(json.dumps(results,indent=2));assert all(x['pass'] for x in results)
 print(f'{len(results)}/{len(results)} group reconciliation checks passed; {len(normalized)} component-period rows')
 # Regression guard: duplicates and mixed periods cannot silently reconcile.
 q=[f for f in normalized if f['filing']=='amzn_2024q3_10q' and f['dimension_type']=='product_service' and f['startdate']=='2024-07-01' and f['enddate']=='2024-09-30']
 assert sum(f['value'] for f in q)==158877000000
 assert sum(f['value'] for f in q+q)!=158877000000
 ytd=[f for f in normalized if f['filing']=='amzn_2024q3_10q' and f['dimension_type']=='product_service' and f['startdate']=='2024-01-01' and f['enddate']=='2024-09-30']
 assert sum(f['value'] for f in ytd)==450167000000
 assert sum(f['value'] for f in q+ytd)!=158877000000
 print('Quarter vs YTD and duplicate-count negative controls passed')
if __name__=='__main__':run()
