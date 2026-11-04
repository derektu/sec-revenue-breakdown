import unittest,tempfile
from pathlib import Path
from extract import parse
from validate import unique
class ExtractionTests(unittest.TestCase):
 def test_scale_sign_context(self):
  raw='''<html><body><xbrli:context id="q"><xbrli:period><xbrli:startDate>2024-07-01</xbrli:startDate><xbrli:endDate>2024-09-30</xbrli:endDate></xbrli:period><xbrldi:explicitMember dimension="srt:ProductOrServiceAxis">demo:CloudMember</xbrldi:explicitMember></xbrli:context><xbrli:unit id="USD"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit><table><tr><td>Cloud</td><td><ix:nonFraction name="demo:Revenue" contextRef="q" unitRef="USD" scale="6" sign="-">1,234</ix:nonFraction></td></tr></table></body></html>'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'test.html';p.write_text(raw);f=parse(p)['facts'][0]
  self.assertEqual(f['value'],-1234000000);self.assertEqual(f['startdate'],'2024-07-01');self.assertEqual(f['dimensions'],{'srt:ProductOrServiceAxis':'demo:CloudMember'});self.assertEqual(f['table_index'],0)
 def test_conflicting_duplicates_raise(self):
  f=dict(concept='demo:Revenue',startdate='2024-01-01',enddate='2024-12-31',unit='USD',dimensions={},value=100)
  with self.assertRaises(AssertionError): unique([f,{**f,'value':101}])
 def test_identical_duplicates_collapse(self):
  f=dict(concept='demo:Revenue',startdate='2024-01-01',enddate='2024-12-31',unit='USD',dimensions={},value=100)
  self.assertEqual(len(unique([f,f])),1)
if __name__=='__main__':unittest.main()
