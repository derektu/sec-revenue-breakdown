# HD parser

## 觀點

商品類別（`view="product"`），共 4 類：Hardlines、Building Materials、Décor、Other。

| 對照來源 | 列出的分類 |
|---|---|
| Stock Analysis | Hardlines、Building Materials、Décor，加上 Other |
| TradingView | Primary、Other（FY2024 起；更早的年度是商品部門） |
| 富途 | Primary Segment、其他（FY2024 Q3 以前為單一分部） |

HD 的營收約 92% 在 Primary 分部，Primary／Other 幾乎等於單一分部，看不出產品組成。所以採用 Stock Analysis 的商品類別（使用者核准）：三個商品類別拆分 Primary，Other 是 Primary 以外的分部。TradingView 與富途的 Primary 等於三個商品類別相加，Other 相同。

分類用到 `us-gaap:StatementBusinessSegmentsAxis`。HD 這個軸的成員是業務別：
- Primary：HD 的主要業務，商品類別只拆這個分部。
- Other：2024 年收購的 SRS 等業務。FY2024 10-K 揭露 SRS 收購後的營收 64 億美元，Other 是 64.06 億。

它們不是地區，所以採用。

HD 另有兩種營收拆分，都不採用：

| 拆分 | XBRL 維度 | 不採用的原因 |
|---|---|---|
| 10-K 的商品部門（Appliances、Paint、Plumbing… 共 16 個） | `srt:ProductOrServiceAxis` 搭配分部軸 | 只在 10-K 揭露，10-Q 沒有 |
| 美國／非美國 | `srt:StatementGeographicalAxis` | 地區拆分 |

## 分類與 tag

concept 是 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`。

| 分類 | 維度 |
|---|---|
| Hardlines | `srt:ProductOrServiceAxis=hd:MajorProductLineHardlinesMember`（兩分部期間另帶 Primary 分部，見下） |
| Building Materials | `srt:ProductOrServiceAxis=hd:MajorProductLineBuildingMaterialsMember` |
| Décor | `srt:ProductOrServiceAxis=hd:MajorProductLineDcorMember`；FY2023 10-K 是 `hd:MajorProductLineDecorMember`（`one_of`） |
| Other | `one_of`：分部 `us-gaap:AllOtherSegmentsMember`、`hd:OtherSegmentMember`（FY2024 Q3 10-Q 以前） |
| 總營收（Net sales） | 不帶維度 |

商品類別的定義以申報期末日分段，相鄰的生效期間首尾相接：

| 期末日 | 申報 | 商品類別 fact 的分部維度 |
|---|---|---|
| 2024-04-28 以前 | FY2024 Q1 10-Q 以前（單一分部，沒有 Other） | 不帶分部軸 |
| 2024-04-29 至 2025-02-01 | FY2024 Q2、Q3 10-Q | `one_of`：分部 `hd:PrimarySegmentMember`，帶或不帶 `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember` |
| 2025-02-02 | FY2024 10-K | 分部 `us-gaap:ReportableSegmentAggregationBeforeOtherOperatingSegmentMember` |
| 2025-02-03 起 | FY2025 10-Q 起 | 同 FY2024 Q2、Q3 的 `one_of` |

- FY2024 10-K 以報告分部合計成員標示 Primary。這個成員是全部報告分部的合計，只在 Primary 是唯一報告分部時等於 Primary，所以只用於這一期。
- FY2024 Q2、Q3 10-Q 與 FY2025 10-K 起的商品類別 fact 帶 `ConsolidationItemsAxis`，FY2025 各 10-Q 不帶。

- 各類加總等於總營收，沒有調節項。兩分部期間，三個商品類別相加等於分部表的 Primary。
- 分類名稱取自商品類別表的列標籤；總營收取自同表的 `Net sales`。

## 期別與推算

- 財年在 1 月底或 2 月初的星期日結束（52 或 53 週），例如 FY2024 期末 2025-02-02，FY2025 期末 2026-02-01。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同年 Q3 10-Q 的九個月累計，前提是年度與 Q1–Q3 的分類相同，且口徑沒有改變。
- FY：10-K 的年度 fact。

## 數字在原文的位置

營收附註的商品類別表：Building Materials、Décor、Hardlines、`Primary segment net sales`、`Other net sales` 與 `Net sales` 分列。Q1–Q3 與 FY 每期一張表；Q4 為 10-K 與 Q3 10-Q 各一張。

## 商品類別的重列

HD 每個財年都依新的部門歸類重列上一財年的商品類別數字（單位百萬美元）：

| 項目 | 原值 | 重列 | 來源申報 |
|---|---|---|---|
| FY2023 九個月 Building Materials | 44,214 | 40,907 | FY2024 Q3 10-Q |
| FY2023 九個月 Hardlines | 35,354 | 37,318 | FY2024 Q3 10-Q |
| FY2023 年度 Building Materials | 57,039 | 52,661 | FY2024 10-K |
| FY2023 年度 Hardlines | 45,335 | 48,063 | FY2024 10-K |
| FY2024 Q1 Hardlines | 11,460 | 11,281 | FY2025 Q1 10-Q |
| FY2024 Q2 Hardlines | 14,375 | 14,167 | FY2025 Q2 10-Q |
| FY2024 Q3 Hardlines | 11,128 | 10,927 | FY2025 Q3 10-Q |
| FY2024 年度 Décor | 51,790 | 52,525 | FY2025 10-K |
| FY2024 年度 Hardlines | 48,562 | 47,721 | FY2025 10-K |

- 總營收不受影響；兩分部期間 Primary 合計與 Other 也不受影響。
- 已上線的各期保留申報當時的數字，重列寫成差異標記，所以序列是各期申報當時的口徑。
- 10-K 列示的上一財年商品類別與先前的申報不同時，該年 Q4 不推算（`not_derived`）。在 10-K 申報時，只靠 XBRL fact 無法確認年度與 Q3 10-Q 的九個月累計是否同一口徑，所以這一期留空。

## 各財年的 Q4

| Q4 | 結果 | 原因 |
|---|---|---|
| FY2023（2024-01-28） | 推算 | FY2023 10-K 減 FY2023 Q3 10-Q 九個月；FY2023 10-K 列示的 FY2022 與 FY2022 10-K 相同，口徑一致 |
| FY2024（2025-02-02） | 不推算 | 年度有 Other，FY2024 Q1 沒有，分類不同；FY2024 10-K 另重列了 FY2023 |
| FY2025（2026-02-01） | 不推算 | FY2025 10-K 重列了 FY2024 的商品類別 |

## 驗證

11 季（2024-01-28 至 2026-08-02）中 FY2024 Q4 與 FY2025 Q4 不推算，9 季有輸出；另有 3 個年度（FY2023 至 FY2025）。與對照資料逐期比對（TradingView 與富途的 Primary 對三個商品類別的加總）：

| 來源 | 結果 |
|---|---|
| Stock Analysis | FY2023 Q4、FY2024 Q3 起各季在顯示精度內。FY2024 Q1、Q2 不同，見下 |
| 富途 | 各季相同。富途的期別標籤比 HD 的財年多一年（例如 FY2025 Q1 標為 2026/Q1） |
| TradingView（只有年度） | FY2024、FY2025 的 Primary 與 Other 都在顯示精度內 |

- Stock Analysis 的 FY2024 Q1 有 Other −100、Hardlines 11,560（我們沒有 Other、Hardlines 11,460）；FY2024 Q2 是 Hardlines 14,740、Other 914（我們 14,375、1,274）。HD 當時是單一分部，Other 不會是負數；富途的 FY2024 Q2 Other 也是 1,274。這兩期屬於 Stock Analysis 本身的差異。
- FY 序列：FY2023 只有 Q4 在範圍內，FY2024 與 FY2025 的 Q4 不推算，都不和四季加總比對。
