# NEE parser

## 觀點

業務分部（`view="business_segment"`），採用富途的分類順序：FPL、NEER、Corporate and Other。沒有調節項，總營收為 Total consolidated revenues。

| 輸出名稱 | 富途名稱 | TradingView 名稱 |
|---|---|---|
| FPL | Florida Power & Light Company (FPL) | Florida Power & Light |
| NEER | NextEra Energy Resources (NEER) | NextEra Energy Resources |
| Corporate and Other | 公司和其他 | Corporate and Other |

FPL、NEER 取自 SEC 分部表的欄標題；Corporate and Other 在 2024 年 Q1–Q3 10-Q 的分部表是欄，FY2024 10-K 起是列。總營收名稱取自 FY2024 10-K 起分部表的 Total consolidated revenues 列，較早的分部表是 NEE Consolidated 欄。富途與 TradingView 都拆分到此業務觀點，且 Corporate and Other 在範圍內有實際數值，因此列為分類。SEC 將它列於分部合計與合併營收之間，不另拆出 Eliminations。

`us-gaap:StatementBusinessSegmentsAxis` 的成員是業務別，不是地區。NEER 是能源資源業務，FPL 是電力公用事業；公司 parser 只使用此軸的 NEER 成員。TradingView 另列 Gulf Power（2019–2021 年有值），在處理範圍以前。現有對照資料沒有 Stock Analysis。

## 分類與 tag

分類與總營收的 concept 都是 `us-gaap:RegulatedAndUnregulatedOperatingRevenue`。下表列出完整 dimensions，未列的維度不加入查找：

| 項目 | 完整 dimensions |
|---|---|
| FPL | `dei:LegalEntityAxis=nee:FloridaPowerLightCompanyMember` |
| NEER | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；`us-gaap:StatementBusinessSegmentsAxis=nee:NEERSegmentMember` |
| Corporate and Other | `srt:ConsolidationItemsAxis=nee:CorporateAndEliminationsMember` |
| Total consolidated revenues | 無維度 |

每項都是一個權重為 1 的 fact，沒有以總營收扣除分部倒算的分類。總營收取合併 fact，不能取只帶 `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember` 的兩個應報導分部合計。

### FPL 法律實體與分部的對應

這些申報是 NEE 與 Florida Power & Light Company 的合併申報文件，包含 NEE 合併損益表、FPL 自己的損益表與分部附註。FPL 損益表的 Operating revenues 使用單一法律實體維度，分部表的 FPL 欄同列也呈現相同營收：

- FY2023 10-K（`0000753308-24-000008`，期末 2023-12-31）：FPL 的年度 Operating revenues 在分部表 t89 直接使用法律實體 fact，與 FPL 損益表 t41 相同。
- 2024 Q1 10-Q（`0000753308-24-000023`，期末 2024-03-31）：分部表 t46 的 FPL 欄直接使用法律實體 fact，與 FPL 損益表 t13 相同。
- 後續分部表的 FPL 欄雖有不同的維度組合，其同一份申報、同一期間的數值仍與法律實體 fact 相同。此對應按每份申報本身確認，不以較晚申報補早期數字。

不採用分部軸 FPL fact，是因為相同分部在申報與期間間有不同標記，沒有單一穩定的分部維度組合：

| 原文例子 | FPL 分部表 fact 的完整 dimensions |
|---|---|
| 2024 Q2、Q3 10-Q，accession `0000753308-24-000050`、`0000753308-24-000057` | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；`us-gaap:StatementBusinessSegmentsAxis=nee:FPLSegmentMember` |
| FY2024 10-K，accession `0000753308-25-000011` | `dei:LegalEntityAxis=nee:FloridaPowerLightCompanyMember`；`srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；`us-gaap:StatementBusinessSegmentsAxis=nee:FloridaPowerLightCompanyMember` |
| 2025 Q3 10-Q，accession `0000753308-25-000056`，單季 | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；`us-gaap:StatementBusinessSegmentsAxis=nee:FloridaPowerLightCompanyMember` |
| 同一份 2025 Q3 10-Q，九個月累計 | `dei:LegalEntityAxis=nee:FloridaPowerLightCompanyMember`；`srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；`us-gaap:StatementBusinessSegmentsAxis=nee:FloridaPowerLightCompanyMember` |

法律實體 fact 在上述申報的單季、累計與年度都有相同口徑，故 parser 固定選用它，不隨分部標記改名切換，也不把額外維度視為可以忽略的維度。法律實體營收與分部 FPL 不同時，三類加總不等於合併總營收，該期在加總檢核失敗。

## 期別與推算

- 財年為曆年，12 月 31 日結束；季末為 3 月 31 日、6 月 30 日、9 月 30 日與 12 月 31 日。財年與季次取自申報的 DEI 宣告，富途期別按這些宣告對齊。
- Q1–Q3 取該季原 10-Q 的單季 fact。FY 取原 10-K 的年度 fact。
- Q4 由框架以同財年 10-K 年度減去 Q3 原 10-Q 九個月累計，依既有分類集合與口徑一致規則決定是否推算。parser 不另補 Q4。
- FY2024 10-K 列示的 FY2023 三類與總營收，和 FY2023 原 10-K 相同；FY2025 10-K 列示的 FY2024 也和 FY2024 原 10-K 相同。這兩個 Q4 的分類集合與上一財年口徑皆一致，沒有因這兩項條件而不推算的期別。
- 正式處理範圍從期末日 2024-01-01 起，目前申報到 2026 Q3。`categories(day)` 的涵蓋下限是 2023-12-31，包含第一個範圍內 Q4 所需的 FY2023 口徑依據；此日期以前的回答不保證正確。
- 已下載最早的 2023 Q1 10-Q（`0000753308-23-000033`，期末 2023-03-31）已呈現 FPL、NEER、Corporate and Other 三類；不推斷它是歷史上首次採用此結構的申報。範圍內三類固定，parser 沒有日期或申報切換。

## 數字在原文的位置

FPL 取 FPL 損益表的 Operating revenues；分部表也以相同法律實體 scope 標記時，框架可依重複 fact 規則選用分部表。NEER 與 Corporate and Other 取分部附註中的營收，合併總營收取分部表或 NEE 損益表的無維度 fact。

正式輸出運算元的證據表格如下。t 編號對應 `data/revenue/N/NEE/<序列>/<期末日>/evidence/` 中檔名結尾的 `-t<編號>.html` 與 `-t<編號>.png`；檔名前段為 accession 與原文 SHA-256 的前 12 碼。FPL 損益表以外的營收均在分部附註表。

| 申報期末日 | accession | FPL | NEER、Corporate and Other、合併總營收 |
|---|---|---|---|
| 2024-03-31 | `0000753308-24-000023` | t46，分部表 | t46，單季 |
| 2024-06-30 | `0000753308-24-000050` | t13，FPL 損益表 | t45，單季 |
| 2024-09-30 | `0000753308-24-000057` | t13，FPL 損益表，單季與九個月累計 | t45，單季；t46，九個月累計 |
| 2024-12-31 | `0000753308-25-000011` | t40，FPL 損益表 | t89，年度 |
| 2025-03-31 | `0000753308-25-000024` | t13，FPL 損益表 | t45，單季 |
| 2025-06-30 | `0000753308-25-000040` | t13，FPL 損益表 | t46，單季 |
| 2025-09-30 | `0000753308-25-000056` | t13，FPL 損益表，單季與九個月累計 | t46，單季；t47，九個月累計 |
| 2025-12-31 | `0000753308-26-000015` | t39，FPL 損益表 | t90，年度 |
| 2026-03-31 | `0000753308-26-000031` | t13，FPL 損益表 | t48，單季 |
| 2026-06-30 | `0000753308-26-000060` | t13，FPL 損益表 | t47，單季 |
| 2026-09-30 | `0000753308-26-000081` | t13，FPL 損益表 | t47，單季 |

分部附註的單季與九個月累計分成不同表格段落：2024 Q3 的 t45 是單季、t46 是九個月累計；2025 Q3 的 t46 是單季、t47 是九個月累計。每段均包含 NEER、Corporate and Other 與合併總營收。這兩份申報的 FPL 證據則都在損益表 t13，同一張表列出單季與九個月累計。

2024、2025 年 Q4 的年度運算元與同年 FY 相同，九個月運算元分別使用同年 Q3 申報的上述累計段落。2026 Q3 的正式輸出只有單季運算元，分部證據為 t47，不使用九個月累計段落。

FY2024 起的新版分部表中，Total 小計只含 FPL 與 NEER，合併總營收取加上 Corporate and Other 後的 Total consolidated revenues。較早的分部表則在 Operating revenues 同一列，以 NEE Consolidated 欄列出合併總營收。

FY2023 10-K 的 t89 為第一個範圍內 Q4 的上一財年口徑依據，並非範圍內正式輸出的證據檔。

## 已知的重複 fact

無維度總營收在 NEE 損益表與分部表重複；部分申報的 FPL 法律實體營收同時出現在 FPL 損益表與分部表。相同 concept、完整 dimensions、期間的重複值由框架核對精度與數值，再選用所在表格包含最多其他運算元的 fact。分部 fact 若另帶維度，不屬於同 scope 的重複 fact，parser 不把它們合併為同一個運算元。

## 驗證

`data/revenue/N/NEE/status.json` 的季度序列有 11 期、年度序列有 2 期，全部為 `published`，沒有 `failed` 或 `not_derived` 的期別。

對照來源為 `data/universe/references/N/NEE/reference.json` 的富途資料，期別按各期 `revenue.json` 的 `fiscal_year` 與 `fiscal_quarter` 對齊。下表金額為百萬美元，取自正式輸出；各期三類與富途 `usd` 均精確相等，共 33 筆，沒有超出顯示精度的差異。

| 財年／季別 | 期末日 | FPL | NEER | Corporate and Other | 與富途比對 |
|---|---|---:|---:|---:|---|
| 2024 Q1 | 2024-03-31 | 3,834 | 1,864 | 33 | 三類均精確一致 |
| 2024 Q2 | 2024-06-30 | 4,389 | 1,645 | 35 | 三類均精確一致 |
| 2024 Q3 | 2024-09-30 | 4,939 | 2,585 | 43 | 三類均精確一致 |
| 2024 Q4 | 2024-12-31 | 3,856 | 1,448 | 81 | 三類均精確一致 |
| 2025 Q1 | 2025-03-31 | 3,997 | 2,163 | 87 | 三類均精確一致 |
| 2025 Q2 | 2025-06-30 | 4,708 | 1,914 | 78 | 三類均精確一致 |
| 2025 Q3 | 2025-09-30 | 5,285 | 2,566 | 115 | 三類均精確一致 |
| 2025 Q4 | 2025-12-31 | 4,273 | 2,117 | 110 | 三類均精確一致 |
| 2026 Q1 | 2026-03-31 | 4,271 | 2,311 | 119 | 三類均精確一致 |
| 2026 Q2 | 2026-06-30 | 4,896 | 2,532 | 106 | 三類均精確一致 |
| 2026 Q3 | 2026-09-30 | 5,421 | 2,516 | 153 | 三類均精確一致 |

未比對的期別與來源：

- FY2024、FY2025：富途現有資料只有季度，沒有年度對照值；正式 FY 數值與同年 Q4 的年度運算元相同。
- 富途的 2022 Q4 至 2023 Q4：期末日在正式處理範圍以前，不列入逐期比對。FY2023 只作 Q4 口徑依據，沒有範圍內正式輸出。
- TradingView 不是採用來源，不列入逐期比對。

## 比較欄

已下載的 10-Q 與 10-K 中，列示且可對齊正式輸出的比較期，包括去年同季、去年九個月累計及去年全年，均沒有超出精度的差異。Q4 的年度與九個月累計運算元分開比對，FY 比對年度運算元。

`data/revenue/N/NEE/status.json` 的 11 個季度與 2 個年度均沒有 `differences` 差異標記，也沒有 `comparison_errors`。
