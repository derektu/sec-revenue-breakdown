# WMT parser

## 觀點

營運分部（`view="business_segment"`），共 4 類：Walmart U.S.、Walmart International、Sam's Club U.S.、Membership and other income。

| 對照來源 | 列出的分類 | 口徑 |
|---|---|---|
| TradingView | 三個分部與 Membership and Other | 分部淨銷售額，會員費及其他收入另列一類 |
| 富途 | 三個分部與企業和支持（2024 年 Q3 至 2025 年 Q1 另有會員制和其他收入） | 分部總營收（含會員費） |
| Stock Analysis | 沒有 WMT 的分類資料 | |

兩個來源各用一種口徑。採用 TradingView 的分部淨銷售額加會員費及其他收入，因為：
- 分部總營收（`us-gaap:Revenues` 帶分部軸）只從 FY2025 10-K 起揭露，更早的申報沒有，無法組成 FY2025 以前的季度與 Q4。
- 分部淨銷售額在每份申報都有。

分部取自 `us-gaap:StatementBusinessSegmentsAxis`。WMT 這個軸的成員是業務別：美國的 Walmart 門市與電商、美國以外的零售業務、會員制倉儲 Sam's Club。Walmart International 是一個業務分部，指美國以外的零售業務，不是地區拆分，所以採用。

## 分類與 tag

| 分類 | concept | 維度 |
|---|---|---|
| Walmart U.S. | `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax` | 分部 `one_of`：`wmt:WalmartUSMember`、`wmt:WalmartUSSegmentMember` |
| Walmart International | 同上 | 分部 `one_of`：`wmt:WalmartInternationalMember`、`wmt:WalmartInternationalSegmentMember` |
| Sam's Club U.S. | 同上 | 分部 `one_of`：`wmt:SamsClubUSMember`、`wmt:SamsClubSegmentMember`、`wmt:SamsClubMember` |
| Membership and other income | `us-gaap:OtherIncome` | 不帶維度 |
| 總營收（Total revenues） | `us-gaap:Revenues` | 不帶維度 |

- 分部成員在申報之間有不同名稱，數字是同一列，所以以 `one_of` 列出：10-Q 多用 `...SegmentMember`，10-K 與部分 10-Q 用 `...Member`；FY2024 10-K 的 Sam's Club 是 `wmt:SamsClubMember`。
- 分部 fact 只帶分部軸。部分申報另有同數字、多帶 `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember` 的寫法，規格不用它：較早的申報沒有這種寫法。
- 四類加總等於總營收，沒有調節項。
- 分類名稱：三個分部取自分部淨銷售額表的標題，Membership and other income 與總營收取自損益表的列標籤。

## 期別與推算

- 財年在 1 月 31 日結束，例如 FY2025 期末 2025-01-31；季末日是 4、7、10 月的最後一天。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同年 Q3 10-Q 的九個月累計，前提是年度與 Q1–Q3 的分類相同，且口徑沒有改變。
- FY：10-K 的年度 fact。

## 數字在原文的位置

- 分部淨銷售額：附註的分部營收表（各分部 net sales）。
- Membership and other income 與總營收：損益表 `Revenues:` 段。
- Q1–Q3 與 FY 每期有分部表與損益表；Q4 為 10-K 與 Q3 10-Q 各一組。

## 驗證

11 季（2024-01-31 至 2026-07-31）與 3 個年度（FY2024 至 FY2026）。

| 來源 | 結果 |
|---|---|
| TradingView（只有年度） | FY2024 至 FY2026 四類都在顯示精度內。TradingView 的年度標籤比 WMT 的財年少一年（例如 FY2026 標為 2025） |
| 富途 | 分部總營收含會員費，口徑不同，不逐類比對 |

- FY 序列：FY2025、FY2026 都等於同財年四季加總。FY2024 只有 Q4 在範圍內，不比對。
- 沒有差異標記：各申報的比較欄與已上線輸出都在精度內相同。
