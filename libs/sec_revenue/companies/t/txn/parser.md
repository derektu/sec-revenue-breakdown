# TXN parser

## 觀點

業務分部（`business_segment`）：Analog、Embedded Processing、Other，採用 Stock Analysis 的分類順序。`us-gaap:StatementBusinessSegmentsAxis` 的成員是業務別，不是地區。沒有調節項；總營收為無維度的 Total revenue。

Analog、Embedded Processing 是兩個可報導分部，Other 為其餘業務。Stock Analysis、TradingView 都直接對應這三類；富途的「模擬」「嵌入式處理」「其他」依序對應。三個來源皆列出 Other 的有效數值，因此它是分類。TradingView 的 Wireless、Semiconductor、Education Technology 在擷取期間皆為空值，不當作零或額外分類。地區營收不採用。

## 分類與 tag

所有項目的 concept 為 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`。完整 dimensions 如下，沒有其他維度：

| 項目 | 完整 dimensions |
|---|---|
| Analog | `us-gaap:StatementBusinessSegmentsAxis=txn:AnalogMember` 或 `txn:AnalogSegmentMember` |
| Embedded Processing | `us-gaap:StatementBusinessSegmentsAxis=txn:EmbeddedProcessingMember` 或 `txn:EmbeddedProcessingSegmentMember` |
| Other | `us-gaap:StatementBusinessSegmentsAxis=us-gaap:AllOtherSegmentsMember` |
| Total revenue | 無維度 |

Analog、Embedded Processing 的成員變體用 `one_of`，每份申報都找兩種寫法，不按日期切換。兩種同時存在時由框架檢查是否同值。

| 申報 | Analog／Embedded Processing 的成員 |
|---|---|
| FY2023 10-K `0000097476-24-000007`、2024 Q1–Q3、FY2024 10-K `0000097476-25-000007` | 不帶 `Segment` |
| 2025 Q1 `0000097476-25-000027`、Q2 `0000097476-25-000036`、Q3 `0000097476-25-000060` | 帶 `Segment` |
| FY2025 10-K `0000097476-26-000059` | 不帶 `Segment` |
| 2026 Q1 `0000097476-26-000101`、Q2 `0000097476-26-000152`、Q3 `0000097476-26-000169` | 帶 `Segment` |

分類名稱取自分部附註的 Revenue 列標籤或分類欄標題；Total revenue 取自 FY2023 及 2024 年 10-Q 的合計列標籤。FY2024 起年報、2025 起季報改為分類欄，Revenue 列的 Total 欄仍為同一合併總營收。

`categories(day)` 固定回傳三類。已查核下限為 2023-12-31，涵蓋第一個 Q4 的上一財年口徑依據；這不是歷史首次揭露日。更早期別未確認。不宣告 `DURATION_DAYS`、`FISCAL_YEAR`、`ATTACHMENTS`、`FORMER_NAMES`，成員名稱變體不屬於分類改名。

## 期別與推算

財年即曆年，季末為 3、6、9、12 月最後一天。查核期間的單季為 90–92 天、六個月 181–182 天、九個月 273–274 天、年度 365–366 天，皆在框架預設範圍內。

- Q1–Q3：主申報 10-Q 的三個月 fact。
- FY：主申報 10-K 的年度 fact。
- Q4：同財年 10-K 年度減 Q3 10-Q 九個月累計。2024、2025 年的分類與口徑一致，兩個 Q4 均可推算。FY2024 的上一財年口徑依據為 FY2023 10-K，三類為 13,040／3,368／1,111 百萬美元，合計 17,519 百萬美元。

每個分類直接取自己的 fact，三類加總等於合併總營收，不用總營收倒算 Other。所有數字只來自主文件 XBRL，單位 USD、`decimals=-6`。

## 數字在原文的位置

以下位置依正式 `revenue.json` 的 `operands[*].evidence.table` 記錄。證據檔位於各期 `data/revenue/T/TXN/<序列>/<期末日>/evidence/`，同一檔名各有 `.html` 表格與 `.png` 截圖；SEC 原文 URL、文件雜湊及 fact 的期間、單位、完整 dimensions 保存在運算元中。

| 期別 | 正式證據檔名（不含副檔名） | 表格及內容 |
|---|---|---|
| 2024 Q1 | `0000097476-24-000021-0f2475ca89eb-t15` | t15，分部表單季 Revenue，三類與總營收 |
| 2024 Q2 | `0000097476-24-000030-092169c02459-t15` | t15，分部表單季 Revenue，三類與總營收 |
| 2024 Q3 | `0000097476-24-000042-657d1197c250-t15` | t15，分部表單季 Revenue，三類與總營收 |
| FY2024、2024 Q4 年度運算元 | `0000097476-25-000007-ea572382fb6f-t23` | t23，分部表 Revenue 列，三類與總營收 |
| 2024 Q4 九個月運算元 | `0000097476-24-000042-657d1197c250-t15` | t15，分部表九個月 Revenue，三類與總營收 |
| 2025 Q1 | `0000097476-25-000027-7a7341151a66-t15` | t15，分部表單季 Revenue，三類與總營收 |
| 2025 Q2 | `0000097476-25-000036-331646ab7773-t15` | t15，分部表單季 Revenue，三類與總營收 |
| 2025 Q3 | `0000097476-25-000060-c6ef1b1f85b5-t15` | t15，分部表單季 Revenue，三類與總營收 |
| FY2025、2025 Q4 年度運算元 | `0000097476-26-000059-6e51f1ce8ea9-t23` | t23，分部表 Revenue 列，三類與總營收 |
| 2025 Q4 九個月運算元 | `0000097476-25-000060-c6ef1b1f85b5-t16` | t16，分部表九個月 Revenue，三類與總營收 |
| 2026 Q1 | `0000097476-26-000101-42ea8077c6a7-t15` | t15，分部表單季 Revenue，三類與總營收 |
| 2026 Q2 | `0000097476-26-000152-b2c77533fd55-t15` | t15，分部表單季 Revenue，三類與總營收 |
| 2026 Q3 | `0000097476-26-000169-7d2face2b6df-t15` | t15，分部表單季 Revenue，三類與總營收 |

FY2023 10-K `0000097476-24-000007` 的 t23 分部表僅作第一個 Q4 的上一財年口徑依據，不是上述期別的營收運算元。其 fact 保存在 `data/snapshots/T/TXN/` 的申報快照中。

2024 Q4 用 FY2024 t23 減 2024 Q3 t15；2025 Q4 用 FY2025 t23 減 2025 Q3 t16。兩組證據均保存在對應 Q4 的 `evidence/`；年度 t23 另保存在對應 FY 的 `evidence/`。

## 已知的重複 fact

無維度總營收另出現在損益表等表格。框架檢查重複值一致，依精度、同表其他項目數、文件順序選取；此處選到與三類相同的分部表。其餘 fact 保留為運算元的 `duplicates`。

## 驗證

驗證依據為 `data/revenue/T/TXN/status.json` 與各期 `revenue.json` 及 evidence。範圍為 2024 Q1–2026 Q3 共 11 季及 FY2024、FY2025；13 期皆為 `published`，沒有 `not_derived` 或 `failed`。各期分類加總與總營收精確相等，所有運算元均有表格 HTML 與 PNG 證據。

對照資料為 `data/universe/references/T/TXN/reference.json`。下表金額為百萬美元，差額為 SEC 減 Stock Analysis；Embedded Processing 與 Other 的差額每期皆為 0。

| 季別 | Analog | Embedded Processing | Other | Total revenue | Stock Analysis Analog | Analog 差額 |
|---|---:|---:|---:|---:|---:|---:|
| 2024 Q1 | 2,836 | 652 | 173 | 3,661 | 2,840 | −4 |
| 2024 Q2 | 2,928 | 615 | 279 | 3,822 | 2,930 | −2 |
| 2024 Q3 | 3,223 | 653 | 275 | 4,151 | 3,220 | +3 |
| 2024 Q4 | 3,174 | 613 | 220 | 4,007 | 3,170 | +4 |
| 2025 Q1 | 3,210 | 647 | 212 | 4,069 | 3,210 | 0 |
| 2025 Q2 | 3,452 | 679 | 317 | 4,448 | 3,450 | +2 |
| 2025 Q3 | 3,729 | 709 | 304 | 4,742 | 3,730 | −1 |
| 2025 Q4 | 3,615 | 662 | 146 | 4,423 | 3,620 | −5 |
| 2026 Q1 | 3,924 | 723 | 178 | 4,825 | 3,920 | +4 |
| 2026 Q2 | 4,365 | 788 | 310 | 5,463 | 4,370 | −5 |
| 2026 Q3 | 4,911 | 858 | 286 | 6,055 | 4,910 | +1 |

Stock Analysis 的 Analog 顯示至 0.01B，半個顯示單位為 5 百萬美元；再加上 SEC 每個運算元 0.5 百萬美元的精度誤差，33 筆均在顯示精度內。其餘兩類顯示至 0.01M，與 SEC 完全相同。Q4 每類有年度與九個月兩個運算元。

Stock Analysis 沒有 FY 資料，年度另以 TradingView 輔助；下表差額亦為 SEC 減來源，單位百萬美元：

| 年度 | SEC Analog／Embedded Processing／Other | SEC Total revenue | TradingView 三類 | 三類差額 |
|---|---|---:|---|---|
| FY2024 | 12,161／2,533／947 | 15,641 | 12,160／2,530／947 | +1／+3／0 |
| FY2025 | 14,006／2,697／979 | 17,682 | 14,010／2,700／979 | −4／−3／0 |

TradingView 的前兩類顯示至 0.01B，Other 至 0.01M，6 筆均在顯示精度內。2024 年以前的對照資料不列入本次逐期驗證。

富途兩個已知錯配保留為差異，不標一致。順序為 Analog／Embedded Processing／Other，單位百萬美元：

| 富途標示 | 快照三類 | 同期 SEC 三類 | 富途減 SEC |
|---|---|---|---|
| 2025 Q2 | 3,729／709／304 | 3,452／679／317 | +277／+30／−13 |
| 2026 Q2 | 4,911／858／286 | 4,365／788／310 | +546／+70／−24 |

富途快照 `captures/futu/20261108T160644Z/table.txt`、`captures/futu/20261108T160500Z/table.txt` 均保留相同的期別及數字組合，非僅 JSON 轉寫問題。這兩組值分別等於 SEC 下一季 [2025 Q3](https://www.sec.gov/Archives/edgar/data/97476/000009747625000060/txn-20250930.htm) t15 與 [2026 Q3](https://www.sec.gov/Archives/edgar/data/97476/000009747626000169/txn-20260930.htm) t15。

同期 [2025 Q2](https://www.sec.gov/Archives/edgar/data/97476/000009747625000036/txn-20250630.htm) t15、[2026 Q2](https://www.sec.gov/Archives/edgar/data/97476/000009747626000152/txn-20260630.htm) t15 的三列及加總均支持 parser；2026 Q2 的 2025 Q2 比較欄也未重列，已下載的後續申報沒有相關營收差異標記。Stock Analysis 同期數字在顯示精度內支持 SEC。因此將這兩筆視為富途對照資料的期別錯配；尚不能區分網站錯置或擷取時頁面更新未完成，不推論成因。

## 比較欄

正式 `status.json` 中，上述 13 期均無 `differences` 或 `comparison_errors`；已下載 12 份 10-K、10-Q 的比較欄比對未見營收差異。成員帶不帶 `Segment` 不改變分類名稱或範圍；FY2024 分部表改為分類欄也沒有營收重列。2026 Q1 起 Other 的業務描述不再列 custom ASIC，未見比較數字搬移或重列，parser 取當期 Other 的 fact。
