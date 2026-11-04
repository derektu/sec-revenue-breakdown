"""Bounded, offline iXBRL evidence experiment; never chooses a vendor taxonomy.

Supports the pinned SEC HTML/linkbases only. Relationships remain evidence, not
an inferred partition. Unknown transformations and scope bridges abstain.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
from pathlib import Path
import re
import time
from lxml import etree, html

ROOT = Path(__file__).resolve().parents[1]
XL = '{http://www.w3.org/1999/xlink}'
REVENUE = frozenset('RevenueFromContractWithCustomerExcludingAssessedTax RevenueFromContractWithCustomerIncludingAssessedTax Revenues SalesRevenueNet SalesRevenueGoodsNet SalesRevenueServicesNet RegulatedAndUnregulatedOperatingRevenue RevenueNotFromContractWithCustomer'.split())
COST = frozenset('CostOfRevenue CostOfGoodsAndServicesSold CostOfGoodsSold CostOfServices'.split())
TRANSFORMS = frozenset(('num-dot-decimal', 'numdotdecimal', 'num-zero', 'zerodash', 'fixed-zero'))


def digest(body):
    return hashlib.sha256(body).hexdigest()


def text(node):
    return ' '.join(' '.join(node.itertext()).split())


def local(node):
    return str(node.tag).split('}')[-1].split(':')[-1].lower()


def read_pinned(entry):
    path = ROOT / entry['path']
    body = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
    if digest(body) != entry['sha256']:
        raise ValueError(f'Hash mismatch: {path}')
    return body


def expanded(qname, namespaces):
    if ':' not in qname:
        return qname
    prefix, name = qname.split(':', 1)
    return '{' + namespaces.get(prefix, 'UNRESOLVED:' + prefix) + '}' + name


def nature(concept, namespaces):
    prefix, _, name = concept.partition(':')
    standard = bool(re.fullmatch(r'https?://fasb.org/us-gaap/\d{4}', namespaces.get(prefix, '')))
    if standard and name in REVENUE:
        return 'revenue'
    if standard and name in COST:
        return 'cost'
    # Revenue-related balances/cash flows are deliberately not revenue.
    return 'abstain'


def period_kind(context):
    try:
        duration = (date.fromisoformat(context['enddate']) - date.fromisoformat(context['startdate'])).days + 1
    except (KeyError, ValueError):
        return 'instant_or_unknown'
    if 70 <= duration <= 126:
        return 'Q'
    if 350 <= duration <= 380:
        return 'FY'
    if 240 <= duration <= 300:
        return 'YTD9'
    return 'other_duration'


def numeric(node, namespaces):
    fmt = node.get('format', '')
    transform_namespace = namespaces.get(fmt.split(':')[0], '')
    if fmt and (fmt.split(':')[-1] not in TRANSFORMS or transform_namespace not in (
            'http://www.xbrl.org/inlineXBRL/transformation/2020-02-12',
            'http://www.xbrl.org/inlineXBRL/transformation/2015-02-26',
            'http://www.xbrl.org/inlineXBRL/transformation/2011-07-31')):
        return None, 'unsupported_transform:' + fmt
    if any(local(x) == 'fraction' for x in node.iter()):
        return None, 'fraction'
    raw = ''.join(node.itertext()).strip().replace(',', '').replace(' ', '').replace('\u00a0', '')
    if fmt.split(':')[-1] == 'fixed-zero':
        raw = '0'
    if raw in ('—', '–', '-'):
        raw = '0'
    if node.get('xsi:nil') in ('true', '1'):
        return None, 'nil'
    try:
        number = Decimal(raw) * Decimal(10) ** int(node.get('scale', '0'))
        if node.get('sign') == '-':
            number = -number
        if not number.is_finite():
            return None, 'nonfinite'
        return str(number), None
    except (InvalidOperation, ValueError):
        return None, 'unsupported_number'


def parse_document(body):
    root = html.fromstring(body)
    namespaces = {key[6:]: value for key, value in root.attrib.items() if key.startswith('xmlns:')}
    contexts, units = {}, {}
    for node in root.iter():
        if local(node) == 'context':
            context = {'dimensions': {}, 'expanded_dimensions': {}, 'entity': {}, 'unsupported_context': []}
            for child in node.iter():
                kind = local(child)
                if kind == 'identifier':
                    context['entity'] = {'scheme': child.get('scheme'), 'identifier': text(child)}
                elif kind in ('startdate', 'enddate', 'instant'):
                    context[kind] = text(child)
                elif kind in ('explicitmember', 'typedmember'):
                    axis = child.get('dimension', '')
                    member = text(child)
                    if axis in context['dimensions']:
                        context['unsupported_context'].append('duplicate_axis')
                    context['dimensions'][axis] = member
                    context['expanded_dimensions'][expanded(axis, namespaces)] = expanded(member, namespaces) if kind == 'explicitmember' else etree.tostring(child).decode()
                    if kind == 'typedmember':
                        context['unsupported_context'].append('typed_dimension')
                elif kind in ('segment', 'scenario') and any(local(x) not in ('explicitmember', 'typedmember') for x in child):
                    context['unsupported_context'].append('non_dimensional_' + kind)
            context['period_kind'] = period_kind(context)
            context['scope_key'] = digest(json.dumps(context, sort_keys=True).encode())
            contexts[node.get('id')] = context
        elif local(node) == 'unit':
            measures = [expanded(text(x), namespaces) for x in node.iter() if local(x) == 'measure']
            units[node.get('id')] = {'measures': measures, 'divide': any(local(x) == 'divide' for x in node.iter())}
    tree = root.getroottree()
    tables = {tree.getpath(t): i for i, t in enumerate(root.iter('table'))}
    facts = []
    for node in root.iter():
        if local(node) != 'nonfraction':
            continue
        concept = node.get('name', '')
        context = contexts.get(node.get('contextref'))
        unit = units.get(node.get('unitref'))
        value, error = numeric(node, namespaces)
        ancestors = list(node.iterancestors())
        row = next((x for x in ancestors if local(x) == 'tr'), None)
        table = next((x for x in ancestors if local(x) == 'table'), None)
        status = nature(concept, namespaces)
        reasons = []
        if error:
            reasons.append(error)
        if context is None:
            reasons.append('missing_context')
        elif context['unsupported_context']:
            reasons.extend(context['unsupported_context'])
        if not unit or unit['divide'] or len(unit['measures']) != 1 or not unit['measures'][0].startswith('{http://www.xbrl.org/2003/iso4217}'):
            reasons.append('non_currency_unit')
        if context and context['period_kind'] == 'instant_or_unknown':
            reasons.append('not_duration')
        facts.append({'fact_id': node.get('id'), 'concept': concept, 'expanded_concept': expanded(concept, namespaces),
                      'context_id': node.get('contextref'), 'context': context, 'unit': unit,
                      'raw': text(node), 'value': value, 'decimals': node.get('decimals'),
                      'nature': status, 'admissible': status in ('revenue', 'cost') and not reasons,
                      'abstain_reasons': reasons + (['concept_not_in_reviewed_standard_set'] if status == 'abstain' else []),
                      'xpath': re.sub(r'([A-Za-z][\w-]*:[\w-]+)', lambda m: "*[name()='" + m.group(1) + "']", tree.getpath(node)), 'source_line': node.sourceline,
                      'table_index': tables.get(tree.getpath(table)) if table is not None else None,
                      'row_text': text(row) if row is not None else '',
                      'rollup_status': 'abstain_partition_not_proven'})
    return facts, namespaces


def relationships(entries):
    """Preserve role/arcrole and original hrefs; do not resolve external DTS."""
    arcs = []
    for entry in entries:
        if entry['kind'] not in ('cal', 'pre', 'def'):
            continue
        root = etree.fromstring(read_pinned(entry), etree.XMLParser(resolve_entities=False, no_network=True))
        for link in root:
            locators = {e.get(XL + 'label'): e.get(XL + 'href') for e in link if local(e) == 'loc'}
            for arc in link:
                if not local(arc).endswith('arc'):
                    continue
                source, target = locators.get(arc.get(XL + 'from')), locators.get(arc.get(XL + 'to'))
                if not source or not target:
                    continue
                def qname(href):
                    fragment = href.split('#')[-1]
                    return fragment.replace('_', ':', 1)
                arcs.append({'kind': entry['kind'], 'role': link.get(XL + 'role'),
                             'arcrole': arc.get(XL + 'arcrole'), 'parent': qname(source), 'child': qname(target),
                             'parent_href': source, 'child_href': target, 'weight': arc.get('weight'),
                             'use': arc.get('use'), 'priority': arc.get('priority', '0'),
                             'target_role': arc.get('{http://xbrl.org/2005/xbrldt}targetRole'),
                             'source_path': entry['path'], 'source_sha256': entry['sha256']})
    return arcs


def hierarchy_warnings(facts, arcs):
    # This is a warning search, not dimensional relationship set validation.
    by_role = defaultdict(lambda: defaultdict(set))
    for arc in arcs:
        if arc['kind'] == 'def' and arc['arcrole'].endswith('/domain-member') and arc['use'] != 'prohibited':
            by_role[arc['role']][arc['parent']].add(arc['child'])
    members = set()
    for fact in facts:
        if fact['admissible'] and fact['nature'] == 'revenue':
            members.update(fact['context']['dimensions'].values())
    warnings = []
    for role, edges in by_role.items():
        for parent in sorted(members):
            pending, seen = list(edges.get(parent, ())), set()
            while pending:
                child = pending.pop()
                if child in seen:
                    continue
                seen.add(child)
                pending.extend(edges.get(child, ()))
            for child in sorted(members & seen - {parent}):
                warnings.append({'role': role, 'parent_member': parent, 'descendant_member': child,
                                 'decision': 'abstain_flat_sum_possible_overlap'})
    return warnings


def equation_checks(facts, arcs):
    # Only same full context/unit; dimensional summations are not inferred.
    groups = defaultdict(list)
    for fact in facts:
        if fact['context'] and fact['value'] is not None and not fact['context']['unsupported_context']:
            key = (fact['context']['scope_key'], json.dumps(fact['unit'], sort_keys=True))
            groups[key].append(fact)
    calculations = defaultdict(list)
    for arc in arcs:
        if arc['kind'] == 'cal':
            calculations[(arc['role'], arc['parent'])].append(arc)
    checks = []
    for (role, parent), children in calculations.items():
        # Effective arc resolution is intentionally unsupported: reject unusual sets.
        if any(c['use'] == 'prohibited' or c['priority'] != '0' for c in children):
            continue
        if len({c['child'] for c in children}) != len(children):
            continue
        for group in groups.values():
            names = defaultdict(list)
            for fact in group:
                names[fact['concept']].append(fact)
            if parent not in names or not any(f['nature'] == 'revenue' for f in names[parent]):
                continue
            required = [parent] + [c['child'] for c in children]
            if any(n not in names or len({f['value'] for f in names[n]}) != 1 for n in required):
                continue
            try:
                difference = sum(Decimal(c['weight']) * Decimal(names[c['child']][0]['value']) for c in children) - Decimal(names[parent][0]['value'])
            except (InvalidOperation, TypeError):
                continue
            checks.append({'role': role, 'parent_fact_id': names[parent][0]['fact_id'],
                           'children': [{'fact_id': names[c['child']][0]['fact_id'], 'weight': c['weight']} for c in children],
                           'difference': str(difference), 'exact_equation': difference == 0,
                           'decision': 'equation_only_partition_not_proven'})
    return checks


def analyze(filing):
    started = time.perf_counter()
    facts, _ = parse_document(read_pinned(filing))
    arcs = relationships(filing['support'])
    equations = equation_checks(facts, arcs)
    warnings = hierarchy_warnings(facts, arcs)
    revenue = [f for f in facts if f['admissible'] and f['nature'] == 'revenue']
    return {'ticker': filing['ticker'], 'report_date': filing['reportDate'], 'form': filing['form'],
            'source_url': filing['url'], 'source_sha256': filing['sha256'],
            'facts': facts, 'relationships': arcs, 'equations': equations, 'hierarchy_warnings': warnings,
            'summary': {'numeric_facts': len(facts), 'nature_counts': dict(Counter(f['nature'] for f in facts)),
                        'admissible_revenue': len(revenue), 'admissible_cost': sum(f['admissible'] and f['nature'] == 'cost' for f in facts),
                        'revenue_period_counts': dict(Counter(f['context']['period_kind'] for f in revenue)),
                        'multi_axis_revenue': sum(len(f['context']['dimensions']) > 1 for f in revenue),
                        'legal_entity_axis_revenue': sum(any(a.endswith('LegalEntityAxis') for a in f['context']['dimensions']) for f in revenue),
                        'hierarchy_warning_count': len(warnings), 'same_context_revenue_equations': len(equations),
                        'exact_equations': sum(c['exact_equation'] for c in equations),
                        'automatic_partitions': 0, 'processing_seconds': time.perf_counter() - started}}


def q4_evidence(annual, quarterly):
    """Require unchanged expanded taxonomy identity; no company alias bridges."""
    fy = [f for f in annual['facts'] if f['admissible'] and f['nature'] == 'revenue'
          and f['context']['period_kind'] == 'FY' and f['context'].get('enddate') == annual['report_date']]
    ytd = [f for f in quarterly['facts'] if f['admissible'] and f['nature'] == 'revenue'
           and f['context']['period_kind'] == 'YTD9' and f['context'].get('enddate') == quarterly['report_date']]
    def key(f, expanded_names):
        c = f['context']
        return json.dumps([f['expanded_concept'] if expanded_names else f['concept'],
                           c['expanded_dimensions'] if expanded_names else c['dimensions'],
                           c['entity'], c.get('startdate'), f['unit']], sort_keys=True)
    strict, lexical = defaultdict(list), defaultdict(list)
    for f in ytd:
        strict[key(f, True)].append(f)
        lexical[key(f, False)].append(f)
    output, seen = [], set()
    for f in fy:
        k = key(f, True)
        if k in seen:
            continue
        seen.add(k)
        matches = strict.get(k, [])
        annual_matches = [a for a in fy if key(a, True) == k]
        item = {'annual_fact_ids': [a['fact_id'] for a in annual_matches], 'concept': f['concept'],
                'dimensions': f['context']['dimensions'], 'decision': 'abstain_missing_same_scope_YTD9'}
        if not matches and lexical.get(key(f, False)):
            item['decision'] = 'abstain_taxonomy_version_bridge_required'
            item['lexical_candidate_ids'] = [p['fact_id'] for p in lexical[key(f, False)]]
        if matches:
            item['nine_month_fact_ids'] = [p['fact_id'] for p in matches]
            if len({a['value'] for a in annual_matches}) != 1 or len({p['value'] for p in matches}) != 1:
                item['decision'] = 'abstain_conflicting_duplicates'
            elif 70 <= (date.fromisoformat(annual['report_date']) - date.fromisoformat(quarterly['report_date'])).days <= 126:
                item.update(decision='same_scope_arithmetic_only', value=str(Decimal(f['value']) - Decimal(matches[0]['value'])),
                            period_end=annual['report_date'], partition_verified=False,
                            limitation='No restatement or business-definition continuity certification')
        output.append(item)
    return {'ticker': annual['ticker'], 'annual_source_sha256': annual['source_sha256'],
            'nine_month_source_sha256': quarterly['source_sha256'], 'candidates': output,
            'statuses': dict(Counter(x['decision'] for x in output))}


def run(manifest_path, output):
    manifest = json.loads(manifest_path.read_text())
    output.mkdir(parents=True, exist_ok=False)
    summary = {'mode': 'retrospective_exposed_historical_SEC', 'blind_cases': 0,
               'company_specific_parser_rules': 0, 'standard_revenue_concepts': len(REVENUE),
               'standard_cost_concepts': len(COST), 'vendor_raw_used': False,
               'parser_sha256': digest(Path(__file__).read_bytes()),
               'comparison_sha256': digest((ROOT / 'scripts/compare_shared_semantics.py').read_bytes()),
               'manifest_sha256': digest(manifest_path.read_bytes()), 'filings': []}
    analyzed = []
    for filing in manifest['filings']:
        result = analyze(filing)
        from compare_shared_semantics import compare
        result['comparison'] = compare(filing, result)
        result['summary']['comparison'] = {k: v for k, v in result['comparison'].items() if k != 'catalog_terms'}
        filename = f'{filing["ticker"]}-{filing["reportDate"]}.json.gz'
        with (output / filename).open('wb') as stream:
            stream.write(gzip.compress(json.dumps(result, ensure_ascii=False, sort_keys=True).encode(), mtime=0))
        analyzed.append(result)
        summary['filings'].append({key: result[key] for key in ('ticker', 'report_date', 'form', 'summary')})
    q4 = [q4_evidence(a, q) for a in analyzed if a['form'] == '10-K'
          for q in analyzed if q['ticker'] == a['ticker'] and q['form'] == '10-Q']
    (output / 'q4-evidence.json').write_text(json.dumps(q4, indent=2) + '\n')
    summary['q4_statuses'] = {x['ticker']: x['statuses'] for x in q4}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'research/shared-raw-semantics/manifest.json')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.manifest, args.out), indent=2))
