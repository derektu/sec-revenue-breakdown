# AAPL parser

## 觀點

產品別（`view="product"`）：iPhone、Mac、iPad、Wearables, Home and Accessories、Services。Stock Analysis、富途、TradingView 三個對照來源都用這五類。

AAPL 的 inline XBRL 另有兩種營收拆分，都不採用：

| 拆分 | XBRL 維度 | 不採用的原因 |
|---|---|---|
| 營運分部：Americas、Europe、Greater China、Japan、Rest of Asia Pacific | `us-gaap:StatementBusinessSegmentsAxis`，搭配 `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember` | 地區拆分 |
| 國家：U.S.、China、其他國家 | `srt:StatementGeographicalAxis` | 地區拆分，只在 10-K |

## 分類與 tag

所有分類都是 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`，只帶一個維度 `srt:ProductOrServiceAxis`：

| 分類 | 成員 |
|---|---|
| iPhone | `aapl:IPhoneMember` |
| Mac | `aapl:MacMember` |
| iPad | `aapl:IPadMember` |
| Wearables, Home and Accessories | `aapl:WearablesHomeandAccessoriesMember` |
| Services | `us-gaap:ServiceMember` |
| 總營收（Total net sales） | 不帶維度 |

適用期間：FY2024 Q1（2023-12-30）到 FY2026 Q4（2026-09-26）的 12 季都使用同一組定義，沒有 `effective` 分段。五類加總等於總營收，沒有調節項。

## 期別與推算

- 財年在 9 月最後一個星期六結束；季末日是星期六，例如 2024-12-28、2025-09-27。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同財年 Q3 10-Q 的九個月累計。年度與 Q1–Q3 的分類相同，範圍內每個 Q4 都推算。
- FY：10-K 的年度 fact，證據是 10-K 中與 Q4 年度運算元相同的表格。

## 數字在原文的位置

- 10-Q：附註「Net sales by category」表，同一張表有三個月與九個月兩欄，五類與總營收都在。
- 10-K：附註「Net sales by category」表（三個年度欄）。

## 已知的重複 fact

同一個值會在多張表各標一次，數值一致：

- 總營收：損益表、產品別表、分部表；10-K 還有國家別表。
- Services：損益表（Products／Services 兩行）與產品別表。

引擎選用所在表格含最多其他運算元的 fact，也就是產品別表，所以每期的證據只有一張表（Q4 為 10-K 與 Q3 10-Q 各一張）。其餘 fact id 記在運算元的 `duplicates`。

## 驗證

12 季（2023-12-30 至 2026-09-26）與對照資料逐期比對：

- Stock Analysis：每季五類都在顯示精度內（0.01B）。
- 富途：以財年季別對齊，每季五類都在顯示精度內。
- TradingView：只有年度，FY2024、FY2025、FY2026 的四季加總都在顯示精度內。
- FY 序列：每個 FY 的數值與同期 Q4 的年度運算元相同。

## 比較欄

已下載的申報（含修正申報）列示的較早期間數字（去年同季、去年九個月累計、去年全年），與已上線輸出都在精度內相同，沒有差異標記。
