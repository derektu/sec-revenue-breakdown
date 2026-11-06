# JPM parser

## 觀點

營運分部（`view="business_segment"`），共 4 類加 1 個調節項：
- 分類：Consumer & Community Banking、Commercial & Investment Bank、Asset & Wealth Management、Corporate。2024 年 Q1 是舊的分部結構，Commercial & Investment Bank 的位置是 Corporate & Investment Bank 與 Commercial Banking 兩類。
- 調節項：Reconciling items。

| 對照來源 | 列出的分類 |
|---|---|
| Stock Analysis | 三個分部與 Corporate（2024 年 Q1 以前是舊的四個分部） |
| TradingView | 三個分部與 Corporate Segment（FY2023 以前是舊的四個分部） |
| 富途 | 三個分部、公司與對賬項目 |

- Corporate 三個來源都列出，列成分類。
- Reconciling items 只有富途列出，宣告為 `reconciling`，參與加總但不輸出成分類。

分部取自 `us-gaap:StatementBusinessSegmentsAxis`。JPM 這個軸的成員是業務別：消費金融、企業與投資銀行、資產與財富管理。它們不是地區，所以採用。

## 分類與 tag

concept 是 `us-gaap:RevenuesNetOfInterestExpense`（Total net revenue）。

| 分類 | 維度 | 期末日 |
|---|---|---|
| Consumer & Community Banking | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`＋分部 `jpm:ConsumerCommunityBankingMember` | 全部 |
| Commercial & Investment Bank | 同上，分部 `one_of`：`jpm:CommercialAndInvestmentBankMember`、`jpm:CorporateAndInvestmentBankMember` | 2024-04-01 起 |
| Corporate & Investment Bank | 同上，分部 `jpm:CorporateAndInvestmentBankMember` | 2024-03-31 以前 |
| Commercial Banking | 同上，分部 `jpm:CommercialBankingMember` | 2024-03-31 以前 |
| Asset & Wealth Management | 同上，分部 `jpm:AssetandWealthManagementSegmentMember` | 全部 |
| Corporate | `srt:ConsolidationItemsAxis=us-gaap:CorporateNonSegmentMember` | 全部 |
| Reconciling items（調節項） | `srt:ConsolidationItemsAxis=us-gaap:MaterialReconcilingItemsMember` | 全部 |
| 總營收（Total net revenue） | 不帶維度 | 全部 |

- 2024 年 Q2 起，Corporate & Investment Bank 與 Commercial Banking 合併為 Commercial & Investment Bank。2024 年 Q2、Q3 的 10-Q 沿用 `jpm:CorporateAndInvestmentBankMember` 標示合併後的分部，FY2024 10-K 起改用 `jpm:CommercialAndInvestmentBankMember`。同一個成員在合併前後代表不同範圍，所以以申報期末日分段定義。相鄰定義的生效期間首尾相接。
- 分部營收是 managed basis，免稅收入以稅負等價（FTE）計入。Reconciling items 主要是這項調整，把分部合計調回報告的總營收。
- 四類（2024 年 Q1 為五類）加上 Reconciling items 等於總營收。
- 分類名稱取自分部表的欄名；總營收取自同表的 `Total net revenue` 列、`Total` 欄。

## 期別與推算

- 財年即曆年，季末日是 3、6、9、12 月的最後一天。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同年 Q3 10-Q 的九個月累計，前提是年度與 Q1–Q3 的分類相同，且口徑沒有改變。
- FY：10-K 的年度 fact。
- 2024 年 Q4 不推算：FY2024 是合併後的分部，2024 年 Q1 是舊的分部，分類不同。

## 數字在原文的位置

分部表（Segment results and reconciliation）分成兩段：三個分部一段，Corporate、Reconciling Items 與 Total 一段，數字都在 `Total net revenue` 列。Q1–Q3 與 FY 每期兩張表；Q4 為 10-K 與 Q3 10-Q 各兩張。

## 驗證

11 季（2024-03-31 至 2026-09-30，2024 年 Q4 不推算）與 2 個年度，與對照資料逐期比對：

| 來源 | 結果 |
|---|---|
| Stock Analysis | 各季在顯示精度內 |
| TradingView（只有年度） | FY2024、FY2025 都在顯示精度內 |
| 富途 | 各季相同，2024 年 Q1 除外：富途的 2024 年 Q1 是合併後的分部（事後重列的數字），我們是申報當時的舊分部 |

- FY 序列：FY2025 等於同財年四季加總。FY2024 的 Q4 不推算，不比對。
- 沒有差異標記：各申報的比較欄與已上線輸出都在精度內相同。
