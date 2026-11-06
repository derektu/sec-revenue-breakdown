# CMCSA parser

## 觀點

營運分部（`view="business_segment"`），共 6 類加 1 個調節項：

- 分類：Residential Connectivity & Platforms、Business Services Connectivity、Media、Studios、Theme Parks、Corporate and Other。
- 調節項：Eliminations。

| 對照來源 | 列出的分類 |
|---|---|
| TradingView | 五個分部，加上 Other（＝ Corporate and Other） |
| 富途 | 五個分部，加上「其他收入」與「抵銷」 |
| Stock Analysis | 兩個事業群：Connectivity and Platforms、Content and Experiences |

分部取自 `us-gaap:StatementBusinessSegmentsAxis`。CMCSA 這個軸的成員是業務別：住宅寬頻與行動、企業連網、媒體、片廠、主題樂園。它們不是地區，所以採用。

Corporate and Other 與 Eliminations 的處理：
- Corporate and Other 有兩個對照來源列出，所以列成分類。
- Eliminations 只有富途列出，所以列為調節項，參與加總但不輸出成分類。
- Stock Analysis 的 Connectivity and Platforms 等於前兩個分部相加。Content and Experiences 另含事業群內的總部與抵銷，與我們的分類不能直接對照。

## 分類與 tag

concept 是 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`。

**分部**

分部 fact 帶 `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember` 與分部成員：

| 分類 | 成員 |
|---|---|
| Residential Connectivity & Platforms | `cmcsa:ResidentialConnectivityAndPlatformsSegmentMember` |
| Business Services Connectivity | `cmcsa:BusinessServicesConnectivitySegmentMember` |
| Media | `cmcsa:MediaSegmentMember` |
| Studios | `cmcsa:StudiosSegmentMember` |
| Theme Parks | `cmcsa:ThemeParksSegmentMember` |

**Corporate and Other、Eliminations 與總營收**

parser 依申報期末日（`filing.report_date`）切換寫法：

| 項目 | 期末日 2024-03-31 以前 | 期末日 2024-04-01 起 |
|---|---|---|
| Corporate and Other | `srt:ConsolidationItemsAxis=us-gaap:CorporateNonSegmentMember` ＋ 同成員再帶 `cmcsa:BusinessUnitAxis=cmcsa:ContentAndExperiencesMember`（兩個 fact 相加） | `srt:ConsolidationItemsAxis=us-gaap:CorporateNonSegmentMember` |
| Eliminations（調節項） | `IntersegmentEliminationMember` 帶 `ContentAndExperiencesMember` ＋ 帶 `cmcsa:InterBusinessUnitEliminationsMember`（兩個 fact 相加） | `srt:ConsolidationItemsAxis=srt:ConsolidationEliminationsMember` |
| 總營收（Total consolidated revenue） | 不帶維度 | 不帶維度 |

- 2024 年 Q1（0001166691-24-000031，期末 2024-03-31）以前，公司層級與 Content & Experiences 事業群內的總部、抵銷各自是一個 fact，所以相加成一類。從 2024 年 Q2（0001166691-24-000048，期末 2024-06-30）起各自只有一個 fact。
- FY2023 10-K（0001166691-24-000011，期末 2023-12-31）的分部、公司層級與總營收 fact 是 `us-gaap:Revenues`，分部另帶 `cmcsa:BusinessUnitAxis`。parser 對這一份申報用這種寫法。FY2023 不在上線範圍，FY2024 Q4 的口徑一致以這份申報組出的年度值作為上一財年先前申報的值。
- `categories` 每一天都是這六類加 Eliminations。
- 六類加上 Eliminations 等於總營收。
- 分類名稱取自 2024 年分部表的列標籤。總營收取自分部表的 `Total consolidated revenue`（2024 年 Q1 為 `Comcast Consolidated`）。

## 期別與推算

- 財年即曆年，季末日是 3、6、9、12 月的最後一天。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同年 Q3 10-Q 的九個月累計。年度與 Q1–Q3 的分類相同，範圍內每個 Q4 都推算。
- FY：10-K 的年度 fact。

## 數字在原文的位置

附註分部表：

- 2024 年 Q1：依事業群分段，列出各分部、事業群內的總部與抵銷、Corporate and Other、公司層級抵銷與 `Comcast Consolidated`。
- 之後：五個分部分欄，下方的營收調節列出 `Other revenue`、`Eliminations` 與 `Total consolidated revenue`。
- Q1–Q3 與 FY 每期一張表；Q4 為 10-K 與 Q3 10-Q 各一張。

## 2026 年的分部重列

CMCSA 於 2026-01-02 分拆 Versant（原屬 Media 的有線電視網等業務）。分拆不列為停業部門。2026 年各 10-Q 依新的分部呈現重列 2025 年的比較數字：
- Media 每季約減少 19 億美元，Corporate and Other、Residential Connectivity & Platforms 與 Eliminations 也有小幅調整。
- 總營收不變。
- 10-Q 附註說明比較數字已重分類，並另列 Versant 的歷史營收。

這次重列對各期的影響：
- **2025 年 Q4（2025-12-31）**：年度與九個月都是重列前的呈現，不受影響。
- **2026 年 Q1–Q3**：已經沒有 Versant，與 2025 年各季不能直接比較。

2025 年 Q1–Q3 與 2025 年 Q4 的九個月運算元寫成差異標記（見比較欄）。

## 驗證

11 季（2024-03-31 至 2026-09-30）與 2 個年度，與對照資料逐期比對：

| 來源 | 結果 |
|---|---|
| TradingView（只有年度） | FY2024、FY2025 的五個分部與 Other 都在顯示精度內 |
| 富途 | 2024 年各季與 2026 年各季都相同；沒有 2025 年 Q4。2025 年 Q1–Q3 是重列後的值（與差異標記的申報列示值相同），2025 年 Q1、Q2 另列 Versant 一項 |
| Stock Analysis | Connectivity and Platforms 等於前兩個分部相加，2024 年 Q1 至 2025 年 Q4 與 2026 年 Q3 相同。2026 年 Q1、Q2 的值與我們的 Q2、Q1 對調，屬於來源本身的期別錯置 |

- 富途的差異都來自 2026 年的分部重列：富途用了事後申報的重列數字，我們用申報當時的原值。
- FY 序列：FY2024、FY2025 與同財年四季加總的差距都在 1 百萬美元以內（Q1–Q3 的單季與九個月累計各自四捨五入）。

## 比較欄

差異標記都是 2026 年的分部重列造成的，來源申報是 2026 年 Q1–Q3 各 10-Q。單位百萬美元：

| 期別 | 運算元 | Media | Corporate and Other | Residential C&P | Eliminations |
|---|---|---|---|---|---|
| 2025-03-31 | 單季 | 6,440 → 4,527 | 752 → 917 | 17,642 → 17,665 | −2,146 → −2,189 |
| 2025-06-30 | 單季 | 6,440 → 4,543 | 717 → 885 | 17,814 → 17,839 | −2,015 → −2,081 |
| 2025-09-30 | 單季 | 6,589 → 4,744 | 752 → 898 | 17,601 → 17,636 | −2,036 → −2,104 |
| 2025-12-31 | 九個月 | 19,470 → 13,813 | 2,221 → 2,700 | 53,057 → 53,140 | −6,198 → −6,374 |

其他申報的比較欄與已上線輸出都在精度內相同。
