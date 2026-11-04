"""Compare evidence extraction to existing selectors without choosing by value."""
from collections import Counter
from decimal import Decimal
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'research/recovered-sec'))
from extract import parse
from cohort_rule_catalog import catalog
from shared_raw_semantics import read_pinned


def compare(filing, result):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'raw.html'
        path.write_bytes(read_pinned(filing))
        old = parse(path)
    by_id = {f['fact_id']: f for f in result['facts']}
    old_natures = Counter(by_id[f['fact_id']]['nature'] for f in old['facts'])
    number_mismatches = [f['fact_id'] for f in old['facts'] if by_id[f['fact_id']]['value'] is not None
                         and Decimal(str(f['value'])) != Decimal(by_id[f['fact_id']]['value'])]
    period = 'FY' if filing['form'] == '10-K' else 'Q'
    facts = [f for f in result['facts'] if f['context'] and f['context'].get('enddate') == filing['reportDate']
             and f['context']['period_kind'] == period]
    # This uses existing catalog scopes only, never imports vendor raw rows.
    rules = catalog()[filing['ticker']]
    terms = []
    for vendor, labels in rules.items():
        for label, rule in labels.items():
            for index, alternative in enumerate(rule['alternatives']):
                for term in alternative:
                    matched = [f for f in facts if f['concept'] == term['concept']
                               and f['context']['dimensions'] == term['dimensions']
                               and f['unit'] == {'measures': ['{http://www.xbrl.org/2003/iso4217}USD'], 'divide': False}]
                    terms.append({'reference_scope': vendor, 'label': label, 'alternative': index,
                                  'concept': term['concept'], 'dimensions': term['dimensions'],
                                  'matching_fact_ids': [f['fact_id'] for f in matched],
                                  'status': 'missing_exact_scope' if not matched else 'admitted_revenue_evidence'
                                  if all(f['admissible'] and f['nature'] == 'revenue' for f in matched) else 'abstain',
                                  'semantic_partition_verified': False})
    return {'legacy_candidates': len(old['facts']), 'legacy_candidate_natures': dict(old_natures),
            'numeric_mismatch_ids': number_mismatches,
            'existing_catalog_term_occurrences': len(terms),
            'catalog_term_statuses': dict(Counter(t['status'] for t in terms)),
            'catalog_terms': terms,
            'vendor_value_comparison': 'not_performed_no_vendor_raw_access',
            'shared_parser_replaces_catalog': False}
