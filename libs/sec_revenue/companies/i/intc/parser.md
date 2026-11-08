# INTC parser

## 觀點

採用抵銷前業務分部營收（`business_segment`），對照來源為 TradingView。`us-gaap:StatementBusinessSegmentsAxis` 的成員為運算、晶圓代工等業務別，不是地區。

| 期別 | 分類順序 |
|---|---|
| 2024 Q1 至 FY2024 | Client Computing Group、Intel Foundry、Data Center and AI、All Other、Network and Edge |
| 2025 Q1 至 2026 Q1 | Client Computing Group、Intel Foundry、Data Center and AI、All Other |
| 2026 Q2 起 | Client Computing and Physical AI Group、Intel Foundry、Data Center and AI、All Other |

Intersegment eliminations 為調節項，參與加總但不列為分類；分部包含內部交易，分類加總加上負值抵銷才等於無維度的合併總營收。

TradingView 的 Data Center and Artificial Intelligence 對應 SEC 的 Data Center and AI，其餘名稱直接對應。TradingView 與 Stock Analysis 均有 Other 層級、均未列抵銷，因此 All Other 列為分類，抵銷列為調節項。

Stock Analysis 僅作輔助，其 Client Computing、Data Center、Foundry Services 分別對應 CCG 或 CCPG、DCAI、Intel Foundry。2024 Q1 至 Q3 的 Other 是不含 Altera、Mobileye 的剩餘 Other，不能與本 parser 的 All Other 合計直接相比。該來源缺 Altera，Mobileye、Network and Edge 亦非每期都有值；Accelerated Computing、Internet of Things 在範圍內沒有值。富途沒有本機對照資料。申報另有產品細項與地區拆分，本觀點不採用。

## 分類與 tag

全部項目使用 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`，單位 USD。以下每列列出完整 dimensions，不另隱含其他維度：

| 分類或項目 | 完整 dimensions |
|---|---|
| Client Computing Group | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；`us-gaap:StatementBusinessSegmentsAxis=intc:ClientComputingGroupMember` |
| Client Computing and Physical AI Group | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；`us-gaap:StatementBusinessSegmentsAxis=intc:ClientComputingAndPhysicalAIGroupMember` |
| Intel Foundry | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；`us-gaap:StatementBusinessSegmentsAxis=intc:IntelFoundryMember` |
| Data Center and AI | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；`us-gaap:StatementBusinessSegmentsAxis=intc:DatacenterAndAIMember` |
| All Other，2024 Q1 至 Q3 | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；`us-gaap:StatementBusinessSegmentsAxis=intc:AlteraMobileyeAndOtherMember` |
| All Other，FY2024 起 | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；`us-gaap:StatementBusinessSegmentsAxis=us-gaap:AllOtherSegmentsMember` |
| Network and Edge | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；`us-gaap:StatementBusinessSegmentsAxis=intc:NetworkAndEdgeMember` |
| Intersegment eliminations | `srt:ConsolidationItemsAxis=us-gaap:IntersegmentEliminationMember` |
| Total net revenue | 無維度 |

`compose` 依該申報、該期間的 fact 選結構，不以後來的分類改寫較早申報：

- 有 Intel Foundry 的新模型 fact 時採新結構；有 CCPG 成員時用新名稱，否則用 CCG。有 NEX fact 時獨立列出。
- All Other 優先取 `AlteraMobileyeAndOtherMember`，沒有才取 `AllOtherSegmentsMember`。不能用 `one_of` 將兩者視為同值：2024 Q1 至 Q3 兩者同時存在，後者只代表剩餘 Other。以 Q3 單季為例，Altera 412、Mobileye 485、剩餘 Other 142，合計 1,039 百萬美元；九個月為 1,115＋1,164＋503＝2,782 百萬美元，均等於明列合計。輸出只取合計 fact，不以細項另算。
- FY2024 起分部表的 All Other 欄已是合計，見 `0000050863-25-000009` t148。分類與調節項各取一個 fact，沒有跨申報補數或倒算分類。

分類名稱取自分部附註及分部表：10-Q 的 CCG、DCAI、NEX 全名與年報的縮寫欄標對應；All Other 沿用年報欄標大小寫。總營收在 10-Q 列為 Total net revenue，年報列為 Total Consolidated 的 Revenue。

### FY2023 口徑基準

`0000050863-24-000010` 的 FY2023 原申報仍是舊模型，僅供第一個 Q4 的上一財年口徑依據，不在預設輸出範圍。完整 dimensions 為 `srt:ConsolidatedEntitiesAxis=us-gaap:OperatingSegmentsMember`，再加 `us-gaap:StatementBusinessSegmentsAxis` 的下列成員：

| 原申報分類順序 | 分部成員 |
|---|---|
| Client Computing | `intc:ClientComputingGroupMember` |
| Data Center and AI | `intc:DatacenterAndAIMember` |
| Network and Edge | `intc:NetworkAndEdgeMember` |
| Mobileye | `intc:MobileyeSegmentMember` |
| Intel Foundry Services | `intc:IntelFoundryServicesMember` |
| All Other | `us-gaap:AllOtherSegmentsMember` |

這份申報沒有新模型的抵銷調節項，六項直接加總為無維度總營收。IFS 與 Intel Foundry 範圍不同，不宣告改名；Mobileye 亦不對應成新的 All Other。FY2023 的 Client Computing 名稱取自 t180 的列標籤。

## 期別與推算

採 52／53 週財年，12 月最後一個星期六結束，季末為星期六。本機範圍內單季 91 天、半年 182 天、九個月 273 天、年度 364 天，沿用框架期間長度範圍。財年與季別依申報 dei，無需 `FISCAL_YEAR`、`DURATION_DAYS` 或 `ATTACHMENTS` 自訂。

`categories(day)` 涵蓋下限為 2023-12-30，包含第一個 Q4 所需的上一財年期末日；更早日期未驗證。切換日期取新結構第一季起日：

| 起日 | 首份主申報及期末日 | 改變 |
|---|---|---|
| 2023-12-31 | `0000050863-24-000076`，2024-03-30 | 內部 foundry 模型、Altera 自 DCAI 移入 All Other，採五類加抵銷 |
| 2024-12-29 | `0000050863-25-000074`，2025-03-29 | NEX 整合進 CCG、DCAI，取消獨立 NEX |
| 2026-03-29 | `0000050863-26-000157`，2026-06-27 | CCG 改名 CCPG |

Q1 至 Q3 取各期原始 10-Q 的單季 fact，FY 取原始 10-K 年度 fact。Q4 由框架以年度減 Q3 九個月累計，並檢核分類集合與上一財年口徑。2024、2025 Q4 均因「Q4 口徑一致」不成立而 `not_derived`，不人工補值。

| Q4 | 上一財年原值 → 該年報比較欄，百萬美元 | 證據 |
|---|---|---|
| 2024-12-28 | FY2023 DCAI 15,521 → 12,635；All Other 644 → 5,608 | FY2023 原申報 `0000050863-24-000010` t180；FY2024 年報 `0000050863-25-000009` t149 |
| 2025-12-27 | FY2024 CCG 30,290 → 33,346；DCAI 12,817 → 16,125；Intel Foundry 17,543 → 17,317；All Other 3,824 → 3,601；抵銷 −17,215 → −17,288 | FY2024 原申報 `0000050863-25-000009` t148；FY2025 年報 `0000050863-26-000011` t159 |

2024 年啟用內部 foundry 模型及 Altera 移出 DCAI，使 FY2023 比較欄重列。2025 年 NEX 整合與其他業務重組使 FY2024 比較欄重列，即使 2025 年前三季與年度同為新結構，框架仍不推算 Q4。較晚申報只解釋差異，不提供早期輸出的數字。

2025 Q3 起 Altera 自 2025-09-12 不再合併，見 `0000050863-25-000179` 的分部附註及 Note 9。All Other 保留該期申報的實際範圍，不調整以前期別。正式輸出範圍截至 2026 Q3，沒有 FY2026 或 2026 Q4。

## CCG 改名證據

`0000050863-26-000157` 的分部附註明列 Client Computing and Physical AI Group (CCPG), formerly the Client Computing Group (CCG)。宣告 `FORMER_NAMES = {"Client Computing and Physical AI Group": ("Client Computing Group",)}`，僅用於比較欄與 Q4 口徑比對，不改早期輸出名稱。

新舊名稱重疊期別同值，單位百萬美元：

| 期間 | 原申報 CCG | 新申報 CCPG | 證據 |
|---|---|---|---|
| 2025 Q2 | 7,871 | 7,871 | `0000050863-25-000109` t28；`0000050863-26-000157` t31 |
| 2025 Q1 | 7,629 | 15,500 − 7,871＝7,629 | `0000050863-25-000074` t29；`0000050863-26-000157` t33 半年減 t31 單季 |
| 2026 Q1 | 7,727 | 16,604 − 8,877＝7,727 | `0000050863-26-000079` t27；`0000050863-26-000157` t32 半年減 t30 單季 |

上述相減只作改名證據，不是輸出的運算元。各項 concept 與完整 dimensions 如「分類與 tag」所列，半年 fact 也取同一套維度。

## 數字在原文的位置

正式證據位於 `data/revenue/I/INTC/<序列>/<期末日>/evidence/`。下表檔名對應各期 `revenue.json` 運算元的 `evidence.table`，各有 `.html` 與 `.png`；季度序列為 `Q`，年度序列為 `FY`。所有正式輸出的分類、抵銷與無維度總營收均取自各列的同一張分部營收表。

| 期別 | 表格內容 | 證據檔名（不含副檔名） |
|---|---|---|
| 2024 Q1 | t32，五類、抵銷、總營收 | `0000050863-24-000076-298c6b48ceb6-t32` |
| 2024 Q2 | t32，五類、抵銷、總營收 | `0000050863-24-000124-1a866137224d-t32` |
| 2024 Q3 | t32，五類、抵銷、總營收 | `0000050863-24-000149-1a8dd8c8eddc-t32` |
| FY2024 | t148，五類、抵銷、總營收 | `0000050863-25-000009-848f860b0adc-t148` |
| 2025 Q1 | t29，四類、抵銷、總營收 | `0000050863-25-000074-cdb187d6f1ea-t29` |
| 2025 Q2 | t28，四類、抵銷、總營收 | `0000050863-25-000109-1c1e8ce0d32f-t28` |
| 2025 Q3 | t28，四類、抵銷、總營收的單季表 | `0000050863-25-000179-9b6450cbbc8a-t28` |
| FY2025 | t158，四類、抵銷、總營收 | `0000050863-26-000011-d43b87103bc3-t158` |
| 2026 Q1 | t27，四類、抵銷、總營收 | `0000050863-26-000079-04f2ca953d1c-t27` |
| 2026 Q2 | t30，四類、抵銷、總營收的單季表 | `0000050863-26-000157-7964c0414f49-t30` |
| 2026 Q3 | t30，四類、抵銷、總營收的單季表 | `0000050863-26-000191-a3ccf3bc518f-t30` |

FY2023 原申報 `0000050863-24-000010` 僅供第一個 Q4 的上一財年口徑基準，沒有正式證據檔。六分部營收在 t180，無維度合併總營收在 t155、t182。兩個 Q4 均為 `not_derived`，沒有 Q4 的 `revenue.json` 或證據檔；2025 Q3 的九個月表 t30、2026 Q2 的半年表 t32、2026 Q3 的九個月表 t32 均不屬於上述正式輸出證據。

## 已知的重複 fact

無維度總營收同時出現在損益表、分部表及部分其他表格，期間與完整維度相同的 fact 由框架檢查一致，再依精度與同表項目數選取。正式輸出運算元的總營收與分部均選在同一張表；FY2023 基準的總營收另外出現在 t155、t182，不把帶 OperatingSegmentsMember 的分部小計當作合併總營收。

## 驗證

`data/revenue/I/INTC/status.json` 記錄 11 期 `published`、2 期 `not_derived`，沒有 `failed`。正式 `revenue.json` 包含 2024 至 2026 年各年的 Q1 至 Q3，以及 FY2024、FY2025；兩個 Q4 因上一財年比較欄重列而不推算，原因與數值見「期別與推算」。下表依正式輸出逐期列示與 TradingView 的比對範圍。

| 財年與期別 | 期末日 | 狀態 | 與採用來源 TradingView 比對 |
|---|---|---|---|
| 2024 Q1 | 2024-03-30 | published | 無季度資料，不比對 |
| 2024 Q2 | 2024-06-29 | published | 無季度資料，不比對 |
| 2024 Q3 | 2024-09-28 | published | 無季度資料，不比對 |
| 2024 Q4 | 2024-12-28 | not_derived | Q4 口徑一致不成立；來源亦無季度資料 |
| FY2024 | 2024-12-28 | published | 五類在顯示精度內 |
| 2025 Q1 | 2025-03-29 | published | 無季度資料，不比對 |
| 2025 Q2 | 2025-06-28 | published | 無季度資料，不比對 |
| 2025 Q3 | 2025-09-27 | published | 無季度資料，不比對 |
| 2025 Q4 | 2025-12-27 | not_derived | Q4 口徑一致不成立；來源亦無季度資料 |
| FY2025 | 2025-12-27 | published | 四類在顯示精度內 |
| 2026 Q1 | 2026-03-28 | published | 無季度資料，不比對 |
| 2026 Q2 | 2026-06-27 | published | 無季度資料，不比對 |
| 2026 Q3 | 2026-09-26 | published | 無季度資料，不比對 |

對照資料位於 `data/universe/references/I/INTC/reference.json`，TradingView 擷取批次 `20261108T070622Z`，以財年 2024、2025 對齊；較早年度在範圍外，未確認。各分類 SEC 原值減來源 usd 的差額如下，單位百萬美元：

| 財年 | 分類 | SEC | TradingView 顯示 | 差額 |
|---|---|---|---|---|
| FY2024 | Client Computing Group | 30,290 | 30.29B | 0 |
| FY2024 | Intel Foundry | 17,543 | 17.54B | +3 |
| FY2024 | Data Center and AI | 12,817 | 12.82B | −3 |
| FY2024 | All Other | 3,824 | 3.82B | +4 |
| FY2024 | Network and Edge | 5,842 | 5.84B | +2 |
| FY2025 | Client Computing Group | 32,228 | 32.23B | −2 |
| FY2025 | Intel Foundry | 17,826 | 17.83B | −4 |
| FY2025 | Data Center and AI | 16,919 | 16.92B | −1 |
| FY2025 | All Other | 3,563 | 3.56B | +3 |

九筆均未超過來源 0.01B 顯示單位的一半加單一 SEC fact 精度誤差，即 5.5 百萬美元，沒有超出精度的差異。來源沒有列抵銷或總營收，本項不宣稱兩者經該來源驗證；兩者由 SEC fact 與加總檢核驗證。

Stock Analysis 保留輔助限制：2024 Q2、Q3 及 2025 Q1 至 Q3 的部分對應分類與 SEC 原申報超出顯示精度，原因未確認，不標一致。例如 2024 Q2 DCAI 為 SEC 3,045、來源 3,000 百萬美元；2025 Q1 All Other 為 SEC 943、來源 900 百萬美元。這些差異不是採用來源 TradingView 的差異，也不據此改動 SEC 原值。

## 比較欄

正式 `status.json` 的 `differences` 共 20 筆，分布於 2024 Q1、Q2、Q3 與 FY2024，各五筆，均為 2025 年 NEX 整合及其他業務重組後重列 2024 年比較欄。每格為正式輸出原值 → 後續申報列示值，單位百萬美元：

| 原期別與角色 | CCG | Intel Foundry | DCAI | All Other | Intersegment eliminations | 來源 accession、表格 |
|---|---|---|---|---|---|---|
| 2024 Q1，quarter | 7,533 → 8,273 | 4,369 → 4,356 | 3,036 → 3,828 | 775 → 643 | −4,353 → −4,376 | `0000050863-25-000074` t30 |
| 2024 Q2，quarter | 7,410 → 8,143 | 4,320 → 4,282 | 3,045 → 3,805 | 968 → 881 | −4,254 → −4,278 | `0000050863-25-000109` t29 |
| 2024 Q3，quarter | 7,330 → 8,161 | 4,352 → 4,339 | 3,349 → 4,141 | 1,039 → 964 | −4,297 → −4,321 | `0000050863-25-000179` t29 |
| FY2024，annual | 30,290 → 33,346 | 17,543 → 17,317 | 12,817 → 16,125 | 3,824 → 3,601 | −17,215 → −17,288 | `0000050863-26-000011` t159 |

分部附註說明重列，原期別保留原始申報值。NEX 在新結構不再獨立列出，不能把缺失當作零；原期別仍保留獨立 NEX。2025 年各季與 FY2025、2026 年各季沒有差異標記，CCG 純改名透過 `FORMER_NAMES` 比對。兩個 Q4 沒有推算輸出，也沒有九個月運算元的輸出差異標記。`comparison_errors` 沒有紀錄。
