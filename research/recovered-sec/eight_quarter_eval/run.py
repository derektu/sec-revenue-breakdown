"""Reproducible eight-quarter SEC dimensional-revenue candidate audit.
No TradingView reference and no claim of semantic or disclosure recall accuracy.
"""
import sys,json,urllib.request,time,hashlib,datetime,concurrent.futures,threading,csv,collections,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from extract import parse
ROOT=Path(__file__).parent
TOTAL_CONCEPTS={'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax','us-gaap:Revenues','us-gaap:SalesRevenueNet','us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax','us-gaap:SalesRevenueGoodsNet','us-gaap:SalesRevenueServicesNet'}
LOCK=threading.Lock();LAST=0

def fetch(url,path):
 global LAST
 if not path.exists():
  for attempt in range(3):
   with LOCK:
    time.sleep(max(0,0.22-(time.monotonic()-LAST)));LAST=time.monotonic()
   try:
    req=urllib.request.Request(url,headers={'User-Agent':os.getenv('SEC_USER_AGENT','SEC Revenue Research research@example.com')})
    with urllib.request.urlopen(req,timeout=60) as response:b=response.read()
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b);break
   except Exception:
    if attempt==2:raise
    time.sleep(2**attempt)
 b=path.read_bytes()
 return {'url':url,'file':str(path.relative_to(ROOT)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def days(f):
 try:return (datetime.date.fromisoformat(f['enddate'])-datetime.date.fromisoformat(f['startdate'])).days+1
 except (KeyError,ValueError):return 0

def signature(f):return (f['concept'],f.get('unit'),json.dumps(f.get('dimensions',{}),sort_keys=True))
def dedupe(facts):
 grouped=collections.defaultdict(list)
 for f in facts:grouped[(signature(f),f.get('startdate'),f.get('enddate'))].append(f)
 out=[];conflicts=[]
 for key,fs in grouped.items():
  if len({str(f['value']) for f in fs})!=1:conflicts.append(fs);continue
  f=dict(fs[0]);f['duplicate_count']=len(fs);out.append(f)
 return out,conflicts

def quarter(facts,end,form,previous):
 direct=[dict(f,derivation='reported_quarter') for f in facts if f.get('enddate')==end and 70<=days(f)<=126]
 if form!='10-K':return dedupe(direct)
 annual=[f for f in facts if f.get('enddate')==end and 350<=days(f)<=380]
 prior=collections.defaultdict(list)
 for f in previous:
  if 240<=days(f)<=300:prior[(signature(f),f.get('startdate'))].append(f)
 deriv=[]
 for f in annual:
  matches=prior.get((signature(f),f.get('startdate')),[])
  matches=[p for p in matches if 70<=(datetime.date.fromisoformat(end)-datetime.date.fromisoformat(p['enddate'])).days<=126]
  if not matches:continue
  latest=max(p['enddate'] for p in matches);matches=[p for p in matches if p['enddate']==latest]
  if len({str(p['value']) for p in matches})!=1:continue
  p=matches[0]
  if not isinstance(f['value'],int) or not isinstance(p['value'],int):continue
  q=dict(f);q.update(value=f['value']-p['value'],startdate=str(datetime.date.fromisoformat(p['enddate'])+datetime.timedelta(days=1)),derivation='annual_minus_nine_months',annual_evidence=f,nine_month_evidence=p)
  deriv.append(q)
 # Prefer directly reported quarter fact for an identical concept/unit/dimensions.
 directkeys={signature(f) for f in direct};return dedupe(direct+[f for f in deriv if signature(f) not in directkeys])

def tolerance(fs):
 result=0
 for f in fs:
  try:result+=0.5*10**(-int(f.get('decimals')))
  except (TypeError,ValueError):pass
 return result

def audit_groups(q):
 totals=[f for f in q if not f.get('dimensions') and f['concept'] in TOTAL_CONCEPTS and f.get('unit') in ('iso4217:USD','USD') and isinstance(f['value'],int)]
 # Preserve candidate totals rather than silently choose one potentially partial concept.
 buckets=collections.defaultdict(list)
 for f in q:
  if len(f.get('dimensions',{}))==1 and f.get('unit') in ('iso4217:USD','USD') and isinstance(f['value'],int):
   axis=next(iter(f['dimensions']));buckets[(f['concept'],axis,f.get('startdate'),f.get('enddate'))].append(f)
 results=[]
 for (concept,axis,start,end),fs in buckets.items():
  if len(fs)<2:continue
  same=[t for t in totals if t['concept']==concept and t.get('startdate')==start and t.get('enddate')==end]
  targets=same or [t for t in totals if t.get('startdate')==start and t.get('enddate')==end]
  summed=sum(f['value'] for f in fs);checks=[{'concept':t['concept'],'value':t['value'],'difference':summed-t['value'],'within_rounding_tolerance':abs(summed-t['value'])<=tolerance(fs+[t])} for t in targets]
  classification='geography' if any(s.lower() in axis.lower() for s in ['geograph','country','countries']) else 'operating_segment' if 'segment' in axis.lower() else 'product_service' if any(s in axis.lower() for s in ['product','service']) else 'unclassified'
  results.append({'concept':concept,'axis':axis,'classification_heuristic':classification,'members':[{ 'member':next(iter(f['dimensions'].values())),'value':f['value'],'fact_id':f.get('fact_id'),'table_index':f.get('table_index'),'derivation':f['derivation']} for f in fs],'sum':summed,'total_checks':checks,'reconciles_to_any_candidate_total':any(c['within_rounding_tolerance'] for c in checks),'hierarchy_status':'axis and members preserved; parent-child relationships NOT resolved; subtotals may overlap'})
 return totals,results

def run_company(company,cutoff):
 ticker,cik=company['ticker'],str(company['cik']).zfill(10);base=ROOT/'data'/ticker;base.mkdir(parents=True,exist_ok=True)
 manifest=[];errors=[];records=[]
 try:
  manifest.append(fetch(f'https://data.sec.gov/submissions/CIK{cik}.json',base/'submissions.json'));j=json.loads((base/'submissions.json').read_text());r=j['filings']['recent']
  filings=[{k:r[k][i] for k in ['form','filingDate','reportDate','accessionNumber','primaryDocument']} for i in range(len(r['form'])) if r['form'][i] in ('10-K','10-Q') and r['filingDate'][i]<=cutoff]
  # High-frequency issuers (e.g. banks) can exhaust recent submissions inside a year.
  if len({f['reportDate'] for f in filings})<9:
   for archive in sorted(j['filings'].get('files',[]),key=lambda a:a.get('filingTo',''),reverse=True):
    if archive.get('filingFrom','')>cutoff:continue
    ap=base/archive['name'];manifest.append(fetch('https://data.sec.gov/submissions/'+archive['name'],ap));ar=json.loads(ap.read_text())
    filings.extend({k:ar[k][i] for k in ['form','filingDate','reportDate','accessionNumber','primaryDocument']} for i in range(len(ar['form'])) if ar['form'][i] in ('10-K','10-Q') and ar['filingDate'][i]<=cutoff)
    if len({f['reportDate'] for f in filings})>=9:break
  filings=sorted(filings,key=lambda f:(f['reportDate'],f['filingDate']),reverse=True);unique={}
  for f in filings:unique.setdefault(f['reportDate'],f)
  filings=list(unique.values())[:9]
  for f in filings:
   url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{f['accessionNumber'].replace('-','')}/{f['primaryDocument']}";path=base/(f['accessionNumber']+'.html')
   try:
    m=fetch(url,path);m.update(f);manifest.append(m);p=parse(path)
    for fact in p['facts']:fact.update(source_url=url,accession=f['accessionNumber'],form=f['form'],filing_date=f['filingDate'])
    records.append({'filing':f,'facts':p['facts'],'parse_errors':p['parse_errors']})
   except Exception as e:errors.append({'filing':f,'url':url,'error':repr(e)})
  quarters=[]
  for f in filings[:8]:
   current=next((x for x in records if x['filing']['accessionNumber']==f['accessionNumber']),None)
   if current is None:quarters.append({'report_date':f['reportDate'],'status':'download_or_parse_failed'});continue
   previous=[fact for x in records if x['filing']['reportDate']<f['reportDate'] for fact in x['facts']]
   q,conflicts=quarter(current['facts'],f['reportDate'],f['form'],previous);totals,groups=audit_groups(q)
   quarters.append({'report_date':f['reportDate'],'form':f['form'],'filing_date':f['filingDate'],'status':'processed','quarter_fact_count':len(q),'derived_fact_count':sum(x['derivation']=='annual_minus_nine_months' for x in q),'conflicting_duplicates':len(conflicts),'candidate_totals':totals,'groups':groups,'facts':q})
  result={'ticker':ticker,'name':j['name'],'cik':cik,'as_of':cutoff,'manifest':manifest,'errors':errors,'quarter_results':quarters,'raw_candidate_count':sum(len(r['facts']) for r in records),'numeric_parse_error_count':sum(len(r['parse_errors']) for r in records),'raw_filings':records}
 except Exception as e:result={'ticker':ticker,'errors':[{'error':repr(e)}],'quarter_results':[],'manifest':manifest}
 (ROOT/'outputs').mkdir(exist_ok=True);(ROOT/'outputs'/f'{ticker}.json').write_text(json.dumps(result,indent=2))
 row={'ticker':ticker,'requested_quarters':8,'selected_quarters':len(result['quarter_results']),'processed_quarters':sum(q['status']=='processed' for q in result['quarter_results']),'quarters_with_any_candidate_total':sum(bool(q.get('candidate_totals')) for q in result['quarter_results']),'quarters_with_any_dimensional_group':sum(bool(q.get('groups')) for q in result['quarter_results']),'quarters_with_any_reconciled_group':sum(any(g['reconciles_to_any_candidate_total'] for g in q.get('groups',[])) for q in result['quarter_results']),'groups':sum(len(q.get('groups',[])) for q in result['quarter_results']),'reconciled_groups':sum(g['reconciles_to_any_candidate_total'] for q in result['quarter_results'] for g in q.get('groups',[])),'download_errors':len(result['errors']),'raw_candidate_count':result.get('raw_candidate_count',0),'numeric_parse_errors':result.get('numeric_parse_error_count',0)}
 print(json.dumps(row),flush=True);return row

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--roster',default=str(ROOT/'roster.json'));p.add_argument('--as-of',default='2026-11-03');p.add_argument('--workers',type=int,default=4);p.add_argument('--tickers');a=p.parse_args()
 roster=json.loads(Path(a.roster).read_text());roster=[c for c in roster if not a.tickers or c['ticker'] in a.tickers.split(',')]
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:rows=list(pool.map(lambda c:run_company(c,a.as_of),roster))
 (ROOT/'outputs'/'summary.json').write_text(json.dumps({'as_of':a.as_of,'companies':rows,'metrics_are_candidate_coverage_not_ground_truth_accuracy':True},indent=2))
 with (ROOT/'outputs'/'summary.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
