"""Conservative inline-XBRL revenue candidate extraction, not a full XBRL processor."""
from lxml import html
from pathlib import Path
from decimal import Decimal,InvalidOperation
import json,re
ROOT=Path(__file__).parent

def lname(e): return str(e.tag).split(':')[-1].lower()
def txt(e): return ' '.join(' '.join(e.itertext()).split())
def parse(path):
 root=html.fromstring(path.read_bytes()); contexts={}; units={}; tree=root.getroottree(); tables={tree.getpath(t):i for i,t in enumerate(root.iter('table'))}
 for e in root.iter():
  if lname(e)=='context':
   c={'dimensions':{}}
   for x in e.iter():
    k=lname(x)
    if k in ('startdate','enddate','instant'): c[k]=txt(x)
    elif k=='explicitmember': c['dimensions'][x.get('dimension')]=txt(x)
    elif k=='typedmember': c['dimensions'][x.get('dimension')]=txt(x)
   contexts[e.get('id')]=c
  elif lname(e)=='unit': units[e.get('id')]=txt(e)
 facts=[];errors=[]
 for e in root.iter():
  if lname(e)!='nonfraction': continue
  concept=e.get('name','')
  if not re.search(r'(revenue|sales)',concept,re.I):continue
  raw=txt(e); cleaned=raw.replace(',','').replace(' ','').replace('\u2212','-')
  if cleaned in ['—','–','-']: cleaned='0'
  try: value=Decimal(cleaned)*Decimal(10)**int(e.get('scale','0'))*(-1 if e.get('sign')=='-' else 1)
  except (InvalidOperation,ValueError) as ex: errors.append({'concept':concept,'raw':raw,'reason':str(ex)});continue
  ancestors=list(e.iterancestors()); row=next((a for a in ancestors if a.tag=='tr'),None); table=next((a for a in ancestors if a.tag=='table'),None)
  fact={'concept':concept,'context_id':e.get('contextref'),'unit':units.get(e.get('unitref')),'value':int(value) if value==int(value) else str(value),'raw':raw,'scale':e.get('scale','0'),'decimals':e.get('decimals'),'fact_id':e.get('id'),'source_line':e.sourceline,'table_index':tables.get(tree.getpath(table)) if table is not None else None,'row_text':txt(row) if row is not None else '',**contexts.get(e.get('contextref'),{})}
  facts.append(fact)
 return {'filing':path.stem,'facts':facts,'parse_errors':errors}
if __name__=='__main__':
 for p in sorted((ROOT/'data').glob('*.html')):
  result=parse(p); (ROOT/'outputs'/f'{p.stem}_facts.json').write_text(json.dumps(result,indent=2))
  print(p.stem,len(result['facts']),'revenue/sales candidates;',len(result['parse_errors']),'numeric parse errors')
  seen=set()
  for f in result['facts']:
   if f.get('enddate','').startswith('2024') and f.get('dimensions'):
    key=(f['concept'],json.dumps(f['dimensions']))
    if key not in seen:
     seen.add(key);print(f['concept'], f['dimensions'],f['value'],f.get('startdate'),f.get('enddate'),f['row_text'][:130])
