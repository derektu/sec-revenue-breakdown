# COST parser

## 觀點

產品別（`view="product"`），共 5 類，依序：Foods and Sundries、Non-Foods、Warehouse Ancillary and Other Businesses、Fresh Foods、Membership fees。

前四類是商品類別的淨銷售額（net sales），加總等於損益表的 Net sales；Membership fees 是會員費，與 Net sales 相加等於總營收。

| 對照來源 | 列出的分類 | 對應 |
|---|---|---|
| TradingView（只有年度） | Foods and Sundries、Non-Foods、Warehouse Ancillary and Other Businesses、Fresh Foods | 前四類，名稱與順序相同；沒有列會員費 |
| Stock Analysis（只有季度） | Net Sales、Membership Fees | Net Sales ＝ 前四類加總；Membership Fees ＝ Membership fees |
| 富途 | 會員制倉庫經營（只有一列） | 總營收 |

採用 TradingView 的四類商品，再列 Membership fees 為分類：會員費是總營收的一部分，Stock Analysis 也把它單獨列出，列成分類讓五類加總等於總營收。

申報中另有營運分部的營收（United States、Canada、Other International），不採用：

| 拆分 | XBRL 維度 | 不採用的原因 |
|---|---|---|
| 營運分部：United States、Canada、Other International | FY2025 10-K 以前為 `srt:StatementGeographicalAxis`（`country:US`、`country:CA`、`cost:OtherInternationalOperationsMember` 或 `cost:OtherInternationalMember`），FY2025 10-K 起為 `us-gaap:StatementBusinessSegmentsAxis`（`cost:UnitedStatesMember`、`cost:CanadaMember`、`cost:OtherInternationalMember`），都搭配 `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember` | 分部是地區拆分 |

## 分類與 tag

所有分類與總營收都是 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`；分類只帶一個維度 `srt:ProductOrServiceAxis`：

| 分類 | 成員 |
|---|---|
| Foods and Sundries | 10-Q `cost:FoodsAndSundriesMember`；10-K `cost:FoodandSundriesMember` |
| Non-Foods | `cost:NonFoodsMember` |
| Warehouse Ancillary and Other Businesses | `cost:OtherMember` |
| Fresh Foods | 10-Q `cost:FreshFoodsMember`；10-K `cost:FreshFoodMember` |
| Membership fees | `us-gaap:MembershipMember` |
| 總營收（Total revenue） | 不帶維度 |

- Foods and Sundries 與 Fresh Foods 在 10-Q 與 10-K 用不同成員，數字是同一列，所以兩種寫法都找（`one_of`）；已下載的每一份 10-Q 都是 `FoodsAndSundries`／`FreshFoods`，每一份 10-K 都是 `FoodandSundries`／`FreshFood`，同一份申報不會兩種都有。
- 總營收用不帶維度的 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`，它在每一份申報的損益表都有。不帶維度的 `us-gaap:Revenues` 只在 2026-02-15 10-Q 及更早的申報出現，不用。
- `us-gaap:ProductMember`（損益表的 Net sales）不用：它等於四類商品的加總，列入會重複計算。
- parser 不依日期或申報切換寫法；`categories` 每一天都回答這五類。已下載的 FY2023 10-K（0000909832-23-000042，期末 2023-09-03，範圍內第一個財年的上一財年）到 FY2026 10-K（0000909832-26-000093，期末 2026-08-30）都是這個結構，所以涵蓋下限是 2023-09-03 以後的每一天。
- 五類加總等於總營收，沒有調節項。
- 分類名稱：四類商品取自附註淨銷售額表（10-Q、10-K 同名）的列標籤；Membership fees 與總營收取自損益表 `REVENUE` 段的列標籤。輸出順序照 TradingView，與附註表的列順序（Foods and Sundries、Non-Foods、Fresh Foods、Warehouse Ancillary and Other Businesses）不同。

## 期別與推算

- 財年採 52／53 週制，在最接近 8 月底的星期日結束，例如 FY2024 期末 2024-09-01、FY2025 期末 2025-08-31、FY2026 期末 2026-08-30；範圍內三個財年都是 52 週，FY2023（期末 2023-09-03）是 53 週。
- 季度是 12／12／12／16 週：Q1–Q3 各 12 週（84 天），Q4 16 週（112 天）；53 週年度的 Q4 是 17 週。10-Q 的累計欄是 24 週與 36 週（252 天）。
- 期間範圍以 `DURATION_DAYS` 自訂：單季 84–119 天（12 週到 17 週）、六個月 168 天（24 週）、九個月 252 天（36 週）、年度 364–371 天（52 或 53 週）。框架的預設單季上限是 98 天（14 週），16、17 週的 Q4 不在預設範圍內，所以需要自訂。範圍取涵蓋上述長度的最窄範圍：累計欄與年度的長度由季度週數決定，不會落在這些值以外。
- Q1–Q3：10-Q 中 12 週期間的 fact。
- Q4：10-K 年度減去同財年 Q3 10-Q 的 36 週累計。年度與 Q1–Q3 的分類相同，年報列示的上一財年數字與先前申報相同，範圍內每個 Q4 都推算。FY2024 Q4 的口徑依據是 FY2023 10-K（0000909832-23-000042）。
- FY：10-K 的年度 fact。
- 每份 10-Q 宣告的財年都等於前一份 10-K 宣告的財年加 1，沒有 `fiscal_year_basis`。

## 數字在原文的位置

每期的證據是兩張表：四類商品在附註的淨銷售額表，Membership fees 與總營收在損益表。

| 申報 | 損益表 | 淨銷售額表 |
|---|---|---|
| 10-Q 0000909832-24-000017（2024-02-18） | t6 | t22 |
| 10-Q 0000909832-24-000029（2024-05-12） | t6 | t22 |
| 10-K 0000909832-24-000049（2024-09-01） | t26 | t55 |
| 10-Q 0000909832-24-000079（2024-11-24） | t6 | t21 |
| 10-Q 0000909832-25-000015（2025-02-16） | t6 | t22 |
| 10-Q 0000909832-25-000033（2025-05-11） | t6 | t22 |
| 10-K 0000909832-25-000101（2025-08-31） | t26 | t55 |
| 10-Q 0000909832-25-000169（2025-11-23） | t6 | t23 |
| 10-Q 0000909832-26-000029（2026-02-15） | t6 | t24 |
| 10-Q 0000909832-26-000051（2026-05-10） | t6 | t24 |
| 10-K 0000909832-26-000093（2026-08-30） | t26 | t57 |
| 10-K 0000909832-23-000042（2023-09-03），只作 FY2024 Q4 口徑依據，沒有證據檔 | t26 | t55 |

Q4 的證據是 10-K 與 Q3 10-Q 各兩張表。

## 已知的重複 fact

2026-05-10 10-Q（0000909832-26-000051）與 FY2026 10-K（0000909832-26-000093）的分部營收表以不帶維度的 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax` 標示合計（10-Q t21、10-K t55），與損益表的總營收數值相同。框架選用損益表的 fact，分部表的 fact 記在運算元的 `duplicates`。更早的申報的分部表合計用 `us-gaap:Revenues`，不是重複 fact。

## 驗證

範圍是 11 季（2024-02-18 至 2026-08-30）與 3 個年度（FY2024 至 FY2026）。

**TradingView（採用的來源，只有年度）**：TradingView 以財年多數月份所在的曆年標示，COST 的財年標結束的那一年（FY2026 標 2026）。FY2024、FY2025、FY2026 的四類商品都在顯示精度內（0.01B）：

| 年度 | Foods and Sundries | Non-Foods | Warehouse Ancillary and Other Businesses | Fresh Foods |
|---|---|---|---|---|
| FY2024 | 101,463M／101.46B | 63,973M／63.97B | 49,969M／49.97B | 34,220M／34.22B |
| FY2025 | 109,564M／109.56B | 71,190M／71.19B | 51,170M／51.17B | 37,988M／37.99B |
| FY2026 | 116,788M／116.79B | 77,375M／77.38B | 61,369M／61.37B | 41,715M／41.72B |

TradingView 沒有會員費，Membership fees 不比對。季度依規則不與 TradingView 比對。

**Stock Analysis（補充，季度）**：Stock Analysis 把期末日對齊到曆年季底（2024-02-18 標 Mar 31, 2024、2024-11-24 標 Dec 31, 2024）。以 Net Sales 對四類商品加總、Membership Fees 對 Membership fees 逐季比對，11 季都在顯示精度內（0.01B，加上運算元精度誤差；Q4 每個運算元有年度與 36 週兩個）：

| 期末 | 四類加總／Net Sales | Membership fees／Membership Fees |
|---|---|---|
| 2024-02-18 | 57,331M／57.33B | 1,111M／1.11B |
| 2024-05-12 | 57,392M／57.39B | 1,123M／1.12B |
| 2024-09-01（Q4） | 78,185M／78.19B | 1,512M／1.51B |
| 2024-11-24 | 60,985M／60.99B | 1,166M／1.17B |
| 2025-02-16 | 62,530M／62.53B | 1,193M／1.19B |
| 2025-05-11 | 61,965M／61.97B | 1,240M／1.24B |
| 2025-08-31（Q4） | 84,432M／84.43B | 1,724M／1.72B |
| 2025-11-23 | 65,978M／65.98B | 1,329M／1.33B |
| 2026-02-15 | 68,242M／68.24B | 1,355M／1.36B |
| 2026-05-10 | 69,154M／69.15B | 1,373M／1.37B |
| 2026-08-30（Q4） | 93,873M／93.87B | 1,850M／1.85B |

**富途（補充，總營收）**：以財年季別對齊，FY2024 Q2、FY2025 Q1–Q4、FY2026 Q1–Q4 共 9 季的總營收都在顯示精度內（0.01 億美元）。富途沒有 FY2024 Q3、Q4。

**FY 序列**：FY2025、FY2026 的總營收與各分類都等於同財年四季加總；FY2024 的 Q1（2023-11-26）在範圍外，不比對。

## 比較欄

已下載的申報列示的較早期間數字（去年同季、去年 36 週累計、去年全年），與已上線輸出都在精度內相同，沒有差異標記。
