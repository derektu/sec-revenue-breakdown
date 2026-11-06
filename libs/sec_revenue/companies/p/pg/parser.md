# PG parser

## 觀點

營運分部（`view="business_segment"`），共 6 類，沒有調節項：Fabric & Home Care、Baby, Feminine & Family Care、Beauty、Health Care、Grooming、Corporate。

採用 Stock Analysis 的觀點。名稱對應：

| 分類 | Stock Analysis |
|---|---|
| Fabric & Home Care | Fabric and Homecare |
| Baby, Feminine & Family Care | Baby, Feminine, and Familycare |
| Beauty | Beauty |
| Health Care | Healthcare |
| Grooming | Grooming |
| Corporate | Corporate |

分部取自 `us-gaap:StatementBusinessSegmentsAxis`。PG 這個軸的成員是業務別：織物與居家清潔、嬰兒／女性／家庭用紙、美容、保健、刮鬍。它們不是地區，所以採用。

Corporate 是五個分部以外、在公司層級管理的附帶業務營收，分部表中與五個分部並列，Stock Analysis 也列出，所以列成分類。

申報中不採用的拆分：

| 拆分 | XBRL 維度 | 不採用的原因 |
|---|---|---|
| 美國／非美國 | `srt:StatementGeographicalAxis`，只在 10-K，精度到億位 | 地區拆分 |
| 營運分部占營收百分比（Fabric Care、Home Care、Hair Care 等） | 沒有金額 fact | 只有百分比 |

## 分類與 tag

concept 都是 `us-gaap:Revenues`。

**分部**

同一個分部在不同申報用不同成員，且 FY2025 Q2 10-Q（0000080424-25-000013，期末 2024-12-31）起分部 fact 另帶 `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`。parser 用 `one_of` 對每份申報找下表每個成員的兩種寫法（帶與不帶 `OperatingSegmentsMember`），不依日期切換：

| 分類 | 成員 |
|---|---|
| Fabric & Home Care | `pg:FabricHomeCareSegmentMember`、`pg:FabricandHomeCareMember`、`pg:FabricHomeCareMember` |
| Baby, Feminine & Family Care | `pg:BabyFeminineFamilyCareSegmentMember`、`pg:BabyFeminineandFamilyCareSegmentMember`、`pg:BabyFeminineFamilyCareMember` |
| Beauty | `pg:BeautySegmentMember` |
| Health Care | `pg:HealthCareSegmentMember`、`pg:HealthCareSegMember` |
| Grooming | `pg:GroomingSegmentMember`、`pg:GroomingMember` |

各申報實際用到的寫法：

| 申報 | Fabric & Home Care | Baby, Feminine & Family Care | Health Care | Grooming | 另帶 `OperatingSegmentsMember` |
|---|---|---|---|---|---|
| FY2023 10-K（0000080424-23-000073，期末 2023-06-30） | `FabricHomeCareMember` | `BabyFeminineFamilyCareMember` | `HealthCareSegMember` | `GroomingMember` | 否 |
| 10-Q，期末 2023-03-31 至 2024-03-31 | `FabricandHomeCareMember` | `BabyFeminineandFamilyCareSegmentMember` | `HealthCareSegmentMember` | `GroomingSegmentMember` | 否 |
| FY2024 10-K、期末 2024-09-30 的 10-Q | `FabricHomeCareSegmentMember` | `BabyFeminineFamilyCareSegmentMember` | `HealthCareSegmentMember` | `GroomingSegmentMember` | 否 |
| 期末 2024-12-31 起 | 同上 | 同上 | 同上 | 同上 | 是 |

Beauty 每份申報都是 `pg:BeautySegmentMember`。

**Corporate 與總營收**

| 項目 | 寫法 |
|---|---|
| Corporate | `one_of`：`srt:ConsolidationItemsAxis=us-gaap:CorporateNonSegmentMember`（期末 2024-12-31 起）；`us-gaap:StatementBusinessSegmentsAxis=us-gaap:CorporateMember`（期末 2024-09-30 以前） |
| 總營收（Total Company） | 不帶維度 |

- `categories` 每一天都是這六類。
- 六類加總等於總營收，沒有調節項。
- 分類名稱取自分部表的欄標題（10-Q）或列標籤（10-K，全大寫，例如 `FABRIC & HOME CARE`）。總營收取自分部表的 `Total Company`。

## 期別與推算

- 財年在 6 月 30 日結束；季末日是 9、12、3、6 月的最後一天。FY2025 是 2024-07-01 至 2025-06-30。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同財年 Q3 10-Q 的九個月累計。年度與 Q1–Q3 的分類相同，範圍內每個 Q4 都推算。
- Q4 口徑一致：FY2024、FY2025、FY2026 的 10-K 列示的上一財年分部營收與先前申報相同，每個 Q4 都推算。FY2024 的先前值由 FY2023 10-K 組出（FY2023 不在上線範圍）。
- FY：10-K 的年度 fact。

## 數字在原文的位置

附註 Segment Information 的分部表，五個分部、Corporate 與 Total Company 並列：

- 10-Q：「summary of reportable segment results」表。期末 2024-09-30 以前分部分列、Net Sales 等科目分欄；期末 2024-12-31 起分部分欄、科目分列，每段期間一張表。三個月與九個月累計在同一張表（期末 2026-03-31 的 10-Q 為相鄰兩張）。
- 10-K：FY2024 以前是「Global Segment Results」表（分部分列、三個年度）；FY2025 起分部分欄、科目分列，每個財年一張表。
- Q1–Q3 與 FY 每期一張表；Q4 為 10-K 與 Q3 10-Q 各一張。

## 已知的重複 fact

總營收同時標在損益表與分部表；部分 10-Q 另標在其他附註表。數值一致，框架選用所在表格含最多其他運算元的分部表。

## 2026 年的分部重列（Habitat Care）

FY2027 Q1 10-Q（0000080424-26-000256，期末 2026-09-30）把原屬 Corporate 的 Habitat Care 併入 Fabric & Home Care，並重列比較期別。該 10-Q 的 Item 5 列出 FY2024–FY2026 依新口徑的 Fabric & Home Care 與 Corporate 年度營收（例如 FY2026 Fabric & Home Care 30,647、Corporate 587，原值 30,314、919）；這張表沒有對應的分部 XBRL 營收 fact，parser 不使用。

對各期的影響：

- **2025-09-30（FY2026 Q1）**：比較欄重列為 Fabric & Home Care 7,870、Corporate 165（原值 7,793、242），總營收不變，寫成差異標記（見「比較欄」）。
- **2026-09-30（FY2027 Q1）起**：Fabric & Home Care 含 Habitat Care，與先前各期不能直接比較。分類名稱與集合不變。
- **FY2027 Q4（期末 2027-06-30，尚未申報）**：FY2027 10-K 列示的 FY2026 數字預期採新口徑，與已上線的 FY2026 不同，Q4 預期因「Q4 口徑一致」而 `not_derived`。

## 驗證

11 季（2024-03-31 至 2026-09-30）與 Stock Analysis 逐期比對（Stock Analysis 只有季度，顯示精度分部 0.01B、Corporate 1M）：

- 8 季六類都在顯示精度內：2024-03-31、2024-09-30、2024-12-31、2025-03-31、2025-09-30、2025-12-31、2026-03-31、2026-06-30。
- 3 筆差異，都是同一數字在不同 SEC 文件或同一份文件的不同表格中的百萬位進位差，Stock Analysis 採用的不是分部附註的那一個：

| 期別 | 分類 | 我們 | Stock Analysis | 原因與證據 |
|---|---|---|---|---|
| 2024-06-30（FY2024 Q4） | Corporate | 203M（601 − 398） | 202M | 我們的 Q4 是 10-K 年度減 Q3 10-Q 九個月累計。FY2024 Q4 業績新聞稿（8-K 0000080424-24-000071 附件 99.1）的單季分部表列 Corporate 202。新聞稿單季數字獨立進位，年度減九個月的推算差 1M |
| 2025-06-30（FY2025 Q4） | Fabric & Home Care | 7,384M（29,617 − 22,233） | 7.39B | FY2025 Q4 業績新聞稿（8-K 0000080424-25-000067 附件 99.1）列 Fabric & Home Care 7,385，以 0.01B 顯示為 7.39B。同樣是推算值與新聞稿獨立進位的 1M 差 |
| 2026-09-30（FY2027 Q1） | Fabric & Home Care | 8,204M | 8.21B | 同一份 10-Q 的分部附註（XBRL fact）是 8,204，MD&A 的分部表列 8,205（沒有 XBRL 標記）。8,205 以 0.01B 顯示為 8.21B |

- FY 序列：每個 FY 的數值與同期 Q4 的年度運算元相同；Stock Analysis 沒有年度可比。
- 富途、TradingView 未比對（採用來源是 Stock Analysis）。

## 比較欄

1 期有差異標記：

- **2025-09-30 的 Fabric & Home Care 與 Corporate**：FY2027 Q1 10-Q（0000080424-26-000256）列示的去年同季為 7,870 與 165，已上線值為 7,793 與 242。原因是上節的 Habitat Care 重列；兩者的差同為 77，總營收沒有標記。

其餘已下載的申報列示的較早期間數字，與已上線輸出都在精度內相同。
