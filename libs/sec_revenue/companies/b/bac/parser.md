# BAC parser

## 觀點

營運分部（`view="business_segment"`），共 5 類：Consumer Banking、Global Wealth & Investment Management、Global Banking、Global Markets、All Other。

| 對照來源 | 列出的分類 |
|---|---|
| Stock Analysis | 四個分部，加上 Other |
| 富途 | 四個分部，加上「所有其他」；部分季度另有 Tax-exempt securities（FTE 調整） |
| TradingView | 只有四個分部 |

分部取自 `us-gaap:StatementBusinessSegmentsAxis`。BAC 這個軸的成員是業務別：消費金融、財富管理、企業金融、交易業務。它們不是地區，所以採用。

All Other 是公司層級的調節項與抵銷（`bac:CorporateReconcilingItemsAndEliminationsMember`），數值常為負。兩個對照來源把它列成一類，所以它是分類，不是 `reconciling`。

## 分類與 tag

concept 是 `bac:RevenuesNetOfInterestExpenseFullTaxEquivalentBasis`（扣除利息費用後的總營收，FTE 口徑）。

| 分類 | 維度 |
|---|---|
| Consumer Banking | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`＋分部 `bac:ConsumerBankingSegmentMember` |
| Global Wealth & Investment Management | 同上，分部 `bac:GlobalWealthAndInvestmentManagementSegmentMember` |
| Global Banking | 同上，分部 `bac:GlobalBankingSegmentMember` |
| Global Markets | 同上，分部 `bac:GlobalMarketsSegmentMember` |
| All Other | `srt:ConsolidationItemsAxis=bac:CorporateReconcilingItemsAndEliminationsMember` |
| 總營收（Total revenue, net of interest expense） | 不帶維度 |

- 所有期別都使用同一組定義，沒有 `effective` 分段。
- 五類加總等於總營收，沒有調節項。
- 總營收是 FTE 口徑：分部表的 Total Corporation 欄。它比損益表的 GAAP 總營收多出 FTE 調整（2024 年 Q1 為 1.58 億美元）。分部營收只有 FTE 口徑，所以總營收也取 FTE，加總才一致。
- 分類名稱取自分部表的欄名；總營收取自同表的列標籤 `Total revenue, net of interest expense`。

## 期別與推算

- 財年即曆年，季末日是 3、6、9、12 月的最後一天。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同年 Q3 10-Q 的九個月累計，前提是年度與 Q1–Q3 的分類相同，且口徑沒有改變。2025 年 Q4 不推算（見下節）。
- FY：10-K 的年度 fact。

## 數字在原文的位置

附註的「Results of Business Segments and All Other」表：

- Total Corporation 與各分部、All Other 分欄列出。
- 數字在 `Total revenue, net of interest expense` 列。
- Q1–Q3 與 FY 每期一張表；Q4 為 10-K 與 Q3 10-Q 各一張。

## 2025 年 Q4 的會計方法變更

BAC 自 2025 年 Q4 起變更租稅抵減投資的會計方法，並追溯適用，影響 Global Banking、Global Markets、All Other 與總營收。

- 2025 年度 10-K 的年度數字是新方法；它把 FY2024 的比較數字也改用新方法。
- 2025 年 Q3 10-Q 的九個月累計是舊方法。

- 10-K 列示的 FY2024 與已上線的 FY2024 不同（Global Banking 23,958 → 23,748、All Other −7,629 → −3,450、總營收 102,506 → 106,475，單位百萬美元），代表年度與 Q3 10-Q 的九個月累計是不同口徑，所以 2025 年 Q4（2025-12-31）不推算（`not_derived`）。
- Consumer Banking 與 GWIM 不受影響。
- 新方法的九個月累計最早出現在 2026 年 Q3 10-Q 的比較欄（申報日 2026-10-30），晚於 2025 年度 10-K，不能回頭用來推算。
- 2025 年 Q4 財報新聞稿（8-K）的附件列出新方法的 Q4 分部營收。它不是 XBRL，不作為運算元。
- 2026 年各 10-Q 與 2025 年度 10-K 的比較欄和已上線值的差異，都寫成差異標記（見比較欄）。

## 驗證

11 季（2024-03-31 至 2026-09-30，2025 年 Q4 不推算）與 2 個年度，與對照資料逐期比對（單位百萬美元）：

| 來源 | 結果 |
|---|---|
| TradingView（只有年度，四個分部） | FY2024、FY2025 都在顯示精度內 |
| Stock Analysis | 都相同（2025 年 Q4 我們不推算） |
| 富途 | 2024 年 Q1–Q3 與 2026 年都相同；2025 年 Q4 我們不推算。2025 年 Q1–Q3 是新方法的值（與差異標記的申報列示值相同）。2024 年 Q4 是新方法的 FY2024 年度減舊方法的九個月（Global Banking 23,748 − 17,867 ＝ 5,881，所有其他 2,101） |

- 所有差異都來自 2025 年 Q4 的會計方法變更：對照來源用了事後申報的新方法數字，我們用申報當時的原值。
- 富途的 Tax-exempt securities 是 FTE 調整，不是分部，不對應我們的分類。
- FY 序列：FY2024 等於同財年四季加總。FY2025 的 Q4 不推算，不比對。

## 比較欄

差異標記都是 2025 年 Q4 的會計方法變更造成的：

| 期別 | 運算元 | 有差異的分類（已上線值 → 申報列示值） | 來源申報 |
|---|---|---|---|
| FY 2024-12-31、Q 2024-12-31 | 年度 | Global Banking 23,958 → 23,748；All Other −7,629 → −3,450；總營收 102,506 → 106,475 | 2025 年度 10-K |
| 2025-03-31 | 單季 | Global Banking 5,977 → 5,992；All Other −1,559 → −694；總營收 27,511 → 28,392 | 2026 年 Q1 10-Q |
| 2025-06-30 | 單季 | Global Markets 5,980 → 5,982；All Other −1,812 → −833；總營收 26,608 → 27,588 | 2026 年 Q2 10-Q |
| 2025-09-30 | 單季 | Global Banking 6,245 → 6,189；All Other −1,705 → −698；總營收 28,242 → 29,194 | 2026 年 Q3 10-Q |

- 2024 年 Q1–Q3 沒有差異標記。2025 年各 10-Q 的比較欄申報於會計方法變更之前，與原值相同。
- 其他申報的比較欄與已上線輸出都在精度內相同。
