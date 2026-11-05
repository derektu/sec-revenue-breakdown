# 先前研究階段總覽

本文件描述先前研究階段的程式、操作方式與結果。這些內容尚未依 [#36](https://github.com/derektu/sec-revenue-breakdown/issues/36) 的流程驗證，僅供參考；目前的規劃見 [README](../../README.md)。

從 SEC 申報文件擷取美股公司每季的 by segment 營收拆分，目標範圍是 S&P 500、400、600。每家公司有自己的 parser，以對照資料驗證，正確率夠高、格式穩定才上線。目前涵蓋三十家公司。

## 原則

完整約束見 [`AGENTS.md`](../../AGENTS.md)，重點如下：

- **數字只來自 SEC**：營收的擷取與計算只用 SEC 申報（10-K、10-Q、8-K 附件）。Stock Analysis、富途、TradingView、公司 IR 是對照資料，用來比對與選擇分類觀點，不能取代 SEC 數字。
- **輸出可追溯**：每筆輸出保留 SEC 文件 URL、期間、單位、完整分類 scope、所有運算元與來源 hash。
- **不補值**：缺值、歧義或解析失敗時輸出 null 與原因，不當作零，也不拿參考資料補。
- **公司互相隔離**：每家公司的規則在自己的資料夾，新增或修改一家公司不影響其他公司。

## 目錄

| 路徑 | 內容 |
|---|---|
| `libs/sec_revenue/` | 正式引擎：下載、XBRL 解析、季度推算、規則比對、萃取流程、viewer |
| `libs/sec_revenue/parsers/` | 公司 parser 共用的 `IssuerParser` 基底與表格來源支援 |
| `libs/sec_revenue/issuers/<首字母>/<ticker>/` | 每家公司一個資料夾：`parser.py` 是公司規則，需解析 HTML 表格的公司另有 `tables.py` |
| `libs/sec_revenue/registry.json` | 支援的公司：parser 位置、CIK、主要 basis、歷史重播期別與參考來源 metadata |
| `scripts/sec_pipeline.py` | 日常入口：`tickers`、`download`、`extract`、`viewer` |
| `scripts/replay_sec.py`、`scripts/check_engine_regression.py` | 三十家、240 季的凍結回歸 |
| `scripts/`（其他） | 歷史研究各輪的實驗程式，保留供重現，不再修改 |
| `tests/` | 引擎與工作流程測試（`test_sec_engine.py`、`test_sec_workflow.py`），以及歷史研究腳本的測試 |
| `research/` | 各輪研究的結果、來源 hash 與凍結基準，例如 `sec-30-baseline-2026-11-04/` |
| `docs/` | 架構說明與研究結論 |
| `data/` | 本機產物：SEC 原文快取、萃取輸出、工作流程索引。除了明確列入追蹤的子目錄之外，都被 Git 忽略 |

## 環境

需要 Python 3.11 以上。依賴裝在 repo 根目錄的 `.venv`：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## 日常操作

下載、萃取、viewer 三個階段可以分開執行。完整參數、快取行為與回傳碼見 [本機分階段操作](../architecture/local-workflow.md)。

```bash
# 列出支援的 ticker，可另存成自己的子集合（tickers.local.* 不進 Git）
.venv/bin/python scripts/sec_pipeline.py tickers > tickers.local.txt

# 下載 SEC 原文。連網時需設定 SEC_USER_AGENT（真實姓名或組織，加上聯絡 email）
.venv/bin/python scripts/sec_pipeline.py download --ticker-file tickers.local.txt --start 2025-01-01 --latest

# 從下載快取萃取營收，不連網
.venv/bin/python scripts/sec_pipeline.py extract --ticker-file tickers.local.txt --start 2025-01-01

# 本機 viewer
.venv/bin/python scripts/sec_pipeline.py viewer --port 8765
```

- **download**：依 SEC 實際 `reportDate` 選期別。年報會自動加上前一季 10-Q，供 Q4 推算。已下載且 hash 正確的檔案直接沿用；`--force` 重抓，`--offline` 只用本機快取。
- **extract**：來源 hash 與規則指紋都沒變時跳過（`cache_hit`），`--force` 強制重算。
- **viewer**：唯讀，只讀 `data/outputs/` 的萃取結果。

產物位置：

| 路徑 | 內容 |
|---|---|
| `data/sec/TICKER/PERIOD/ACCESSION/HASH.html` | SEC 原始 HTML 與 hash 收據 |
| `data/pipeline/TICKER/{catalog,downloads,extractions}.json` | 申報清單、下載紀錄、萃取紀錄 |
| `data/outputs/TICKER/PERIOD/TICKER_PERIOD_BASIS_revenue.json` | 萃取結果：期間、會計年度與季度、USD、完整 scope、運算元、申報精度、風險 |

## 程式架構

| 模組 | 職責 |
|---|---|
| `engines.py` | `XbrlEngine` 從 inline XBRL 讀出 facts。`QuarterEngine` 篩出季度 fact，沒有單季 Q4 時以「年度減九個月累計」推算，並保留兩個運算元。`SelectionEngine` 依規則精確比對 concept、dimensions、unit。`PrecisionAnalyzer` 與 `RevenueReconciliation` 依申報精度計算誤差上限並對帳 |
| `workflow.py` | SEC 申報清單、下載與萃取流程，以及快取 |
| `service.py` | `ParserRegistry` 載入公司 parser；`ReplayService` 做歷史重播；`RiskAnalyzer` 計算 parser 維護風險 |
| `viewer.py`、`viewer.html` | 唯讀的本機 viewer |

公司規則寫在 `IssuerParser` 子類別裡：
- `rules` 以精確的 concept、完整 dimensions、unit 定義每個分類；
- `aliases` 處理有日期範圍的 tag 變動；
- 需要時覆寫 `categories`（依期間切換分部）、`pool`（額外的比較欄）或 `download_dependencies`。

萃取快取的規則指紋涵蓋共用引擎與該公司資料夾內的所有程式，所以修改一家公司只會讓那家公司重算。

**新增公司**：
1. 建立 `libs/sec_revenue/issuers/<首字母>/<ticker>/parser.py`，在其中定義 `IssuerParser` 子類別；
2. 在 `registry.json` 登記 module（資料夾名稱）、class、CIK、主要 basis；
3. 不修改共用引擎或其他公司的 parser。

## 測試與回歸

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/check_engine_regression.py
```

- `check_engine_regression.py` 用 `research/sec-30-baseline-2026-11-04/` 的凍結 SEC facts 重播三十家公司，並比對凍結答案。
- 單獨重播可以用 `scripts/replay_sec.py AAPL --out data/engine-check`。輸出放在 `data/engine-check`，跟 `sec_pipeline.py` 的 `data/outputs` 分開。

## 目前狀態

- 三十家公司各八季的指定欄位都有 SEC 輸出。
- 跨來源逐期裁決的成績是 **29 / 30 OK**；固定單一供應商（Stock Analysis）的基準是 **24 / 30**，兩者分開列示。見 [逐公司結論](../vendor/historical-rule-study.md) 與 [SEC 來源規則](../vendor/sec-primary-source-policy.md)。
- 這些季度都已經接觸過，屬於回溯驗證，不是盲測，也不代表完整披露的召回率。
- 擴展到 1,500 家的限制見 [可行性總結](../vendor/feasibility-conclusion.md)。

以對照資料驅動的逐家上線流程，規劃在 [#36](https://github.com/derektu/sec-revenue-breakdown/issues/36)。

## 文件索引

**架構**
- [本機分階段操作](../architecture/local-workflow.md)
- [引擎資料契約](../architecture/sec-engine.md)
- [引擎驗證紀錄](../architecture/cloud-engine-verification.md)

**三十家公司結論**
- [逐公司歷史規則與回溯驗證](../vendor/historical-rule-study.md)
- [可行性總結](../vendor/feasibility-conclusion.md)、[逐公司盤點](../vendor/feasibility-inventory.md)
- [三十家雲端基準與重現](../SEC_30_BASELINE.md)
- 逐公司 SEC 結果：[company_summary.csv](../../research/sec-30-baseline-2026-11-04/company_summary.csv)、[quarter_summary.csv](../../research/sec-30-baseline-2026-11-04/quarter_summary.csv)

**來源與裁決**
- [SEC 來源規則](../vendor/sec-primary-source-policy.md)
- [跨來源裁決](../vendor/cross-source-adjudication.md)
- [第二輪來源裁決與測試切分](../vendor/evidence-review.md)
- [三十家日期與分類稽核](../vendor/company-audit.md)
- [WMT 與 NEE 範圍缺口](../vendor/scope-gap-review.md)
- [參考來源入口](../vendor/README.md)

**方法研究**
- [時間切分評估](../TEMPORAL_EVALUATION.md)
- [原始財報共用解析](../SHARED_RAW_SEMANTICS.md)
- [Q／FY taxonomy 版本橋接](../TAXONOMY_BRIDGE.md)

**歷史交接**
- [研究需求](../RESEARCH_PLAN.md)
- [雲端狀態與限制](../CLOUD_HANDOFF.md)、[雲端重構交接](../CLOUD_REFACTOR_HANDOFF.md)、[雲端整合審查](../RECOVERED_INTEGRATION.md)
- [還原程式入口](../../research/recovered-sec/HANDOFF.md)、[封存來源登錄](../../research/sources.json)

封存檔匯入與完整性檢查使用 `scripts/stage_archive.py` 與 `scripts/verify_recovered.py`，用法見 [雲端整合審查](../RECOVERED_INTEGRATION.md)。
