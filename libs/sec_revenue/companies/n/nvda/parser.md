# NVDA parser

## 觀點

營運分部（`view="business_segment"`）：Compute & Networking、Graphics。Stock Analysis、富途、TradingView 三個對照來源都用這兩類。

分部取自 `us-gaap:StatementBusinessSegmentsAxis`。NVDA 的這個軸是業務別（運算與網路產品、繪圖產品），不是地區，所以採用。

NVDA 另有兩種營收拆分，都不採用：

| 拆分 | XBRL 維度 | 不採用的原因 |
|---|---|---|
| 市場平台：Data Center（Compute、Networking）、Gaming、Professional Visualization、Automotive、OEM and Other | `srt:ProductOrServiceAxis` | 三個對照來源都不用這個觀點 |
| 國家：United States、Taiwan、China（含香港）、其他 | `srt:StatementGeographicalAxis` | 地區拆分 |

## 分類與 tag

concept 是 `us-gaap:Revenues`。分部 fact 帶兩個維度：`srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember` 與分部成員。

| 分類 | 成員（期末日至 2024-10-27 的申報） | 成員（期末日 2025-01-26 起的申報） |
|---|---|---|
| Compute & Networking | `nvda:ComputeAndNetworkingMember` | `nvda:ComputeAndNetworkingSegmentMember` |
| Graphics | `nvda:GraphicsMember` | `nvda:GraphicsSegmentMember` |
| 總營收（Revenue） | 不帶維度 | 不帶維度 |

- 成員在 FY2025 10-K（期末 2025-01-26）改名，以兩個 `effective` 定義宣告。定義依運算元來源申報的期末日選取，所以 FY2025 Q4 的年度運算元（10-K）用新成員、九個月運算元（2024-10-27 的 Q3 10-Q）用舊成員。兩個定義屬於同一個分類，Q4 照常推算。
- 「All Other」欄（`srt:ConsolidationItemsAxis=us-gaap:CorporateNonSegmentMember`，部分申報才有）營收為 0，兩個分部加總等於總營收，沒有調節項。FY2026 Q2 起的申報改以 `OperatingSegmentsMember` 標示分部合計，不影響選取。

## 期別與推算

- 財年在 1 月最後一個星期日結束，52／53 週制；季末日是星期日，例如 2025-01-26、2025-10-26。財年以結束的曆年命名：期末 2026-01-25 是 FY2026。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同財年 Q3 10-Q 的九個月累計。年度與 Q1–Q3 的分類相同，範圍內每個 Q4 都推算。
- FY：10-K 的年度 fact，證據是 10-K 中與 Q4 年度運算元相同的表格。

## 數字在原文的位置

- 分部：附註「Segment Information」表，分部欄位與「All Other」、「Consolidated」並列。
- 總營收：舊申報（期末日至 2025-04-27）的分部表有不帶維度的總營收，運算元選在分部表；之後的分部表合計改用帶 `OperatingSegmentsMember` 的 fact，不帶維度的總營收只在損益表等其他表，運算元選損益表，證據多一張表。

## 驗證

11 季（2024-01-28 至 2026-07-26）與對照資料逐期比對：

- Stock Analysis：每季兩類都在顯示精度內（0.01B）。
- 富途：以財年季別對齊（例如 2026/Q4 = 期末 2026-01-25），每季都在顯示精度內。
- TradingView：只有年度，以財年多數月份所在的曆年標示（FY2026 標為 2025）。FY2025、FY2026 的四季加總都在顯示精度內；FY2024、FY2027 範圍內不足四季。
- FY 序列：每個 FY 的數值與同期 Q4 的年度運算元相同。

## 比較欄

已下載的申報（含修正申報）列示的較早期間數字（去年同季、去年九個月累計、去年全年），與已上線輸出都在精度內相同，沒有差異標記。
