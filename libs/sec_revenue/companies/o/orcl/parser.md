# ORCL parser

## 觀點

業務分部（`view="business_segment"`），共 3 類，依序：Cloud and license／Cloud and software、Services、Hardware。三個分部的營收加總等於合併總營收，沒有調節項。

`us-gaap:StatementBusinessSegmentsAxis` 的成員是業務別（雲端與軟體、硬體、服務），不是地區。

| 對照來源 | 列出的分類 | 對應 |
|---|---|---|
| 富途（季度，採用） | Cloud and software、服務、硬件 | 三個分部，順序相同；富途每一期都用 Cloud and software 這個名稱 |
| TradingView（只有年度） | Cloud and License、Services、Hardware | 三個分部；TradingView 每一期都用 Cloud and License 這個名稱 |
| Stock Analysis（季度） | 2025-06-30 及更早：Cloud Services and License Support、Cloud License and On-Premise License、Hardware、Services；2025-09-30 起：Cloud、Software、Hardware、Services | 營收類型（產品別），不採用 |

富途與 TradingView 都拆到業務分部，名稱、範圍一致；Stock Analysis 是損益表的營收類型，在 FY2026 改成另一組類別（Cloud 只含雲端服務，Software 含授權與授權支援），與 FY2025 及更早的類別不能接續比較。分部觀點在範圍內只有第一個分部改名、範圍不變（見「Cloud and license 改名」），所以採用業務分部。

申報中另有的拆分，不採用：

| 拆分 | XBRL 維度 | 不採用的原因 |
|---|---|---|
| 營收類型：FY2025 10-K 及更早為 Cloud services and license support、Cloud license and on-premise license、Hardware、Services；FY2026 Q1 10-Q 起為 Cloud、Software、Hardware、Services | 損益表的公司自訂 concept（`orcl:CloudServicesAndLicenseSupportRevenue`、`orcl:CloudRevenues` 等，不帶維度），以及 `srt:ProductOrServiceAxis` 的細項 | 不是採用的觀點，類別在 FY2026 重新劃分 |
| 地區：Americas、EMEA、Asia Pacific；以及 United States、United Kingdom 等國家 | `srt:StatementGeographicalAxis` | 地區拆分 |

## 分類與 tag

所有分類與總營收都是 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`。分類帶兩個維度：`us-gaap:StatementBusinessSegmentsAxis` 與 `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`。

| 分類 | `us-gaap:StatementBusinessSegmentsAxis` 成員 |
|---|---|
| Cloud and license | `orcl:CloudAndLicenseBusinessMember` |
| Cloud and software | `orcl:CloudAndSoftwareBusinessMember` |
| Services | `orcl:ServicesBusinessMember` |
| Hardware | `orcl:HardwareBusinessMember` |
| 總營收（Total revenues） | 不帶維度 |

- 第一類依這份申報、這段期間有哪個成員決定名稱：先找 `orcl:CloudAndSoftwareBusinessMember`，沒有時找 `orcl:CloudAndLicenseBusinessMember`。FY2025 10-K（0000950170-25-087926，期末 2025-05-31）及更早的申報只有 Cloud and license；FY2026 Q1 10-Q（0001193125-25-200095，期末 2025-08-31）起營收 fact 只有 Cloud and software，同表的比較欄也用新成員；舊成員只出現在重組費用的三維 context（加上 `us-gaap:RestructuringPlanAxis`），不在營收 fact 上。`categories` 以那一季的起日 2025-06-01 切換。
- `categories` 的涵蓋下限是 2023-05-31（範圍內第一期 2024-02-29 所在財年 FY2024 的上一財年期末日）以後的每一天。FY2023 10-K（0000950170-23-028914）到 2026-08-31 10-Q（0001193125-26-389274）都是這三個分部；更早的申報 parser 沒有查核，以 `--start` 處理更早的期別前要先確認。
- 總營收用不帶維度的合併 fact。只帶 `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember` 的分部合計在範圍內每一期都與合併數相同，不用。
- 分類名稱取自分部附註表的分部標題（`Cloud and license:`、`Cloud and software:`、`Hardware:`、`Services:`，去掉冒號）；總營收名稱取自損益表的 `Total revenues` 列。輸出順序照富途，與分部表的列順序（Cloud、Hardware、Services）不同。

## 期別與推算

- 財年在 5 月 31 日結束，季末為 8 月 31 日、11 月 30 日、2 月底與 5 月 31 日。財年以結束的年份命名：FY2026 是 2025-06-01 至 2026-05-31。
- 季度長度 90–92 天、六個月 183 天、九個月 273–274 天、年度 365–366 天，都在框架的預設範圍內，不自訂 `DURATION_DAYS`。
- Q1–Q3：10-Q 的單季 fact。
- Q4：10-K 年度減同財年 Q3 10-Q 的九個月累計。範圍內每個財年的 Q1–Q3 與年度都是同一組分類，年報列示的上一財年數字與先前申報相同，FY2024、FY2025、FY2026 的 Q4 都推算。FY2024 Q4 的口徑依據是 FY2023 10-K（0000950170-23-028914）。FY2026 Q4 的口徑比對中，第一類在年報與上一財年的名稱不同（Cloud and software、Cloud and license），依 `FORMER_NAMES` 以年報的 Cloud and software 比對上一財年的 Cloud and license，與 Services、Hardware、總營收都相同（FY2026 10-K 0001193125-26-277521 t70 列示的 FY2025 Cloud and software 49,230，對已上線 FY2025 的 Cloud and license 49,230）；改名的依據見「Cloud and license 改名」。
- FY：10-K 的年度 fact。

### 財年（`FISCAL_YEAR = "prior_annual"`）

ORCL 在 2026-08-31 的 10-Q（0001193125-26-389274）宣告 `DocumentFiscalYearFocus=2026`、`DocumentFiscalPeriodFocus=Q1`。這一季是 2026-06-01 起的財年第一季，屬於 FY2027：前一份 10-K（0001193125-26-277521，期末 2026-05-31）已宣告 FY2026。照宣告值會讓這一季成為第二個「FY2026 Q1」，與 2025-08-31 的 FY2026 Q1 衝突。parser 宣告 `FISCAL_YEAR = "prior_annual"`，10-Q 的財年由框架以前一份 10-K 宣告的財年加 1 推算；10-K 的財年仍取宣告值。

已下載的每一份 10-Q，推算值與宣告值的關係：

| 10-Q | 期末 | 宣告 | 前一份 10-K | 推算 |
|---|---|---|---|---|
| 0000950170-24-029904 | 2024-02-29 | FY2024 Q3 | 0000950170-23-028914（FY2023） | 2024 |
| 0000950170-24-104905、0000950170-24-134973、0000950170-25-037143 | 2024-08-31、2024-11-30、2025-02-28 | FY2025 | 0000950170-24-075605（FY2024） | 2025 |
| 0001193125-25-200095、0001193125-25-315925、0001193125-26-101045 | 2025-08-31、2025-11-30、2026-02-28 | FY2026 | 0000950170-25-087926（FY2025） | 2026 |
| 0001193125-26-389274 | 2026-08-31 | FY2026 Q1 | 0001193125-26-277521（FY2026） | 2027 |

只有 2026-08-31 這一季的推算值與宣告不同，它的 `revenue.json` 與 `status.json` 紀錄附 `fiscal_year_basis`（宣告 2026、推算 2027、前一份 10-K 0001193125-26-277521）。其餘各季推算值等於宣告值，沒有這個欄位。推算 2024-02-29 那一季需要 FY2023 10-K，已下載。

## 數字在原文的位置

每期的證據是兩張表：三個分部在分部附註表（各分部的 `Revenues` 列），總營收在損益表的 `Total revenues` 列。Q4 的證據是 10-K 與 Q3 10-Q 各兩張表。

| 申報 | 損益表 | 分部表 |
|---|---|---|
| 10-Q 0000950170-24-029904（2024-02-29） | t5 | t18 |
| 10-K 0000950170-24-075605（2024-05-31） | t35 | t65 |
| 10-Q 0000950170-24-104905（2024-08-31） | t5 | t15 |
| 10-Q 0000950170-24-134973（2024-11-30） | t5 | t16 |
| 10-Q 0000950170-25-037143（2025-02-28） | t5 | t16 |
| 10-K 0000950170-25-087926（2025-05-31） | t35 | t69 |
| 10-Q 0001193125-25-200095（2025-08-31） | t5 | t18 |
| 10-Q 0001193125-25-315925（2025-11-30） | t5 | t19 |
| 10-Q 0001193125-26-101045（2026-02-28） | t5 | t20 |
| 10-K 0001193125-26-277521（2026-05-31） | t33 | t70 |
| 10-Q 0001193125-26-389274（2026-08-31） | t5 | t21 |
| 10-K 0000950170-23-028914（2023-05-31），只作 FY2024 Q4 口徑依據，沒有證據檔 | t33 | t65 |

## 已知的重複 fact

總營收的合併 fact 在損益表與地區營收表的合計列各標一次，數值相同。地區營收表在 2024-02-29 10-Q 是 t20，2024-08-31 是 t17，2024-11-30 與 2025-02-28 是 t18，2025-08-31 是 t20，2025-11-30 是 t21，2026-02-28 是 t22，2026-08-31 是 t23；FY2024、FY2025、FY2026 10-K 是 t67、t71、t72。框架選用損益表的 fact，地區營收表的 fact 記在運算元的 `duplicates`。

## Cloud and license 改名

FY2026 Q1 10-Q（0001193125-25-200095）的分部說明寫明三個業務為「cloud and software (formerly referred to as cloud and license), hardware and services」。較晚申報以新成員列示的比較欄，與原申報以舊成員列示的值逐一相同（單位百萬美元，`decimals=-6`）：

| 期間 | 原申報（Cloud and license） | 較晚申報（Cloud and software） |
|---|---|---|
| 2024-06-01～2024-08-31 | 0000950170-24-104905 t15：11,389 | 0001193125-25-200095 t18：11,389 |
| 2024-09-01～2024-11-30 | 0000950170-24-134973 t16：12,001 | 0001193125-25-315925 t19：12,001 |
| 2024-12-01～2025-02-28 | 0000950170-25-037143 t16：12,136 | 0001193125-26-101045 t20：12,136 |
| 2024-06-01～2025-02-28（九個月） | 0000950170-25-037143 t16：35,525 | 0001193125-26-101045 t20：35,525 |
| FY2024 | 0000950170-24-075605 t65：44,464 | 0001193125-26-277521 t70：44,464 |
| FY2025 | 0000950170-25-087926 t69：49,230 | 0001193125-26-277521 t70：49,230 |

同期間的 Services、Hardware 與總營收也相同，所以這是純改名，範圍不變。名稱仍跟各期申報：FY2025 及更早的期別是 Cloud and license，FY2026 起是 Cloud and software。較晚的申報只作證據，不用來組早期期別。

`parser.py` 依這些證據宣告 `FORMER_NAMES = {"Cloud and software": ("Cloud and license",)}`：比較欄比對與 Q4 口徑一致把較晚申報的 Cloud and software 接上已上線的 Cloud and license（見 `docs/architecture/parser.md` 的「自訂點」）。

## 驗證

範圍是 11 季（2024-02-29 至 2026-08-31）與 3 個年度（FY2024 至 FY2026），每一期都是 `published`，沒有 `not_derived` 與 `failed`。

**富途（採用的來源，季度）**：以財年季別對齊（富途 2027/Q1 是 2026-08-31 這一季，與推算的財年一致）。11 季、33 筆分類值都在顯示精度內（0.01 億美元，加上運算元精度誤差；Q4 每個運算元有年度與九個月兩個）：

| 期末 | 財年季別 | 第一類／Cloud and software | Services／服務 | Hardware／硬件 |
|---|---|---|---|---|
| 2024-02-29 | FY2024 Q3 | 11,219M／112.19 億 | 1,307M／13.07 億 | 754M／7.54 億 |
| 2024-05-31 | FY2024 Q4 | 12,072M／120.72 億 | 1,373M／13.73 億 | 842M／8.42 億 |
| 2024-08-31 | FY2025 Q1 | 11,389M／113.89 億 | 1,263M／12.63 億 | 655M／6.55 億 |
| 2024-11-30 | FY2025 Q2 | 12,001M／120.01 億 | 1,330M／13.3 億 | 728M／7.28 億 |
| 2025-02-28 | FY2025 Q3 | 12,136M／121.36 億 | 1,291M／12.91 億 | 703M／7.03 億 |
| 2025-05-31 | FY2025 Q4 | 13,705M／137.05 億 | 1,348M／13.48 億 | 850M／8.5 億 |
| 2025-08-31 | FY2026 Q1 | 12,907M／129.07 億 | 1,349M／13.49 億 | 670M／6.7 億 |
| 2025-11-30 | FY2026 Q2 | 13,854M／138.54 億 | 1,428M／14.28 億 | 776M／7.76 億 |
| 2026-02-28 | FY2026 Q3 | 15,033M／150.33 億 | 1,443M／14.43 億 | 714M／7.14 億 |
| 2026-05-31 | FY2026 Q4 | 16,737M／167.37 億 | 1,523M／15.23 億 | 924M／9.24 億 |
| 2026-08-31 | FY2027 Q1 | 17,157M／171.57 億 | 1,414M／14.14 億 | 774M／7.74 億 |

第一類在 FY2025 及更早的期別是 Cloud and license，與富途的 Cloud and software 是同一個分部（見「Cloud and license 改名」）。富途沒有年度，FY 不與富途比對。

**TradingView（補充，年度）**：TradingView 以財年多數月份所在的曆年標示（FY2026 標 2025）。FY2024、FY2025、FY2026 的三類都在顯示精度內（0.01B）：

| 年度 | 第一類／Cloud and License | Services | Hardware |
|---|---|---|---|
| FY2024 | 44,464M／44.46B | 5,431M／5.43B | 3,066M／3.07B |
| FY2025 | 49,230M／49.23B | 5,233M／5.23B | 2,936M／2.94B |
| FY2026 | 58,530M／58.53B | 5,743M／5.74B | 3,084M／3.08B |

**Stock Analysis**：營收類型觀點，與業務分部不是同一組分類，不比對。

**FY 序列**：FY2025 的總營收與各分類都等於同財年四季加總；FY2026 的總營收比四季加總少 1M（67,357M 對 67,358M），來自 Q1–Q3 單季與九個月累計各自的百萬位捨入，在運算元精度內。FY2024 的 Q1、Q2（2023-08-31、2023-11-30）在範圍外，不比對。

## 比較欄

已下載的申報列示的較早期間數字（去年同季、九個月累計、上一財年全年），與已上線輸出都在精度內相同，沒有差異標記。較晚申報以 Cloud and software 列示的 FY2025 及更早期間，依 `FORMER_NAMES` 與已上線的 Cloud and license 比對，都相同（逐期數字見「Cloud and license 改名」）。
