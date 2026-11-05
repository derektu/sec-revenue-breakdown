# TSLA parser

## 觀點

營運分部（`view="business_segment"`）：Automotive、Energy generation and storage。TradingView 與富途都用這兩類；Stock Analysis 用 Auto、Energy and Storage、Services and Other（產品別，Automotive 再拆服務），不採用。

分部取自 `us-gaap:StatementBusinessSegmentsAxis`。TSLA 的兩個成員是業務別（汽車、能源），不是地區。

## 分類與 tag

concept 是 `us-gaap:Revenues`，分部 fact 只帶分部軸。Automotive 含汽車銷售、租賃、碳權、服務及其他。

| 分類 | 成員 |
|---|---|
| Automotive | `tsla:AutomotiveSegmentMember` |
| Energy generation and storage | `tsla:EnergyGenerationAndStorageSegmentMember` |
| 總營收（Total revenues） | `us-gaap:Revenues` 不帶維度 |

FY2023 Q4（2023-12-31）到 FY2026 Q3（2026-09-30）的 12 季使用同一組定義，兩類加總等於總營收。

## 期別與推算

- 曆年財年。Q1–Q3：10-Q 三個月；Q4：10-K 年度減 Q3 10-Q 九個月。
- FY2024、FY2025 各有一份只修 Part III 的 10-K/A，下載紀錄的表單種類記為 10-K。主申報取最早的一份，所以用的是原始 10-K。

## 數字在原文的位置

分部附註的分部表（兩個分部的營收與毛利），總營收在緊接的另一張表，每期證據兩張表（Q4 四張）。

## 驗證

- 富途：12 季，以財年季別對齊，兩類都在顯示精度內。
- TradingView：FY2024、FY2025 的四季加總在顯示精度內。
- 舊流程：有分部輸出的期別數值一致（舊流程的 Q4 沒有分部輸出）。

## 標註

- 2024-12-31：Energy generation and storage YoY +113%、兩類占比 ±6.19 個百分點。
- 2025-03-31：Energy generation and storage YoY +67%、兩類占比 ±6.44 個百分點。
