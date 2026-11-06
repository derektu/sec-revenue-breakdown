# UPS parser

## 觀點

營運分部（`view="business_segment"`），每期 3 類：U.S. Domestic Package、International Package，加上 2024 年的 Supply Chain Solutions 或 2025 年起的 Other revenues。Stock Analysis、富途、TradingView 都用三類，但對第三類的稱呼不同：

- Stock Analysis：Supply Chain and Freight
- 富途：近期叫 Other revenues
- TradingView：近兩年叫 Other

分部取自 `us-gaap:StatementBusinessSegmentsAxis`。UPS 這個軸的成員是業務別：國內包裹、國際包裹、供應鏈服務。International Package 是一個業務分部，指美國以外的包裹業務，不是地區拆分，所以採用。

UPS 另有兩種營收拆分，都不採用：

| 拆分 | XBRL 維度 | 不採用的原因 |
|---|---|---|
| 包裹產品（Next Day Air、Deferred、Ground、Export…）與 SCS 細項（Forwarding、Logistics） | `srt:ProductOrServiceAxis` 搭配分部軸與地區軸 | 對照來源不用；包裹產品的 fact 帶 `srt:StatementGeographicalAxis` |
| 美國／非美國 | `srt:StatementGeographicalAxis` | 地區拆分 |

## 分類與 tag

concept 是 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`。

2025 年起 UPS 的分部標記不同：
- Supply Chain Solutions 不再是報告分部，分部表的營收調節把它列為 `Other revenues`。
- 兩個包裹分部改用新的成員。

parser 依申報期末日（`filing.report_date`）切換寫法，分界在 2025 財年起點：

| 分類 | 期末日 2024-01-01 至 2024-12-31 | 期末日 2025-01-01 起 |
|---|---|---|
| U.S. Domestic Package | 分部 `ups:USDomesticPackageMember` | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`＋分部 `ups:U.S.DomesticPackageSegmentMember` |
| International Package | 分部 `ups:InternationalPackageMember` | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`＋分部 `ups:InternationalSegmentMember` |
| Supply Chain Solutions | 分部 `ups:SupplyChainSolutionsMember` | （沒有這一類） |
| Other revenues | （沒有這一類） | `srt:ConsolidationItemsAxis=us-gaap:CorporateNonSegmentMember` 或分部 `ups:SupplyChainSolutionsMember`（兩種寫法都找） |
| 總營收（Consolidated revenue） | 不帶維度 | 不帶維度 |

- 三類加總等於總營收，沒有調節項。
- 分界：FY2024 10-K（0001090727-25-000019，期末 2024-12-31）是最後一份用舊成員與 Supply Chain Solutions 的申報；2025 年 Q1 10-Q（0001090727-25-000049，期末 2025-03-31）起用新成員與 Other revenues。`categories` 對期末日 2025-01-01 以前的每一天列出 Supply Chain Solutions，之後列出 Other revenues，中間沒有空檔，Q4 推算條件逐日比對分類集合時不會誤判。
- 分類名稱與 tag 都只依該期申報本身：2024 年的申報把第三類列為 Supply Chain Solutions 分部；2025 年起的申報列為營收調節的 `Other revenues`。
- 2025 年各 10-Q 以 `us-gaap:CorporateNonSegmentMember` 與 `ups:SupplyChainSolutionsMember` 兩種寫法標示同一個數字，FY2025 10-K（0001628280-26-008432）起只有前者，所以兩種寫法都找；同一份申報兩種寫法都有時，數值必須在精度內一致。
- 2024 年度 10-K 與 2024 年 Q3 10-Q 都用舊成員，2025 年度 10-K 與 2025 年 Q3 10-Q 都用新成員，所以同一個 Q4 的兩個運算元用同一種寫法。
- 期末日 2023-12-31 以前：FY2023 10-K（0001090727-24-000008，期末 2023-12-31）的包裹分部另帶 `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`，parser 對期末日 2023-10-01 至 2023-12-31 的申報用這種寫法；更早的申報只帶分部軸。這些寫法供 `--start` 指定更早的期別，以及 FY2024 Q4 口徑一致以 FY2023 10-K 組出上一財年的值時使用。
- 分類名稱：U.S. Domestic Package、International Package、Supply Chain Solutions 取自 2024 年營收拆分表的列標籤（`Supply Chain Solutions ("SCS")` 去掉縮寫）；Other revenues 取自 2025 年起分部表營收調節的列標籤。總營收取自 2024 年營收拆分表的 `Consolidated revenue`。

## 期別與推算

- 財年即曆年，季末日是 3、6、9、12 月的最後一天。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同年 Q3 10-Q 的九個月累計，前提是年度與 Q1–Q3 的分類相同，且口徑沒有改變。2024 年 Q4 不推算（見下節）。
- FY：10-K 的年度 fact。

## 數字在原文的位置

- 2024 年：附註分部表，三個分部與合併營收並列。
- 2025 年起：附註的分部損益表。兩個包裹分部各一段（`Revenue` 列），Other revenues 與總營收在同表的營收調節（`Other revenues`、`Total Consolidated Revenue`）。
- Q1–Q3 與 FY 每期一張表；Q4 為 10-K 與 Q3 10-Q 各一張。

## 2024 年 Q4 的重分類

2024 年 Q4 起，UPS 把航空貨運營收從 Supply Chain Solutions 移到 U.S. Domestic Package：
- 2024 年度 10-K 的年度數字是新歸類。
- 2024 年 Q3 10-Q 的九個月累計是舊歸類。
- 2024 年 Q4 財報新聞稿（8-K）的附件註明這次重分類；它不是 XBRL，不作為運算元。

2024 年度 10-K 也以新歸類重列了 FY2023（單位百萬美元）：U.S. Domestic Package 59,958 → 60,205、Supply Chain Solutions 13,169 → 12,922，International Package 與總營收不變。

- 10-K 列示的上一財年數字與上一份 10-K 不同，代表年度與 Q3 10-Q 的九個月累計可能是不同口徑，所以 2024 年 Q4（2024-12-31）不推算（`not_derived`）。
- 新歸類的九個月累計最早出現在 2025 年 Q3 10-Q 的比較欄（申報日 2025-11-05），晚於 2024 年度 10-K，不能回頭用來推算。
- 2025 年各 10-Q 的比較欄與 2024 年 Q1–Q3 的差異，都寫成差異標記（見比較欄）。

## 驗證

11 季（2024-03-31 至 2026-09-30，2024 年 Q4 不推算）與 2 個年度，與對照資料逐期比對。下表數值單位為百萬美元：

| 來源 | 結果 |
|---|---|
| TradingView（只有年度） | FY2024、FY2025 三類都在顯示精度內（FY2025 的 Other 對 Other revenues） |
| Stock Analysis | 2024 年 Q2、Q3 與 2025 年起都相同（2025 年起的 Supply Chain and Freight 對 Other revenues）。2024 年 Q1 是新歸類的值（Domestic 14,270、SCS 3,180，我們 14,234、3,216）。2024 年 Q4 我們不推算 |
| 富途 | 2025 年起都相同。2024 年 Q1–Q3 是新歸類的值（與差異標記的申報列示值相同）。2024 年 Q4 我們不推算 |

- 所有差異都來自 2024 年 Q4 的重分類：對照來源用了事後申報的新歸類數字，我們用申報當時的原值。
- FY 序列：FY2025 等於同財年四季加總。FY2024 的 Q4 不推算，不比對。

## 比較欄

差異標記都是 2024 年 Q4 重分類造成的。2025 年各 10-Q 列示的 2024 年同季，U.S. Domestic Package 增加、Supply Chain Solutions 減少相同金額：

| 期別 | 運算元 | U.S. Domestic Package（已上線值 → 申報列示值） | Supply Chain Solutions 的對應變動 | 來源申報 |
|---|---|---|---|---|
| 2024-03-31 | 單季 | 14,234 → 14,266 | 3,216 → 3,184 | 2025 年 Q1 10-Q |
| 2024-06-30 | 單季 | 14,119 → 14,201 | 3,329 → 3,247 | 2025 年 Q2 10-Q |
| 2024-09-30 | 單季 | 14,450 → 14,597 | 3,384 → 3,237 | 2025 年 Q3 10-Q |

- 只有 U.S. Domestic Package 寫成差異標記。2025 年申報期別沒有 Supply Chain Solutions 這一類（第三類是 Other revenues），比對結果是 `not_found`，不寫標記；表中 Supply Chain Solutions 的變動取自同一批 10-Q 的 `ups:SupplyChainSolutionsMember` fact，供對照。
- 其他申報的比較欄與已上線輸出都在精度內相同。
