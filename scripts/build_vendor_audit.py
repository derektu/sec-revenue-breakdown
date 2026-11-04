#!/usr/bin/env python3
"""由本機比對紀錄產生不含第三方原始列的逐公司稽核及資料切分紀錄。"""
from collections import Counter
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path

from compare_vendor_cohort import ROOT, futu_fiscal_date

NOTES = {
    'AAPL': '產品／服務五分類已覆核；Q4 為全年減九個月。採公司揭露口徑，兩家參考支持；不是盲測。',
    'MSFT': '營運分部分類集合改變；須核對重分類與公司項目，未選定單一供應商答案。',
    'NVDA': '營運分部含 OperatingSegments 範圍；兩筆無數字候選，待查 Q4／重編。',
    'ORCL': '產品／服務及營運分部混合候選，分類亦變動；月末相差一月的期間建議未核准。',
    'GOOGL': '產品／服務細項與營運分部混合；避險項目須另查，不可重複加廣告小計。',
    'META': '產品／服務與營運分部交叉維度；兩筆差異仍未判定。',
    'DIS': '營運分部；顯示季度截止日較財季晚數日，名稱縮寫不能證明重分類連續。',
    'CMCSA': '需合併分部；已檢查的二分部運算五期相同、三期不同；另一大類未判定。',
    'AMZN': '產品／服務細項須與 AWS 營運分部區分；兩年 Q4 廣告成員改名造成推算缺口。',
    'TSLA': '產品／服務收入三類具對應候選；尚未逐期覆核全表、重編與最新季泛化。',
    'HD': '產品線維度外另有營運分部與合併範圍；財季月份位移建議待確認。',
    'MCD': '直營、加盟及其他的產品／服務口徑；富途七個目標季度，一期缺漏，差異待判。',
    'WMT': '採公司 Revenues 分部口徑，不能混用合約淨銷售；18 筆指定範圍相同，14 筆未判定。',
    'COST': '淨銷售與會員費口徑；兩期無日期對照，其餘也包含月份位移，不能宣稱八季。',
    'PG': '營運分部及公司項目；縮寫表格精度低，兩筆無候選仍待查。',
    'KO': '營運分部、公司與抵銷項目；含自訂 concept 和分類變動，須逐期檢查 gross/net。',
    'JNJ': '營運分部；舊醫藥標籤與 InnovativeMedicine 的對應需證據，名稱不可直接延續。',
    'UNH': '營運分部、Optum 合計與抵銷層級；三筆差異未判定，不可把子類加到父類。',
    'LLY': '治療領域產品分類；一顯示期超出基準，其他差異及舊類別名稱待查。',
    'JPM': '扣利息費用後營收，與一般銷售不同；分部重組／公司項目須核對。',
    'BAC': '候選採 FullTaxEquivalentBasis 淨利息費用後營收；不可與 GAAP 合併口徑混用。',
    'BRK-B': '採公司八分部／抵銷範圍，六季 48 筆相同（含 16 筆 Q4 推算）；缺兩季，無完整八季結論。',
    'PGR': '保險、投資及證券損益，可能重疊；富途七季，現有 revenue filter 不完整，未選標準答案。',
    'XOM': '分部 gross sales 與負抵銷；Q4 符號與合計異常待原報表裁決；先處理 successor CIK。',
    'CVX': '上下游 gross sales 需美國＋非美國加總；八筆運算相同、兩筆 Q4 缺運算元。',
    'CAT': '營運分部名稱與合併範圍改變；參考最新顯示季度不在凍結 SEC 基準，不能說來源落後。',
    'UPS': '營運分部及地區維度版本不同；參考最新季度不在基準，其他差異需範圍判讀。',
    'NEE': '採監管／非監管營運收入的分部口徑；23 筆指定範圍相同，1 筆僅有法人維度而棄權。',
    'LIN': '地理命名的營運分部與工程，不等同地區銷售；40 筆數字候選仍不是全表語意認證。',
    'PLD': '公司 IR 的租金、策略資本及其他三列優於缺漏的 vendor 入口作本輪參考；32 筆及八個合計相同。',
}


def main():
    private = ROOT / 'data/vendor/local'
    first = json.loads((private / 'cohort-20261104/private-report-verified.json').read_text())
    details = {c['ticker']: c['detail'] for c in first['private_details']
               if c['source'] == 'stockanalysis' and isinstance(c['detail'], dict)}
    exposure_files = {}
    for path in sorted((private / 'cohort-20261104').glob('batch*.json')):
        for capture in json.loads(path.read_text()):
            if capture.get('quarterly_confirmed'):
                exposure_files[capture['ticker']] = (path, {p['sec_date'] for p in details[capture['ticker']]['periods']})
    for relative in ('cohort-20261104/futu-observations.json', 'evidence-review-20261104/futu-second-round.json'):
        path = private / relative
        for capture in json.loads(path.read_text()):
            dates = {futu_fiscal_date(capture['ticker'], p['period']) for p in capture['captures']}
            exposure_files.setdefault(capture['ticker'], (path, dates))
    pld_path = private / 'evidence-review-20261104/pld-ir-review.json'
    exposure_files['PLD'] = (pld_path, {p['date'] for p in json.loads(pld_path.read_text())})
    roster = json.loads((ROOT / 'research/recovered-sec/eight_quarter_eval/roster.json').read_text())
    rows, splits = [], []
    frozen_paths = ['research/recovered-sec/extract.py', 'research/recovered-sec/eight_quarter_eval/run.py',
                    'scripts/compare_vendor_cohort.py', 'scripts/review_vendor_evidence.py']
    hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in frozen_paths}
    lines = ['# 逐公司日期與分類稽核', '',
             '每家公司均列入；日期來自公開 SEC 基準。日期完全相同也不保證分類定義正確。',
             '近日期／月份位移仍是建議，不能把數字命中率寫成準確率。完整原始數值及決策證據留在忽略的本機目錄。', '',
             '| 公司 | SEC 已有季度數 | 參考日期對照：相同／近日期建議／月份位移建議／無對照 | 分類與來源判斷 |',
             '| --- | ---: | --- | --- |']
    for company in roster:
        ticker = company['ticker']
        baseline = ROOT / 'research/sec-30-baseline-2026-11-04' / (ticker + '.json.gz')
        sec = json.loads(gzip.decompress(baseline.read_bytes()))
        dates = [q['report_date'] for q in sec['quarter_results']]
        periods = details.get(ticker, {}).get('periods', [])
        counts = Counter(p['alignment'] for p in periods)
        period_summary = '/'.join(str(counts[k]) for k in ('exact_date', 'nearby_date_proposal',
                                   'fiscal_label_shift_proposal', 'no_unique_nearby_period')) if periods else '見第二輪／富途／公司 IR'
        row = {'ticker': ticker, 'sec_quarter_dates': dates,
               'sec_baseline_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest(),
               'stockanalysis_period_alignment_counts': dict(counts),
               'classification_review': NOTES[ticker], 'cross_company_accuracy_measured': False}
        rows.append(row)
        lines.append(f'| {ticker} | {len(dates)} | {period_summary} | {NOTES[ticker]} |')
        exposure_unknown = ticker in ('LLY', 'PGR', 'XOM')
        evidence_path, evidence_dates = exposure_files[ticker]
        if not exposure_unknown and dates[0] not in evidence_dates:
            raise ValueError(f'Latest-period exposure lacks local evidence: {ticker}')
        exposure_evidence = {
            'path': str(evidence_path.relative_to(ROOT)),
            'sha256': hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            'scope': 'historical_reference_only_latest_exposure_unknown' if exposure_unknown else 'latest_baseline_period_used_in_diagnostics',
            'latest_period_mapping_is_semantically_certified': False,
        }
        splits.append({'ticker': ticker, 'historical_training_dates_proposed': dates[1:],
                       'latest_quarter_retrospective_test_date': dates[0] if dates else None,
                       'latest_quarter_exposure': 'exposure_unknown' if exposure_unknown else 'latest_baseline_quarter_used_in_local_reference_diagnostics',
                       'strict_blind_test': False,
                       'leakage_status': 'exposure_unknown_not_unseen' if exposure_unknown else 'latest_quarter_seen_before_rule_freeze',
                       'local_exposure_evidence': exposure_evidence,
                       'unseen_period_test_status': 'not_run_no_unseen_period_selected'})
    lines += ['', '## 逐季日期與狀態', '',
              '下表列的是 SEC 日期；無配對不直接歸責來源。CAT／UPS 有參考期比凍結基準新，LLY 有較舊參考期。',
              'Stock Analysis 的全部 22 家均已逐期核對日期字串及分類集合；除了 Apple 已另行覆核，其餘',
              '近日期和月份位移未經獨立財季證據確認，仍屬未判定。各季明細狀態另存 JSON。', '']
    for row in rows:
        ticker = row['ticker']
        ps = details.get(ticker, {}).get('periods', [])
        mapped = {p['sec_date']: p['alignment'] for p in ps if p['sec_date']}
        row['sec_quarter_alignment_review'] = [{'sec_date': date, 'stockanalysis_status': mapped.get(date, 'no_proposed_match')}
                                              for date in row['sec_quarter_dates']]
        lines.append(f"- **{ticker}**：" + '、'.join(row['sec_quarter_dates']) + '。')
    (ROOT / 'docs/vendor/company-audit.md').write_text('\n'.join(lines) + '\n')
    (ROOT / 'docs/vendor/company-audit.json').write_text(json.dumps({'companies': rows}, ensure_ascii=False, indent=2) + '\n')
    (ROOT / 'docs/vendor/training-test-split.json').write_text(json.dumps({
        'study_mode': 'retrospective_with_known_leakage', 'frozen_rule_sha256': hashes,
        'official_evaluation_protocol': 'docs/TEMPORAL_EVALUATION.md',
        'this_snapshot_is_not_a_temporal_eval_freeze_receipt': True,
        'frozen_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'latest_quarter_used_for_independent_generalization_claim': False,
        'annual_and_quarterly_formats_require_separate_checks': True,
        'q4_annual_minus_nine_months_requires_same_scope_and_recast_review': True,
        'companies': splits}, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
