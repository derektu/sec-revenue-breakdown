# MRVL parser

## 觀點

終端市場別（`product`），採各期原申報結構。採用 TradingView 對照，Stock Analysis 作季度輔助。沒有調節項，總營收為 Net revenue。

分類名稱取自主文件「Net revenue by end market」表的列標籤，順序依 TradingView：

- 至 FY2026 Q3：Data center、Enterprise networking、Carrier infrastructure、Automotive/industrial、Consumer。
- FY2026 10-K 起：Data center、Communications and other。

TradingView 的 Data Center、Enterprise Networking、Carrier Infrastructure、Automotive/Industrial、Communications and Other 分別對應上述 SEC 名稱，Consumer 同名。TradingView 的 2023、2024、2025 對應 SEC FY2024、FY2025、FY2026。

Stock Analysis 的 Data Center 與 Automotive Industrial 分別對應 Data center 與 Automotive/industrial。其標示 2024-03-31 起的季度已追溯採用兩類，不據此改寫較早原申報的五類。富途沒有既存對照資料。公司另列地區、銷售通路，以及單一報導分部；不採用這些拆分。`us-gaap:StatementBusinessSegmentsAxis=mrvl:ReportableSegmentMember` 是單一業務分部總額，不能取代終端市場分類。

## 分類與 tag

所有分類與總營收的 concept 均為 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`，單位為 USD。下表列出完整 dimensions，沒有其他維度。

| 分類 | 完整 dimensions |
|---|---|
| Data center | `srt:ProductOrServiceAxis=mrvl:DataCenterMember` |
| Enterprise networking | `srt:ProductOrServiceAxis=mrvl:EnterpriseNetworkingMember` |
| Carrier infrastructure | `srt:ProductOrServiceAxis=mrvl:CarrierInfrastructureMember` |
| Automotive/industrial | `srt:ProductOrServiceAxis=mrvl:AutomotiveAndIndustrialMember` |
| Consumer | `srt:ProductOrServiceAxis=mrvl:ConsumerMember` |
| Communications and other | `srt:ProductOrServiceAxis=mrvl:CommunicationsAndOtherMember` |
| Net revenue | `{}`（無維度合併營收） |

`compose` 依該申報、該要求期間是否存在 CommunicationsAndOtherMember 的 fact 選兩類或五類。選擇透過 `find` 的 namespace URI 精確比對，不依數值或 fact id，也不以後來申報重組較早主申報。較晚申報的比較欄按該份申報自己的結構組成。

`categories(day)` 在 **2025-11-02** 切為兩類，這是最後一份五類主申報 FY2026 Q3 期末 2025-11-01 的隔天。依據是 [FY2026 10-K，0001835632-26-000011，期末 2026-01-31](https://www.sec.gov/Archives/edgar/data/1835632/000183563226000011/mrvl-20260131.htm) 的營收附註：自 FY2026 Q4 起，Enterprise networking、Carrier infrastructure、Consumer、Automotive/industrial 合併為 Communications and other，Data center 組成不變。

涵蓋下限為 **2023-01-28**，包含 FY2023 10-K 與 FY2024 全財年，供預設起始日後第一個 Q4 的分類檢查與口徑依據使用。本機最早可確認五類的申報為 FY2023 10-K，不宣稱是歷史首次。更早期別未確認，以更早的 `--start` 處理前須重新評估。

## 期別與推算

財年為最接近 1 月 31 日的星期六結束的 52 或 53 週年度，財年與季別取申報的 DEI。FY2024 為 53 週，Q4 為 14 週；FY2025、FY2026 為 52 週。單季 91 天，FY2024 Q4 為 98 天；半年 182 天、九個月 273 天、年度 364 或 371 天，均適用框架預設範圍。

- Q1–Q3 取主 10-Q 的當期單季 fact。
- FY 取主 10-K 的當期年度 fact。
- FY2024、FY2025 Q4 為同財年年度減 Q3 九個月累計，每個分類與總營收各自相減。
- FY2024 Q4 的上一年度口徑依據為 [FY2023 10-K，0001835632-23-000013](https://www.sec.gov/Archives/edgar/data/1835632/000183563223000013/mrvl-20230128.htm)。其五類年度值與 FY2024 10-K 的 FY2023 比較欄相同，依輸出順序為 2,408.8、1,369.2、1,084.0、356.5、701.1 百萬美元，總營收 5,919.6 百萬美元。
- FY2025 Q4 的上一年度 FY2024 五類亦與 FY2025 10-K 比較欄相同，沒有口徑變更。
- **FY2026 Q4（2026-01-31）為 `not_derived`**：年度是兩類，Q1–Q3 期間 2025-02-02 至 2025-11-01 是五類，框架的「Q4 推算條件」不成立。FY2026 年度照常組成，不為補 Q4 追溯合併前三季。

不自訂 `DURATION_DAYS`、`FISCAL_YEAR` 或 `ATTACHMENTS`。所有所需 fact 均在主文件。四類合併成一類不是同範圍改名，不宣告 `FORMER_NAMES`。

## 數字在原文的位置

下表依正式 `data/revenue/M/MRVL/` 各期 `revenue.json` 的 `operands[*].evidence.table` 列出表格與證據檔名主體。各表均為營收附註的「Net revenue by end market」，含所有分類及無維度總營收。證據檔位於各期的 `evidence/`，同一主體各有 `.html` 與 `.png`。FY2023 10-K 僅作第一個 Q4 的上一年度口徑依據，沒有正式證據檔，其 t29 為原申報表格編號。

| 申報期末 | accession | 表格 | 證據檔名主體 | 用途 |
|---|---|---|---|---|
| 2023-01-28 | 0001835632-23-000013 | t29 | 無，僅作口徑依據 | FY2024 Q4 的上一年度口徑依據，不是範圍內輸出 |
| 2023-10-28 | 0001835632-23-000046 | t12 | `0001835632-23-000046-ec80687a13ac-t12` | FY2024 Q4 的九個月運算元 |
| 2024-02-03 | 0001835632-24-000009 | t31 | `0001835632-24-000009-c6b9fc40a9b4-t31` | FY2024 與 Q4 年度運算元，FY2023 比較欄 |
| 2024-05-04 | 0001835632-24-000063 | t12 | `0001835632-24-000063-2a6983a8a410-t12` | FY2025 Q1 |
| 2024-08-03 | 0001835632-24-000142 | t12 | `0001835632-24-000142-6c04a6ff6811-t12` | FY2025 Q2 |
| 2024-11-02 | 0001835632-24-000200 | t12 | `0001835632-24-000200-8a297348c886-t12` | FY2025 Q3、Q4 九個月運算元 |
| 2025-02-01 | 0001835632-25-000057 | t28 | `0001835632-25-000057-42084a767c97-t28` | FY2025 與 Q4 年度運算元，FY2024 比較欄 |
| 2025-05-03 | 0001835632-25-000117 | t12 | `0001835632-25-000117-0974b9176985-t12` | FY2026 Q1 |
| 2025-08-02 | 0001835632-25-000189 | t12 | `0001835632-25-000189-d7628fe0f5b9-t12` | FY2026 Q2 |
| 2025-11-01 | 0001835632-25-000197 | t12 | `0001835632-25-000197-02acfe7177a5-t12` | FY2026 Q3 |
| 2026-01-31 | 0001835632-26-000011 | t28 | `0001835632-26-000011-ff9b4bde3967-t28` | FY2026，FY2024、FY2025 兩類比較欄 |
| 2026-05-02 | 0001835632-26-000019 | t12 | `0001835632-26-000019-6cc0f66daeb8-t12` | FY2027 Q1 |
| 2026-08-01 | 0001835632-26-000025 | t12 | `0001835632-26-000025-6d3a3249f1ae-t12` | FY2027 Q2 |

## 已知的重複 fact

無維度總營收同時標在損益表、終端市場表、通路及地區表；較早三份 10-Q 的總營收亦有多表重複。所需期間的同 concept、完整 dimensions、起訖日之重複值一致，框架核對後依精度、表格涵蓋項目數與原文順序選取。範圍內分類與總營收均選到上列終端市場表，不寫死 fact id 或表格編號。

## FY2026 Q4 分類合併

FY2026 10-K t28 將 FY2024、FY2025 比較欄也列為兩類。Communications and other 分別為 3,291.0 與 1,603.1 百萬美元，等於各原申報四個非資料中心分類的合計：

- FY2024，0001835632-24-000009 t31：1,228.4 ＋ 1,051.9 ＋ 388.3 ＋ 622.4 ＝ 3,291.0。
- FY2025，0001835632-25-000057 t28：626.4 ＋ 338.2 ＋ 322.4 ＋ 316.1 ＝ 1,603.1。

兩個年度的 Data center 保持 2,216.7 與 4,164.2 百萬美元。上述較晚比較欄只作合併範圍證據，不作較早輸出的運算元。FY2027 Q1、Q2 的去年同季比較欄也採兩類，原五類季度保留不動。

## 驗證

本節期別狀態以 `data/revenue/M/MRVL/status.json` 為準，數字與運算元證據取自各期正式 `revenue.json` 及 `evidence/`。

預設範圍內 13 期 `published`、1 期 `not_derived`、0 期 `failed`，所有可組成期別分類加總等於 Net revenue。下表數字為百萬美元，五類依輸出順序列示，兩類為 Data center、Communications and other。

| 期別 | 期末 | 狀態 | 分類值 | Net revenue | TradingView 對照 |
|---|---|---|---|---|---|
| FY2024 | 2024-02-03 | published | 2,216.7 / 1,228.4 / 1,051.9 / 388.3 / 622.4 | 5,507.7 | 標示 2023，5 筆在顯示精度內 |
| FY2024 Q4 | 2024-02-03 | published | 765.3 / 265.0 / 170.0 / 82.3 / 143.9 | 1,426.5 | 無季度資料 |
| FY2025 Q1 | 2024-05-04 | published | 816.4 / 153.1 / 71.8 / 77.6 / 42.0 | 1,160.9 | 無季度資料 |
| FY2025 Q2 | 2024-08-03 | published | 880.9 / 151.0 / 75.9 / 76.2 / 88.9 | 1,272.9 | 無季度資料 |
| FY2025 Q3 | 2024-11-02 | published | 1,101.1 / 150.9 / 84.7 / 82.9 / 96.5 | 1,516.1 | 無季度資料 |
| FY2025 | 2025-02-01 | published | 4,164.2 / 626.4 / 338.2 / 322.4 / 316.1 | 5,767.3 | 標示 2024，5 筆在顯示精度內 |
| FY2025 Q4 | 2025-02-01 | published | 1,365.8 / 171.4 / 105.8 / 85.7 / 88.7 | 1,817.4 | 無季度資料 |
| FY2026 Q1 | 2025-05-03 | published | 1,440.6 / 177.5 / 138.4 / 75.7 / 63.1 | 1,895.3 | 無季度資料 |
| FY2026 Q2 | 2025-08-02 | published | 1,490.5 / 193.6 / 130.1 / 76.0 / 115.9 | 2,006.1 | 無季度資料 |
| FY2026 Q3 | 2025-11-01 | published | 1,517.9 / 237.2 / 167.8 / 35.0 / 116.6 | 2,074.5 | 無季度資料 |
| FY2026 | 2026-01-31 | published | 6,100.3 / 2,094.3 | 8,194.6 | 標示 2025，2 筆在顯示精度內 |
| FY2026 Q4 | 2026-01-31 | not_derived | 分類集合改變，不推算 | 不輸出 | 無季度資料 |
| FY2027 Q1 | 2026-05-02 | published | 1,832.7 / 585.1 | 2,417.8 | 無季度資料 |
| FY2027 Q2 | 2026-08-01 | published | 2,171.5 / 567.8 | 2,739.3 | 無季度資料 |

採用的對照為 `data/universe/references/M/MRVL/reference.json` 的 TradingView 20261108T070646Z 快照。年度共比對 12 筆，沒有超出顯示精度的差異。下表列出各筆 SEC 值、對照顯示與差額，差額為 SEC 減對照換算值，單位百萬美元。

| SEC 財年 | 分類 | SEC | TradingView | 差額 |
|---|---|---|---|---|
| FY2024 | Data center | 2,216.7 | 2.22B | -3.3 |
| FY2024 | Enterprise networking | 1,228.4 | 1.23B | -1.6 |
| FY2024 | Carrier infrastructure | 1,051.9 | 1.05B | +1.9 |
| FY2024 | Automotive/industrial | 388.3 | 388.30M | 0 |
| FY2024 | Consumer | 622.4 | 622.40M | 0 |
| FY2025 | Data center | 4,164.2 | 4.16B | +4.2 |
| FY2025 | Enterprise networking | 626.4 | 626.40M | 0 |
| FY2025 | Carrier infrastructure | 338.2 | 338.20M | 0 |
| FY2025 | Automotive/industrial | 322.4 | 322.40M | 0 |
| FY2025 | Consumer | 316.1 | 316.10M | 0 |
| FY2026 | Data center | 6,100.3 | 6.10B | +0.3 |
| FY2026 | Communications and other | 2,094.3 | 2.09B | +4.3 |

非零差額均由網站以 0.01B 顯示造成，半個顯示單位為 5 百萬美元，加 SEC 年度單一運算元 `decimals=-5` 的 0.05 百萬美元誤差後，容許值為 5.05 百萬美元。0.01M 顯示的容許值為 0.055 百萬美元，這些筆數差額均為零。證據為上述各年度原申報 t31 或 t28 的 XBRL fact，以及已保存的 TradingView 表格快照。

TradingView 沒有季度資料，全部 11 個季度期別未作採用來源的數值比對。FY2023 及更早年度在預設輸出範圍外，不納入年度比對；FY2023 只核對第一個 Q4 的口徑依據。

Stock Analysis 20261108T070446Z 快照作季度輔助。其 2023-12-31 對應 FY2024 Q4，五類值皆相等。其後的兩類與較早原申報存在分類結構差異，下表逐季列出四個非資料中心市場合計與該來源 Communications and Other，單位百萬美元。這些合計只用於解釋對照差異，不改 parser 輸出結構。

| SEC 期別 | Stock Analysis 標示 | 原申報四類合計 | Stock Analysis |
|---|---|---|---|
| FY2025 Q1 | 2024-03-31 | 344.5 | 344.50M |
| FY2025 Q2 | 2024-06-30 | 392.0 | 392.00M |
| FY2025 Q3 | 2024-09-30 | 415.0 | 415.00M |
| FY2025 Q4 | 2024-12-31 | 451.6 | 451.60M |
| FY2026 Q1 | 2025-03-31 | 454.7 | 454.70M |
| FY2026 Q2 | 2025-06-30 | 515.6 | 515.60M |
| FY2026 Q3 | 2025-09-30 | 556.6 | 556.60M |

上述七季的 Data center 均在網站顯示精度內。FY2027 Q1、Q2 分別對齊網站 2026-03-31、2026-06-30，兩類亦在顯示精度內。FY2026 Q4 不產生輸出，因此不以網站 2025-12-31 的兩類值作一致性判定。

## 比較欄

正式 `data/revenue/M/MRVL/status.json` 沒有比較欄差異標記（`differences`），也沒有申報讀取錯誤（`comparison_errors`）。

FY2026 10-K 及 FY2027 10-Q 的兩類比較欄能核對同名 Data center 與總營收；四個舊分類在新結構不再單列，框架視為 `not_found`，不產生 `different` 或 `unparseable` 標記。0 筆標記不表示各舊分類都已與新比較欄逐項比對。合併的等值依據見「FY2026 Q4 分類合併」。
