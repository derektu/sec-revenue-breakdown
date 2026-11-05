# BRK-B parser

## 觀點

營運分部（`view="business_segment"`），共 8 類：Insurance、BNSF、BHE、Manufacturing、McLane、Pilot、Service and retailing，以及 Corporate, eliminations and other。富途與 TradingView 都用這個呈現，Corporate, eliminations and other 也列為一類。Stock Analysis 沒有 BRK-B 的資料。

分部取自 `us-gaap:StatementBusinessSegmentsAxis`。BRK-B 這個軸的成員是業務別，也就是保險、鐵路、能源、製造、經銷、零售等子公司群，不是地區，所以採用。

BRK-B 另有兩種營收拆分，都不採用：

| 拆分 | XBRL 維度 | 不採用的原因 |
|---|---|---|
| 商品與服務類別（Food and beverage、Auto sales、Electricity and natural gas…） | `srt:ProductOrServiceAxis` 搭配分部軸 | 兩個對照來源都不用；只涵蓋客戶合約營收，不含保費與租賃 |
| 兩大群（Insurance and Other、Railroad, Utilities and Energy） | `srt:ProductOrServiceAxis` | 對照來源不用，層級太粗 |

## 分類與 tag

concept 是 `us-gaap:Revenues`。分部 fact 帶兩個維度：`srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember` 與分部成員。

| 分類 | 維度 |
|---|---|
| Insurance | 分部 `brka:BerkshireHathawayInsuranceGroupMember` |
| BNSF | 分部 `brka:BurlingtonNorthernSantaFeCorporationMember` |
| BHE | 分部 `brka:BerkshireHathawayEnergyCompanyMember` |
| Manufacturing | 分部 `brka:ManufacturingBusinessesMember` |
| McLane | 分部 `brka:McLaneCompanyMember` |
| Pilot | 分部 `brka:PilotTravelCentersLLCMember` |
| Service and retailing | 分部 `brka:ServiceAndRetailingBusinessesMember` |
| Corporate, eliminations and other | 只帶 `srt:ConsolidationItemsAxis=brka:CorporateReconcilingItemsAndEliminationsMember` |
| 總營收（Revenues） | 不帶維度 |

- 8 類加總等於總營收，沒有調節項。
- 同一個 concept 另有一組只帶分部軸、不帶 `srt:ConsolidationItemsAxis` 的 fact。那組把保險與公司層級合併為 `brka:InsuranceCorporateAndOtherMember`，數字是對外營收，與分部表不同，所以規格一律寫完整的兩個維度。
- 分類名稱取自附註分部表的欄標題或列標籤：BNSF、BHE、Manufacturing、McLane、Pilot、Service and retailing 是各分部營業結果表的欄標題，Corporate, eliminations and other 是分部與合併營收調節表的列標籤。Insurance 的列標籤是「Premiums earned and investment income」，名稱取該表的分部名稱。

## 期別與推算

- 財年即曆年，季末日是 3、6、9、12 月的最後一天。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同年 Q3 10-Q 的九個月累計。

## 數字在原文的位置

- 2024-09-30 以前的申報：附註「Business segment data」有一張分部營收表，8 類與總營收都在，每期證據一張表（2023Q4 為 10-K 與 Q3 10-Q 各一張）。
- 2024 年度 10-K 起：各分部的營業結果分成多張表，包括保險一張（承保與投資收益）、BNSF 與 BHE 各一張、Manufacturing／Service and retailing 一張、McLane／Pilot 一張。Corporate, eliminations and other 與總營收在分部營收與合併營收的調節表。每季證據有 6 張表；2024Q4 為 10-K 6 張加 Q3 10-Q 1 張，2025Q4 為 10-K 與 Q3 10-Q 各 6 張。

## 營收定義

保險分部的營收是承保保費加投資收益（表中 Total 欄）。投資與衍生工具損益、權益法投資收益不在營收內，列在稅前盈餘的調節表。

## 驗證

11 季（2023-12-31 至 2026-06-30）與對照資料逐期比對：

- 富途：以財年季別對齊，有資料的 8 季（2023Q4、2024Q1、2024Q4、2025Q1、2025Q2、2025Q4、2026Q1、2026Q2）8 類都在顯示精度內。
- TradingView：只有年度。FY2024、FY2025 的四季加總，8 類都在顯示精度內；FY2023、FY2026 在範圍內不足四季。
- Stock Analysis：沒有 BRK-B 的資料。
- 舊流程輸出（`segments`）：有輸出的 8 季（2024-09-30 起）數值完全一致。

## 跨期檢核

Corporate, eliminations and other 金額小（數億美元）、波動大，2024Q4 到 2025Q4 每季的 YoY 都超過 ±50%，各有一筆 YoY 標註。其餘分類沒有標註。
