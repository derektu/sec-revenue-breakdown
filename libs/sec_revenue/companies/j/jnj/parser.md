# JNJ parser

## 觀點

業務分部（`view="business_segment"`），採用富途的分類順序：Innovative Medicine、MedTech。期別依申報宣告的財年與季別對齊富途，不以曆季末日取代 SEC context 的實際期末日。沒有調節項。

| 對照來源 | 分類與對應 |
|---|---|
| 富途 | Innovative Medicine、MedTech，與 SEC 名稱及順序相同 |
| Stock Analysis | Pharmaceutical 對應 Innovative Medicine；Medtech 對應 MedTech。Consumer Health 只有 2023 年 Q2 及更早季度有值 |
| TradingView | Innovative Medicine、MedTech；Consumer 只有 2022 年及更早年度有值 |

`us-gaap:StatementBusinessSegmentsAxis` 的成員是業務別。Innovative Medicine 是藥品業務，MedTech 是醫療科技業務，不是地區。名稱取自申報「Analysis of sales by business segments」的分部標題；總營收名稱取自合併損益表的 `Sales to customers` 列。

申報另有 `srt:StatementGeographicalAxis` 地區拆分，以及各分部下的治療領域、產品線與產品細項。本觀點採兩個業務分部，不採地區或分部下的細項。Consumer 是分拆前的業務分部，不是 Other 或調節項；對照表在分拆後只有欄名或空值，不將空值當作零。

## 分類與 tag

分類與總營收的 concept 均為 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`，單位為 USD。

| 項目 | 完整 dimensions |
|---|---|
| Innovative Medicine | 僅 `us-gaap:StatementBusinessSegmentsAxis=jnj:InnovativeMedicineMember` |
| MedTech | 僅 `us-gaap:StatementBusinessSegmentsAxis=jnj:MedTechMember` |
| 總營收（Sales to customers） | 無維度 |

不選帶地區、產品或子分部維度的 fact。兩個分類加總等於無維度的合併總營收，沒有調節項。

FY2023 10-K（`0000200406-24-000013`，期末 2023-12-31）與 2024 年 Q1 至 2026 年 Q3 的主申報均使用這一組 tag，parser 不依日期或申報切換寫法。

`categories(day)` 的涵蓋下限為 **2023-12-31，含當日**。這是範圍內第一期 FY2024 Q1 所在財年的上一財年期末日，涵蓋第一個 Q4 口徑檢核所需的 `categories(2023-12-31)`。涵蓋範圍內固定回傳上述兩類。更早的三分部結構及舊分類名稱不在涵蓋範圍，不以這兩類重建分拆前的主申報。

## 期別與推算

公司財年在最接近 12 月底的星期日結束，通常為 52 週，每五或六年有一個 53 週財年。規則見 FY2025 10-K（`0000200406-26-000016`）附註 1 的「Annual closing date」。季末日也是星期日，FY2024、FY2025 的年度期末日分別為 2024-12-29、2025-12-28，均為 52 週財年。FY2025 10-K 揭露 FY2026 為 53 週財年，Q4 為 14 週，仍在框架單季 84–98 天的範圍內。2026 年前三季的實際期末日為 2026-03-29、2026-06-28、2026-09-27。

- Q1–Q3 取 10-Q 的三個月 fact。
- FY 取 10-K 的年度 fact。
- Q4 由框架以同財年的年度 fact 減去 Q3 10-Q 的九個月累計，逐項保留兩個運算元。是否推算依框架的分類與口徑一致檢核，不從 10-K 的單季表補值。
- FY2024 Q4 的上一財年年度依據為 FY2023 10-K。該申報可用相同兩個分部成員與無維度總營收組出 FY2023 年度。

FY2024、FY2025 的 Q4 均通過分類與口徑一致檢核，依年度減九個月累計推算並發布。範圍內沒有 `not_derived` 或 `failed` 的期別。

## 數字在原文的位置

兩個分部的 fact 在 MD&A「Analysis of sales by business segments」下的分部銷售表，各分部的 `Worldwide` 列。這張表跨數頁，每頁一個表格編號，編號每份申報不同：Innovative Medicine 的 `Worldwide` 列在其中一段（2024 年 Q1 10-Q 為 t62），MedTech 的 `Worldwide` 列、`TOTAL MEDTECH` 與末尾的無維度 `WORLDWIDE` 合計在後面一段（同一份為 t64）；10-K 結構相同（FY2024 10-K 為 t171、t175）。這些 fact 只有分部維度；同表的 `U.S.` 與 `International` 列另有地區維度，不採用。10-Q 的表同時列單季與累計欄；10-K 列年度欄。

以下為正式 `revenue.json` 運算元的 `evidence.table` 實際記錄的表格，編號取自證據檔名 `<accession>-<sha12>-t<編號>.html` 與同名 `.png`。總營收證據均取自 MedTech 銷售表末尾的無維度合併總計，而非合併損益表或地區銷售表中的重複 fact。

| 主申報期末日 | 表單 | Innovative Medicine 證據表格 | MedTech 證據表格 | 總營收證據表格 |
|---|---|---|---|---|
| 2024-03-31 | 10-Q | t62 | t64 | t64 |
| 2024-06-30 | 10-Q | t66 | t70 | t70 |
| 2024-09-29 | 10-Q | t66 | t70 | t70 |
| 2024-12-29 | 10-K | t171 | t175 | t175 |
| 2025-03-30 | 10-Q | t63 | t67 | t67 |
| 2025-06-29 | 10-Q | t65 | t69 | t69 |
| 2025-09-28 | 10-Q | t65 | t69 | t69 |
| 2025-12-28 | 10-K | t173 | t177 | t177 |
| 2026-03-29 | 10-Q | t61 | t65 | t65 |
| 2026-06-28 | 10-Q | t65 | t69 | t69 |
| 2026-09-27 | 10-Q | t64 | t68 | t68 |

Q1–Q3 與 FY 每期使用兩張表。Q4 使用四張表，年度運算元取自同財年的 10-K，九個月運算元取自 Q3 10-Q。例如 FY2024 Q4 的證據為 `0000200406-25-000038-17e73421b1cc-t171`、`0000200406-25-000038-17e73421b1cc-t175`、`0000200406-24-000096-eb6f017be187-t66`、`0000200406-24-000096-eb6f017be187-t70`。

## 已知的重複 fact

無維度總營收會在合併損益表、分部分析末尾及地區銷售表重複標記，相同期間的數值一致。框架檢查重複 fact 的一致性並選取證據，parser 不指定 fact id 或表格編號。

FY2023 10-K 另有季報資訊表，列示帶相同分部維度的 Q4 單季 fact。parser 的 Q4 仍由框架以年度減九個月累計，不使用該單季表。

## 2023 年分拆與名稱邊界

2023 年 Q3 10-Q（[`0000200406-23-000102`，期末 2023-10-01](https://www.sec.gov/Archives/edgar/data/200406/000020040623000102/jnj-20231001.htm)）說明，Kenvue 交換要約完成後，公司改為 Innovative Medicine 與 MedTech 兩個業務分部，Pharmaceutical 改稱 Innovative Medicine，Consumer Health 列為停業部門。FY2023 10-K（[`0000200406-24-000013`](https://www.sec.gov/Archives/edgar/data/200406/000020040624000013/jnj-20231231.htm)）已按持續營業呈現兩個分部及較早年度比較欄。

兩類結構在本 parser 涵蓋下限以前已存在。更早主申報的 Consumer、Pharmaceutical 與 Medical Devices 等結構及名稱不涵蓋；不因對照來源事後沿用新名稱而將其套回早期主申報。

## 驗證

`status.json` 中 Q 序列 11 期（2024-03-31 至 2026-09-27）與 FY 序列 2 期（2024-12-29、2025-12-28）全部為 `published`，沒有 `not_derived` 或 `failed`。各期 `revenue.json` 的結構與證據完整檢核均通過，兩個分類加總與總營收的差額均為零。

富途依申報宣告的財年與季別對齊。下表為正式輸出與富途的共同數值，單位為百萬美元；每季兩個分類均完全相同，共 22 筆，沒有超出顯示精度的差異。

| 財年與季別 | SEC 實際期末日 | Innovative Medicine | MedTech |
|---|---|---|---|
| 2024/Q1 | 2024-03-31 | 13,562 | 7,821 |
| 2024/Q2 | 2024-06-30 | 14,490 | 7,957 |
| 2024/Q3 | 2024-09-29 | 14,580 | 7,891 |
| 2024/Q4 | 2024-12-29 | 14,332 | 8,188 |
| 2025/Q1 | 2025-03-30 | 13,873 | 8,020 |
| 2025/Q2 | 2025-06-29 | 15,202 | 8,541 |
| 2025/Q3 | 2025-09-28 | 15,563 | 8,430 |
| 2025/Q4 | 2025-12-28 | 15,763 | 8,801 |
| 2026/Q1 | 2026-03-29 | 15,426 | 8,636 |
| 2026/Q2 | 2026-06-28 | 16,384 | 8,926 |
| 2026/Q3 | 2026-09-27 | 16,757 | 8,642 |

富途對照資料沒有年度，因此 FY2024、FY2025 不與富途比對。富途的 2022/Q4 至 2023/Q4 在預設起始日（2024-01-01）以前，不比對；FY2023 僅作 Q4 口徑檢核的上一財年依據，不是範圍內的發布期別。Stock Analysis 與 TradingView 不作本 parser 的逐期驗證來源。

## 比較欄

正式 `status.json` 的 11 個季度與 2 個年度均未記錄 `differences`，沒有比較欄差異標記，也沒有需要列出的來源申報或受影響運算元。
