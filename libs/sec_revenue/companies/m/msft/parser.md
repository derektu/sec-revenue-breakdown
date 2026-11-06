# MSFT parser

## 觀點

業務分部（`view="business_segment"`），採用 Stock Analysis，順序照該來源。

- 至 2026-06-30：Intelligent Cloud、More Personal Computing、Productivity and Business Processes。
- 自 2026-07-01（FY2027）起，依據期末 2026-09-30 的 10-Q：Agents and Infra、Devices and Consumer。
- 沒有 Corporate、Other 分類或調節項。Stock Analysis 的 Corporate and Other 全期為 `-`，不是零，也不算列出分類。

`us-gaap:StatementBusinessSegmentsAxis` 的成員是業務別，不是地區。三個對照來源主要使用這個觀點，富途有事後重編的歷史季度，TradingView 只有年度。Stock Analysis 的兩類始於 2026-09-30，符合當期 SEC 呈現。

申報另有產品別（`srt:ProductOrServiceAxis`）、Microsoft Cloud 的跨分部拆分（`msft:ProductsOrServicesSecondaryCategorizationAxis`）與地區別。產品別層級不同，Microsoft Cloud 與分部重疊，地區不屬於本專案的觀點，均不採用。

## 分類與 tag

全部使用 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`。分類的完整 dimensions 只有 `us-gaap:StatementBusinessSegmentsAxis` 一個軸，沒有其他維度：

| 分類 | 成員 |
|---|---|
| Intelligent Cloud | `msft:IntelligentCloudMember` |
| More Personal Computing | `msft:MorePersonalComputingMember` |
| Productivity and Business Processes | `msft:ProductivityAndBusinessProcessesMember` |
| Agents and Infra | `msft:AgentsAndInfraMember` |
| Devices and Consumer | `msft:DevicesAndConsumerMember` |
| Total revenue | 無維度的合併 fact |

分類名稱取自 10-Q 分部附註的列標籤，與 Stock Analysis 英文名稱相同。

`compose` 以本次期間是否有 Agents and Infra fact 選擇兩類或三類，不以請求期間的日期把較晚申報的比較欄轉回舊分類。`categories(day)` 自 2026-07-01（FY2027）起切換為兩類，依據期末 2026-09-30 的 10-Q `0001193125-26-436133`，申報日 2026-10-28。該申報 Note 1 與 Note 16 明列 FY2027 起的新結構，2026-07-01 至 2026-09-30 的本期 fact 已為兩類。框架的 `check_categories` 逐日檢查財年起日到 Q3 期末，因此切換點使用新結構第一期的起日。原始季度仍使用各期自己的申報，不重編早期輸出。

## 期別與推算

財年 6 月 30 日結束，季度期末是 9 月 30 日、12 月 31 日、3 月 31 日及 6 月 30 日，非 52／53 週制。

- Q1 至 Q3 使用當期最早原始 10-Q 的三個月 fact。
- FY 使用當期最早原始 10-K 的年度 fact。
- Q4 由框架使用當期 10-K 年度減同財年 Q3 10-Q 九個月累計，受分類集合與 Q4 口徑一致檢核約束。
- FY2025 Q4 不推算。FY2025 10-K 的 FY2024 比較欄已重編，與原 FY2024 年報不同。即使 FY2025 年度減九個月可算出對照來源的值，仍照框架記為 `not_derived`，不補值。FY2025 年度照常輸出。

## 數字在原文的位置

10-Q 與 10-K 的 Segment Information and Geographic Data 附註，分部營收表列各分部與總營收。總營收在損益表、分部表、地區表及產品表有重複 fact，框架核對數值一致，選擇與分類同表的運算元。

## 重列與重分類

### FY2025 起，同名分部範圍改變

[2024-09-30 10-Q](https://www.sec.gov/Archives/edgar/data/789019/000095017024118967/msft-20240930.htm)，accession `0000950170-24-118967`，Note 1 說明 FY2025 起將 Microsoft 365 商業組成集中至 Productivity and Business Processes，並重編比較期。分類名稱與成員未變，parser 不以之後的新口徑改寫原期別。

FY2025 10-K（`0000950170-25-100235`）的 FY2024 年度比較欄，與 FY2024 原年報（`0000950170-24-087843`）不同。單位為百萬美元：

| 分類 | FY2024 原申報 | FY2025 年報列示 FY2024 |
|---|---:|---:|
| Intelligent Cloud | 105,362 | 87,464 |
| More Personal Computing | 62,032 | 50,838 |
| Productivity and Business Processes | 77,728 | 106,820 |

這是 FY2025 Q4 不推算的依據，並在 FY2024 的已輸出期別留下比較欄差異標記。

### FY2027 起，三個分部改為兩個

[2026-09-30 10-Q](https://www.sec.gov/Archives/edgar/data/789019/000119312526436133/msft-20260930.htm)，accession `0001193125-26-436133`，Note 1 與 Note 16 明列 Agents and Infra、Devices and Consumer。它重編 FY2026 Q1 比較欄為兩類，不能據此回填 2025-09-30 的原始三類。

## 驗證

依預設起始日 2024-01-01，逐期比較正式季度輸出與 Stock Analysis 保存資料。來源只有季度，年度核對 SEC 年度 fact 與結構檢核。

### 數值比對

依 fact 的 decimals 誤差，加上 Stock Analysis 的顯示單位一半判定。三類依 Intelligent Cloud、More Personal Computing、Productivity and Business Processes 排列，兩類依 Agents and Infra、Devices and Consumer 排列。每格是「SEC 組合值 / Stock Analysis 值」，單位為百萬美元。對照來自 `data/universe/references/M/MSFT/reference.json`，Stock Analysis capture `20261105T035933Z`。

| 期末日 | 第一類 | 第二類 | 第三類 | 結果 |
|---|---:|---:|---:|---|
| 2024-03-31 | 26,708 / 26,710 | 15,580 / 15,580 | 19,570 / 19,570 | 顯示精度內 |
| 2024-06-30 | 28,515 / 28,520 | 15,895 / 15,900 | 20,317 / 20,320 | 顯示精度內 |
| 2024-09-30 | 24,092 / 24,090 | 13,176 / 13,180 | 28,317 / 28,320 | 顯示精度內 |
| 2024-12-31 | 25,544 / 25,540 | 14,651 / 14,650 | 29,437 / 29,440 | 顯示精度內 |
| 2025-03-31 | 26,751 / 26,750 | 13,371 / 13,370 | 29,944 / 29,940 | 顯示精度內 |
| 2025-06-30 | 不推算 / 29,880 | 不推算 / 13,450 | 不推算 / 33,110 | `not_derived`，不當作一致 |
| 2025-09-30 | 30,897 / 30,900 | 13,756 / 13,760 | 33,020 / 33,020 | 顯示精度內 |
| 2025-12-31 | 32,907 / 32,910 | 14,250 / 14,250 | 34,116 / 34,120 | 顯示精度內 |
| 2026-03-31 | 34,681 / 34,680 | 13,192 / 13,750 | 35,013 / 35,010 | 第二類對照來源錯誤，見查證 |
| 2026-06-30 | 39,306 / 39,310 | 12,854 / 12,850 | 37,847 / 37,850 | 顯示精度內 |
| 2026-09-30 | 76,795 / 76,800 | 15,484 / 15,480 | 不適用 | 顯示精度內 |

10 個已發布季度共 29 個分類值，28 個在顯示精度內，1 個為對照來源錯誤。另有 FY2025 Q4 的 3 個分類不推算，不列入一致數。FY2024、FY2025、FY2026 三個年度均通過數值結構檢核。

### FY2026 Q3 More Personal Computing 對照來源錯誤

SEC 值為 13,192M，Stock Analysis 顯示 13.75B，即 13,750M，高出 558M，超過 5.5M 的比較容許誤差。此筆判定為對照來源錯誤，依據如下：

- [2026-03-31 10-Q](https://www.sec.gov/Archives/edgar/data/789019/000119312526191507/msft-20260331.htm)，accession `0001193125-26-191507`，Note 16 分部表，即框架表格 40。More Personal Computing 單季營收 fact `F_8dd265a2-6916-455e-b5d0-acc93f3db0da` 為 13,192M，期間為 2026-01-01 至 2026-03-31。同期九個月累計為 41,198M，等於 FY2026 Q1 至 Q3 的 13,756 + 14,250 + 13,192M。
- [2026-04-29 8-K 的 EX-99.1](https://www.sec.gov/Archives/edgar/data/789019/000119312526191457/msft-ex99_1.htm)，accession `0001193125-26-191457`，Segment Revenue Constant Currency Reconciliation 與 Segment Results 表也列 More Personal Computing 營收 13,192M。
- Stock Analysis 的該季三類顯示值合計為 34.68 + 13.75 + 35.01 = 83.44B，比 SEC 合併營收 82,886M 高 554M。顯示值經四捨五入，若保留其他兩類的 SEC 精確值，34,681 + 13,750 + 35,013 = 83,444M，比 82,886M 高 558M，正是該筆誤差。
- Stock Analysis 的 FY2026 More Personal Computing 四季合計為 13.76 + 14.25 + 13.75 + 12.85 = 54.61B，比 SEC 年度 54,052M 高 558M。其 Q4 顯示 12.85B，對應年度 54,052M 減以 13,192M 計算的九個月 41,198M，結果為 12,854M，四捨五入為 12.85B。若 Q3 真為 13,750M，九個月會是 41,756M，Q4 應為 12,296M，與它自己的 Q4 不符。
- 較晚申報 `0001193125-26-323660`、`0001193125-26-436133` 沒有以三類重列 2026-01-01 至 2026-03-31 的單季資料，沒有可支持 13,750M 的季度重編。

可能的機制是誤取 Intelligent Cloud 營業利益。同份 10-Q 表格 40 的 fact `F_2d0f773e-9cab-428a-bcaa-5d186fe13967` 為 13,753M，concept 為 `us-gaap:OperatingIncomeLoss`，完整 dimensions 為 `us-gaap:StatementBusinessSegmentsAxis=msft:IntelligentCloudMember`，期間相同，四捨五入為 13.75B。8-K EX-99.1 也列該營業利益。這只是可能的誤取機制，不是判定對照來源錯誤的依據。

## 比較欄

`data/revenue/M/MSFT/status.json` 實際記錄 18 筆 `different` 標記，均為 FY2025 起的分部範圍重編。下表逐筆列出序列、期別、分類、角色、來源 accession 與新舊值，單位為百萬美元。

| 序列 | 原期末日 | 分類 | 角色 | 較晚申報 accession | 已發布值 | 比較欄值 |
|---|---|---|---|---|---:|---:|
| FY | 2024-06-30 | Intelligent Cloud | annual | `0000950170-25-100235` | 105,362 | 87,464 |
| FY | 2024-06-30 | More Personal Computing | annual | `0000950170-25-100235` | 62,032 | 50,838 |
| FY | 2024-06-30 | Productivity and Business Processes | annual | `0000950170-25-100235` | 77,728 | 106,820 |
| FY | 2024-06-30 | Intelligent Cloud | annual | `0001193125-26-323660` | 105,362 | 87,464 |
| FY | 2024-06-30 | More Personal Computing | annual | `0001193125-26-323660` | 62,032 | 50,838 |
| FY | 2024-06-30 | Productivity and Business Processes | annual | `0001193125-26-323660` | 77,728 | 106,820 |
| Q | 2024-03-31 | Intelligent Cloud | quarter | `0000950170-25-061046` | 26,708 | 22,141 |
| Q | 2024-03-31 | More Personal Computing | quarter | `0000950170-25-061046` | 15,580 | 12,604 |
| Q | 2024-03-31 | Productivity and Business Processes | quarter | `0000950170-25-061046` | 19,570 | 27,113 |
| Q | 2024-06-30 | Intelligent Cloud | nine_months | `0000950170-25-061046` | 76,847 | 63,679 |
| Q | 2024-06-30 | More Personal Computing | nine_months | `0000950170-25-061046` | 46,137 | 38,523 |
| Q | 2024-06-30 | Productivity and Business Processes | nine_months | `0000950170-25-061046` | 57,411 | 78,193 |
| Q | 2024-06-30 | Intelligent Cloud | annual | `0000950170-25-100235` | 105,362 | 87,464 |
| Q | 2024-06-30 | More Personal Computing | annual | `0000950170-25-100235` | 62,032 | 50,838 |
| Q | 2024-06-30 | Productivity and Business Processes | annual | `0000950170-25-100235` | 77,728 | 106,820 |
| Q | 2024-06-30 | Intelligent Cloud | annual | `0001193125-26-323660` | 105,362 | 87,464 |
| Q | 2024-06-30 | More Personal Computing | annual | `0001193125-26-323660` | 62,032 | 50,838 |
| Q | 2024-06-30 | Productivity and Business Processes | annual | `0001193125-26-323660` | 77,728 | 106,820 |

FY 2024-06-30 有 6 筆年度標記，Q 2024-03-31 有 3 筆單季標記，Q 2024-06-30 有 3 筆九個月累計與 6 筆年度標記。原值與重編理由見「重列與重分類」，總營收沒有差異。

FY2027 Q1 的兩類比較欄中，FY2026 Q1 的舊三類不存在，比較結果為三筆 `not_found`。依框架現有規則，`not_found` 不寫入 `differences`。因此這三筆不在上述 18 筆標記中，也不代表舊三類與新兩類一致。FY2026 Q1 的原始三類輸出保留。
