# 歷史訓練、規則凍結與保留季度評估

使用者指定的方法是：先用歷史季度及年報建立規則，再凍結規則，最後與最新季度的參考資料比較。TradingView、富途及 Stock Analysis 都可能有錯，不能預設其中一家是正確答案。逐家公司回查 SEC 原始揭露，判斷期間、產品／部門／地理分類、對外／部門間銷售與重編口徑，再記錄選擇及不確定性。

入口為 [`scripts/temporal_eval.py`](../scripts/temporal_eval.py)。本次新增獨立的評估層，沒有修改復原 parser、既有 234 季基準或 `docs/vendor/`。

## 已執行與未完成的範圍

- [`cohort-plans.json`](../research/temporal-evaluation/cohort-plans.json) 保存 30 家公司各自的 cutoff、歷史 training 與最新 holdout accession、期間、表單、來源 URL、原始 HTML 雜湊、基準檔雜湊，以及三家參考來源的接觸紀錄。cutoff 同時檢查申報可用日期與財報期末，不使用統一的日曆季度推測公司財年。
- 這是既有資料的**回溯時間切分**。Apple 最新季度已經查看與核對，標記 `contaminated`；另外 29 家的開發接觸紀錄不完整，標記 `exposure_unknown`。目前真正保留測試數為 **0**，不能將未知改稱未見。各 plan 的 `rule_version: null` 表示尚未逐公司凍結；實際規則版本存於各次 freeze receipt。
- Apple 有可直接重播的 [`apple-freeze.json`](../research/temporal-evaluation/apple-freeze.json) 及 [`apple-replay.json`](../research/temporal-evaluation/apple-replay.json)。這次只是合併營收候選概念的示範，Q4 為 114,477,000,000 USD，FY 為 478,834,000,000 USD；原始 facts 與 Q4 兩個運算元均保留。**沒有新增供應商比對、產品組成的人工答案或準確率。**
- 30 家 training pack 均可建立。NEE 歷史申報中有 10 個延伸至 2029 年的費率相關候選 facts，被訓練期間檢查排除；每筆保留原始 fact 索引、ID、SHA-256 與排除原因，原值仍在原基準檔中。

## 隔離與資料角色

`pack` 只讀 plan 列明的歷史 accession。整份較新 10-K／10-Q 都排除，包含其中的往年比較欄、重編值、表格文字及解析錯誤，因此不會因比較欄看起來是歷史日期而加入 training。訓練檔內期間超過 cutoff 的 facts 也會排除；排除登錄不攜帶其數值。原始基準檔保持不變，可按索引與雜湊回查。不要直接拿整包 baseline 或原有 vendor comparison 輸出當成訓練輸入：它們含 holdout 資料。

凍結前，歷史供應商參考應另外依 ticker、**實際期間起訖**及 Q／FY 檢查後用於開發；此入口不會自動匯入、切割或校準供應商檔，也不會自動學習規則。其 training pack 不包含任何供應商數值或人工答案。供應商的歷史檔若同時含最新季度，必須先隔離最新欄；若開發者已看到，須更新接觸紀錄，無法事後恢復為盲測。

數值與證據分成以下角色：

| 角色 | 本入口如何處理 |
| --- | --- |
| parser observations | 原始 SEC facts 與來源、context、維度、單位、期間、原值、scale、decimals、表格資訊保留；不是裁決後答案 |
| frozen selectors | 以 concept、完整 dimensions、unit 精確選取；Q 與 FY 分開；不按供應商數值反查候選 |
| vendor reference | 各來源獨立比較；不以多數決或資料量決定正確性 |
| SEC／人工裁決 | 分別標為 `sec_adjudication`／`human_adjudication`，保留原始證據、裁決理由與不確定性；不回寫 parser facts |
| missing / zero | `null` 是缺值；數字 `0` 仍是數值。另分 parser 缺值、衝突、參考缺值、語意／單位／期間不一致 |

每個 selector 的 `semantic_basis` 是明確的口徑識別字串，需由研究者以證據定義與審查，程式不會自行證明其語意。不同口徑即使數字一樣也不記為 numeric match。plan 的 `adjudication` 預留 `preferred_reference`、`status`、`rationale`、`evidence`、`uncertainty`；本次全部為 unresolved，沒有假造逐公司選擇。若裁決看過 holdout，必須將整體 `exposure.seen_during_development` 設為 `yes`，另開下一期實驗。

## 凍結與重播

以下命令由 repo 根目錄執行，輸出採建立新檔，拒絕覆寫。Python 3.12、`lxml==6.1.1` 與既有基準即可，全程離線，不需要 SEC 請求。

```sh
python3 scripts/temporal_eval.py seed --out /tmp/cohort-plans-new.json
python3 scripts/temporal_eval.py pack \
  --plan research/temporal-evaluation/apple-plan.json \
  --out /tmp/apple-training.json
python3 scripts/temporal_eval.py freeze \
  --plan research/temporal-evaluation/apple-plan.json \
  --rules research/temporal-evaluation/apple-candidate-rules.json \
  --out /tmp/apple-freeze-new.json
python3 scripts/temporal_eval.py replay \
  --freeze research/temporal-evaluation/apple-freeze.json \
  --out /tmp/apple-replay-new.json
```

plan 來源需符合 baseline 中的 ticker／CIK、accession、日期、URL 及 SHA-256。規則必須有版本及 selectors。freeze 保存整份 plan、規則、訓練包及三個執行程式的 SHA-256。修改程式、規則或訓練資料後，舊 receipt 會拒絕重播；請切回該實驗的 Git commit，或建立新版本與新實驗。freeze 本身只證明保存的設定可核對，不證明人員未見資料，也不是防竄改或獨立時間戳記服務。

重播使用 baseline 的 `raw_filings`，**不是重新解析 HTML**，也不使用已存的 `quarter_results`。Q4 只從當期年報及 training 中九個月資料推算，保留兩個 operand；全年 facts 另作 FY 候選，不能流入 Q selector。延用既有 runner 的天數、維度及單位相容檢查；原 parser 尚未完整保存 entity／會計基礎等資訊，因此還無法證明跨申報重編語意相容。缺 operand 時回報 missing，候選重複衝突時回報 ambiguous，不補零、不猜答案。

## 參考資料介面

比較時使用 JSON 陣列，每筆須有：

- `ticker`、`selector_id`、`period_kind`（`Q` 或 `FY`）、`period_start`、`period_end`、`unit`、`semantic_basis`。
- `value`：已正規化至指定單位的數值字串／數字或 `null`；`absolute_tolerance`：根據原畫面精度保留的非負容許差額，不能為了配對放寬。
- `source_kind`（`vendor`／`sec_adjudication`／`human_adjudication`）、`source`（vendor 僅允許 `tradingview`／`futu`／`stockanalysis`）。
- `evidence`：實際保存的本機原始證據路徑、`sha256`：該檔 SHA-256、`url`：原始來源。程式會讀取證據核對雜湊，缺檔或不符則拒絕；裁決原因等其他欄位亦原樣保存。
- `first_seen_at`：含時區的首次查看時間，`used_for_rule_development`：明確布林值。已用於開發或凍結前看過的參考資料會使測試標為 contaminated。

受限制的供應商證據與詳細比較輸出請保留在既有忽略路徑 `data/vendor/local/`，不要提交 Git。此文件不提供虛構的公司數值作為範例。

```sh
python3 scripts/temporal_eval.py compare \
  --freeze /tmp/company-freeze.json \
  --references data/vendor/local/company-holdout-references.json \
  --out data/vendor/local/company-holdout-comparison.json
```

`compare` 會先驗證並重新執行 frozen replay，不接收手填 prediction。逐筆輸出原 reference、數字比對結果；不把不同來源混成 accuracy 的分母，也不替公司決定 preferred source。只有整體及三家 holdout 來源都明確記錄未見、有佐證，且至少一筆完成相同期間／單位／語意的數值比較，才會令 `genuine_holdout_by_recorded_attestations` 為 true。這依賴接觸紀錄的真實性；來源缺少或接觸未知時，維持未知。

下一次真正保留測試需在查看未來季度財報、供應商季度答案或人工裁決前，以歷史資料完成規則並保存 receipt。未來季度公布後，可用 `attach` 接合已知的新 accession：

```sh
python3 scripts/temporal_eval.py attach \
  --freeze /tmp/preregistered-freeze.json \
  --plan /tmp/future-quarter-plan.json \
  --baseline /tmp/new-sec-baseline \
  --out /tmp/future-quarter-bound-freeze.json
```

新 baseline 需保留原 training 的 facts；新 plan 可從 `seed --baseline` 開始整理，但必須將 training 與 cutoff 維持為原登記內容。新 holdout 的申報日期須嚴格晚於原凍結日、期末晚於原 target；綁定時核對訓練包、程式與規則雜湊，保留完整原 receipt 及原 `frozen_at`，另記 `bound_at`。接觸紀錄針對**新的 holdout**重新記錄，不能沿用過去的未見宣告。這允許目前已洩漏的季度作為開發背景、未來季度另作保留測試；本次沒有不存在的未來 accession 或未見宣告。若要加入較新的 training 季度或改規則，應先開新的 freeze，再等另一個未見季度。現有基準無法補做真正盲測。

## 驗證

```sh
python3 scripts/verify_recovered.py
```

新增 14 項時間切分測試；連同既有測試共 38 項通過，並檢查復原程式雜湊未變。涵蓋 accession 隔離、年報比較欄、未來期間、Q4／FY、來源證據、規則／程式／訓練資料變更、缺值與零、候選衝突、跨口徑及洩漏狀態。實際執行證據見 [`verification.json`](../research/temporal-evaluation/verification.json)。
