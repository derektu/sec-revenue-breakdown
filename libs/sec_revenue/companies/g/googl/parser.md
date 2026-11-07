# GOOGL parser

## 觀點

營收類型別（`view="product"`），共 7 類，依 Stock Analysis 的順序：Google Search & other、Google Cloud、Google subscriptions, platforms, and devices、YouTube ads、Google Network、Other Bets、Hedging gains (losses)。這是 Alphabet 營收附註「revenues by type」表的各列：Google Services 拆成四項產品，Google Cloud 與 Other Bets 是分部，Hedging gains (losses) 是不屬於任何分部的避險損益。

| 對照來源 | 拆分 | 名稱對應 |
|---|---|---|
| Stock Analysis（季度） | 同樣的 7 類 | Google Search & Other、Google Cloud、Google Subscriptions, Platforms & Devices、YouTube Ads、Google Network、Other Bets、Hedging Gains |
| 富途（季度） | 業務分部：谷歌服務、Google Cloud、其他押注、套期保值收益(損失) | 谷歌服務 ＝ 前四項產品之和 |
| TradingView（只有年度） | 業務分部：Google Services、Google Cloud、Other Bets、Reconciling Items（FY2024 有值，FY2025 沒有列） | Reconciling Items ＝ Hedging gains (losses) |

採用營收類型別：三個來源都能從申報重現，這組拆分把 Google Services 再細分成四項產品，業務分部的每一類都可由它加總得到。Hedging gains (losses) 是分類：採用觀點的來源（Stock Analysis）每期都列出它。

`us-gaap:StatementBusinessSegmentsAxis` 的成員是業務別（`goog:GoogleServicesMember`、`goog:GoogleCloudMember`、`us-gaap:AllOtherSegmentsMember` 即 Other Bets），不是地區。

不採用的拆分：

| 拆分 | XBRL 維度 | 不採用的原因 |
|---|---|---|
| Google advertising（Search & other、YouTube ads、Google Network 的小計） | `srt:ProductOrServiceAxis=goog:GoogleAdvertisingRevenueMember` | 是三項產品的小計，不是另一個分類 |
| 地區（United States、EMEA、APAC、Other Americas） | `srt:StatementGeographicalAxis` | 地區拆分 |

## 分類與 tag

Google Services 的四項產品與兩個分部的 concept 都是 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`，每份申報寫法相同：

| 分類 | dimensions |
|---|---|
| Google Search & other | `srt:ProductOrServiceAxis=goog:GoogleSearchOtherMember`、`us-gaap:StatementBusinessSegmentsAxis=goog:GoogleServicesMember` |
| Google Cloud | `us-gaap:StatementBusinessSegmentsAxis=goog:GoogleCloudMember` |
| Google subscriptions, platforms, and devices | `srt:ProductOrServiceAxis=goog:SubscriptionsPlatformsAndDevicesRevenueMember`、`us-gaap:StatementBusinessSegmentsAxis=goog:GoogleServicesMember` |
| YouTube ads | `srt:ProductOrServiceAxis=goog:YouTubeAdvertisingRevenueMember`、`us-gaap:StatementBusinessSegmentsAxis=goog:GoogleServicesMember` |
| Google Network | `srt:ProductOrServiceAxis=goog:GoogleNetworkMember`、`us-gaap:StatementBusinessSegmentsAxis=goog:GoogleServicesMember` |
| Other Bets | `us-gaap:StatementBusinessSegmentsAxis=us-gaap:AllOtherSegmentsMember` |

Hedging gains (losses) 與總營收（Total revenues）都不帶維度，concept 在期末 2025-06-30 的 10-Q（0001652044-25-000062）改變：

| 項目 | 到期末 2025-03-31 的 10-Q（0001652044-25-000043）為止 | 期末 2025-06-30 的 10-Q 起 |
|---|---|---|
| Hedging gains (losses) | `us-gaap:GainLossOnOilAndGasHedgingActivity` | `us-gaap:RevenueNotFromContractWithCustomer` |
| 總營收 | `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax` | `us-gaap:Revenues` |

- 每份申報（含比較欄）只有其中一種寫法，parser 以 `one_of` 在每份申報都找兩種。舊寫法的 concept 名稱與內容不符（油氣避險、客戶合約營收），但它們就是原文 Hedging gains (losses) 與 Total revenues 兩列標記的 fact；舊寫法的總營收含避險損益，等於分類加總。
- 兩種寫法在重疊期別相等（原申報的舊寫法 → 較晚申報比較欄的新寫法；較晚的申報只作證據）：

  | 期間 | 原申報（舊寫法） | 較晚申報（新寫法） | Hedging | 總營收 |
  |---|---|---|---|---|
  | 2024 年 Q2 | 0001652044-24-000079 | 0001652044-25-000062 | 102 | 84,742 |
  | 2024 年 Q3 | 0001652044-24-000118 | 0001652044-25-000091 | 17 | 88,268 |
  | 2024 年前九個月 | 0001652044-24-000118 | 0001652044-25-000091 | 191 | 253,549 |
  | FY2024 | 0001652044-25-000014 | 0001652044-26-000018 | 211 | 350,018 |
  | FY2023 | 0001652044-24-000022 | 0001652044-26-000018 | 236 | 307,394 |
  | 2025 年 Q1 | 0001652044-25-000043 | 0001652044-26-000048 | 260 | 90,234 |

  單位：百萬美元。
- `categories` 每一天都是這 7 類，涵蓋 FY2023 期末（2023-12-31）以後；營收類型表的 7 列在 FY2023 10-K（0001652044-24-000022）以來每份申報都相同。
- 7 類加總等於總營收，沒有調節項。
- 分類名稱取自營收類型表的列標籤，10-K 與 10-Q 寫法相同；總營收取自同表的 `Total revenues`。

## 期別與推算

- 財年即曆年，季末日是 3、6、9、12 月的最後一天。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同年 Q3 10-Q 的九個月累計。2024 年 Q4 的兩個運算元都是舊寫法，2025 年 Q4 都是新寫法。年度與 Q1–Q3 的分類相同，範圍內每個 Q4 都推算。
- FY：10-K 的年度 fact。
- 2024 年 Q4 的口徑依據是 FY2023 10-K（0001652044-24-000022）組出的 FY2023 年度值；2025 年 Q4 用已上線的 FY2024，與 FY2025 10-K 比較欄的新寫法比對。

## 數字在原文的位置

營收附註的營收類型表（「Revenues by type」），7 類、Google advertising 與 Google Services 小計、Total revenues 同表；同一組數字也標在分部附註的分部營收表。證據取自營收類型表：

| 申報 | 表格 |
|---|---|
| 10-Q 2024-03-31（0001652044-24-000053） | t24 |
| 10-Q 2024-06-30（0001652044-24-000079） | t27 |
| 10-Q 2024-09-30（0001652044-24-000118） | t27 |
| 10-K FY2024（0001652044-25-000014） | t99 |
| 10-Q 2025-03-31（0001652044-25-000043） | t24 |
| 10-Q 2025-06-30（0001652044-25-000062） | t27 |
| 10-Q 2025-09-30（0001652044-25-000091） | t27 |
| 10-K FY2025（0001652044-26-000018） | t94 |
| 10-Q 2026-03-31（0001652044-26-000048） | t23 |
| 10-Q 2026-06-30（0001652044-26-000071） | t28 |
| 10-Q 2026-09-30（0001652044-26-000084） | t28 |

Q4 的證據是 10-K 年度表與 Q3 10-Q 九個月欄所在的表。FY2023 10-K（0001652044-24-000022）只作 2024 年 Q4 的口徑依據，營收類型表是 t98。

## 驗證

11 季（2024-03-31 至 2026-09-30）與 2 個年度，與 Stock Analysis 逐期比對：

- 11 季 7 類中，除下列兩筆外都在顯示精度內。
- 2024-06-30 的 Hedging gains (losses)：我們 102M，Stock Analysis 3.00M。判定為來源錯誤：(a) 10-Q 0001652044-24-000079 營收類型表（t27）該列為 102，本期加總檢核通過；(b) 較晚的 10-Q 0001652044-25-000062 比較欄列示 102，沒有重列；(c) 富途同期為 1.02 億，與我們一致。Stock Analysis 的 3.00M 等於 2023 年 Q2 的值。
- 2025-12-31 的 Hedging gains (losses)：我們 -67M，Stock Analysis -68.00M。差異來自捨入：我們的 Q4 是 FY2025 10-K 的年度 -127 減 Q3 10-Q 的九個月累計 -60；Stock Analysis 的值等於年度減三季加總（260 − 112 − 207 = -59）。九個月累計與三季加總各自捨入到百萬，相差 1M。富途同期為 -6,700 萬，與我們一致。
- Stock Analysis 只有季度，FY 序列不比對。

其他來源（不作採用來源，只作補充）：富途 11 季的四個業務分部，與我們前四項產品之和、Google Cloud、Other Bets、Hedging gains (losses) 都在顯示精度內；TradingView FY2024、FY2025 的 Google Services、Google Cloud、Other Bets 與 FY2024 的 Reconciling Items 一致。

## 比較欄

沒有差異標記：各申報的比較欄（含兩種寫法跨申報的期別）與已上線輸出都在精度內相同。
