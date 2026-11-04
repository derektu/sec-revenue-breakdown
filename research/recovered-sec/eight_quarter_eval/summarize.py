import json,csv,collections
from pathlib import Path
ROOT=Path(__file__).parent
roster=json.loads((ROOT/'roster.json').read_text());rows=[];normalized=[];qrows=[];manifest=[]
for company in roster:
 t=company['ticker'];p=ROOT/'outputs'/f'{t}.json'
 if not p.exists():rows.append({'ticker':t,'status':'not_finished','requested_quarters':8});continue
 j=json.loads(p.read_text());qs=j['quarter_results'];gs=[g for q in qs for g in q.get('groups',[])];facts=[f for q in qs for f in q.get('facts',[])];raw=[f for r in j.get('raw_filings',[]) for f in r['facts']]
 row={'ticker':t,'status':'complete','requested_quarters':8,'selected_quarters':len(qs),'processed_quarters':sum(q['status']=='processed' for q in qs),'oldest_quarter':min((q['report_date'] for q in qs),default=''),'latest_quarter':max((q['report_date'] for q in qs),default=''),'quarters_with_candidate_totals':sum(bool(q.get('candidate_totals')) for q in qs),'quarters_with_dimensional_groups':sum(bool(q.get('groups')) for q in qs),'quarters_with_any_reconciled_group':sum(any(g['reconciles_to_any_candidate_total'] for g in q.get('groups',[])) for q in qs),'candidate_groups':len(gs),'reconciled_groups':sum(g['reconciles_to_any_candidate_total'] for g in gs),'groups_without_candidate_total':sum(not g['total_checks'] for g in gs),'quarter_candidates':len(facts),'derived_quarter_candidates':sum(f['derivation']=='annual_minus_nine_months' for f in facts),'multi_axis_quarter_candidates':sum(len(f.get('dimensions',{}))>1 for f in facts),'raw_candidates':len(raw),'numeric_parse_errors':j.get('numeric_parse_error_count',0),'conflicting_duplicate_groups':sum(q.get('conflicting_duplicates',0) for q in qs),'download_errors':len(j['errors']),'issuer_history_warning':'New issuer CIK 2115436; legacy CIK 34088 deliberately not bridged' if t=='XOM' else ''}
 rows.append(row)
 manifest.extend(dict(m,ticker=t) for m in j['manifest'])
 for q in qs:
  qrows.append({'ticker':t,'quarter_end':q['report_date'],'status':q['status'],'form':q.get('form'),'candidate_facts':q.get('quarter_fact_count',0),'derived_facts':q.get('derived_fact_count',0),'candidate_totals':len(q.get('candidate_totals',[])),'dimensional_groups':len(q.get('groups',[])),'reconciled_groups':sum(g['reconciles_to_any_candidate_total'] for g in q.get('groups',[]))})
  for f in q.get('facts',[]):
   normalized.append({'ticker':t,'quarter_end':q['report_date'],'concept':f['concept'],'start_date':f.get('startdate'),'end_date':f.get('enddate'),'value':f['value'],'unit':f.get('unit'),'dimensions':json.dumps(f.get('dimensions',{}),sort_keys=True),'derivation':f['derivation'],'source_url':f['source_url'],'context_id':f.get('context_id'),'fact_id':f.get('fact_id'),'table_index':f.get('table_index'),'raw_row_text':f.get('row_text'),'nine_month_source_url':f.get('nine_month_evidence',{}).get('source_url'),'nine_month_context_id':f.get('nine_month_evidence',{}).get('context_id'),'annual_value':f.get('annual_evidence',{}).get('value'),'nine_month_value':f.get('nine_month_evidence',{}).get('value')})
def write_csv(name,data):
 if not data:return
 with (ROOT/'outputs'/name).open('w') as f:
  writer=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in data for k in r)));writer.writeheader();writer.writerows(data)
write_csv('company_summary.csv',rows);write_csv('quarter_summary.csv',qrows);write_csv('quarter_candidates.csv',normalized)
metrics={k:sum(r.get(k,0) for r in rows) for k in ['requested_quarters','selected_quarters','processed_quarters','quarters_with_candidate_totals','quarters_with_dimensional_groups','quarters_with_any_reconciled_group','candidate_groups','reconciled_groups','groups_without_candidate_total','quarter_candidates','derived_quarter_candidates','multi_axis_quarter_candidates','raw_candidates','numeric_parse_errors','conflicting_duplicate_groups','download_errors']}
metrics.update(companies_requested=len(roster),companies_finished=sum(r['status']=='complete' for r in rows),filing_snapshots=sum(m['file'].endswith('.html') for m in manifest),snapshot_bytes=sum(m['bytes'] for m in manifest),accuracy_measured=False,tradingview_reference_used=False)
(ROOT/'outputs'/'summary.json').write_text(json.dumps({'metrics':metrics,'companies':rows},indent=2));(ROOT/'outputs'/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(metrics,indent=2))
