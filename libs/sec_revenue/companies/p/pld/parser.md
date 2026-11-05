# PLD parser

## 觀點

營運分部（`view="business_segment"`），共 2 類：Real estate segment 與 Strategic capital segment。對照來源中只有 TradingView 有 PLD 的資料（Real Estate、Strategic Capital）；Stock Analysis 與富途都沒有。

分部取自 `us-gaap:StatementBusinessSegmentsAxis`。PLD 這個軸的成員是業務別：不動產營運是物流不動產的租賃與開發，strategic capital 是替共同投資基金管理資產。兩者不是地區，所以採用。

PLD 另有兩種營收拆分，都不採用：

| 拆分 | XBRL 維度 | 不採用的原因 |
|---|---|---|
| 各分部再分 U.S.、Other Americas、Europe、Asia | 分部軸搭配地區成員 | 地區拆分 |
| 損益表營收類型（Rental、Strategic capital、Development management and other） | 不帶維度的 `pld:RentalRevenue`、`pld:ManagementFeesRevenue`、`pld:OtherRealEstateRevenue` | 對照來源不用；有些申報的 concept 名稱不同（`pld:ManagementFeesRevenue1`、`pld:OtherRealEstateRevenue1`） |

## 分類與 tag

concept 是 `us-gaap:Revenues`。分部 fact 帶兩個維度：`srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember` 與分部成員。

| 分類 | 成員 |
|---|---|
| Real estate segment | `pld:RealEstateOperationsSegmentMember` |
| Strategic capital segment | `pld:StrategicCapitalSegmentMember` |
| 總營收（Total revenues） | 不帶維度 |

- 所有期別都使用同一組定義，沒有 `effective` 分段。
- 兩類加總等於總營收，沒有調節項。
- 分類名稱取自附註分部表的列標籤（`Total real estate segment`、`Total strategic capital segment`，去掉 Total）；總營收取自同表的 `Total revenues`。
- 申報以千美元為單位（`decimals="-3"`）。
- PLD 是 Prologis, Inc. 與 Prologis, L.P. 的合併申報。不帶維度的 fact 屬於 Prologis, Inc.，L.P. 的 fact 帶 `srt:ConsolidatedEntitiesAxis=srt:PartnershipInterestMember`，不選用。

## 期別與推算

- 財年即曆年，季末日是 3、6、9、12 月的最後一天。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同年 Q3 10-Q 的九個月累計。年度與 Q1–Q3 的分類相同，範圍內每個 Q4 都推算。
- FY：10-K 的年度 fact，證據是 10-K 中與 Q4 年度運算元相同的表格。

## 數字在原文的位置

附註「Business Segments」表：各分部先依地區列出，再列分部合計（`Total real estate segment`、`Total strategic capital segment`），最後是 `Total revenues`。每期證據只有一張表（Q4 為 10-K 與 Q3 10-Q 各一張）。

## 驗證

12 季（2023-12-31 至 2026-09-30）與對照資料逐期比對：

- TradingView：只有年度。FY2024、FY2025 的四季加總兩類都在顯示精度內；FY2023、FY2026 在範圍內不足四季。
- Stock Analysis、富途：沒有 PLD 的資料。
- 舊流程輸出（`reported`）用的是損益表的營收類型。有輸出的 8 季（2024-12-31 起）：Rental 加 Development management and other 等於 Real estate segment，Strategic capital 等於 Strategic capital segment，總營收也相同，三者都完全一致。
- FY 序列：每個 FY 的數值與同期 Q4 的年度運算元相同。

## 比較欄

- 已下載的申報（含修正申報）列示的較早期間數字（去年同季、去年九個月累計、去年全年），與已上線輸出都在精度內相同，沒有差異標記。
- 10-K 有季度總營收（`us-gaap:Revenues` 的單季 fact），但沒有季度分部營收。10-K 涵蓋同一年度與前一年度各季，這些季度的分部運算元比對結果是 `not_found`（找不到同期間的 fact），不是差異，不寫差異標記。
