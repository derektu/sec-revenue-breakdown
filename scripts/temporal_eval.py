#!/usr/bin/env python3
"""Offline, accession-isolated development packs and frozen temporal evaluation."""
import argparse
import datetime as dt
from decimal import Decimal
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'research/sec-30-baseline-2026-11-04'
RULE_FILES = ['scripts/temporal_eval.py', 'research/recovered-sec/extract.py',
              'research/recovered-sec/eight_quarter_eval/run.py']
SOURCES = ('tradingview', 'futu', 'stockanalysis')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def baseline(path):
    return json.loads(gzip.decompress(Path(path).read_bytes()))


def timestamp(value):
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timestamp requires timezone')
    return result


def validate(plan):
    if plan['schema_version'] != 1:
        raise ValueError('Unsupported schema')
    dt.date.fromisoformat(plan['cutoff']['filing_date'])
    end = plan['cutoff']['period_end']
    dt.date.fromisoformat(end)
    train = plan['training']
    hold = plan['holdout']
    if not train or not hold:
        raise ValueError('Explicit training and holdout filings required')
    accessions = [f['accession'] for f in train + hold]
    if len(accessions) != len(set(accessions)):
        raise ValueError('Accession overlap/duplicate')
    for f in train:
        if f['filing_date'] > plan['cutoff']['filing_date'] or f['period_end'] > end:
            raise ValueError('Training filing exceeds cutoff')
    for f in hold:
        if f['period_end'] <= end or f['filing_date'] <= plan['cutoff']['filing_date']:
            raise ValueError('Holdout must be strictly after both cutoffs')
    for f in train + hold:
        dt.date.fromisoformat(f['period_end'])
        dt.date.fromisoformat(f['filing_date'])
        if f['form'] not in ('10-Q', '10-K') or not f['url'] or len(f['sha256']) != 64:
            raise ValueError('Filing evidence missing')
    for row in [plan['exposure'], *plan['references']]:
        if row['seen_during_development'] not in ('yes', 'no', 'unknown'):
            raise ValueError('Exposure must be yes/no/unknown')
        if row['seen_during_development'] != 'unknown' and not row.get('evidence'):
            raise ValueError('Known exposure needs evidence/attestation')
    if {r['source'] for r in plan['references']} != set(SOURCES) or len(plan['references']) != 3:
        raise ValueError('Track all three reference sources separately')
    return plan


def seed(baseline_dir):
    """Metadata only: all old outputs have uncertain exposure, never retroactive blindness."""
    plans = []
    for path in sorted(Path(baseline_dir).glob('*.json.gz')):
        data = baseline(path)
        filings = sorted([m for m in data['manifest'] if m.get('accessionNumber')],
                         key=lambda m: (m['reportDate'], m['filingDate']))
        if len(filings) < 2:
            continue
        def entry(m):
            return {'accession': m['accessionNumber'], 'period_end': m['reportDate'],
                    'filing_date': m['filingDate'], 'form': m['form'], 'url': m['url'],
                    'sha256': m['sha256']}
        train, hold = [entry(f) for f in filings[:-1]], [entry(filings[-1])]
        apple = data['ticker'] == 'AAPL'
        plan = {'schema_version': 1, 'ticker': data['ticker'], 'cik': data['cik'],
                'rule_version': None,
                'baseline_file': str(path.relative_to(ROOT)), 'baseline_sha256': digest(path.read_bytes()),
                'cutoff': {'filing_date': max(f['filing_date'] for f in train),
                           'period_end': max(f['period_end'] for f in train)},
                'training': train, 'holdout': hold,
                'exposure': {'seen_during_development': 'yes' if apple else 'unknown',
                             'evidence': ['docs/vendor/apple-comparison.md', 'user: Apple latest quarter already inspected'] if apple else [],
                             'note': 'Retrospective split; historical development exposure is not fully recorded.'},
                'references': [{'source': source, 'availability': 'not_loaded_by_this_workflow',
                                'seen_during_development': 'yes' if apple and source in ('futu', 'stockanalysis') else 'unknown',
                                'evidence': ['docs/vendor/apple-comparison.md'] if apple and source in ('futu', 'stockanalysis') else []}
                               for source in SOURCES],
                'adjudication': {'preferred_reference': None, 'status': 'unresolved',
                                 'rationale': None, 'evidence': [], 'uncertainty': 'No company-specific adjudication added.'}}
        plans.append(validate(plan))
    return plans


def checked_data(plan, path):
    validate(plan)
    if digest(Path(path).read_bytes()) != plan['baseline_sha256']:
        raise ValueError('Baseline changed')
    data = baseline(path)
    if data['ticker'] != plan['ticker'] or data['cik'] != plan['cik']:
        raise ValueError('Issuer mismatch')
    manifest = {m['accessionNumber']: m for m in data['manifest'] if m.get('accessionNumber')}
    for f in plan['training'] + plan['holdout']:
        m = manifest[f['accession']]
        if any(f[k] != m[v] for k, v in [('period_end', 'reportDate'), ('filing_date', 'filingDate'),
                ('form', 'form'), ('sha256', 'sha256'), ('url', 'url')]):
            raise ValueError('Plan and SEC evidence disagree')
    return data


def select_records(plan, data, partition):
    selected = []
    records = {r['filing']['accessionNumber']: r for r in data['raw_filings']}
    for f in plan[partition]:
        record = records[f['accession']]
        kept, excluded = [], []
        for index, fact in enumerate(record['facts']):
            if fact.get('accession') != f['accession'] or fact.get('filing_date') != f['filing_date']:
                raise ValueError('Fact provenance mismatch')
            if partition == 'training' and max(fact.get('enddate', ''), fact.get('instant', '')) > plan['cutoff']['period_end']:
                excluded.append({'fact_index': index, 'fact_id': fact.get('fact_id'),
                                 'sha256': digest(canonical(fact)), 'reason': 'period_after_training_cutoff'})
            else:
                kept.append(fact)
        selected.append({**record, 'facts': kept, 'excluded_facts': excluded})
    return selected


def training_pack(plan, data):
    validate(plan)
    # Whole accession isolation excludes every comparison column from a later K/Q.
    # No quarter_results, vendor values, holdout facts or manual answers are copied.
    return {'ticker': plan['ticker'], 'cutoff': plan['cutoff'],
            'raw_filings': select_records(plan, data, 'training'),
            'source_kind': 'parser_observations_not_adjudicated_answers'}


def rule_hashes():
    return {name: digest((ROOT / name).read_bytes()) for name in RULE_FILES}


def freeze(plan, data, rules, now=None):
    pack = training_pack(plan, data)
    if not rules.get('version'):
        raise ValueError('Explicit rule version required')
    # Selectors are explicit company rules. No matching by reference numeric value.
    for selector in rules['selectors']:
        if selector['period_kind'] not in ('Q', 'FY'):
            raise ValueError('Selectors must distinguish Q and FY')
        if not all(selector.get(k) for k in ('id', 'concept', 'unit', 'semantic_basis')) or 'dimensions' not in selector:
            raise ValueError('Selector lacks exact concept/dimensions/unit/meaning')
    ids = [r['id'] for r in rules['selectors']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate selector id')
    return {'schema_version': 1, 'frozen_at': now or dt.datetime.now(dt.timezone.utc).isoformat(),
            'rule_version': rules['version'],
            'plan': plan, 'plan_sha256': digest(canonical(plan)), 'rules': rules,
            'rules_sha256': digest(canonical(rules)), 'code_sha256': rule_hashes(),
            'training_pack_sha256': digest(canonical(pack)),
            'note': 'A freeze is a reproducibility receipt, not proof of unseen data.'}


def verify_freeze(receipt, data):
    if receipt['code_sha256'] != rule_hashes():
        raise ValueError('Code changed since freeze; create a new experiment')
    for key in ('plan', 'rules'):
        if digest(canonical(receipt[key])) != receipt[key + '_sha256']:
            raise ValueError('Frozen ' + key + ' changed')
    if receipt['rule_version'] != receipt['rules']['version']:
        raise ValueError('Rule version mismatch')
    timestamp(receipt['frozen_at'])
    if 'registration' in receipt:
        registration = receipt['registration']
        verify_freeze(registration, data)
        check_future_binding(registration, receipt['plan'])
        if any(receipt[k] != registration[k] for k in ('frozen_at', 'rules_sha256', 'code_sha256', 'training_pack_sha256')):
            raise ValueError('Registered rules or training changed')
    pack = training_pack(receipt['plan'], data)
    if digest(canonical(pack)) != receipt['training_pack_sha256']:
        raise ValueError('Training pack changed')


def check_future_binding(registration, plan):
    if plan['training'] != registration['plan']['training'] or plan['cutoff'] != registration['plan']['cutoff']:
        raise ValueError('Future binding must preserve registered training and cutoff')
    registered_date = timestamp(registration['frozen_at']).date().isoformat()
    previous_end = max(f['period_end'] for f in registration['plan']['holdout'])
    if any(f['filing_date'] <= registered_date or f['period_end'] <= previous_end for f in plan['holdout']):
        raise ValueError('Future holdout must be published after registration and later than old target')


def attach_future(registration, plan, data):
    verify_freeze(registration, data)
    validate(plan)
    check_future_binding(registration, plan)
    result = freeze(plan, data, registration['rules'], now=registration['frozen_at'])
    result['registration'] = registration
    result['bound_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    result['note'] = 'Future accession bound to previously frozen rules; original registration retained.'
    verify_freeze(result, data)
    return result


def holdout_status(plan):
    rows = [plan['exposure'], *plan['references']]
    if any(r['seen_during_development'] == 'yes' for r in rows):
        return 'contaminated'
    if any(r['seen_during_development'] == 'unknown' for r in rows):
        return 'exposure_unknown'
    return 'declared_unseen_pending_evaluation'


def runner():
    path = ROOT / 'research/recovered-sec/eight_quarter_eval/run.py'
    spec = importlib.util.spec_from_file_location('temporal_quarter_runner', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replay(receipt, data):
    verify_freeze(receipt, data)
    plan = receipt['plan']
    train = select_records(plan, data, 'training')
    hold = select_records(plan, data, 'holdout')
    engine = runner()
    results = []
    for record, filing in zip(hold, plan['holdout']):
        previous = [f for r in train for f in r['facts']]
        q, conflicts = engine.quarter(record['facts'], filing['period_end'], filing['form'], previous)
        annual = [f for f in record['facts'] if f.get('enddate') == filing['period_end'] and 350 <= engine.days(f) <= 380]
        annual, annual_conflicts = engine.dedupe(annual)
        # FY never enters Q selectors. Q4 keeps both original operands intact.
        for selector in receipt['rules']['selectors']:
            pool = q if selector['period_kind'] == 'Q' else annual
            ambiguous = conflicts if selector['period_kind'] == 'Q' else annual_conflicts
            def matches(f):
                return all(f.get(k) == selector[k] for k in ('concept', 'unit', 'dimensions'))
            facts = [f for f in pool if matches(f)]
            conflict = any(matches(f) for group in ambiguous for f in group)
            status = 'ambiguous' if conflict or len(facts) > 1 else 'observed' if facts else 'parser_missing'
            results.append({'selector_id': selector['id'], 'period_kind': selector['period_kind'],
                            'period_end': filing['period_end'], 'semantic_basis': selector['semantic_basis'],
                            'unit': selector['unit'], 'period_start': facts[0].get('startdate') if status == 'observed' else None, 'status': status,
                            'value': facts[0]['value'] if status == 'observed' else None,
                            'facts': facts, 'conflicts': [g for g in ambiguous if any(matches(f) for f in g)]})
    return {'ticker': plan['ticker'], 'freeze_sha256': digest(canonical(receipt)),
            'exposure_status': holdout_status(plan), 'results': results,
            'execution': 'stored_parser_facts_replayed_not_html_reparsed',
            'semantic_accuracy_measured': False}


def compare(receipt, prediction, references):
    """Compare separately by source; adjudications stay distinct and never feed selectors."""
    if prediction['freeze_sha256'] != digest(canonical(receipt)):
        raise ValueError('Prediction belongs to another freeze')
    frozen_at = timestamp(receipt['frozen_at'])
    rows = []
    status = prediction['exposure_status']
    for ref in references:
        if ref['ticker'] != prediction['ticker']:
            raise ValueError('Reference issuer mismatch')
        if ref['source_kind'] not in ('vendor', 'sec_adjudication', 'human_adjudication'):
            raise ValueError('Reference role required')
        if ref['source_kind'] == 'vendor' and ref['source'] not in SOURCES:
            raise ValueError('Unknown vendor')
        if not ref.get('evidence') or not ref.get('url') or len(ref.get('sha256', '')) != 64:
            raise ValueError('Reference requires retained evidence, URL and hash')
        evidence_path = Path(ref['evidence'])
        if not evidence_path.is_absolute():
            evidence_path = ROOT / evidence_path
        if digest(evidence_path.read_bytes()) != ref['sha256']:
            raise ValueError('Reference evidence hash mismatch')
        if type(ref['used_for_rule_development']) is not bool:
            raise ValueError('Development use must be explicit')
        first_seen = timestamp(ref['first_seen_at'])
        if ref['used_for_rule_development'] or first_seen <= frozen_at:
            status = 'contaminated'
        candidates = [r for r in prediction['results'] if all(r[k] == ref[k] for k in ('selector_id', 'period_kind', 'period_end'))]
        if len(candidates) != 1:
            outcome = 'period_or_selector_unaligned'
        elif ref['value'] is None:
            outcome = 'reference_missing'
        elif candidates[0]['status'] != 'observed':
            outcome = candidates[0]['status']
        elif candidates[0]['period_start'] != ref['period_start']:
            outcome = 'period_start_differs'
        elif candidates[0]['semantic_basis'] != ref['semantic_basis']:
            outcome = 'semantic_basis_differs'
        elif candidates[0]['unit'] != ref['unit']:
            outcome = 'unit_differs'
        else:
            tolerance = Decimal(str(ref['absolute_tolerance']))
            if not tolerance.is_finite() or tolerance < 0:
                raise ValueError('Invalid tolerance')
            a, b = Decimal(str(candidates[0]['value'])), Decimal(str(ref['value']))
            if not a.is_finite() or not b.is_finite():
                raise ValueError('Non-finite amount')
            outcome = 'numeric_match' if abs(a - b) <= tolerance else 'numeric_difference'
        rows.append({'reference': ref, 'outcome': outcome,
                     'prediction': candidates[0] if len(candidates) == 1 else None})
    genuine = status == 'declared_unseen_pending_evaluation' and any(
        r['outcome'] in ('numeric_match', 'numeric_difference') for r in rows)
    return {'ticker': prediction['ticker'], 'freeze_sha256': prediction['freeze_sha256'],
            'exposure_status': status,
            'genuine_holdout_by_recorded_attestations': genuine,
            'reference_comparisons': rows, 'reference_count': len(rows),
            'semantic_accuracy_measured': False,
            'note': 'No vendor is ground truth; no automatic preferred source or accuracy denominator.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['seed', 'pack', 'freeze', 'attach', 'replay', 'compare'])
    parser.add_argument('--baseline', type=Path, default=BASELINE)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--rules', type=Path)
    parser.add_argument('--freeze', type=Path)
    parser.add_argument('--references', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'seed':
        result = seed(args.baseline)
    else:
        receipt = load(args.freeze) if args.freeze else None
        plan = load(args.plan) if args.plan else receipt['plan']
        data_path = args.baseline / (plan['ticker'] + '.json.gz') if args.baseline.is_dir() else args.baseline
        data = checked_data(plan, data_path)
        if args.action == 'pack':
            result = training_pack(plan, data)
        elif args.action == 'freeze':
            result = freeze(plan, data, load(args.rules))
        elif args.action == 'attach':
            result = attach_future(receipt, plan, data)
        else:
            result = replay(receipt, data)
            if args.action == 'compare':
                result = compare(receipt, result, load(args.references))
    save(args.out, result)
    print(json.dumps({'output': str(args.out), 'sha256': digest(args.out.read_bytes())}))


if __name__ == '__main__':
    main()
