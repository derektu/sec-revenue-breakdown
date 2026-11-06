# META parser

## 觀點

營運分部（`view="business_segment"`）：Family of Apps、Reality Labs。TradingView 與富途都用這兩類；Stock Analysis 用 Advertising、Payments and Other、Reality Labs（Family of Apps 再拆兩項），不採用。

分部取自 `us-gaap:StatementBusinessSegmentsAxis`。META 的兩個成員是業務別（應用程式家族、AR／VR 硬體與軟體），不是地區。地區拆分（`srt:StatementGeographicalAxis`）不採用。

## 分類與 tag

concept 是 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`，分部 fact 只帶分部軸。

| 分類 | 成員 |
|---|---|
| Family of Apps | `meta:FamilyOfAppsMember` |
| Reality Labs | `meta:RealityLabsMember` |
| 總營收（Revenue） | 不帶維度 |

FY2024 Q1（2024-03-31）到 FY2026 Q3（2026-09-30）的 11 季使用同一組寫法。兩類加總等於總營收，沒有調節項。

Family of Apps 另有 `srt:ProductOrServiceAxis` 的細項（Advertising、`us-gaap:ServiceOtherMember`），fact 多帶一個維度，不會被選到。

## 期別與推算

- 曆年財年，季末日是 3／6／9／12 月月底。
- Q1–Q3：10-Q 中三個月期間的 fact；Q4：10-K 年度減 Q3 10-Q 的九個月累計。年度與 Q1–Q3 的分類相同，範圍內每個 Q4 都推算。
- FY：10-K 的年度 fact，證據是 10-K 中與 Q4 年度運算元相同的表格。

## 數字在原文的位置

分部營收表：兩個分部、各自細項與總營收在同一張表，每期證據一張表（Q4 兩張）。

## 驗證

- 富途：11 季，以財年季別對齊，兩類都在顯示精度內。
- TradingView：只有年度，FY2024、FY2025 的四季加總在顯示精度內；FY2026 在範圍內不足四季。
- 舊流程（Advertising、Payments and Other、Reality Labs）：有輸出的 8 季，Advertising＋Payments and Other 等於 Family of Apps，Reality Labs 相同。
- FY 序列：每個 FY 的數值與同期 Q4 的年度運算元相同。

## 比較欄

已下載的申報（含修正申報）列示的較早期間數字（去年同季、去年九個月累計、去年全年），與已上線輸出都在精度內相同，沒有差異標記。
