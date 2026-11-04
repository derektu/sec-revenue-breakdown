"""Evidence-gated bridges for the pinned 64 historical taxonomy-version scopes.

No value-based matching, renaming, external DTS resolution, or vendor access.
Passing this contract supports a version bridge for this pair only; it does not
certify business-definition continuity, restatements, or revenue partitions.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
import gzip
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from lxml import etree, html
from shared_raw_semantics import ROOT, XL, analyze, digest, expanded, local, read_pinned, text

BASE = ROOT / 'research/shared-raw-semantics'
XML_LANG = '{http://www.w3.org/XML/1998/namespace}lang'
XBRLI = '{http://www.xbrl.org/2003/instance}'
ROLE = 'http://www.xbrl.org/2003/role/'


def owner(namespace):
    return re.sub(r'/\d{8}$', '', namespace)


def taxonomy(filing):
    started = time.perf_counter()
    schema_entry = next(s for s in filing['support'] if s['kind'] == 'schema')
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    schema = etree.fromstring(read_pinned(schema_entry), parser)
    ns = schema.get('targetNamespace')
    elements = {}
    id_names = {}
    for e in schema:
        if local(e) != 'element':
            continue
        id_names[e.get('id')] = e.get('name')
        elements[e.get('name')] = {
            'type': expanded(e.get('type', ''), e.nsmap),
            'substitutionGroup': expanded(e.get('substitutionGroup', ''), e.nsmap),
            'periodType': e.get(XBRLI + 'periodType'), 'balance': e.get(XBRLI + 'balance'),
            'abstract': e.get('abstract', 'false'), 'nillable': e.get('nillable', 'false')}
    labels = defaultdict(set)
    schema_file = Path(urlsplit(schema_entry['url']).path).name
    for entry in filing['support']:
        if entry['kind'] != 'lab':
            continue
        root = etree.fromstring(read_pinned(entry), parser)
        for link in root:
            locs = {e.get(XL + 'label'): e.get(XL + 'href', '') for e in link if local(e) == 'loc'}
            # Several resource roles can share an XLink label; retain all.
            resources = defaultdict(list)
            for e in link:
                if local(e) == 'label':
                    resources[e.get(XL + 'label')].append(e)
            for arc in link:
                if local(arc) != 'labelarc':
                    continue
                href = locs.get(arc.get(XL + 'from'), '')
                path, _, fragment = href.partition('#')
                if Path(urlsplit(path).path).name != schema_file or fragment not in id_names:
                    continue
                for e in resources[arc.get(XL + 'to')]:
                    labels[id_names[fragment]].add((e.get(XL + 'role'), e.get(XML_LANG), text(e)))
    root = html.fromstring(read_pinned(filing))
    namespaces = {k[6:]: v for k, v in root.attrib.items() if k.startswith('xmlns:')}
    rows = {}
    for e in root.iter():
        if local(e) != 'nonfraction':
            continue
        row = next((p for p in e.iterancestors() if local(p) == 'tr'), None)
        leading = []
        if row is not None:
            for cell in row:
                if local(cell) not in ('td', 'th'):
                    continue
                if any(local(x) == 'nonfraction' for x in cell.iter()):
                    break
                leading.append(text(cell))
        rows[e.get('id')] = ' '.join(' '.join(leading).split()).strip(' $\u00a0')
    result = analyze(filing)
    preferred = {}
    for entry in filing['support']:
        if entry['kind'] != 'pre':
            continue
        for link in etree.fromstring(read_pinned(entry), parser):
            locs = {e.get(XL + 'label'): e.get(XL + 'href', '').split('#')[-1].replace('_', ':', 1)
                    for e in link if local(e) == 'loc'}
            for arc in link:
                if local(arc) == 'presentationarc':
                    preferred[(link.get(XL + 'role'), locs.get(arc.get(XL + 'from')),
                               locs.get(arc.get(XL + 'to')))] = arc.get('preferredLabel', '')
    for arc in result['relationships']:
        if arc['kind'] == 'pre':
            arc['preferred_label'] = preferred.get((arc['role'], arc['parent'], arc['child']), '')
    return {'filing': filing, 'namespace': ns, 'namespaces': namespaces,
            'elements': elements, 'labels': {k: sorted(v) for k, v in labels.items()},
            'arcs': result['relationships'], 'facts': result['facts'], 'row_labels': rows,
            'schema_source': schema_entry, 'processing_seconds': time.perf_counter() - started}


def paths_and_neighbors(tax, axis, member):
    by_role = defaultdict(list)
    for a in tax['arcs']:
        if a['kind'] == 'def' and a['arcrole'].rsplit('/', 1)[-1] in ('dimension-domain', 'domain-member'):
            by_role[a['role']].append(a)
    result = {}
    for role, arcs in by_role.items():
        edges = defaultdict(set)
        for a in arcs:
            edges[a['parent']].add(a['child'])
        pending = [(axis, [axis])]
        paths = []
        complex_graph = False
        while pending:
            node, route = pending.pop()
            if len(route) > 20 or len(pending) > 1000:
                complex_graph = True
                break
            if node == member:
                paths.append(route)
                continue
            for child in sorted(edges.get(node, ())):
                if child in route:
                    complex_graph = True
                else:
                    pending.append((child, route + [child]))
        if paths:
            neighbors = sorted((a['arcrole'].rsplit('/', 1)[-1], a['parent'], a['child'])
                               for a in arcs if member in (a['parent'], a['child']))
            relevant_nodes = {n for path in paths for n in path} | {n for a in neighbors for n in a[1:]}
            unusual = any(a.get('use') == 'prohibited' or a.get('priority') != '0' or a.get('target_role')
                          for a in arcs if a['parent'] in relevant_nodes or a['child'] in relevant_nodes)
            result[role] = {'paths': sorted(paths), 'neighbors': neighbors,
                            'unsupported_relationships': complex_graph or unusual}
    return result


def presentation_neighbors(tax, qname):
    by_role = defaultdict(set)
    for a in tax['arcs']:
        if a['kind'] == 'pre' and qname in (a['parent'], a['child']):
            by_role[a['role']].add((a['parent'], a['child'], a.get('use') or '', a.get('priority') or '0', a.get('target_role') or '', a.get('preferred_label') or ''))
    return {role: sorted(arcs) for role, arcs in by_role.items()}


def role_difference(before, after):
    return {'only_before': sorted(set(before) - set(after)),
            'only_after': sorted(set(after) - set(before)),
            'changed_shared_roles': sorted(r for r in set(before) & set(after) if before[r] != after[r])}


def neighborhood_metadata(tax, definitions, presentations):
    names = set()
    for d in definitions.values():
        names.update(n for path in d['paths'] for n in path)
        names.update(n for a in d['neighbors'] for n in a[1:])
    for arcs in presentations.values():
        names.update(n for a in arcs for n in a[:2])
    metadata = {}
    for qname in sorted(names):
        prefix, _, name = qname.partition(':')
        namespace = tax['namespaces'].get(prefix)
        entry = {'namespace_owner_or_exact_standard': owner(namespace) if namespace == tax['namespace'] else namespace}
        if namespace == tax['namespace']:
            entry.update(schema=tax['elements'].get(name), labels=tax['labels'].get(name, []))
        metadata[qname] = entry
    return metadata


def element_bridge(left, right, before, after, axis=None):
    """No numbers enter this metadata comparison."""
    reasons = []
    bp, _, bn = before.partition(':')
    ap, _, an = after.partition(':')
    old_ns, new_ns = left['namespaces'].get(bp), right['namespaces'].get(ap)
    evidence = {'before': before, 'after': after, 'before_namespace': old_ns, 'after_namespace': new_ns}
    if before != after:
        reasons.append('renamed_QName_requires_review')
    if not old_ns or not new_ns or old_ns != left['namespace'] or new_ns != right['namespace']:
        reasons.append('missing_local_schema_ownership')
    if owner(old_ns or '') != owner(new_ns or ''):
        reasons.append('namespace_owner_changed')
    old_element, new_element = left['elements'].get(bn), right['elements'].get(an)
    evidence['schema_before'], evidence['schema_after'] = old_element, new_element
    if not old_element or not new_element:
        reasons.append('missing_schema_declaration')
    elif old_element != new_element:
        reasons.append('schema_attributes_changed')
    old_labels, new_labels = left['labels'].get(bn, []), right['labels'].get(an, [])
    evidence['labels_before'], evidence['labels_after'] = old_labels, new_labels
    for label_role, reason in [('label', 'standard_label'), ('documentation', 'documentation')]:
        old = [x for x in old_labels if x[0] == ROLE + label_role and x[1] and x[1].startswith('en')]
        new = [x for x in new_labels if x[0] == ROLE + label_role and x[1] and x[1].startswith('en')]
        if not old or not new:
            reasons.append('missing_' + reason)
        elif old != new:
            reasons.append(reason + '_changed')
    if old_labels != new_labels:
        reasons.append('label_role_set_changed')
    definition_before, definition_after = {}, {}
    if axis:
        a, b = paths_and_neighbors(left, axis, before), paths_and_neighbors(right, axis, after)
        evidence['definition_before'], evidence['definition_after'] = a, b
        definition_before, definition_after = a, b
        evidence['definition_difference'] = role_difference(a, b)
        if not a or not b:
            reasons.append('missing_axis_member_definition_path')
        elif a != b:
            reasons.append('axis_member_paths_or_neighbors_changed')
        if any(x['unsupported_relationships'] for x in list(a.values()) + list(b.values())):
            reasons.append('unsupported_definition_relationships')
    a, b = presentation_neighbors(left, before), presentation_neighbors(right, after)
    evidence['presentation_before'], evidence['presentation_after'] = a, b
    evidence['presentation_difference'] = role_difference(a, b)
    if any(arc[2] == 'prohibited' or arc[3] != '0' or arc[4] for arcs in list(a.values()) + list(b.values()) for arc in arcs):
        reasons.append('unsupported_presentation_relationships')
    if not a or not b:
        reasons.append('missing_presentation_neighborhood')
    elif a != b:
        reasons.append('presentation_neighborhood_changed')
    before_nodes = neighborhood_metadata(left, definition_before, evidence['presentation_before'])
    after_nodes = neighborhood_metadata(right, definition_after, evidence['presentation_after'])
    evidence['neighborhood_nodes_before'], evidence['neighborhood_nodes_after'] = before_nodes, after_nodes
    common = set(before_nodes) & set(after_nodes)
    if any(before_nodes[n] != after_nodes[n] for n in common):
        reasons.append('neighbor_metadata_changed')
    for nodes in (before_nodes, after_nodes):
        for n, metadata in nodes.items():
            if 'schema' in metadata:
                label_roles = {x[0] for x in metadata.get('labels', [])}
                if not metadata['schema'] or not {ROLE + 'label', ROLE + 'documentation'} <= label_roles:
                    reasons.append('missing_neighbor_schema_or_definition')
    evidence['reasons'] = sorted(set(reasons))
    return evidence


def evaluate_pair(quarterly, annual, q, a):
    """Validate the full scope without inspecting fact values or row numbers."""
    reasons, elements = [], []
    qc, ac = q.get('context') or {}, a.get('context') or {}
    for tax in (quarterly, annual):
        ns = tax['namespace']
        expected_date = tax['filing']['reportDate'].replace('-', '')
        if not ns or not ns.endswith('/' + expected_date):
            reasons.append('namespace_version_does_not_match_source_date')
        source_url = urlsplit(tax['filing']['url'])
        if source_url.scheme != 'https' or source_url.hostname != 'www.sec.gov':
            reasons.append('unapproved_source_host')
    for tax, context in ((quarterly, qc), (annual, ac)):
        try:
            source_cik = int(urlsplit(tax['filing']['url']).path.split('/')[4])
            entity = context.get('entity', {})
            if entity.get('scheme') != 'http://www.sec.gov/CIK' or int(entity.get('identifier', '')) != source_cik:
                reasons.append('entity_does_not_match_SEC_source')
        except (IndexError, ValueError, TypeError):
            reasons.append('entity_does_not_match_SEC_source')
    if qc.get('entity') != ac.get('entity') or not qc.get('entity', {}).get('identifier'):
        reasons.append('entity_identifier_changed_or_missing')
    if owner(quarterly['namespace'] or '') != owner(annual['namespace'] or ''):
        reasons.append('namespace_owner_changed')
    if q.get('unit') != a.get('unit'):
        reasons.append('unit_changed')
    if q.get('nature') != 'revenue' or a.get('nature') != 'revenue' or not q.get('admissible') or not a.get('admissible'):
        reasons.append('not_admissible_revenue')
    if qc.get('startdate') != ac.get('startdate') or qc.get('period_kind') != 'YTD9' or ac.get('period_kind') != 'FY':
        reasons.append('incompatible_fiscal_periods')
    try:
        if not 70 <= (date.fromisoformat(ac['enddate']) - date.fromisoformat(qc['enddate'])).days <= 126:
            reasons.append('incompatible_period_endpoints')
    except (KeyError, ValueError):
        reasons.append('missing_period_endpoints')
    if qc.get('dimensions') != ac.get('dimensions'):
        reasons.append('full_dimensions_changed')
    if q.get('concept') != a.get('concept'):
        reasons.append('concept_changed')
    elif q.get('expanded_concept') != a.get('expanded_concept'):
        elements.append(element_bridge(quarterly, annual, q['concept'], a['concept']))
    if qc.get('unsupported_context') or ac.get('unsupported_context'):
        reasons.append('unsupported_context')
    for axis, member in sorted(qc.get('dimensions', {}).items()):
        if ac.get('dimensions', {}).get(axis) != member:
            continue
        if expanded(axis, quarterly['namespaces']) != expanded(axis, annual['namespaces']):
            reasons.append('custom_axis_bridge_not_implemented')
        old_member = expanded(member, quarterly['namespaces'])
        new_member = expanded(member, annual['namespaces'])
        if old_member != new_member:
            elements.append(element_bridge(quarterly, annual, member, member, axis))
    qrow, arow = quarterly['row_labels'].get(q['fact_id']), annual['row_labels'].get(a['fact_id'])
    if not qrow or not arow:
        reasons.append('missing_table_row_label')
    elif qrow != arow:
        reasons.append('table_row_label_changed')
    for e in elements:
        reasons.extend(e['reasons'])
    if not elements:
        reasons.append('no_version_changed_element')
    return {'decision': 'evidence_supported_version_bridge' if not reasons else 'abstain_needs_review',
            'reasons': sorted(set(reasons)), 'elements': elements,
            'row_labels': {'Q_YTD9': qrow, 'FY': arow},
            'business_continuity_certified': False, 'partition_certified': False}


def arithmetic_check(annuals, quarters):
    if len({a['value'] for a in annuals}) != 1 or len({q['value'] for q in quarters}) != 1:
        return {'decision': 'abstain_conflicting_duplicates'}
    return {'decision': 'bridged_arithmetic_only',
            'value': str(Decimal(annuals[0]['value']) - Decimal(quarters[0]['value'])),
            'restatement_continuity_certified': False}


def legacy_numeric_check(ticker, period_end, concept, dimensions, arithmetic):
    path = ROOT / f'research/sec-30-baseline-2026-11-04/{ticker}.json.gz'
    data = json.loads(gzip.decompress(path.read_bytes()))
    quarter = next((q for q in data['quarter_results'] if q['report_date'] == period_end), {})
    facts = [f for f in quarter.get('facts', []) if f['concept'] == concept and f.get('dimensions') == dimensions
             and f.get('unit') in ('iso4217:USD', 'USD')]
    values = {str(f['value']) for f in facts}
    status = 'missing_legacy_scope' if not facts else 'ambiguous_legacy_values' if len(values) != 1 else (
        'numeric_equal_only' if Decimal(next(iter(values))) == Decimal(arithmetic['value']) else 'numeric_different')
    return {'status': status, 'baseline_path': str(path.relative_to(ROOT)),
            'baseline_sha256': digest(path.read_bytes()), 'fact_ids': [f['fact_id'] for f in facts],
            'values': sorted(values), 'semantic_identity_certified': False}


def comparison_period(qt, at, original):
    year = int(at['filing']['reportDate'][:4]) - 1
    end, ytd_end = f'{year}-12-31', f'{year}-09-30'
    def select(tax, period, period_end):
        return [f for f in tax['facts'] if f.get('context') and f['concept'] == original['concept']
                and f['context']['dimensions'] == original['dimensions']
                and f['context'].get('enddate') == period_end and f['context']['period_kind'] == period]
    annuals, quarters = select(at, 'FY', end), select(qt, 'YTD9', ytd_end)
    result = {'period_end': end, 'annual_fact_ids': [f['fact_id'] for f in annuals],
              'nine_month_fact_ids': [f['fact_id'] for f in quarters],
              'as_filed_in': 'FY2025 and Q3 2025 comparative columns; not original FY2024 disclosures'}
    if not annuals or not quarters:
        result.update(decision='abstain_missing_historical_scope', reasons=['missing_historical_scope'])
        return result
    evaluations = [evaluate_pair(qt, at, q, a) for a in annuals for q in quarters]
    reasons = sorted({r for e in evaluations for r in e['reasons']})
    result.update(decision='abstain_needs_review' if reasons else 'evidence_supported_version_bridge',
                  reasons=reasons, pair_evidence=evaluations)
    if not reasons:
        result['arithmetic'] = arithmetic_check(annuals, quarters)
        if result['arithmetic']['decision'] == 'bridged_arithmetic_only':
            result['legacy_numeric_comparison'] = legacy_numeric_check(qt['filing']['ticker'], end, original['concept'], original['dimensions'], result['arithmetic'])
    return result


def run(output):
    started = time.perf_counter()
    manifest = json.loads((BASE / 'manifest.json').read_text())
    previous = json.loads((BASE / 'results/q4-evidence.json').read_text())
    taxonomies = {(f['ticker'], f['form']): taxonomy(f) for f in manifest['filings']}
    cases = []
    for company in previous:
        ticker = company['ticker']
        qt, at = taxonomies[(ticker, '10-Q')], taxonomies[(ticker, '10-K')]
        qfacts, afacts = ({f['fact_id']: f for f in t['facts']} for t in (qt, at))
        for index, original in enumerate(company['candidates']):
            if original['decision'] != 'abstain_taxonomy_version_bridge_required':
                continue
            annuals = [afacts[fid] for fid in original['annual_fact_ids']]
            quarters = [qfacts[fid] for fid in original['lexical_candidate_ids']]
            evaluations = [evaluate_pair(qt, at, q, a) for a in annuals for q in quarters]
            reasons = sorted({r for e in evaluations for r in e['reasons']})
            decision = 'abstain_needs_review' if reasons else 'evidence_supported_version_bridge'
            item = {'id': f'{ticker}:{index}', 'ticker': ticker, 'concept': original['concept'],
                    'dimensions': original['dimensions'], 'annual_fact_ids': original['annual_fact_ids'],
                    'nine_month_fact_ids': original['lexical_candidate_ids'], 'decision': decision,
                    'reasons': reasons, 'pair_evidence': evaluations,
                    'sources': {'annual': at['filing'], 'nine_month': qt['filing']}}
            # Semantic gate is finished before arithmetic or duplicate-value checks.
            if decision == 'evidence_supported_version_bridge':
                item['arithmetic'] = arithmetic_check(annuals, quarters)
                if item['arithmetic']['decision'] == 'bridged_arithmetic_only':
                    item['legacy_numeric_comparison'] = legacy_numeric_check(ticker, at['filing']['reportDate'], original['concept'], original['dimensions'], item['arithmetic'])
            item['historical_comparison'] = comparison_period(qt, at, original)
            cases.append(item)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'cases.json.gz').write_bytes(gzip.compress(json.dumps(cases, sort_keys=True).encode(), mtime=0))
    summary = {'mode': 'retrospective_Q3_FY2025_version_bridge_contract', 'blind_cases': 0,
               'scope': 'Only 64 lexical-QName-identical version-blocked scopes; no renamed or missing scopes added',
               'company_specific_bridge_rules': 0, 'input_cases': len(cases),
               'statuses': dict(Counter(c['decision'] for c in cases)),
               'reason_counts': dict(Counter(r for c in cases for r in c['reasons'])),
               'refusal_structure_categories': dict(Counter(
                   'changed_shared_role' if any(e.get(k, {}).get('changed_shared_roles')
                       for p in c['pair_evidence'] for e in p['elements']
                       for k in ('definition_difference', 'presentation_difference')) else 'role_inventory_only'
                   for c in cases if c['decision'] == 'abstain_needs_review')),
               'by_company': {ticker: dict(Counter(c['decision'] for c in cases if c['ticker'] == ticker)) for ticker in sorted({c['ticker'] for c in cases})},
               'historical_comparison_statuses': dict(Counter(c['historical_comparison']['decision'] for c in cases)),
               'primary_legacy_numeric_statuses': dict(Counter(c['legacy_numeric_comparison']['status'] for c in cases if 'legacy_numeric_comparison' in c)),
               'historical_legacy_numeric_statuses': dict(Counter(c['historical_comparison']['legacy_numeric_comparison']['status'] for c in cases if 'legacy_numeric_comparison' in c['historical_comparison'])),
               'processing_seconds': time.perf_counter() - started,
               'taxonomy_processing_seconds': {ticker + ':' + form: t['processing_seconds'] for (ticker, form), t in taxonomies.items()},
               'code_sha256': digest(Path(__file__).read_bytes()),
               'baseline_manifest_sha256': digest((BASE / 'manifest.json').read_bytes()),
               'input_q4_sha256': digest((BASE / 'results/q4-evidence.json').read_bytes()),
               'vendor_raw_used': False, 'independent_human_review': False}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.out), indent=2))
