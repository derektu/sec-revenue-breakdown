# 開發流程

這份文件說明新增一個 ticker、讓它上線的完整流程，寫給兩種讀者：負責擴充 ticker 的 RD，以及 RD 交辦工作的 agent。每一步都寫明 agent 可以做什麼、哪些事一定要人做、用哪些指令、做完要回報什麼。RD 可以把任何一步（或連續幾步）交辦給 agent；agent 收到交辦時，照對應步驟做，做到「要人做」的地方停下來回報。

寫 parser 的細節見 [Parser 開發指南](parser-dev-guide.md)；規則與輸出格式見 [Parser 與正式輸出](../architecture/parser.md)；研究約束見 [`AGENTS.md`](../../AGENTS.md)。

指令都從 repo 根目錄執行。環境設定（`.venv`、`.env` 的 `SEC_USER_AGENT` 與 `SEC_DATA_DIR`）見 [README](../../README.md) 的 Setup。

## 流程總覽

```
1 選 ticker ─→ 2 tickers.csv ─→ 3 下載 SEC 申報 ─→ 4 擷取對照資料 ─→ 5 觀點建議 ─→ 6 決定觀點
   ─→ 7 寫 parser ─→ 8 獨立 review ─→ 9 判斷上線 ─→ 10 上線之後
```

| 步驟 | agent 做 | 人做 |
|---|---|---|
| 1. 選 ticker | 評估候選 ticker 做不做得出來 | 決定要做哪些 ticker |
| 2. `tickers.csv` | 查 CIK 與正式名稱，新增 `wip` 列並驗證 | 核准列入；`ok`、`drop` 由人決定 |
| 3. 下載 SEC 申報 | 下載、檢查缺漏 | 設定 `.env`（`SEC_USER_AGENT` 是人的聯絡資訊） |
| 4. 擷取對照資料 | 執行擷取、驗證、回報結果 | 在專用瀏覽器登入三個網站 |
| 5. 觀點建議 | 比較各來源、對照 SEC 申報，提出建議 | |
| 6. 決定觀點 | | 決定觀點與分類 |
| 7. 寫 parser | 寫 `parser.py`、`parser.md`，驗證、比對 | 決定 agent 回報的待決事項 |
| 8. 獨立 review | 另一個 agent review 還沒 commit 的改動；修完 review 的問題 | 在第 9 步一併決定需要人判斷的 review 問題 |
| 9. 判斷上線 | 整理上線條件的證據、重跑檢查，請人核准；核准後寫入 `tickers.csv`，commit、開 PR、等 CI、合併 | 判斷能不能上線、核准 |
| 10. 上線之後 | 下載新申報、產生快照、parse、回報結果 | 處理失敗與標記的後續決定 |

交辦的例子：

```text
幫我新增 MSFT、ORCL：照 docs/guides/dev-workflow.md 做第 1–5 步，每個 ticker 回報觀點建議後停下來。
MSFT 用 Stock Analysis 的觀點，照 docs/guides/dev-workflow.md 第 7 步寫 parser。
幫 MSFT 整理第 9 步的上線條件，告訴我能不能上線。
新一期財報出來了，照 docs/guides/dev-workflow.md 第 10 步更新全部上線的 ticker。
```

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

## 1. 選 ticker

適合的 ticker：營收以產品或業務別組成，申報有對應的 XBRL 標記。營收只以地區揭露的 ticker 做不出來（觀點不收地區拆分）。

**agent**：對每個候選 ticker，先下載申報（第 3 步），用 [開發指南](parser-dev-guide.md) 第 2 步的程式看最新 10-K 與 10-Q 的營收 fact，回報：

- 申報中有哪些產品別或業務別的營收 fact，是不是地區。
- 有沒有框架不支援的情形：非 13 週的季度、財報在附件、需要的數字沒有 XBRL 標記、申報宣告的財年錯誤。已知的例子見 [資料使用指南](data-guide.md) 的「目前狀態」。
- 建議做或不做，與理由。

**人**：決定要做哪些 ticker。

## 2. `tickers.csv`

`data/universe/tickers.csv` 的格式與驗證規則見 [ticker 清單與對照資料格式](../architecture/universe.md)。

| 欄位 | 何時填 |
|---|---|
| `ticker`、`cik`、`name` | 列入時。有前身與繼受實體時 `cik` 列多個，以 `;` 分隔（例如 XOM 的 `2115436;34088`），下載會合併它們的申報 |
| `status` | 列入時為 `wip`；判斷能上線時改為 `ok`；放棄時改為 `drop` |
| `adopted_source`、`stability_score`、`stability_note` | 改為 `ok` 時必填：採用的對照來源與 1–5 的穩定度評分（5 最穩定） |

下載、擷取、parse 都不需要 ticker 先列入 `tickers.csv`：`download --tickers` 接受任何 ticker（沒列入時由 SEC 的 ticker 對照表查 CIK），`capture` 不讀 `tickers.csv`，`parse` 只看這個 ticker 有沒有 parser。用到 `tickers.csv` 的是 `download --all`（下載清單中的全部 ticker）與 viewer（以 `status` 標示 ticker 是否上線）。

**agent**：人核准列入後，新增 `wip` 列。CIK 取自下載結果的 `cik`（`source` 為 `sec_company_tickers` 時是由 SEC 對照表查到的），`name` 用申報封面的正式名稱。有前身或繼受實體時回報，由人決定是否列多個 CIK。改完執行驗證：

```bash
.venv/bin/python scripts/validate_universe.py
```

**人**：核准列入；`ok` 與 `drop` 由人決定（第 9 步）。

## 3. 下載 SEC 申報

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

## 4. 擷取對照資料

對照資料（Stock Analysis、富途、TradingView）只用來選觀點、首次比對與解釋差異，不當作數字來源。

**agent**：

```bash
.venv/bin/python scripts/capture_references.py setup                                   # 開專用瀏覽器，逐站檢查登入
.venv/bin/python scripts/capture_references.py capture --source stockanalysis --tickers MSFT
.venv/bin/python scripts/capture_references.py capture --source futu --tickers MSFT
.venv/bin/python scripts/capture_references.py capture --source tradingview --tickers MSFT
```

- 先跑 `setup`；有網站未登入時，停下來請人在開啟的視窗中登入。
- 三個來源依序擷取，不平行；多個 ticker 用 `--tickers MSFT,ORCL`，工具一次處理一個 ticker、兩檔之間預設間隔 10 秒。
- 結果累積寫進 `data/universe/references/<首字母>/<TICKER>/`，結束時自動執行對照資料驗證。
- 回報：每個 ticker 每個來源擷取到的期別與分類、失敗的來源與原因（例如頁面不存在、找不到表格）。

**人**：在專用瀏覽器中登入三個網站。

登入判斷、證據與合併規則見 [對照資料擷取工具](../architecture/capture.md)。

## 5. 觀點建議

**agent**：照 [開發指南](parser-dev-guide.md) 第 1 步，比較各對照來源的分類，對照 SEC 申報的 XBRL fact，回報後停下來：

- 各來源的分類是什麼，哪些能從申報重現、哪些不能、為什麼。
- 建議的觀點與分類清單。各來源一致時通常直接採用；不一致（面向、層級、名稱或範圍不同）時，說明為什麼選這一個。
- Other、Corporate、Eliminations 這類差額項目：多數來源列出的列成分類，多數沒列的列成調節項。
- 有沒有要改框架、或要違反原則才做得出來的地方。

## 6. 決定觀點

**人**：決定採用的觀點與分類，告訴 agent。記下採用的來源，上線時填 `adopted_source`。

## 7. 寫 parser

**agent**：照 [開發指南](parser-dev-guide.md) 的第 2–9 步寫 `parser.py` 與 `parser.md`、跑 parse、與對照資料逐期比對、產生快照、自我驗收。一個 ticker 一個 issue、一個分支。只改這個 ticker 的目錄；需要的 utility 可以新增，既有 utility 與框架不改。遇到開發指南「停下來交給人」的情況，停下來回報。

做完停在 commit 之前，回報：各期結果（`published`、`not_derived`、`failed` 的期別與原因）、與對照來源的比對與差異、差異標記、需要人決定的事項。

**人**：決定回報中的待決事項。

## 8. 獨立 review

**agent**（沒參與開發的另一個 agent）：review 還沒 commit 的改動，必看項目：

- `parser.md` 與程式一致；每個依日期的切換都能在那份申報裡看到。
- 「時點與寫 parser 的人的知識」的三條規則（見 [parser.md](../architecture/parser.md)）。
- 只改了這個 ticker 的目錄；新增的 utility 不含任何 ticker 的知識，既有 utility 沒有改。
- 開發指南的驗收清單。

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

整理完停下來請人核准，附上改動摘要、review 結果、驗證結果與上表每一條的證據。人核准上線時，在 `tickers.csv` 把 `status` 改為 `ok`，填人決定的 `adopted_source`、`stability_score` 與 `stability_note`，執行 `validate_universe.py`；人決定先不上線時維持 `wip`。接著照[從寫完到合併](#從寫完到合併)的第 5 步完成：一個 ticker 一個 PR，parser 與 `tickers.csv` 在同一個 commit。寫入 `tickers.csv` 的是人決定的值，由 `validate_universe.py` 檢查，不另外 review。

**人**：判斷能不能上線、核准。數字與證據可以在 viewer 檢視：

```bash
.venv/bin/python scripts/sec_pipeline.py viewer --host 127.0.0.1 --port 7290
```

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
