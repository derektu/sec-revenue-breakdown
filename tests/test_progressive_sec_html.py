"""實際 SEC 原始 HTML 與先前 DOM 快照的交叉核對及錯誤輸入測試。"""
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from parse_progressive_sec import load_sources
from evaluate_progressive_sec import period_facts


@unittest.skipUnless(importlib.util.find_spec('lxml'), 'Install research/recovered-sec/requirements.txt')
class ProgressiveHtmlTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / 'research/progressive-sec-html-20261104/manifest.json').read_text())

    def test_all_five_real_documents_match_dom_and_q4(self):
        raw = load_sources(self.manifest, ROOT)
        dom = load_sources(json.loads((ROOT / 'research/sec-dom-sources-20261104/PGR-manifest.json').read_text()), ROOT)
        ignore = {'source_artifact_sha256', 'source_format'}
        self.assertEqual([{k: v for k, v in f.items() if k not in ignore} for f in raw],
                         [{k: v for k, v in f.items() if k not in ignore} for f in dom])
        self.assertTrue(all(f['source_format'] == 'SEC_raw_HTML_bytes' for f in raw))
        for year in (2024, 2025):
            derived = period_facts(raw, year, 12)
            expected = period_facts(dom, year, 12)
            self.assertEqual({k: f['value'] for k, f in derived.items()}, {k: f['value'] for k, f in expected.items()})
            self.assertTrue(all(f['startdate'] == f'{year}-10-01' for f in derived.values()))

    def test_raw_bytes_hash_is_checked_separately_from_gzip(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['files'][0]['raw_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Raw HTML hash mismatch'):
            load_sources(manifest, ROOT)

    def test_snapshot_url_must_match_manifest(self):
        manifest = json.loads((ROOT / 'research/sec-dom-sources-20261104/PGR-manifest.json').read_text())
        manifest['files'][0]['source_url'] = manifest['files'][1]['source_url']
        with self.assertRaisesRegex(ValueError, 'identity differ'):
            load_sources(manifest, ROOT)

    def test_real_html_with_wrong_unit_or_parent_url_is_rejected(self):
        from parse_progressive_sec_html import parse_html
        source = self.manifest['files'][0]
        raw = gzip.decompress((ROOT / source['path']).read_bytes())
        with self.assertRaisesRegex(ValueError, 'Exhibit 13'):
            parse_html(raw, source['source_url'].replace('_d2.htm', '.htm'))
        with self.assertRaisesRegex(ValueError, 'units'):
            parse_html(raw.replace(b'millions', b'thousands'), source['source_url'])

    def test_altered_artifact_cannot_pass_capture_hash(self):
        source = copy.deepcopy(self.manifest['files'][0])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'altered.gz'
            path.write_bytes((ROOT / source['path']).read_bytes() + b'changed')
            source['path'] = str(path)
            with self.assertRaisesRegex(ValueError, 'Capture hash mismatch'):
                load_sources({'files': [source]})
