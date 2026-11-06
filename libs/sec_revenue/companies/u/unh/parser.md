# UNH parser

## 觀點

營運分部（`view="business_segment"`），共 5 類加 1 個調節項：
- 分類：UnitedHealthcare、Optum Health、Optum Insight、Optum Rx、Corporate and eliminations。
- 調節項：Optum eliminations。

| 對照來源 | 列出的分類 | 口徑 |
|---|---|---|
| 富途 | 四個分部、Optum 抵銷、公司和抵銷 | 分部總營收（含分部間營收） |
| Stock Analysis | UnitedHealthcare、Optum（Optum 三個分部合計）、Eliminations | 分部總營收 |
| TradingView | 四個分部 | 對外營收（不含分部間營收），沒有抵銷項 |

兩個來源用分部總營收，所以採用這個口徑：
- 分部的數字含分部間營收。UNH 的 Optum 有大量營收來自 UnitedHealthcare，所以抵銷項很大。
- Corporate and eliminations 有兩個來源列出（富途的「公司和抵銷」、Stock Analysis 的 Eliminations），列成分類。
- Optum eliminations 只有富途列出，宣告為 `reconciling`，參與加總但不輸出成分類。Stock Analysis 的 Optum 是扣除這一項後的合計。

分部取自 `us-gaap:StatementBusinessSegmentsAxis`。UNH 這個軸的成員是業務別：健康保險（UnitedHealthcare）、醫療服務（Optum Health）、資訊與科技服務（Optum Insight）、藥品福利管理（Optum Rx）。它們不是地區，所以採用。

## 分類與 tag

concept 是 `us-gaap:Revenues`。

| 分類 | 維度 |
|---|---|
| UnitedHealthcare | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`＋分部 `unh:UnitedhealthcareMember` |
| Optum Health | 同上，分部 `one_of`：`unh:OptumHealthMember`（10-Q）、`unh:OptumhealthMember`（10-K） |
| Optum Insight | 同上，分部 `one_of`：`unh:OptumInsightMember`、`unh:OptuminsightMember` |
| Optum Rx | 同上，分部 `one_of`：`unh:OptumRxMember`、`unh:OptumrxMember` |
| Corporate and eliminations | `srt:ConsolidationItemsAxis=us-gaap:CorporateNonSegmentMember` |
| Optum eliminations（調節項） | `srt:ConsolidationItemsAxis=us-gaap:IntersegmentEliminationMember` |
| 總營收（Consolidated） | 不帶維度 |

- Optum 三個分部的成員在 10-Q 與 10-K 之間只差大小寫，數字是分部表的同一列，所以以 `one_of` 列出兩種寫法。
- 分部 fact 另有帶 `srt:MajorCustomersAxis`（對外／分部間）的拆分，規格用不帶這個軸的合計。
- 五類加上 Optum eliminations 等於總營收。
- 分類名稱取自分部表的欄名；總營收取自同表的 `Consolidated` 欄、`Total revenues` 列。

## 期別與推算

- 財年即曆年，季末日是 3、6、9、12 月的最後一天。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同年 Q3 10-Q 的九個月累計，前提是年度與 Q1–Q3 的分類相同，且口徑沒有改變。
- FY：10-K 的年度 fact。

## 數字在原文的位置

附註分部表：UnitedHealthcare、Optum 三個分部、Optum Eliminations、Optum 合計、Corporate and Eliminations 與 Consolidated 分欄，數字在 `Total revenues` 列。Q1–Q3 與 FY 每期一張表；Q4 為 10-K 與 Q3 10-Q 各一張。

## 2026 年的分部重列

2026 年各 10-Q 把一部分 Optum Health 的業務改列 Optum Insight，並重列 2025 年的比較數字（單位百萬美元）：

| 期別 | 運算元 | Optum Health | Optum Insight | Optum eliminations | 來源申報 |
|---|---|---|---|---|---|
| 2025-03-31 | 單季 | 25,309 → 24,837 | 4,630 → 5,027 | −1,186 → −1,111 | 2026 年 Q1 10-Q |
| 2025-06-30 | 單季 | 25,205 → 24,725 | 4,828 → 5,232 | −1,267 → −1,191 | 2026 年 Q2 10-Q |
| 2025-09-30 | 單季 | 25,900 → 25,422 | 4,915 → 5,320 | −1,317 → −1,244 | 2026 年 Q3 10-Q |
| 2025-12-31 | 九個月 | 76,414 → 74,984 | 14,373 → 15,579 | −3,770 → −3,546 | 2026 年 Q3 10-Q |

- UnitedHealthcare、Optum Rx、Corporate and eliminations 與總營收不變。
- 2025 年 Q4：年度與九個月都是重列前的呈現，照常推算。
- 2026 年各季是新歸類，與 2025 年各季不能直接比較。
- 以上都寫成差異標記。

## 驗證

11 季（2024-03-31 至 2026-09-30）與 2 個年度，與對照資料逐期比對：

| 來源 | 結果 |
|---|---|
| Stock Analysis | 各季 UnitedHealthcare 與 Eliminations 在顯示精度內（Optum 是三個分部與 Optum eliminations 的合計） |
| 富途 | 各季相同，2025 年 Q1 除外：富途用了 2026 年 Q1 10-Q 重列後的數字（與差異標記的申報列示值相同） |
| TradingView（只有年度） | UnitedHealthcare 相同；Optum 三個分部是對外營收，口徑不同，不比對 |

- FY 序列：FY2024、FY2025 都等於同財年四季加總。
