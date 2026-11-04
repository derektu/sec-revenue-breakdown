import unittest
from run import quarter,dedupe,audit_groups

def fact(value,start,end,dimensions=None,concept='us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'):
 return dict(concept=concept,unit='iso4217:USD',value=value,startdate=start,enddate=end,dimensions=dimensions or {},decimals='-6')
class Tests(unittest.TestCase):
 def test_quarter_not_ytd(self):
  q,c=quarter([fact(20,'2025-07-01','2025-09-30'),fact(55,'2025-01-01','2025-09-30')],'2025-09-30','10-Q',[])
  self.assertEqual([x['value'] for x in q],[20])
 def test_sixteen_week_retail_quarter(self):
  q,c=quarter([fact(100,'2025-09-01','2025-12-21')],'2025-12-21','10-Q',[]);self.assertEqual(len(q),1)
 def test_q4_derivation(self):
  q,c=quarter([fact(100,'2025-01-01','2025-12-31')],'2025-12-31','10-K',[fact(70,'2025-01-01','2025-09-30')])
  self.assertEqual(q[0]['value'],30);self.assertEqual(q[0]['startdate'],'2025-10-01');self.assertEqual(q[0]['nine_month_evidence']['value'],70)
 def test_mismatched_member_abstains(self):
  q,c=quarter([fact(100,'2025-01-01','2025-12-31',{'axis':'new'})],'2025-12-31','10-K',[fact(70,'2025-01-01','2025-09-30',{'axis':'old'})]);self.assertEqual(q,[])
 def test_conflict_rejected(self):
  q,c=dedupe([fact(1,'2025-01-01','2025-03-31'),fact(2,'2025-01-01','2025-03-31')]);self.assertEqual(q,[]);self.assertEqual(len(c),1)
 def test_duplicate_collapse(self):
  q,c=dedupe([fact(1,'2025-01-01','2025-03-31')]*2);self.assertEqual(len(q),1)
 def test_subtotal_double_count_not_reconciled(self):
  fs=[fact(v,'2025-01-01','2025-03-31',{'ProductAxis':m}) for m,v in [('A',30_000_000),('B',70_000_000),('Total',100_000_000)]]+[fact(100_000_000,'2025-01-01','2025-03-31')]
  for f in fs:f['derivation']='reported_quarter'
  totals,groups=audit_groups(fs);self.assertFalse(groups[0]['reconciles_to_any_candidate_total'])
 def test_two_axis_not_flattened(self):
  fs=[fact(10,'2025-01-01','2025-03-31',{'ProductAxis':'a','GeoAxis':'b'})];self.assertEqual(audit_groups(fs)[1],[])
 def test_direct_q4_preferred(self):
  q,c=quarter([fact(100,'2025-01-01','2025-12-31'),fact(29,'2025-10-01','2025-12-31')],'2025-12-31','10-K',[fact(70,'2025-01-01','2025-09-30')]);self.assertEqual(len(q),1);self.assertEqual(q[0]['value'],29)
if __name__=='__main__':unittest.main()
