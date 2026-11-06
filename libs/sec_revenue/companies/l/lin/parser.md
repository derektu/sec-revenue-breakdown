# LIN parser

## 觀點

業務別（`view="business_segment"`），共 3 類：Industrial Gases、Engineering、Other。

| 對照來源 | 列出的分類 |
|---|---|
| TradingView | Industrial Gases、Engineering、Other |
| Stock Analysis | Americas、EMEA、APAC、Engineering、Other |
| 富途 | 與 Stock Analysis 相同 |

分部取自 `us-gaap:StatementBusinessSegmentsAxis`，成員有兩種：
- 工業氣體業務的 3 個報告分部，依地區劃分：Americas、EMEA、APAC。
- 業務別：Engineering（工廠設計與建造），以及 Other（`us-gaap:CorporateAndOtherMember`）。

地區拆分不是觀點，所以三個地區分部加總成一類 Industrial Gases，與 TradingView 相同。Stock Analysis 與富途的地區三類加總後就是這一類。

## 分類與 tag

concept 是 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`。分部 fact 帶 `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember` 與分部成員。

| 分類 | 加數 |
|---|---|
| Industrial Gases | `lin:AmericasSegmentMember` ＋ `lin:EMEASegmentMember` ＋ `lin:APACSegmentMember`（三個 fact 相加） |
| Engineering | `lin:EngineeringSegmentMember` |
| Other | `us-gaap:CorporateAndOtherMember` |
| 總營收（Sales） | 不帶維度 |

- 所有申報用同一種寫法，parser 不依申報期末日切換；`categories` 每一天都是這三類。
- 三類加總等於總營收，沒有調節項。
- 分類名稱：Industrial Gases 沿用 TradingView 的名稱。Engineering、Other 取自分部表的欄名；總營收取自損益表的 `Sales`。

## 期別與推算

- 財年即曆年，季末日是 3、6、9、12 月的最後一天。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同年 Q3 10-Q 的九個月累計。年度與 Q1–Q3 的分類相同，範圍內每個 Q4 都推算。
- FY：10-K 的年度 fact。

## 數字在原文的位置

- 分類：附註分部表（Americas、EMEA、APAC、Engineering、Other、Total 分欄），數字在 `Sales` 列。
- 總營收：損益表的 `Sales` 列。
- 每期證據有兩張表；Q4 是 10-K 與 Q3 10-Q 各兩張。

## 2026 年 Q3 的重分類

2026 年 Q3 10-Q 把一部分 Americas 的營收改列 Other，並重列比較數字：
- 2025 年 Q3：Americas 減少 593，Other 增加 593，總營收不變。
- 2025 年九個月累計：Americas 減少 1,767，Other 增加 1,767。
- 單位為百萬美元；EMEA、APAC 與 Engineering 不受影響。

這次重分類對各期的影響：
- **2025 年 Q4（2025-12-31）**：年度與九個月都是舊歸類，不受影響。
- **2026 年 Q1、Q2**：已上線的是舊歸類，Q3 是新歸類，Other 由約 4 億跳到 9.44 億。
- **2026 年 Q4**：2026 年 Q3 10-Q 已重列 2025 年的九個月累計；FY2026 10-K 若同樣重列 FY2025，年報列示的上一財年會與已上線的 FY2025 不同，這一期預期會因口徑一致的條件不成立而不推算。

2025 年 Q3 與 2025 年 Q4 的九個月運算元寫成差異標記（見比較欄）。

## 驗證

11 季（2024-03-31 至 2026-09-30）與 2 個年度，與對照資料逐期比對（Stock Analysis 與富途的地區三類先加總成 Industrial Gases）：

| 來源 | 結果 |
|---|---|
| TradingView（只有年度） | FY2024、FY2025 三類都在顯示精度內 |
| Stock Analysis | 11 季全部相同 |
| 富途 | 除 2025 年 Q3 外都相同。2025 年 Q3 是新歸類的值（Industrial Gases 7,172、Other 924，我們 7,765、331） |

- 唯一的差異來自 2026 年 Q3 的重分類：富途用了事後申報的新歸類數字，我們用申報當時的原值。
- FY 序列：FY2024、FY2025 都等於同財年四季加總。

## 比較欄

差異標記都是 2026 年 Q3 重分類造成的（單位百萬美元）：

| 期別 | 運算元 | 已上線值 → 申報列示值（Industrial Gases／Other） | 來源申報 |
|---|---|---|---|
| 2025-09-30 | 單季 | 7,765 → 7,172／331 → 924 | 2026 年 Q3 10-Q |
| 2025-12-31 | 九個月 | 22,630 → 20,863／957 → 2,724 | 2026 年 Q3 10-Q |

其他申報的比較欄與已上線輸出都在精度內相同。
