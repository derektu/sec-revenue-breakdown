# KO parser

## 觀點

產品別（`view="product"`），依營運類型分 2 類：Concentrate operations、Finished product operations。

| 對照來源 | 拆分 |
|---|---|
| TradingView | Concentrate、Finished Product |
| Stock Analysis | 營運分部：North America、EMEA、Latin America、Asia Pacific、Bottling Investments、Corporate、Eliminations（2024 年另有 Global Ventures） |
| 富途 | 與 Stock Analysis 相同的營運分部 |

KO 的營運分部除了 Bottling Investments、Global Ventures 與 Corporate，都以地區劃分。地區拆分不是觀點，所以不採用，改用營運類型。

## 分類與 tag

| 分類 | 期末日至 2023-09-29、2024-01-01 起 | 期末日 2023-09-30 至 2023-12-31 |
|---|---|---|
| Concentrate operations | `us-gaap:Revenues` × `srt:ProductOrServiceAxis=ko:ConcentrateOperationsMember` | `ko:Netoperatingrevenuesrelatedtoconcentrateoperations`（不帶維度） |
| Finished product operations | `us-gaap:Revenues` × `srt:ProductOrServiceAxis=ko:FinishedProductOperationsMember` | `ko:Netoperatingrevenuesrelatedtofinishedproductoperations`（不帶維度） |
| 總營收（Net operating revenues） | `us-gaap:Revenues` 不帶維度 | 同左 |

- 兩類加總等於總營收，沒有調節項。
- FY2023 10-K（期末 2023-12-31）以公司自訂 concept 標示兩類營收，所以每個分類有三個 `effective` 定義。
- 相鄰定義的生效期間首尾相接。Q4 推算條件逐日比對財年起日到 Q3 期末的分類集合，生效期間中間若有空檔，會被判為分類不同。
- 範圍內（2024-01-01 起）的期別與運算元都用 `us-gaap:Revenues` 的定義。自訂 concept 的定義供 `--start` 指定更早的期別時使用。
- 分類名稱取自營收附註表的列標籤；總營收取自同表的 `Total`，即損益表的 `Net operating revenues`。

## 期別與推算

- 財年即曆年。Q1–Q3 的季末日是接近季底的星期五（例如 2024-03-29、2026-04-03），Q4 期末是 12 月 31 日。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同年 Q3 10-Q 的九個月累計。年度與 Q1–Q3 的分類相同，範圍內每個 Q4 都推算。
- FY：10-K 的年度 fact。

## 數字在原文的位置

- 位置：營收附註中依營運類型與 United States／International 拆分的營收表，數字取 Total 欄。
- Q1–Q3 與 FY 每期一張表；Q4 為 10-K 與 Q3 10-Q 各一張。

## 2025 年度的重分類

FY2025 10-K 與 2026 年各 10-Q 的 2025 比較欄，改用另一個 Concentrate／Finished 拆分口徑：

- 總營收不變。
- 每季約 6–7 億美元由 Concentrate 移到 Finished，主要在 International 欄。
- 2025 年三份 10-Q 原本揭露的 Concentrate 占比約 65%；新口徑與 FY2024 約 59%–60%。
- 10-K 與 2026 年 10-Q 都沒有說明這次調整。
- FY2024 的年度數字沒有被重列。

因此 2025 年 Q4（2025-12-31）是新口徑的年度減舊口徑的九個月（單位百萬美元）：

| 分類 | 我們（年度 − 九個月原值） | 依新口徑九個月計算 |
|---|---|---|
| Concentrate operations | 28,462 − 23,670 ＝ 4,792 | 28,462 − 21,711 ＝ 6,751 |
| Finished product operations | 19,479 − 12,449 ＝ 7,030 | 19,479 − 14,408 ＝ 5,071 |

- 新口徑的九個月累計最早出現在 2026 年 Q3 10-Q 的比較欄（申報日 2026-10-28），晚於 2025 年度 10-K。依 point in time，2025 年 Q4 用的是 10-K 申報當時可見的九個月原值。
- 兩類的分類集合沒有改變，Q4 推算條件成立。
- FY2025 10-K 沒有重列 FY2024，10-K 也沒有九個月的數字，所以年報申報時無法判斷口徑已經改變，口徑一致的條件也成立。
- 使用者核准：這一期照常推算，口徑變更由之後申報的比較欄寫成差異標記揭露，不另訂規則。
- 2026 年各 10-Q 的比較欄與已上線值的差異，都寫成差異標記（見比較欄）。

## 驗證

11 季（2024-03-29 至 2026-10-02）與 2 個年度，與對照資料逐期比對：

- TradingView（只有年度）：FY2024、FY2025 兩類都在顯示精度內。FY2025 是 10-K 的新口徑數字。
- Stock Analysis、富途：只有營運分部，沒有可比的分類。KO 的財報新聞稿也沒有這組拆分的金額，所以 2025 年 Q4 沒有外部來源可以核對。
- FY 序列：FY2024、FY2025 都等於同財年四季加總。

## 比較欄

差異標記都是 2025 年度的重分類造成的，Concentrate 減少的金額等於 Finished 增加的金額（單位百萬美元）：

| 期別 | 運算元 | 已上線值 → 申報列示值（Concentrate／Finished） | 來源申報 |
|---|---|---|---|
| 2025-03-28 | 單季 | 7,183 → 6,594／3,946 → 4,535 | 2026 年 Q1 10-Q |
| 2025-06-27 | 單季 | 8,289 → 7,618／4,246 → 4,917 | 2026 年 Q2 10-Q |
| 2025-09-26 | 單季 | 8,198 → 7,499／4,257 → 4,956 | 2026 年 Q3 10-Q |
| 2025-12-31 | 九個月 | 23,670 → 21,711／12,449 → 14,408 | 2026 年 Q3 10-Q |

其他申報的比較欄與已上線輸出都在精度內相同。
