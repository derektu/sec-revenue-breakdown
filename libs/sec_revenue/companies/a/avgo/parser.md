# AVGO parser

## 觀點

業務分部（`business_segment`）：Semiconductor solutions、Infrastructure software。
`us-gaap:StatementBusinessSegmentsAxis` 的成員是業務別，不是地區。

採用 `futu`，輸出順序依富途；TradingView 年度與 Stock Analysis 季度作輔助。來源為
[`reference.json`](../../../../../data/universe/references/A/AVGO/reference.json)。

| SEC 分類 | 富途 | Stock Analysis、TradingView |
|---|---|---|
| Semiconductor solutions | 半導體解決方案 | Semiconductor Solutions |
| Infrastructure software | 基礎設施軟件 | Infrastructure Software |

兩分部涵蓋全部營收，沒有調節項。分部表的 Unallocated expenses 調節營業利益，不是營收。
不採用 Products、Subscriptions and services 的產品類型拆分，也不採用地區拆分。
對照來源較早的 Intellectual Property Licensing、Wired Infrastructure 等歷史分類，在本次範圍內沒有值，不列為分類。

## 分類與 tag

三項都取主文件的 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`，完整 dimensions 如下。

| 項目 | 完整 dimensions |
|---|---|
| Semiconductor solutions | `us-gaap:StatementBusinessSegmentsAxis=avgo:SemiconductorSolutionsMember` |
| Infrastructure software | `us-gaap:StatementBusinessSegmentsAxis=avgo:InfrastructureSoftwareMember` |
| 總營收 Total net revenue | 無維度 |

每個分類各取一個 fact，總營收另取無維度的合併 fact，不以分部加總代替。
單位為 USD；本次運算元的原文以百萬美元列示，`scale=6`、`decimals=-6`。
名稱取自各期分部表的列標籤。FY2025 10-K 起分部名稱改放在段落標題，數字列為 Net revenue，名稱及 fact 寫法不變。

相同寫法涵蓋已下載的 FY2023 10-K（期末 2023-10-29）至 2026 Q3 10-Q。
`categories(day)` 固定回傳兩分部；已確認的分類下限是 2023-10-29，包含第一個 Q4 所需的上一財年期末。
這不代表兩分部始於該日，更早的主申報尚未確認。以 `--start` 處理更早期別前須另外查核。
沒有日期切換、改名或自訂點；不宣告 `DURATION_DAYS`、`FISCAL_YEAR`、`ATTACHMENTS`、`FORMER_NAMES`。

## 期別與推算

財年採 52／53 週制，於 10 月底或 11 月初的星期日結束，各季末也為星期日。
FY2024 是 53 週，額外一週在 Q1。已查核期間的單季為 91 或 98 天，半年 182 或 189 天，
九個月 273 或 280 天，年度 364 或 371 天，適用框架預設範圍。
10-Q 宣告的財年與前一份 10-K 財年加一一致。

- Q1–Q3 取當期 10-Q 的單季 fact。
- FY 取當期 10-K 的年度 fact。
- Q4 由當期 10-K 年度減同財年原 Q3 10-Q 九個月累計，兩份申報的期間起日相同。
  分類集合全年不變，FY2024、FY2025 的上一財年比較值也與先前申報相同，兩個 Q4 均可推算。

Q4 的全部運算如下，單位百萬美元。較晚申報只用於比較欄查核，不提供早期期別的運算元。

| 財季 | 年度申報／Q3 申報 | Semiconductor solutions | Infrastructure software | Total net revenue |
|---|---|---:|---:|---:|
| 2024 Q4 | 0001730168-24-000139／0001730168-24-000099 | 30,096 − 21,866 = 8,230 | 21,478 − 15,654 = 5,824 | 51,574 − 37,520 = 14,054 |
| 2025 Q4 | 0001730168-25-000121／0001730168-25-000098 | 36,858 − 25,786 = 11,072 | 27,029 − 20,086 = 6,943 | 63,887 − 45,872 = 18,015 |

## 數字在原文的位置

下表依正式 `revenue.json` 運算元的 `evidence.table` 列出表格位置與證據檔名。
每張證據表都含兩分部及合併總營收。Q4 使用同財年 10-K 與 Q3 10-Q 兩張表，
兩張表的 HTML 與 PNG 均保存在該 Q4 的 `evidence/` 目錄。
證據路徑以 [`data/revenue/A/AVGO/`](../../../../../data/revenue/A/AVGO/) 為根目錄；
同一列的 HTML 與 PNG 檔名主體相同，副檔名分別為 `.html` 與 `.png`。

| 申報 | accession 與 SEC 原文 | 表格 | 正式證據 HTML／PNG |
|---|---|---|---|
| FY2023，2023-10-29 | [0001730168-23-000096](https://www.sec.gov/Archives/edgar/data/1730168/000173016823000096/avgo-20231029.htm) | t66，僅作 FY2024 Q4 的上一財年口徑依據 | 無證據檔 |
| 2024 Q1，2024-02-04 | [0001730168-24-000023](https://www.sec.gov/Archives/edgar/data/1730168/000173016824000023/avgo-20240204.htm) | t42 | `0001730168-24-000023-ebc50a64e6d4-t42`：[HTML](../../../../../data/revenue/A/AVGO/Q/2024-02-04/evidence/0001730168-24-000023-ebc50a64e6d4-t42.html)、[PNG](../../../../../data/revenue/A/AVGO/Q/2024-02-04/evidence/0001730168-24-000023-ebc50a64e6d4-t42.png) |
| 2024 Q2，2024-05-05 | [0001730168-24-000080](https://www.sec.gov/Archives/edgar/data/1730168/000173016824000080/avgo-20240505.htm) | t46 | `0001730168-24-000080-5197514f4fe4-t46`：[HTML](../../../../../data/revenue/A/AVGO/Q/2024-05-05/evidence/0001730168-24-000080-5197514f4fe4-t46.html)、[PNG](../../../../../data/revenue/A/AVGO/Q/2024-05-05/evidence/0001730168-24-000080-5197514f4fe4-t46.png) |
| 2024 Q3，2024-08-04 | [0001730168-24-000099](https://www.sec.gov/Archives/edgar/data/1730168/000173016824000099/avgo-20240804.htm) | t45 | `0001730168-24-000099-9aa8f518c78d-t45`：[HTML](../../../../../data/revenue/A/AVGO/Q/2024-08-04/evidence/0001730168-24-000099-9aa8f518c78d-t45.html)、[PNG](../../../../../data/revenue/A/AVGO/Q/2024-08-04/evidence/0001730168-24-000099-9aa8f518c78d-t45.png) |
| FY2024，2024-11-03 | [0001730168-24-000139](https://www.sec.gov/Archives/edgar/data/1730168/000173016824000139/avgo-20241103.htm) | t74 | `0001730168-24-000139-13be04a4c1fd-t74`：[HTML](../../../../../data/revenue/A/AVGO/FY/2024-11-03/evidence/0001730168-24-000139-13be04a4c1fd-t74.html)、[PNG](../../../../../data/revenue/A/AVGO/FY/2024-11-03/evidence/0001730168-24-000139-13be04a4c1fd-t74.png) |
| 2025 Q1，2025-02-02 | [0001730168-25-000021](https://www.sec.gov/Archives/edgar/data/1730168/000173016825000021/avgo-20250202.htm) | t36 | `0001730168-25-000021-ee69021dce4b-t36`：[HTML](../../../../../data/revenue/A/AVGO/Q/2025-02-02/evidence/0001730168-25-000021-ee69021dce4b-t36.html)、[PNG](../../../../../data/revenue/A/AVGO/Q/2025-02-02/evidence/0001730168-25-000021-ee69021dce4b-t36.png) |
| 2025 Q2，2025-05-04 | [0001730168-25-000064](https://www.sec.gov/Archives/edgar/data/1730168/000173016825000064/avgo-20250504.htm) | t39 | `0001730168-25-000064-34db94464def-t39`：[HTML](../../../../../data/revenue/A/AVGO/Q/2025-05-04/evidence/0001730168-25-000064-34db94464def-t39.html)、[PNG](../../../../../data/revenue/A/AVGO/Q/2025-05-04/evidence/0001730168-25-000064-34db94464def-t39.png) |
| 2025 Q3，2025-08-03 | [0001730168-25-000098](https://www.sec.gov/Archives/edgar/data/1730168/000173016825000098/avgo-20250803.htm) | t40 | `0001730168-25-000098-d6a25ece002f-t40`：[HTML](../../../../../data/revenue/A/AVGO/Q/2025-08-03/evidence/0001730168-25-000098-d6a25ece002f-t40.html)、[PNG](../../../../../data/revenue/A/AVGO/Q/2025-08-03/evidence/0001730168-25-000098-d6a25ece002f-t40.png) |
| FY2025，2025-11-02 | [0001730168-25-000121](https://www.sec.gov/Archives/edgar/data/1730168/000173016825000121/avgo-20251102.htm) | t73 | `0001730168-25-000121-84ac6a6b2ba4-t73`：[HTML](../../../../../data/revenue/A/AVGO/FY/2025-11-02/evidence/0001730168-25-000121-84ac6a6b2ba4-t73.html)、[PNG](../../../../../data/revenue/A/AVGO/FY/2025-11-02/evidence/0001730168-25-000121-84ac6a6b2ba4-t73.png) |
| 2026 Q1，2026-02-01 | [0001730168-26-000016](https://www.sec.gov/Archives/edgar/data/1730168/000173016826000016/avgo-20260201.htm) | t35 | `0001730168-26-000016-d81a5cba55a5-t35`：[HTML](../../../../../data/revenue/A/AVGO/Q/2026-02-01/evidence/0001730168-26-000016-d81a5cba55a5-t35.html)、[PNG](../../../../../data/revenue/A/AVGO/Q/2026-02-01/evidence/0001730168-26-000016-d81a5cba55a5-t35.png) |
| 2026 Q2，2026-05-03 | [0001730168-26-000054](https://www.sec.gov/Archives/edgar/data/1730168/000173016826000054/avgo-20260503.htm) | t37 | `0001730168-26-000054-c815ae78df06-t37`：[HTML](../../../../../data/revenue/A/AVGO/Q/2026-05-03/evidence/0001730168-26-000054-c815ae78df06-t37.html)、[PNG](../../../../../data/revenue/A/AVGO/Q/2026-05-03/evidence/0001730168-26-000054-c815ae78df06-t37.png) |
| 2026 Q3，2026-08-02 | [0001730168-26-000080](https://www.sec.gov/Archives/edgar/data/1730168/000173016826000080/avgo-20260802.htm) | t37 | `0001730168-26-000080-b36b604a4faf-t37`：[HTML](../../../../../data/revenue/A/AVGO/Q/2026-08-02/evidence/0001730168-26-000080-b36b604a4faf-t37.html)、[PNG](../../../../../data/revenue/A/AVGO/Q/2026-08-02/evidence/0001730168-26-000080-b36b604a4faf-t37.png) |

FY2025 10-K 以前，表格的 Net revenue 區段逐列列出兩分部與 Total net revenue。
從 FY2025 10-K 起，表格按分部分段，兩分部與 Total 段落各有 Net revenue 列，並增加成本與費用。
這是表格呈現改變，不需改 fact 或運算式。

## 已知的重複 fact

總營收也出現在合併損益表及地區拆分表的合計，與分部表數值一致。
框架選擇含最多其他運算元的表格，因此各期總營收與兩分部均選在同一張分部表；
其餘同期間、同 concept、無維度的 fact 保留在運算元 `duplicates`。
正式輸出選用的分部 fact 沒有重複值。

## 驗證

正式輸出見 [`status.json`](../../../../../data/revenue/A/AVGO/status.json) 與各期 `revenue.json`。
範圍為 FY2024 Q1 至 FY2026 Q3 的 11 季，以及 FY2024、FY2025 兩個年度，
共 13 期均為 `published`，沒有 `not_derived` 或 `failed` 期別。
各期均保留運算元、SEC 原文 URL、文件雜湊，以及對應的 HTML 與 PNG 表格證據。

以下單位為百萬美元，分類順序為 Semiconductor solutions、Infrastructure software。
富途按財年季別對齊，11 季共 22 個值全部精確一致；富途沒有 FY 資料，兩個 FY 不作富途比對。

| 財季 | SEC 期末日 | 狀態 | Semiconductor solutions | Infrastructure software | Total net revenue | SEC 減富途，兩分部 |
|---|---|---|---:|---:|---:|---|
| 2024 Q1 | 2024-02-04 | published | 7,390 | 4,571 | 11,961 | 0／0 |
| 2024 Q2 | 2024-05-05 | published | 7,202 | 5,285 | 12,487 | 0／0 |
| 2024 Q3 | 2024-08-04 | published | 7,274 | 5,798 | 13,072 | 0／0 |
| 2024 Q4 | 2024-11-03 | published | 8,230 | 5,824 | 14,054 | 0／0 |
| 2025 Q1 | 2025-02-02 | published | 8,212 | 6,704 | 14,916 | 0／0 |
| 2025 Q2 | 2025-05-04 | published | 8,408 | 6,596 | 15,004 | 0／0 |
| 2025 Q3 | 2025-08-03 | published | 9,166 | 6,786 | 15,952 | 0／0 |
| 2025 Q4 | 2025-11-02 | published | 11,072 | 6,943 | 18,015 | 0／0 |
| 2026 Q1 | 2026-02-01 | published | 12,515 | 6,796 | 19,311 | 0／0 |
| 2026 Q2 | 2026-05-03 | published | 15,009 | 7,178 | 22,187 | 0／0 |
| 2026 Q3 | 2026-08-02 | published | 20,839 | 8,752 | 29,591 | 0／0 |
| FY2024 | 2024-11-03 | published | 30,096 | 21,478 | 51,574 | 無年度對照 |
| FY2025 | 2025-11-02 | published | 36,858 | 27,029 | 63,887 | 無年度對照 |

Stock Analysis 的來源期末標籤與 SEC 財季不同，保留原始標籤，依實際財季對齊。
例如來源 2023-12-31 對應 SEC 2024 Q1，實際期末 2024-02-04，屬於預設起始日以後的範圍。
來源的 Q1–Q4 依序標成上一曆年 12 月、當年 3 月、6 月、9 月底。
下表列出全部輔助來源差額，方向為 SEC 減來源。

| 財季 | Stock Analysis 原始標籤 | Semiconductor solutions 差額 | Infrastructure software 差額 |
|---|---|---:|---:|
| 2024 Q1 | 2023-12-31 | 0 | +1 |
| 2024 Q2 | 2024-03-31 | +2 | −5 |
| 2024 Q3 | 2024-06-30 | +4 | −2 |
| 2024 Q4 | 2024-09-30 | 0 | +4 |
| 2025 Q1 | 2024-12-31 | +2 | +4 |
| 2025 Q2 | 2025-03-31 | −2 | −4 |
| 2025 Q3 | 2025-06-30 | −4 | −4 |
| 2025 Q4 | 2025-09-30 | +2 | +3 |
| 2026 Q1 | 2025-12-31 | −5 | −4 |
| 2026 Q2 | 2026-03-31 | −1 | −2 |
| 2026 Q3 | 2026-06-30 | −1 | +2 |

| 年度 | TradingView 原始標籤 | Semiconductor solutions 差額 | Infrastructure software 差額 |
|---|---|---:|---:|
| FY2024 | 2024 | −4 | −2 |
| FY2025 | 2025 | −2 | −1 |

兩輔助來源均顯示到 `0.01B`，每值有 ±5 百萬美元顯示誤差，以上差額全部在顯示精度內。
SEC 值來自上列申報分部表及 Q4 全部運算元，來源值來自 `reference.json` 與其表格快照。
這些差額不涉及補值或改分類。兩個 FY 也均等於各自四季加總。
FY2023 及更早年度、2023 Q4 及更早季度不在本次輸出範圍，未與對照來源逐期比對。

## 比較欄

正式 `status.json` 沒有 `differences` 或 `comparison_errors` 紀錄。
各期 `revenue.json` 的兩分部加總均等於合併營收，`checks.sum.difference` 均為 0。

FY2024 Q4 的口徑依據為 FY2023 10-K t66；FY2024 10-K t74 的 FY2023 比較值與它相同，
兩分部依序為 28,182、7,637，總營收 35,819 百萬美元。
FY2025 10-K t73 的 FY2024 比較值與 FY2024 10-K t74 相同，
兩分部依序為 30,096、21,478，總營收 51,574 百萬美元。
因此兩個 Q4 都沒有口徑變更或無法判斷註記。

FY2025 10-K 的產品類型重分類不影響本觀點。該申報 Note 3 將 upfront license revenue
由 Subscriptions and services 改列 Products，並重列 FY2024、FY2023 比較欄，
但上述業務分部值不變。產品類型比較欄不是此 parser 的運算元，也不產生業務分部差異標記。
