# 開發流程

這份文件說明新增一個 ticker、讓它上線的完整流程，寫給兩種讀者：負責擴充 ticker 的 RD，以及 RD 交辦工作的 agent。每一步都寫明 agent 可以做什麼、哪些事一定要人做、用哪些指令、做完要回報什麼。RD 可以把任何一步（或連續幾步）交辦給 agent；agent 收到交辦時，照對應步驟做，做到「要人做」的地方停下來回報。

寫 parser 的細節見 [Parser 開發指南](parser-dev-guide.md)；規則與輸出格式見 [Parser 與正式輸出](../architecture/parser.md)；研究約束見 [`AGENTS.md`](../../AGENTS.md)。

指令都從 repo 根目錄執行。環境設定（`.venv`、`.env` 的 `SEC_USER_AGENT` 與 `SEC_DATA_DIR`）見 [README](../../README.md) 的「上手」。

## 流程總覽

流程從人決定要試做哪些 ticker 開始。評估要看申報的 fact，觀點建議要看對照資料，所以先下載，再評估。

```
1 下載 SEC 申報 ─→ 2 tickers.csv ─→ 3 擷取對照資料 ─→ 4 評估 ticker ─→ 5 觀點建議 ─→ 6 決定觀點
   ─→ 7 寫 parser ─→ 8 獨立 review ─→ 9 判斷上線 ─→ 10 上線之後
```

| 步驟 | agent 做 | 人做 |
|---|---|---|
| 1. 下載 SEC 申報 | 下載、檢查缺漏 | 決定要試做的 ticker；設定 `.env`（`SEC_USER_AGENT` 是人的聯絡資訊） |
| 2. `tickers.csv` | 查 CIK 與正式名稱，新增 `wip` 列並驗證 | `ok`、`drop` 由人決定 |
| 3. 擷取對照資料 | 執行擷取、驗證、回報結果 | 在專用瀏覽器登入三個網站 |
| 4. 評估 ticker | 看申報的營收 fact，評估做不做得出來 | 決定繼續或放棄 |
| 5. 觀點建議 | 比較各來源、對照 SEC 申報，提出建議 | |
| 6. 決定觀點 | | 決定觀點與分類 |
| 7. 寫 parser | 寫 `parser.py`、`parser.md`，驗證、比對 | 決定 agent 回報的待決事項 |
| 8. 獨立 review | 另一個 agent review 還沒 commit 的改動；修完 review 的問題 | 在第 9 步一併決定需要人判斷的 review 問題 |
| 9. 判斷上線 | 整理上線條件的證據、重跑檢查，在工作目錄開 viewer，請人核准；核准後寫入 `tickers.csv`，commit、開 PR、等 CI、合併 | 判斷能不能上線、核准 |
| 10. 上線之後 | 下載新申報、產生快照、parse、回報結果 | 處理失敗與標記的後續決定 |

交辦的順序與範例見 [README](../../README.md) 的「新增 ticker」。新一期財報交辦第 10 步，指定要更新的 ticker。

## 從寫完到合併

所有改動（parser、utility、框架、文件）都照這個順序：

1. 寫完，停在 commit 之前。
2. 沒參與開發的 agent 對還沒 commit 的 diff 做獨立 review。
3. 修完 review 的問題，必要時再 review。
4. orchestrator（負責交辦與整合的 agent）判斷可以合併時，停下來請人核准。
5. 人核准後：commit 一次、push、開 PR（附 review 摘要）、等 CI 通過、squash 合併，回到 main。

開發者自己就是合併的人，所以 review 放在 commit 之前，問題在 commit 前就修完：每個 PR 只有一個 commit，CI 只跑一次。CI 沒通過不合併。

## agent 的共通規則

- 遵守 [`AGENTS.md`](../../AGENTS.md)：數字只來自 SEC 申報；空值不當作零；不讀、不印 `.env` 的內容。
- 一次只跑一個下載或擷取，不平行執行。
- 不經手任何網站的帳密、cookie 或 token；網站需要登入時，請人在專用瀏覽器中登入。
- 不改框架（`libs/sec_revenue/revenue/`）與既有 utility，非改不可時停下來回報。
- 沒有人核准時不 commit、不 push、不合併；做完停下來回報。
- 任何改動從寫完到合併都照這個順序（[從寫完到合併](#從寫完到合併)）：寫完 → 獨立 review → 修完 → 人核准 → commit、開 PR、CI 通過、合併。
- 每一步做完回報：做了什麼、結果、遇到的問題、需要人決定的事項（附選項與建議）。

## 1. 下載 SEC 申報

**agent**：

```bash
.venv/bin/python scripts/sec_pipeline.py download --tickers MSFT --start 2024-01-01 --latest
.venv/bin/python scripts/sec_pipeline.py download --tickers MSFT --start 2024-01-01 --dry-run   # 不連網，列出還沒下載完整的申報
```

- `--start` 用預設起始日（2024-01-01）；推算 Q4 需要的較早申報（同財年的 10-Q、上一份 10-K）會一併下載。
- 多個 ticker 依序下載，或一次以 `--tickers` 列出；不要同時跑多個下載。
- 原文存在 `SEC_DATA_DIR`，不進 Git。
- 回報：每個 ticker 的申報期別範圍、`--dry-run` 有沒有缺漏、失敗的 ticker 與原因。

**人**：設定 `.env`。下載失敗並提示缺 `SEC_USER_AGENT` 時，agent 停下來請人設定，不自己填。

下載規則與回傳碼見 [SEC 下載](../architecture/download.md)，其他參數見 [本機操作](local-workflow.md)。

## 2. `tickers.csv`

`data/universe/tickers.csv` 的格式與驗證規則見 [ticker 清單與對照資料格式](../architecture/universe.md)。

| 欄位 | 何時填 |
|---|---|
| `ticker`、`cik`、`name` | 列入時。有前身與繼受實體時 `cik` 列多個，以 `;` 分隔（例如 XOM 的 `2115436;34088`），下載會合併它們的申報 |
| `status` | 列入時為 `wip`；判斷能上線時改為 `ok`；放棄時改為 `drop` |
| `adopted_source`、`stability_score`、`stability_note` | 改為 `ok` 時必填：採用的對照來源與 1–5 的穩定度評分（5 最穩定） |

下載、擷取、parse 都不需要 ticker 先列入 `tickers.csv`：`download --tickers` 接受任何 ticker（沒列入時由 SEC 的 ticker 對照表查 CIK），`capture` 不讀 `tickers.csv`，`parse` 只看這個 ticker 有沒有 parser。用到 `tickers.csv` 的是 `download --all`（下載清單中的全部 ticker）與 viewer（以 `status` 標示 ticker 是否上線）。

**agent**：下載完成後，新增 `wip` 列。CIK 取自下載結果的 `cik`（`source` 為 `sec_company_tickers` 時是由 SEC 對照表查到的），`name` 用申報封面的正式名稱。有前身或繼受實體時回報，由人決定是否列多個 CIK。改完執行驗證：

```bash
.venv/bin/python scripts/validate_universe.py
```

第 1 步還沒有 `tickers.csv` 的列時，下載只用 SEC 對照表查到的單一 CIK。人決定列多個 CIK 時，改完後重跑第 1 步的兩個指令，補齊前身或繼受實體的申報。

**人**：`ok` 與 `drop` 由人決定（第 9 步）。

## 3. 擷取對照資料

對照資料（Stock Analysis、富途、TradingView）只用來選觀點、首次比對與解釋差異，不當作數字來源。

**agent**：

```bash
.venv/bin/python scripts/capture_references.py capture --source stockanalysis --tickers MSFT
.venv/bin/python scripts/capture_references.py capture --source futu --tickers MSFT
.venv/bin/python scripts/capture_references.py capture --source tradingview --tickers MSFT
```

- 有網站未登入時，停下來請人在自己的終端機執行 `npm run capture:setup` 並登入，完成後重跑擷取。`setup` 與未登入時的 `capture` 都會等人按 Enter，agent 的 shell 無法代替：看到「未登入，開啟瀏覽器視窗登入」時，先結束這個行程，專用 profile 才開得起來。
- 三個來源依序擷取，不平行；多個 ticker 用 `--tickers MSFT,ORCL`，工具一次處理一個 ticker、兩檔之間預設間隔 10 秒。
- 結果累積寫進 `data/universe/references/<首字母>/<TICKER>/`，結束時自動執行對照資料驗證。
- 回報：每個 ticker 每個來源擷取到的期別與分類、失敗的來源與原因（例如頁面不存在、找不到表格）。來源本身沒有這家公司的資料（不是未登入或擷取失敗）時，第 5 步用現有的來源繼續，例如 XOM、CVX、NEE 沒有 Stock Analysis。

**人**：執行 `npm run capture:setup`，在專用瀏覽器中登入三個網站。

登入判斷、證據與合併規則見 [對照資料擷取工具](../architecture/capture.md)。

## 4. 評估 ticker

適合的 ticker：營收以產品或業務別組成，申報有對應的 XBRL 標記。營收只以地區揭露的 ticker 做不出來（觀點不收地區拆分）。

**agent**：對每個 ticker，用 [開發指南](parser-dev-guide.md) 第 2 步的程式看最新 10-K 與 10-Q 的營收 fact，回報：

- 申報中有哪些產品別或業務別的營收 fact，是不是地區。
- 有沒有不符合框架預設的地方（見 [parser.md](../architecture/parser.md) 的「預設與自訂」）：期間長度不在預設範圍（單季 12–14 週、六個月 25–27 週、九個月 38–40 週、年度 51–54 週），例如 COST 的 12／12／12／16 週季度；10-Q 宣告的財年與「前一份 10-K 宣告的財年 ＋ 1」不同，例如 ORCL 2026-08-31 的 10-Q；財報在附件，例如 PGR。框架有自訂點的（期間長度、財年）由公司 parser 自訂，回報要自訂什麼（期間長度要寫出各範圍與理由，範圍多寬由公司 parser 決定）；還沒有自訂點的（附件）回報，由人決定。
- 有沒有只能違反硬原則才做得出來的地方：需要的數字沒有 XBRL 標記，例如 GOOGL 的避險損益列。
- 已知的例子見 [資料使用指南](data-guide.md) 的「目前狀態」。
- 建議做或不做，與理由。與第 5 步一併交辦時，合併回報。

**人**：看評估結果，決定繼續或放棄。放棄的 ticker 由人決定改為 `drop` 或維持 `wip`（第 9 步）。

## 5. 觀點建議

**agent**：照 [開發指南](parser-dev-guide.md) 第 1 步，比較各對照來源的分類，對照 SEC 申報的 XBRL fact，回報後停下來：

- 各來源的分類是什麼，哪些能從申報重現、哪些不能、為什麼。
- 建議的觀點與分類清單。各來源一致時通常直接採用；不一致（面向、層級、名稱或範圍不同）時，說明為什麼選這一個。
- Other、Corporate、Eliminations 這類差額項目：多數來源列出的列成分類，多數沒列的列成調節項；只計算拆分到建議觀點的來源、只看期末日在起始日以後的期別，無法判定時列為待決事項。抵銷前後的口徑差異先當觀點決定，見開發指南第 1 步。來源只有欄名、每期都沒有值（`-`）的不算列出。
- 有沒有要改框架、或要違反原則才做得出來的地方。

## 6. 決定觀點

**人**：決定採用的觀點與分類，告訴 agent。記下採用的來源，上線時填 `adopted_source`。

## 7. 寫 parser

**agent**：照 [開發指南](parser-dev-guide.md) 的第 2–9 步寫 `parser.py` 與 `parser.md`、跑 parse、與對照資料逐期比對、產生快照、自我驗收。一個 ticker 一個 issue（由 agent 開）、一個分支；第 2、3 步還沒 commit 的 `wip` 列與對照資料，帶到這個 ticker 的分支。只改這個 ticker 的目錄；需要的 utility 可以新增，既有 utility 與框架不改。遇到開發指南「停下來交給人」的情況，停下來回報。

做完停在 commit 之前，回報：各期結果（`published`、`not_derived`、`failed` 的期別與原因）、與對照來源的比對與差異、差異標記、需要人決定的事項。

**人**：決定回報中的待決事項。

## 8. 獨立 review

**agent**（沒參與開發的另一個 agent）：review 還沒 commit 的改動，必看項目：

- `parser.md` 與程式一致；每個依日期的切換都能在那份申報裡看到。
- 「時點與寫 parser 的人的知識」的三條規則（見 [parser.md](../architecture/parser.md)）。
- 只改了這個 ticker 的目錄，以及第 2、3 步留下的這個 ticker 的 `wip` 列與對照資料；新增的 utility 不含任何 ticker 的知識，既有 utility 沒有改。
- 開發指南的驗收清單。

範圍外的較早期別可以用 `parse --tickers <TICKER> --check --start <較早日期>` 試跑，從輸出的 JSON 看各期的狀態，驗證切換日與 `not_derived`。較早期別沒有已提交的輸出，回報為差異是預期的；現行分類結構開始以前的期別失敗（例如找不到現行成員）也是預期的，結果不代表那些期別的正確組法。要看的是範圍內已提交的期別：它們出現差異時（例如第一個 Q4 的口徑依據改由較早的已上線 FY 提供），逐筆看原因。`--check` 不寫入輸出。

回報發現的問題，依嚴重程度排列。

**agent**（orchestrator）：修完 review 的問題，必要時再 review，接著做第 9 步。需要人決定的 review 問題，放進第 9 步請人核准時的回報。

**人**：決定 review 問題怎麼處理。

## 9. 判斷上線

`ok` 代表這個 ticker 進入 viewer，作為 PM 檢視的候選，不代表對外發布。以下都成立才標 `ok`：

| 條件 | 看哪裡 |
|---|---|
| 範圍內每一期都是 `published`，或 `not_derived` 而原因已寫明 | `data/revenue/<首字母>/<TICKER>/status.json`；開發指南第 5 步的摘要指令 |
| 沒有 `failed` 的期別 | 同上 |
| 與採用的對照來源逐期比對，每一筆差異都有原因與證據；沒有「原因未確認」卻當作一致的 | `parser.md` 的「驗證」 |
| 差異標記都有說明 | `parser.md` 的「比較欄」 |
| 兩種 `--check` 與 `npm run check` 都通過 | 下面的指令 |
| 獨立 review 通過，需要人決定的事項都已決定 | 第 8 步的 review 結果 |

**agent**：逐條整理上表的證據並重跑檢查，回報每一條是否成立，並建議穩定度評分與理由：

```bash
.venv/bin/python scripts/sec_pipeline.py parse --tickers MSFT --check
.venv/bin/python scripts/sec_pipeline.py parse --tickers MSFT --check --snapshots
npm run check
```

這時 parser 與輸出都還沒 commit，只有 agent 的工作目錄裡看得到，所以由 agent 在工作目錄開 viewer，把這個 ticker 的網址給人（`wip` 不在搜尋清單上，網址加 `#ticker=MSFT&series=Q`）。7290 已被占用時用 `--port` 指定其他 port：

```bash
.venv/bin/python scripts/sec_pipeline.py viewer --host 127.0.0.1 --port 7290
```

整理完停下來請人核准，附上改動摘要、review 結果、驗證結果與上表每一條的證據。人核准上線時，在 `tickers.csv` 把 `status` 改為 `ok`，填人決定的 `adopted_source`、`stability_score` 與 `stability_note`，執行 `validate_universe.py`；人決定先不上線時維持 `wip`。接著照[從寫完到合併](#從寫完到合併)的第 5 步完成：一個 ticker 一個 PR，parser、`tickers.csv` 與這個 ticker 的對照資料在同一個 commit；`ok` 的 `adopted_source` 必須存在於對照資料，少了對照資料 CI 不會通過。寫入 `tickers.csv` 的是人決定的值，由 `validate_universe.py` 檢查，不另外 review。

**人**：判斷能不能上線、核准。對照 agent 的回報和 viewer 的內容，看數字、缺格子、標記與 SEC 證據是否和回報一致。

做不出來的 ticker（框架不支援、只能違反原則）由人決定改為 `drop` 或維持 `wip`，原因寫在 `notes` 或對應的 issue。

## 10. 上線之後

上線後的新期別不比對對照資料：結構檢核通過就寫入。

**agent**：新一期財報出來時，對上線的 ticker 依序執行：

```bash
.venv/bin/python scripts/sec_pipeline.py download --tickers MSFT --latest
.venv/bin/python scripts/sec_pipeline.py snapshot --tickers MSFT
.venv/bin/python scripts/sec_pipeline.py parse --tickers MSFT
```

回報：新寫入的期別、失敗與 Q4 不推算的期別與原因、新的差異標記。失敗、Q4 不推算與差異標記的意義見 [資料使用指南](data-guide.md)。

**人**：新申報改了 tag 或分類而失敗時，交辦第 7 步修改那個 ticker 的 parser；已上線的期別要覆寫（`--republish`）時由人決定。
