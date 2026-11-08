# AMAT parser

## 觀點

採業務分部（`business_segment`），分類名稱與結構跟隨每期原申報。`us-gaap:StatementBusinessSegmentsAxis` 的成員是半導體設備、服務與顯示器業務，不是地區。Corporate and Other、Other 都列為分類，沒有調節項。各分類加總等於無維度的合併總營收。

採用 TradingView，分類順序為 Semiconductor Systems、Applied Global Services、Corporate and Other，最後列仍獨立揭露的 Display 業務。對照資料在 `data/universe/references/A/AMAT/reference.json`。

| 對照來源 | 分類與 SEC 名稱的對應 |
|---|---|
| TradingView | Semiconductor Systems、Applied Global Services、Corporate and Other 同名。長名稱 `Liquid Crystals Displays, Organic Light-emitting Diodes and Equipment Upgrades and Other Display Technologies` 對應 Display and Adjacent Markets 或 Display。FY2025 不再單列 Display。只有年度資料。 |
| Stock Analysis（季度輔助） | Other 對應當期 Corporate and Other 或 Other。Display and Adjacent Markets 同時對應 SEC 舊名與 Display。其他兩個分類同名。 |

兩個來源都在範圍內列出 Corporate 或 Other，因此列為分類。沒有富途資料。另有地區營收 facts，屬地區拆分，不採用。

## 分類與 tag

全部數字取自 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`，單位為 `iso4217:USD`，原文以百萬美元列示，`scale=6`、`decimals=-6`。

Semiconductor Systems、Applied Global Services 與獨立揭露的 Display 業務使用兩個完整維度：

```text
srt:ConsolidationItemsAxis = us-gaap:OperatingSegmentsMember
us-gaap:StatementBusinessSegmentsAxis = 下表成員
```

| 分類 | 成員 |
|---|---|
| Semiconductor Systems | `amat:SemiconductorSystemsMember` 或 `amat:SemiconductorSystemsSegmentMember` |
| Applied Global Services | `amat:AppliedGlobalServicesMember` 或 `amat:AppliedGlobalServicesSegmentMember` |
| Display and Adjacent Markets | `amat:DisplayandAdjacentMarketsMember` |
| Display | `amat:DisplayMember` 或 `amat:DisplaySegmentMember` |

Corporate and Other 與 Other 只有一個維度 `srt:ConsolidationItemsAxis=amat:CorporateAndReconcilingItemsMember`。總營收 `Total net revenue` 不帶任何維度，取分部表的合併數，不取 `OperatingSegmentsMember` 的分部小計。

FY2025 Q1（`0000006951-25-000011`，期末 2025-01-26）起，三個分部改用帶 `SegmentMember` 的成員。`one_of` 在每份申報搜尋兩種成員，找到多種時由框架核對同值，不依日期挑數字。

Display 的名稱與是否單列，依該份申報、該段期間的 fact 決定。有 `DisplayandAdjacentMarketsMember` 時用舊名，有 Display 成員時用 Display，兩者都沒有時不列。Corporate and Other 與 Other 使用相同 tag，無法由 tag 區分列名，故依申報期末日切換名稱。列名取自原文 Industry Segment Operations 附註。

`categories(day)` 的切換如下。涵蓋下限為 2023-10-29（FY2023 10-K 期末，亦為第一個 Q4 的上一財年口徑依據）；更早日期的分類不保證正確。

| 日期範圍 | 分類（依順序） | 切換依據 |
|---|---|---|
| 2023-10-29 至 2024-07-28 | Semiconductor Systems、Applied Global Services、Corporate and Other、Display and Adjacent Markets | FY2023 10-K `0000006951-23-000041` 與 FY2024 Q1–Q3 原申報 |
| 2024-07-29 至 2025-07-27 | Semiconductor Systems、Applied Global Services、Corporate and Other、Display | FY2024 10-K `0000006951-24-000044`，期末 2024-10-27，切換日取 Q4 起日 |
| 2025-07-28 至 2025-10-26 | Semiconductor Systems、Applied Global Services、Corporate and Other | FY2025 10-K `0001628280-25-056742`，期末 2025-10-26，切換日取 Q4 起日 |
| 2025-10-27 起 | Semiconductor Systems、Applied Global Services、Other | FY2026 Q1 10-Q `0001628280-26-009694`，期末 2026-01-25，切換日取 Q1 起日 |

## 期別與推算

財年採 52 或 53 週制，於 10 月最後一個星期日結束。範圍內 FY2024、FY2025 均為 364 天；Q1–Q3 單季 91 天、半年 182 天、九個月 273 天，都在框架預設範圍。財年取申報宣告，所需 facts 均在主文件。不宣告 `DURATION_DAYS`、`FISCAL_YEAR` 或 `ATTACHMENTS`。

Q1–Q3 取主申報的單季 facts，FY 取主 10-K 的年度 facts。Q4 原則為年度減同財年原 Q3 的九個月累計，但以下兩期依「Q4 推算條件」不推算：

| 季別 | 期末日 | 原因 |
|---|---|---|
| FY2024 Q4 | 2024-10-27 | 年報列 Display，Q1–Q3 列 Display and Adjacent Markets。純改名仍改變分類集合，`FORMER_NAMES` 不豁免 Q4 條件。 |
| FY2025 Q4 | 2025-10-26 | 年報將 Display 併入 Corporate and Other，Q1–Q3 仍分列，分類集合不同。 |

## 數字在原文的位置

表號與證據檔名取自正式 `data/revenue/A/AMAT/<序列>/<期末日>/revenue.json` 的運算元 `evidence.table`。每期所有分類與總營收都選在同一張表。下表的檔名不含副檔名，對應各期 `evidence/` 內的 `.html` 與 `.png`；原 SEC 文件 URL、文件雜湊與表格證據雜湊保留在各運算元。

| 期別 | accession | 表格 | 證據檔名（不含副檔名） | 內容 |
|---|---|---|---|---|
| FY2024 Q1 | `0000006951-24-000012` | t45 | `0000006951-24-000012-bc1c5fac4404-t45` | 分部營收及營業損益表 |
| FY2024 Q2 | `0000006951-24-000022` | t45 | `0000006951-24-000022-188ce0a0cf42-t45` | 同上，另有半年累計 |
| FY2024 Q3 | `0000006951-24-000032` | t45 | `0000006951-24-000032-979098308c62-t45` | 同上，另有九個月累計 |
| FY2024 | `0000006951-24-000044` | t59 | `0000006951-24-000044-65d9c6ebd80c-t59` | Industry Segment Operations，三個年度的營收及營業損益 |
| FY2025 Q1 | `0000006951-25-000011` | t35 | `0000006951-25-000011-21dbd5b7b791-t35` | 分部營收及營業損益表 |
| FY2025 Q2 | `0000006951-25-000024` | t35 | `0000006951-25-000024-c4aab38a5f1f-t35` | 同上，另有半年累計 |
| FY2025 Q3 | `0000006951-25-000037` | t35 | `0000006951-25-000037-4f53013433a0-t35` | 同上，另有九個月累計 |
| FY2025 | `0001628280-25-056742` | t61 | `0001628280-25-056742-3d6c0b142778-t61` | 本年度分部資訊，分類各自列 Net revenue，末列 Total 的 Net revenue 為合併數 |
| FY2026 Q1 | `0001628280-26-009694` | t37 | `0001628280-26-009694-6e43d62c23a3-t37` | 本季分部資訊 |
| FY2026 Q2 | `0001628280-26-037227` | t38 | `0001628280-26-037227-0b73d186c130-t38` | 本季分部資訊 |
| FY2026 Q3 | `0001628280-26-058235` | t38 | `0001628280-26-058235-aeb596931b03-t38` | 本季分部資訊 |

FY2023 10-K `0000006951-23-000041` 的 t84 為 Industry Segment Operations，列出三個分部、Corporate and Other 與合併總營收。此申報保存在 `data/snapshots/A/AMAT/0000006951-23-000041.jsonl`，只作第一個 Q4 的上一財年口徑依據，不在正式營收輸出範圍內。

## 已知的重複 fact

合併營收另標於損益表及地區表。Corporate and Other 在部分申報的其他表格重複標記，FY2024、FY2025 各 10-Q 的分部營收也在 MD&A 重複。框架先依精度，再選含最多其他項目的表格，最後依文件順序選 fact，其餘 fact id 留在運算元的 `duplicates`。範圍內選中的重複 facts 均通過一致性檢核。

## 改名、合併與 200mm 重列

以下金額均為百萬美元。較晚申報僅作比較證據，不是早期輸出的運算元。

### Display 純改名

宣告 `FORMER_NAMES = {"Display": ("Display and Adjacent Markets",)}`。首次改名是 [FY2024 10-K](https://www.sec.gov/Archives/edgar/data/6951/000000695124000044/amat-20241027.htm)，其原文列名與 tag 均改為 Display。重疊期別新舊值如下，沒有以後期數字改寫原申報：

| 期間 | 舊名原申報、表格、值 | 新名比較欄申報、表格、值 |
|---|---|---|
| FY2023 | `0000006951-23-000041` t84：868 | `0000006951-24-000044` t59：868 |
| FY2024 Q1 | `0000006951-24-000012` t45：244 | `0000006951-25-000011` t35：244 |
| FY2024 Q2 | `0000006951-24-000022` t45：179 | `0000006951-25-000024` t35：179 |
| FY2024 上半年 | `0000006951-24-000022` t45：423 | `0000006951-25-000024` t35：423 |
| FY2024 Q3 | `0000006951-24-000032` t45：251 | `0000006951-25-000037` t35：251 |
| FY2024 前九個月 | `0000006951-24-000032` t45：674 | `0000006951-25-000037` t35：674 |

### Display 合併

[FY2025 10-K](https://www.sec.gov/Archives/edgar/data/6951/000162828025056742/amat-20251026.htm) Note 15 將 Display 併入 Corporate and Other。FY2024 比較欄 t62 的 Corporate and Other 為 1,040，等於 FY2024 原 10-K t59 的 155 加 Display 885。FY2023 比較欄 t63 為 1,087，等於 FY2023 原 10-K t84 的 219 加 Display and Adjacent Markets 868。這是合併，不宣告名稱對應，也不替早期輸出補合併值。

### Other 名稱對應的限制

[FY2026 Q1 10-Q](https://www.sec.gov/Archives/edgar/data/6951/000162828026009694/amat-20260125.htm) 起，原文改列 Other。現有 FY2026 Q1–Q3 比較欄只列 FY2025 季度與累計，沒有 FY2025 年度。因此無法直接與 FY2025 10-K 已合併 Display 的 Corporate and Other 做同期間同值比較，不宣告 `Other ← Corporate and Other`。

已取得的比較欄數字如下，但都是與合併前兩分類相加比較，不能把 Other 說成合併前 Corporate and Other 的純改名：

| FY2025 期間 | 原 10-Q 的 Corporate and Other + Display | FY2026 比較欄 Other |
|---|---|---|
| Q1 | `0000006951-25-000011` t35：33 + 183 = 216 | `0001628280-26-009694` t39：216 |
| Q2 | `0000006951-25-000024` t35：20 + 259 = 279 | `0001628280-26-037227` t40：279 |
| 上半年 | `0000006951-25-000024` t35：53 + 442 = 495 | `0001628280-26-037227` t41：495 |
| Q3 | `0000006951-25-000037` t35：12 + 263 = 275 | `0001628280-26-058235` t40：275 |
| 前九個月 | `0000006951-25-000037` t35：65 + 705 = 770 | `0001628280-26-058235` t41：770 |

### 200mm 業務移轉

FY2026 Q1 起，200mm 設備業務由 Applied Global Services 移至 Semiconductor Systems，申報並說明比較欄已依新結構重列。原季度數字保留，比較欄留下差異標記，見下表。Corporate 支援成本全數分攤亦自 FY2026 起改變，涉及成本及費用，不能用來改寫營收。

## 驗證

正式 `data/revenue/A/AMAT/status.json` 涵蓋 FY2024 Q1 至 FY2026 Q3，共 13 期：9 個 Q1–Q3 與 2 個年度為 `published`，FY2024、FY2025 Q4 為 `not_derived`，沒有 `failed`。不推算的原因見「期別與推算」。11 期正式 `revenue.json` 的分類加總均等於總營收，差額為 0；各期運算元均有表格 HTML 與 PNG 證據。快照及 manifest 位於 `data/snapshots/A/AMAT/`。下列數字均取自正式輸出。

採用來源 TradingView 只有年度資料。以下每個分類都在顯示精度內，超出精度的差異為 0 筆。表中值依 Semiconductor Systems、Applied Global Services、Corporate and Other、Display 的順序，單位為百萬美元。

| FY、SEC 期末日 | parser | TradingView 顯示值 | parser 減來源（百萬美元） | 結論 |
|---|---|---|---|---|
| FY2024，2024-10-27 | 19,911；6,225；155；885 | 19.91B；6.22B；155.00M；885.00M | +1；+5；0；0 | 全部在顯示精度內 |
| FY2025，2025-10-26 | 20,798；6,385；1,185；不單列 Display | 20.80B；6.38B；1.19B；不單列 Display | −2；+5；−5；不適用 | 全部在顯示精度內 |

`0.01B` 的半個顯示單位為 5 百萬，加一個 SEC 運算元的半個精度單位 0.5 百萬，容許差為 5.5 百萬。`0.01M` 的容許差為 0.005 + 0.5 = 0.505 百萬。上表的 5 百萬邊界差額均符合規則，沒有將空值當零。合併總營收 FY2024 為 27,176，FY2025 為 28,368；此對照來源沒有獨立總營收列可比。

TradingView 沒有範圍內季度，因此九個 Q1–Q3 都沒有與採用來源比對，改用 Stock Analysis 作季度輔助。下表每個已列分類都在顯示精度內。前三個數字依 Semiconductor Systems、Applied Global Services、當期 Corporate and Other 或 Other 排列，第四個是仍獨立列示的 Display 業務。

| 季別 | SEC 期末日 | Stock Analysis 對齊日期 | parser（百萬美元） | 輔助比對 |
|---|---|---|---|---|
| FY2024 Q1 | 2024-01-28 | 2023-12-31 | 4,909；1,476；78；244 | 全部在顯示精度內 |
| FY2024 Q2 | 2024-04-28 | 2024-03-31 | 4,901；1,530；36；179 | 同上 |
| FY2024 Q3 | 2024-07-28 | 2024-06-30 | 4,924；1,580；23；251 | 同上 |
| FY2025 Q1 | 2025-01-26 | 2024-12-31 | 5,356；1,594；33；183 | 同上 |
| FY2025 Q2 | 2025-04-27 | 2025-03-31 | 5,255；1,566；20；259 | 同上 |
| FY2025 Q3 | 2025-07-27 | 2025-06-30 | 5,427；1,600；12；263 | 同上 |
| FY2026 Q1 | 2026-01-25 | 2025-12-31 | 5,141；1,559；312 | 同上 |
| FY2026 Q2 | 2026-04-26 | 2026-03-31 | 5,965；1,665；280 | 同上 |
| FY2026 Q3 | 2026-07-26 | 2026-06-30 | 7,040；1,781；294 | 同上 |

FY2024、FY2025 Q4 均 `not_derived`，沒有 parser 數字，不拿 Stock Analysis 的 Q4 作通過比對，也不以來源值補入。沒有完整四季的 parser 加總，不作四季加總對年度的驗證。TradingView 的 FY2023 與更早年度，以及對齊後落在 FY2024 以前的 Stock Analysis 季度，都在處理範圍外，不列入正式逐期比對。

## 比較欄

正式 `data/revenue/A/AMAT/status.json` 共記錄 7 筆 `different`，沒有 `unparseable` 或 `comparison_errors`。下表逐筆列出原值、較晚申報列示值及原因，金額為百萬美元。原值保留於各期正式 `revenue.json`；比較欄表號對應較晚申報的快照 fact 所在表格，不是原期輸出的 `evidence.table`。

| 被比較期別 | 分類、角色 | 原值 | 較晚申報列示值 | 來源、表格與原因 |
|---|---|---|---|---|
| FY2024 | Corporate and Other，annual | 155 | 1,040 | `0001628280-25-056742` t62；併入 Display 885 |
| FY2025 Q1 | Semiconductor Systems，quarter | 5,356 | 5,597 | `0001628280-26-009694` t39；200mm 業務移入 241 |
| FY2025 Q1 | Applied Global Services，quarter | 1,594 | 1,353 | 同上；200mm 業務移出 241 |
| FY2025 Q2 | Semiconductor Systems，quarter | 5,255 | 5,401 | `0001628280-26-037227` t40；200mm 業務移入 146 |
| FY2025 Q2 | Applied Global Services，quarter | 1,566 | 1,420 | 同上；200mm 業務移出 146 |
| FY2025 Q3 | Semiconductor Systems，quarter | 5,427 | 5,564 | `0001628280-26-058235` t40；200mm 業務移入 137 |
| FY2025 Q3 | Applied Global Services，quarter | 1,600 | 1,463 | 同上；200mm 業務移出 137 |

FY2025 Q3 的九個月比較欄 t41，Semiconductor Systems 為 16,562，原 Q3 t35 為 16,038；AGS 為 4,236，原值為 4,760。兩側差額均為 524 = 241 + 146 + 137。兩個 Q4 不推算，沒有 Q4 九個月運算元供框架留下 `nine_months` 差異標記。

Display 純改名的比較欄與原值相同，因此沒有差異標記。Display 併入 Corporate and Other 後，消失的 Display 分類不另外產生差異標記。未宣告 Other 名稱對應，框架也不比較 FY2025 的 Corporate and Other 與 FY2026 比較欄 Other；沒有標記不能當作兩個名稱同值的證明。
