# MU parser

## 觀點

業務分部（`business_segment`）。`us-gaap:StatementBusinessSegmentsAxis` 的成員是業務別，不是地區。

採 TradingView 為年度對照來源，Stock Analysis 為季度輔助。分類名稱採 SEC 分部表縮寫，順序依本次核定清單：

| 期間 | 分類順序 | 調節項 |
|---|---|---|
| 至 FY2025 Q3 | CNBU、MBU、EBU、SBU、All Other | 無 |
| FY2025 10-K 起 | CMBU、CDBU、MCBU、AEBU、All Other | Unallocated |

| SEC 名稱 | TradingView 名稱 | Stock Analysis 名稱 |
|---|---|---|
| CNBU | Compute and Networking Business Unit | Compute and Networking |
| MBU | Mobile Business Unit | Mobile |
| EBU | Embedded Business Unit | Embedded |
| SBU | Storage Business Unit | Storage |
| CMBU | Cloud Memory Business Unit | Cloud Memory |
| CDBU | Core Data Center Business Unit | Core Data Center |
| MCBU | Mobile and Client Business Unit | Mobile & Client |
| AEBU | Automotive and Embedded Business Unit | Automotive & Embedded |
| All Other | All Other | 新結構為 All Other；舊結構未列 |

All Other 由 TradingView 與富途列出，列為分類。新結構 Unallocated 三來源均未列出，列為調節項。TradingView 的 Memory、Numonyx 沒有值，不納入分類。富途 FY2025 季度回填新分部，FY2024 Q4 混用新年度與舊九個月分類，不採為主要來源。對照資料位於 `data/universe/references/M/MU/reference.json`。

不採產品別 DRAM、NAND、Other (primarily NOR)，也不採地區別。

## 分類與 tag

所有項目 concept 均為 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`，單位 USD，所用 fact 的 `decimals=-6`。下表列出完整 dimensions，不另有隱含維度。

| 分類 | 至 FY2025 Q3 的完整 dimensions |
|---|---|
| CNBU | `us-gaap:StatementBusinessSegmentsAxis=mu:CNBUMember` |
| MBU | `us-gaap:StatementBusinessSegmentsAxis=mu:MBUMember` |
| EBU | `us-gaap:StatementBusinessSegmentsAxis=mu:EBUMember` |
| SBU | `us-gaap:StatementBusinessSegmentsAxis=mu:SBUMember` |
| All Other | `us-gaap:StatementBusinessSegmentsAxis=us-gaap:AllOtherSegmentsMember` |

| 分類／調節項 | FY2025 10-K 起的完整 dimensions |
|---|---|
| CMBU | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`、`us-gaap:StatementBusinessSegmentsAxis=mu:CMBUMember` |
| CDBU | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`、`us-gaap:StatementBusinessSegmentsAxis=mu:CDBUMember` |
| MCBU | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`、`us-gaap:StatementBusinessSegmentsAxis=mu:MCBUMember` |
| AEBU | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`、`us-gaap:StatementBusinessSegmentsAxis=mu:AEBUMember` |
| All Other | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`、`us-gaap:StatementBusinessSegmentsAxis=us-gaap:AllOtherSegmentsMember` |
| Unallocated（調節項） | `srt:ConsolidationItemsAxis=us-gaap:CorporateNonSegmentMember` |

總營收取同 concept、無維度的合併 fact，內部名稱為 `Total revenue`。分類加上調節項等於總營收；新架構 Unallocated 的零值來自明確標記的 fact，不將空值補零。

`compose` 以要求期間中有沒有帶完整新結構 dimensions 的 `mu:CMBUMember` fact 判斷結構。因此新申報的比較欄依該申報列示的新分部組成，不將新結構套用早期主申報。

`categories(day)` 從 2025-05-30 切換。依據為 [FY2025 10-K，0000723125-25-000028，期末 2025-08-28](https://www.sec.gov/Archives/edgar/data/723125/000072312525000028/mu-20250828.htm)，其 Business and Segment Information 說明重組於 FY2025 Q4 生效。最後一份舊結構主申報為 FY2025 Q3，期末 2025-05-29。

舊結構已在本機最早的 FY2023 10-K（0000723125-23-000054，期末 2023-08-31）出現；這是本次查核下限，不代表歷史首次揭露。`categories` 涵蓋下限為 2023-08-31，包含第一個範圍內 Q4 所需的上一財年期末與整個財年。更早期別未確認。

### All Other 大小寫

依核定觀點，FY2025 Q3 表格的 `All other` 視為排版差異，統一輸出 `All Other`，不宣告 `FORMER_NAMES`。同 scope、同 member 的證據：

- FY2024 Q3（0000723125-24-000019，t36）列 `All Other`；FY2025 Q3（0000723125-25-000021，t35）列 `All other`。兩份申報的完整 dimensions 都只有 `us-gaap:StatementBusinessSegmentsAxis=us-gaap:AllOtherSegmentsMember`，concept 相同。
- FY2025 Q3 的 FY2024 比較欄，單季 3、九個月 34 百萬美元，分別等於 FY2024 Q3 原申報的 3、34；沒有改分類範圍。
- FY2025 Q4 的重組是另一件事。新結構 All Other 多了合併軸，FY2024 年度也由 38 重列為 37 百萬，不能把這次重組當成純改名。

## 期別與推算

財年在最接近 8 月 31 日的星期四結束，採 52／53 週制。所查 Q1–Q3 各 91 天、半年 182 天、九個月 273 天；年度 364 或 371 天，FY2026 Q4 為 98 天。使用框架預設期間範圍及申報宣告財年，不需 `DURATION_DAYS`、`FISCAL_YEAR` 或 `ATTACHMENTS`。

- Q1–Q3 取各期原始 10-Q 的單季 facts。
- FY 取各年度原始 10-K 的年度 facts。
- Q4 由年度減同財年 Q3 原始 10-Q 九個月累計。FY2024、FY2026 結構及口徑檢核成立，照常推算。
- FY2025 Q4 為 `not_derived`：年度是新分部，前三季是舊分部，分類集合不同。不以後續比較欄回填，不用直接季度數字補救。
- FY2024 Q1 期末 2023-11-30 在預設起始日前，只作 FY2024 Q4 的依據；FY2023 10-K 作第一個 Q4 的上一年度口徑依據。兩者不列入範圍內發布期數。

## 數字在原文的位置

正式證據位於 `data/revenue/M/MU/<series>/<period_end>/evidence/`，各期 `revenue.json` 的運算元以 `evidence.table` 指向下表檔名主體；每個主體均有 `.html` 與 `.png`。所有項目位於主文件的分部資訊附註，舊結構取 Revenue 下的各分部列及合計，新結構取 Revenue 橫列的各分部、Unallocated 與 Total 欄。Q4 的年度與九個月來源均保留於該季證據目錄。

| 期別／用途 | 表格 | 正式證據檔名主體 |
|---|---|---|
| FY2024 Q2 | t35 | `0000723125-24-000007-d70f233a9541-t35` |
| FY2024 Q3、Q4 九個月來源 | t36 | `0000723125-24-000019-44fe4569c284-t36` |
| FY2024、Q4 年度來源 | t56 | `0000723125-24-000027-1fc2b51977b5-t56` |
| FY2025 Q1 | t33 | `0000723125-24-000047-450307aae09e-t33` |
| FY2025 Q2 | t35 | `0000723125-25-000009-848762238f21-t35` |
| FY2025 Q3 | t35 | `0000723125-25-000021-f09dde3e5671-t35` |
| FY2025 | t58 | `0000723125-25-000028-0b6c26ffe629-t58` |
| FY2026 Q1 | t34 | `0000723125-25-000046-b2184ba5bea0-t34` |
| FY2026 Q2 | t27 | `0000723125-26-000006-224265f80d87-t27` |
| FY2026 Q3 單季 | t27 | `0000723125-26-000015-8fa00dbf5ed3-t27` |
| FY2026 Q4 九個月來源 | t29 | `0000723125-26-000015-8fa00dbf5ed3-t29` |
| FY2026、Q4 年度來源 | t45 | `0000723125-26-000023-2dfb26a50319-t45` |

FY2026 Q3 的 t27 與 t29 分別列單季及九個月損益，兩表的 Revenue 列均含全部分類、調節項及總營收。FY2023 10-K（0000723125-23-000054）的 t57 只作第一個 Q4 的上一年度口徑依據，沒有正式證據檔。

## FY2025 分部重組

FY2025 10-K 的分部附註明示所有先前期間已依重組回溯調整，但合併財務報表不變。t59 將 FY2024 重列為 CMBU 3,792、CDBU 4,984、MCBU 11,667、AEBU 4,631、All Other 37、Unallocated 0 百萬美元，總營收仍為 25,111。parser 保留 FY2024 原年報的 CNBU、MBU、EBU、SBU，不以這些重列數字改寫舊輸出。新舊四個分部沒有純改名對應，不宣告 `FORMER_NAMES`。

## 驗證

`data/revenue/M/MU/status.json` 記錄 14 期，其中 13 期 `published`、1 期 `not_derived`，沒有 `failed`。13 期均有正式 `revenue.json` 與運算元對應的 HTML／PNG 證據；原文快照及文件雜湊列於 `data/snapshots/M/MU/manifest.json`。FY2025 Q4 因分部重組不推算，沒有該季營收輸出。

下列 SEC 值單位百萬美元；舊結構依 CNBU／MBU／EBU／SBU／All Other 排序，新結構依 CMBU／CDBU／MCBU／AEBU／All Other 排序。Unallocated 均為明確零。

| 期別 | 期末 | 正式狀態 | SEC 分類值 | 對照結果 |
|---|---|---|---|---|
| FY2024 Q2 | 2024-02-29 | published | 2,185／1,598／1,111／905／25 | Stock Analysis 前四類在精度內，All Other 未列 |
| FY2024 Q3 | 2024-05-30 | published | 2,573／1,588／1,294／1,353／3 | 同上 |
| FY2024 Q4 | 2024-08-29 | published | 3,018／1,875／1,172／1,681／4 | 同上 |
| FY2024 | 2024-08-29 | published | 9,513／6,354／4,614／4,592／38 | TradingView 五類在精度內 |
| FY2025 Q1 | 2024-11-28 | published | 4,395／1,527／1,052／1,731／4 | Stock Analysis 前四類在精度內，All Other 未列 |
| FY2025 Q2 | 2025-02-27 | published | 4,564／1,068／1,025／1,392／4 | 同上 |
| FY2025 Q3 | 2025-05-29 | published | 5,069／1,551／1,227／1,451／3 | 同上 |
| FY2025 Q4 | 2025-08-28 | not_derived | 不輸出 | 年度與前三季分類不同，未比對 |
| FY2025 | 2025-08-28 | published | 13,524／7,229／11,859／4,753／13 | TradingView 五類在精度內 |
| FY2026 Q1 | 2025-11-27 | published | 5,284／2,379／4,255／1,720／5 | Stock Analysis 五類在精度內 |
| FY2026 Q2 | 2026-02-26 | published | 7,749／5,687／7,711／2,708／5 | 同上 |
| FY2026 Q3 | 2026-05-28 | published | 13,769／11,524／11,521／4,634／8 | 同上 |
| FY2026 Q4 | 2026-09-03 | published | 16,283／18,002／13,114／6,824／6 | 同上 |
| FY2026 | 2026-09-03 | published | 43,085／37,592／36,601／15,886／24 | TradingView 五類在精度內 |

TradingView 只有年度，FY2024–FY2026 共 15 個分類值全部在顯示精度內，沒有超出精度差異。其 0.01B 顯示值可與 SEC 相差至 5 百萬，另加 SEC fact 精度誤差；All Other 的 M 顯示值均相同。來源較早年度在範圍外，不列入首次比對。

TradingView 沒有季度，不宣稱季度已獲採用來源驗證。季度輔助 Stock Analysis 用曆季末標籤對齊 MU 財季，例如 Mar 31, 2024 對 FY2024 Q2（2024-02-29），Dec 31, 2025 對 FY2026 Q1（2025-11-27）。10 個可輸出季度共 44 個可比值均在顯示精度內；其舊結構 6 季各缺 All Other，合計 6 值未比對，不當作零或一致。FY2025 Q4 來源雖有新架構值，parser 依規則不推算，故未比對。FY2024 Q1 及更早季度在範圍外。

## 比較欄

正式 `data/revenue/M/MU/status.json` 只有 1 筆比較欄差異標記，沒有 `comparison_errors`：

| 已發布期間 | 角色／分類 | 原申報值 | 較晚申報列示值 | 來源 |
|---|---|---|---|---|
| FY2025 Q2，2024-11-29 至 2025-02-27 | quarter／All Other | 4 百萬 | 6 百萬 | FY2026 Q2 10-Q，0000723125-26-000006，2026-03-19 申報，t28，fact `f-929` |

原值取 FY2025 Q2 10-Q（0000723125-25-000009）t35 的分部軸 AllOtherSegmentsMember，對應正式 `Q/2025-02-27/revenue.json` 的 `op5`；較晚值同 concept、同分部成員，另帶 OperatingSegmentsMember 合併軸，是新結構重列值。FY2025 10-K 已說明分部資料回溯重組，兩者 scope 不同；保留原值，不將 6 回填。其餘舊四個分部沒有新舊名稱對應，不會強行比較；沒有標記不表示它們未重列。All Other 同名的其他比較值在框架精度內，故沒有額外標記。
