# SEC 營收組成

這個 repo 提供一套流程：從 SEC 申報與對照資料，產生美股公司每季、每年的 revenue breakdown，每個數字都附 SEC 原文證據。

讀者是接手這個 repo 的 RD 與 PM。第一次接觸的人，先讀第 1、2 章了解為什麼這樣做，再照第 4 章動手。

## 1. 這個 repo 做什麼

**輸入**是 SEC 申報（10-K、10-Q）的 XBRL 標記，以及 Stock Analysis、富途、TradingView 的 by segment 營收（對照資料）。**輸出**是 `data/revenue/` 的正式資料：每個 ticker 的季度與年度營收拆分，連同每個數字的運算式與 SEC 表格證據，全部進 Git，在本機 viewer 檢視。

**上線**指的是 ticker 的輸出寫進 repo、在 `tickers.csv` 標為 `ok`，viewer 看得到，RD/PM 可以 review。上線不代表客戶看得到。對單一期別而言，「已上線」指這一期已寫入正式輸出。

以下不在這個 repo 的範圍內，由 RD/PM 另外決定：

- 要放哪些商品。`tickers.csv` 裡的 ticker 是研究範例，不代表收錄範圍。
- 上線之後怎麼處理資料，包括要不要進 production、怎麼整合。

第一階段只做 by segment。地區拆分先擱置，讓範圍單純。

## 2. 設計理念

之後會不斷加入新的 ticker，而每個 ticker 的營收組成方式千變萬化：有的按產品、有的按業務群，用的 XBRL tag 和成員各不相同。同一家公司也會逐年改變。例如 CAT 把 Energy & Transportation 改名為 Power & Energy，HD 每年依新的部門歸類重列商品類別。

沒有一套共用規則寫得完這些變化，所以設計從這個前提出發：

- **每個 ticker 是獨立單位**：每家公司有自己的 parser，新增或修改一家，不影響其他家。代價是相近的程式碼會重複，換來的是新 ticker 再特殊，也不會動到已經做好的 ticker。
- **每一期照當時的申報**：公司改了分類，不回頭統一歷史。每期的項目與數字都是該期申報當時的樣子；公司事後重編，以差異標記揭露，已上線的數字不改。
- **寧缺毋濫**：不補值、不當作零。找不到數字時該期不寫入，看得出 Q4 算不準時留空，兩者都記錄原因。缺格子是正常結果，不是錯誤。
- **SEC 決定數字，對照資料決定方向**：數字只來自 SEC 申報。對照資料用來選擇拆分方式、初次比對與解釋差異，不當作數字來源。
- **agent 動手，RD 判斷**：每個 ticker 都是一項小研究，要逐家做才維持得住正確率。研究、寫 parser、比對、整理證據交給 agent；選哪些 ticker、採用哪種拆分、能不能上線、已上線的數字要不要覆寫，由 RD 決定。

## 3. 技術設計

### 資料怎麼拼出來

| 資料 | 取自 | 用途 |
|---|---|---|
| Q1–Q3 | 10-Q 的 XBRL fact | 季度序列 |
| FY | 10-K 的 XBRL fact | 年度序列 |
| Q4 | 10-K 年度 − 九個月累計 | 季度序列；年度與前三季的分類不同，或年報重列上一年、看得出口徑改變時留空 |
| 比較欄 | 較晚申報列出的較早期間數字 | 與已上線數字比對，不同時留下差異標記 |
| 表格 HTML 與截圖 | SEC 原文 | 每個數字的證據 |
| 對照資料 | Stock Analysis、富途、TradingView | 選擇觀點（拆分方式）、上線前逐期比對、解釋差異 |

### 兩條硬原則

- **一期一期往下看，不偷看**：處理一份申報，只能用它申報日（含）之前已公開的申報。
- **數字只來自公司 parser 指定的 XBRL fact**：不解析 HTML 或其他文件的文字。

公司 parser 交回的是「每個分類用了哪些 fact、權重多少」，不交數字；數值由框架依 fact 算出，再檢核加總是否等於總營收。規則與檢核見 [Parser 與正式輸出](docs/architecture/parser.md)，完整研究約束見 [`AGENTS.md`](AGENTS.md)。

### 三層分工

| 層 | 負責 | 怎麼改 |
|---|---|---|
| 框架 | 提供資料、檢核、寫入；對申報方式的預設 | 影響所有 ticker，由 RD 決定 |
| utility | 查 fact、判斷期間長度、加總等小工具 | 只增不改 |
| 公司 parser | 這家公司的分類、tag、成員、寫法切換；不符合框架預設時的自訂 | 只影響這家公司 |

新增 ticker 只動公司 parser，需要時新增 utility。公司不符合框架預設、而框架沒有對應的自訂點，或非改框架、既有 utility 不可時，停下來由 RD 決定（見 [parser.md](docs/architecture/parser.md) 的「預設與自訂」）。

### 資料位置

| 路徑 | 內容 |
|---|---|
| `data/universe/tickers.csv` | ticker 清單：CIK、狀態（`wip` 研究中、`ok` 上線、`drop` 放棄）、採用的來源觀點、穩定度評分 |
| `data/universe/references/<首字母>/<TICKER>/` | 對照資料：`reference.json` 與每次擷取的證據 |
| `data/revenue/<首字母>/<TICKER>/` | 正式輸出：`Q/`、`FY/` 每期的 `revenue.json` 與表格證據，以及 `status.json` |
| `data/snapshots/<首字母>/<TICKER>/` | 每份申報的 XBRL fact 快照與申報清單（`manifest.json`），讓沒有 SEC 原文的環境也能驗證正式輸出 |
| `SEC_DATA_DIR` | SEC 原文與下載索引，放在 repo 以外、不進 Git；可依申報清單重新下載 |

ticker 清單與對照資料的格式見 [universe.md](docs/architecture/universe.md)。

### 程式結構

| 路徑 | 內容 |
|---|---|
| `scripts/` | CLI 入口：`sec_pipeline.py`（tickers、download、parse、snapshot、viewer）、`capture_references.py`、`validate_universe.py` |
| `libs/sec_revenue/common/` | 跨子套件共用、不依賴其他子套件的小工具：JSON 讀寫、`.env`、期間範圍 |
| `libs/sec_revenue/download/` | SEC 下載：HTTP、快取、CIK 與申報清單、申報包 |
| `libs/sec_revenue/revenue/` | 框架：讀 inline XBRL、公司 parser 的介面、組數值、檢核、比較欄比對、證據、寫入 |
| `libs/sec_revenue/companies/<首字母>/<ticker>/` | 公司 parser（`parser.py`）與說明（`parser.md`） |
| `libs/sec_revenue/parser_utils/` | 公司 parser 可呼叫的 utility |
| `libs/sec_revenue/capture/` | 對照資料擷取 |
| `libs/sec_revenue/universe/` | `tickers.csv` 與對照資料的格式、讀取與驗證 |
| `libs/sec_revenue/viewer/` | 正式輸出的唯讀 viewer |
| `tests/` | unit test：`tests/sec_revenue/` 對應 `libs/sec_revenue/`，`tests/scripts/` 對應 `scripts/`；以 repo 根目錄為 top-level 執行，測試模組以 `tests.sec_revenue.*` 載入，不會蓋掉 `libs/` 的 `sec_revenue` 套件 |

## 4. 上手

指令都從 repo 根目錄執行。需要 Python 3.11 以上與 Node.js（只用 `npm run` 執行常用指令，沒有 Node 依賴）。

### 4.1 Build

```bash
npm run setup    # 建立 .venv，安裝依賴與擷取、截圖用的 Chromium
npm run check    # unit test、對照資料驗證、快照回歸
```

這一步不需要 SEC 設定。`check` 的快照回歸以 `data/snapshots/` 重算全部公司，與 `data/revenue/` 逐欄比對：正式輸出已經在 Git 裡，不用先產生資料。

### 4.2 用 viewer 看資料

```bash
npm run viewer   # http://127.0.0.1:7290
```

viewer 唯讀，不執行 parser。選一家公司，切換 Q 與 FY，點格子可以看到運算式、用到的申報、檢核結果，以及 SEC 表格截圖。

畫面上的缺格子與提示都有原因：

| 畫面 | 意思 |
|---|---|
| 空格子 | 那一期的申報沒有這個分類 |
| 灰底「留空」 | Q4 不推算；滑鼠停留可以看到原因 |
| 紅底「失敗」 | 這一期沒有通過檢核，沒有寫入；正常情況下上線公司不會有失敗的期別 |
| 橘底加 △ | 差異標記：較晚的申報列出的數字和已上線的值不同，已上線的值不改 |
| 斜體「調節」列 | 調節項，例如公司間抵銷，接在分類之後 |
| 欄名註明「重算不同」 | 重算結果和已上線的值不同，已上線的值保留，等 RD 確認 |

開這幾家走一遍，最容易理解第 2 章的設計：

| 公司與期別 | 看到什麼 | 原因 |
|---|---|---|
| CAT 2025 年 Q4 | 灰底「留空」 | 前三季是 Energy & Transportation，年報改名 Power & Energy，分類不同 |
| UPS 2024 年 Q4 | 灰底「留空」 | 年報重列上一年的數字，看得出口徑改變 |
| KO 2025 年 Q4 | 有數字，帶橘底標記 | 年報看不出口徑變更，照常推算；之後的 10-Q 以新口徑重列 |

狀態與標記的完整說明見[資料使用指南](docs/guides/data-guide.md)的「用 viewer 看資料」。

### 4.3 新增 ticker

新增 ticker 的主要工作交給 agent，RD 負責環境、登入與決定。

先完成一次性的設定：

1. **SEC 身分**：SEC 不需要註冊帳號，只要求自動化請求註明身分。複製 `.env.example` 為 `.env`，填入 `SEC_USER_AGENT`（姓名或組織加上聯絡得到的 email）與 `SEC_DATA_DIR`（SEC 原文的目錄，放在 repo 以外，例如 `~/sec-revenue-data`）。`.env` 不進 Git，主 repo 與每個 worktree 各放一份；每個 worktree 也要各跑一次 `npm run setup`。
2. **對照資料的瀏覽器**：`npm run capture:setup` 開啟擷取用的專用瀏覽器，由 RD 用自己的帳號登入 Stock Analysis、富途、TradingView，三個網站都要登入才看得到完整資料。登入狀態保存在 repo 以外的專用 profile（預設 `~/.sec-revenue-capture/profile/`），程式不經手帳密。

**開始之前，請讀 [開發流程](docs/guides/dev-workflow.md)**：它寫明每一步的指令、agent 回報什麼、在哪裡停下來等 RD 決定，以及上線的條件。agent 寫 parser 時照 [Parser 開發指南](docs/guides/parser-dev-guide.md) 做，RD 不需要記這份文件的細節。

#### 實際操作的順序

以下假設已經決定要試做 `<TICKER1>`、`<TICKER2>`。每個區塊是一次交辦，等 agent 回報、RD 做完決定，再交辦下一段。第 1、2 段接續同一個 agent；第 3、4 段每個 ticker 接續同一個 agent，因為這些結果還沒 commit，只在那個 agent 的工作目錄裡。

**第 1 段：下載資料**

```text
要試做 <TICKER1>、<TICKER2>：照 docs/guides/dev-workflow.md 第 1–3 步，下載 SEC 申報、列入 tickers.csv、擷取對照資料，回報申報期別範圍、有沒有缺漏，以及每個來源擷取到的期別與分類。
```

RD 這時要做：

- agent 回報缺 `SEC_USER_AGENT` 時，設定 `.env` 後請它繼續。agent 不自己填這項設定。
- agent 回報有網站未登入時，RD 在自己的終端機執行 `npm run capture:setup` 登入，再請它重跑擷取。
- agent 回報有前身或繼受實體時，RD 決定要不要列多個 CIK。

**第 2 段：評估**

```text
照 docs/guides/dev-workflow.md 第 4–5 步，評估 <TICKER1>、<TICKER2> 做不做得出來，回報各來源的分類、建議的觀點、看到的問題與需要我決定的事項，回報後停下來。
```

RD 這時要做：回答 agent 的問題，決定每個 ticker 採用的觀點與分類，或決定放棄。

**第 3 段：寫 parser**

一個 ticker 一個 agent、一個 issue、一個分支。第 1、2 段的 `wip` 列與對照資料還沒 commit，要帶到這個 ticker 的分支。issue 由 agent 開，獨立 review 的流程寫在開發流程裡，都不用在交辦時說明。

```text
<TICKER1> 用 Stock Analysis 的觀點，照 docs/guides/dev-workflow.md 第 7–9 步寫 parser、做獨立 review、修完問題，再整理上線條件，停在 commit 之前回報，並附上與對照來源的逐期比對。
```

RD 這時要做：agent 遇到需要人決定的事項會停下來回報，RD 回答後請它繼續。

**第 4 段：判斷上線**

這時 parser 與輸出都還沒 commit，只有 agent 的工作目錄裡看得到，所以請 agent 開 viewer：

```text
在你的工作目錄開 viewer，給我 <TICKER1> 的網址。
```

RD 這時要做：對照 agent 的回報和 viewer 的內容，看數字、缺格子、標記與 SEC 證據是否和回報一致。要看對照來源時，到該網站查看，擷取時的網址記在 `data/universe/references/` 的 `reference.json`。

判斷之後，選一種交辦：

```text
<TICKER1> 核准上線，採用來源 stockanalysis，穩定度評分 4，理由是……。照 docs/guides/dev-workflow.md 第 9 步寫入 tickers.csv，commit、開 PR、合併。
```

```text
<TICKER1> 先不上線，以下地方要修改：……
```

合併後，這個 ticker 就出現在 viewer 的搜尋清單。

做不出來的 ticker（框架不支援、只能違反硬原則）不繞過，由 RD 決定標 `drop` 或維持 `wip`。

### 4.4 指令總表

指令定義在 `package.json`，額外參數接在 `--` 之後。

| 指令 | 用途 |
|---|---|
| `npm run setup` | 建立 `.venv`，安裝 `requirements.txt` 與 Chromium |
| `npm run test` | unit test（`unittest discover -s tests -t .`） |
| `npm run validate` | 驗證 `tickers.csv` 與對照資料 |
| `npm run regression` | 以快照重算全部公司 parser，與正式輸出比對，不需要 SEC 原文 |
| `npm run check` | 依序執行以上三項 |
| `npm run tickers` | 列出有公司 parser 的 ticker |
| `npm run download -- ...` | 下載 SEC 申報包；`--dry-run` 只列出還沒下載的申報；`--from-manifest` 依申報清單重新下載並逐檔核對 |
| `npm run parse -- ...` | 依公司 parser 產生正式輸出與證據，不連網；不指定 `--start` 時從預設起始日（2024-01-01）起；`--check` 與已提交的輸出比對，加 `--snapshots` 時不讀原文 |
| `npm run snapshot -- ...` | 由 SEC 原文產生快照與申報清單；`--check` 核對已提交的快照與原文一致 |
| `npm run capture:setup` | 開啟擷取用的專用瀏覽器，檢查並等待登入 |
| `npm run capture -- ...` | 擷取對照資料 |
| `npm run viewer` | 本機唯讀 viewer，<http://127.0.0.1:7290> |

範例：

```bash
# 下載任何 ticker 自 2025 年起的申報包，並刷新到最新一期
npm run download -- --tickers AAPL PGR --start 2025-01-01 --latest

# 列出 tickers.csv 全部公司在範圍內還沒下載的申報，不連網
npm run download -- --all --start 2024-01-01 --dry-run

# 擷取對照資料
npm run capture -- --source stockanalysis --tickers AAPL,MSFT

# 產生正式輸出，或與已提交的輸出比對
npm run parse -- --tickers AAPL
npm run parse -- --tickers AAPL --check

# 依申報清單下載原文，再以原文核對全部輸出（連表格 HTML 一起驗證）
npm run download -- --all --from-manifest
npm run parse -- --all --check
```

`ALL` 是 Allstate 的 ticker；全部公司用 `--all`。更多選項見[本機操作](docs/guides/local-workflow.md)、[SEC 下載](docs/architecture/download.md)與[對照資料擷取工具](docs/architecture/capture.md)。

### 4.5 CI

CI 定義在 `.github/workflows/tests.yml`，在每個 PR 與 push 到 main 時，以 Python 3.12 執行與 `npm run check` 相同的三項：

1. unit test。
2. 驗證 `tickers.csv` 與對照資料。
3. 快照回歸：以 `data/snapshots/` 重跑全部公司 parser，與 `data/revenue/` 逐欄比對。

CI 不做這些事：

- 不連 SEC，不下載申報，也不產生或更新資料。
- 不核對表格 HTML 的內容；這要在本機以原文跑 `parse --check`。
- 不比對對照資料；這是上線前的工作，記在各公司的 `parser.md`。
- 沒有排程，也不部署。

ticker 數增加後快照進 Git 的取捨，見 [parser.md](docs/architecture/parser.md) 的「兩種 CI 環境」。

## 5. 未來維運

目前沒有專門處理新財報的增量流程：沒有排程，不會自動偵測新申報，也沒有 review 新一期結果的工具。新一期財報要由 RD 交辦 agent，對上線的 ticker 下載、產生快照、parse，步驟見[開發流程](docs/guides/dev-workflow.md)第 10 步。

parse 對新一期的處理方式是：

- 結構檢核通過就寫入。新的期別不比對對照資料。
- 找不到需要的 fact 時，該期失敗並記錄原因，不猜、不補。
- 一般 parse 不覆寫已上線的數字。

所以新一期的數字仍然需要 RD/PM 判斷。新數字也可能讓人發現之前的拆分需要調整，這時由 RD/PM 決定怎麼處理：

| 情境 | 系統的行為 | RD/PM 要決定什麼 |
|---|---|---|
| 公司改了 tag 或分類，新一期失敗 | 該期不寫入，記錄原因；年報失敗時，Q4 也失敗 | 交辦 agent 修改那個 ticker 的 parser |
| 年報改了分類項目 | parser 更新後 FY 寫入，Q4 留空 | 確認新分類的對應；Q4 留空，不另做補救 |
| 年報重列上一年，看得出口徑改變 | FY 寫入，Q4 留空 | 確認留空的原因 |
| 公司改了口徑，年報看不出來 | Q4 照常推算並寫入，之後的申報重列時留下差異標記 | 數字一開始看起來正常，看到標記時判斷這段期間的數字怎麼解讀 |
| 新申報重編了舊期別 | 舊期別留下差異標記，數字不改 | 請 agent 查明原因；要採用重編後的數字時，見下方說明 |
| 公司重組，原本的觀點不再適用 | 系統不會判斷，繼續照 parser 處理；新一期可能失敗 | 要不要換觀點，舊期別怎麼處理 |

parser 或框架規則修正後，重算結果可能和已上線的值不同。一般 parse 不寫入，只在 `status.json` 記錄 `differs_from_published`，viewer 的欄名會註明「重算不同」。RD 確認後以 `parse --tickers TICKER --republish TICKER SERIES PERIOD` 覆寫，`revenue.json` 會記錄原值與原因。

覆寫不能用來採用重編後的數字：每一期的主申報固定是該期最早的原申報，重算的數字仍取自那份申報。要採用重編後的數字，得改變框架規則，由 RD 決定。

差異標記怎麼看、怎麼請 agent 調查，見[資料使用指南](docs/guides/data-guide.md)的「遇到標記或客戶問題時」。

## 6. 文件地圖

| 想知道 | 看哪裡 |
|---|---|
| 資料怎麼讀、狀態與標記的意思、輸出格式 | [資料使用指南](docs/guides/data-guide.md) |
| 新增 ticker 到上線的每一步 | [開發流程](docs/guides/dev-workflow.md) |
| 寫 parser 的做法 | [Parser 開發指南](docs/guides/parser-dev-guide.md) |
| 指令的完整選項 | [本機操作](docs/guides/local-workflow.md) |
| parser 規則、檢核與輸出格式 | [Parser 與正式輸出](docs/architecture/parser.md) |
| SEC 下載規則 | [SEC 下載](docs/architecture/download.md) |
| 對照資料的擷取 | [對照資料擷取工具](docs/architecture/capture.md) |
| ticker 清單與對照資料的格式 | [universe.md](docs/architecture/universe.md) |
| viewer 的頁面與 API | [Viewer](docs/architecture/viewer.md) |
| 研究約束 | [`AGENTS.md`](AGENTS.md) |
| 整體計畫與進度 | [#36](https://github.com/derektu/sec-revenue-breakdown/issues/36) |
