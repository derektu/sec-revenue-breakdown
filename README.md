# SEC 營收組成

從 SEC 申報文件擷取美股公司每季的 by segment 營收拆分，範圍逐步擴大到 S&P 1500。以正確率優先，寧缺毋濫：每家公司有自己的 parser，每個數字都附 SEC 原文證據，通過對照資料驗證、格式穩定的公司才上線。

整體計畫與進度見 [#36](https://github.com/derektu/sec-revenue-breakdown/issues/36)。

## 原則

完整約束見 [`AGENTS.md`](AGENTS.md)，重點如下：

- **數字只來自 SEC**：營收的擷取與計算只用 SEC 申報（10-K、10-Q、8-K 附件）。Stock Analysis、富途、TradingView 等對照資料只用於比對與選擇分類觀點。
- **只做 by segment**，不做地區拆分。
- **每個數字有證據**：正式輸出的每個數字連到 SEC 原文表格（HTML 與截圖）；推算的欄位附每個運算元的證據與運算式。
- **不補值**：缺值、歧義或驗證不過時輸出 null 與原因，不當作零，也不拿對照資料補。
- **公司互相隔離**：每家公司的 parser 在自己的資料夾，新增或修改一家不影響其他公司；測試範圍由改動推得。

## 流程

```
擷取對照資料（瀏覽器）──┐
                         ├─→ 開發 parser ─→ 驗證關卡 ─→ 上線
下載 SEC 財報 ───────────┘                       │
                    新一期財報 ─→ parse ─→ 跨期比對 ─→ 標註
```

1. **擷取對照資料**：專用瀏覽器確認 Stock Analysis、富途、TradingView 都已登入後，擷取指定股票的 by segment 營收，並保存表格截圖、HTML 片段與文字作為證據。擷取不依賴 parser，可以先大量進行；多次擷取累積保存，逐步拉長期間。
2. **下載 SEC 財報**：任何 ticker 都能下載完整申報包，並保存每份文件的 SEC URL，必要時開啟原文或 SEC 的 XBRL viewer 比對。
3. **開發 parser**：parser 從 XBRL 找出與對照資料一致的數據，並由 fact 找到所在的 SEC 表格作為證據。每家 parser 附 `parser.md` 說明分類對應、tag 變動與推算邏輯。
4. **驗證關卡**：各分類與採用的來源觀點相符、加總等於總營收、每個數字都有證據，三者都通過才輸出。比對結果附穩定度評分（1–5），由使用者決定採用的觀點。
5. **上線**：使用者在 `tickers.csv` 將該公司標為 `ok`。
6. **新一期財報**：與先前各期比對，分類變動、占比或成長率異常時寫成標註，照常上線；PM 看新財報時一併看到標註。

## 資料

| 路徑 | 內容 |
|---|---|
| `data/universe/tickers.csv` | 使用者維護的 ticker 清單：CIK、狀態（`wip` 研究中、`ok` 上線、`drop` 放棄）、採用的來源觀點、穩定度評分 |
| `data/universe/references/<首字母>/<TICKER>/` | 對照資料：`reference.json` 與每次擷取的證據 |
| `libs/sec_revenue/companies/<首字母>/<ticker>/` | 每家公司的 parser 規格（`spec.py`）與說明（`parser.md`） |
| `data/revenue/<首字母>/<TICKER>/` | parser 的正式輸出：季度（`Q/`）與年度（`FY/`）兩個序列每期的 `revenue.json` 與 SEC 表格證據，以及 `status.json` |
| `data/snapshots/<首字母>/<TICKER>/` | 由 SEC 原文產生的 XBRL fact 快照（每份申報一個 JSON Lines 檔，主文件的全部數值 fact、一行一個，與公司 parser 無關）與申報清單（`manifest.json`，每個檔案的 sha256）；沒有原文時以快照驗證正式輸出，需要原文時依清單重新下載 |

格式規格見 [ticker 清單與對照資料格式](docs/architecture/universe.md)。

## 程式結構

| 路徑 | 內容 |
|---|---|
| `scripts/` | CLI 入口：`sec_pipeline.py`（tickers、download、parse、viewer）、`capture_references.py`、`validate_universe.py` |
| `libs/sec_revenue/common/` | 跨子套件共用、不依賴其他子套件的小工具：JSON 讀寫、`.env`、期間範圍 |
| `libs/sec_revenue/download/` | SEC 下載：HTTP、快取、CIK 與申報清單、要下載的申報、申報包、download 的 ticker 選擇 |
| `libs/sec_revenue/revenue/` | parser 引擎：規格結構、讀 inline XBRL、組數值、檢核、比較欄比對、證據、寫入 |
| `libs/sec_revenue/companies/` | 公司規格 |
| `libs/sec_revenue/capture/` | 對照資料擷取 |
| `libs/sec_revenue/universe/` | `tickers.csv` 與對照資料的格式（`model`）、讀取與驗證（`tickers`、`references`、`validate`），以及 CLI 的 ticker 解析 |
| `libs/sec_revenue/viewer/` | 正式輸出的唯讀 viewer |
| `tests/` | unit test：`tests/sec_revenue/` 對應 `libs/sec_revenue/`，`tests/scripts/` 對應 `scripts/`。以 repo 根目錄為 top-level 執行：`python -m unittest discover -s tests -t .`，測試模組以 `tests.sec_revenue.*` 載入，不會蓋掉 `libs/` 的 `sec_revenue` 套件 |
| `docs/architecture/` | 系統規格：parser 與正式輸出、SEC 下載、viewer、對照資料格式、擷取工具 |
| `docs/guides/` | 操作手冊：[資料使用指南](docs/guides/data-guide.md)（給使用資料的 RD 與 PM）、[本機操作](docs/guides/local-workflow.md) |

## Setup

需要 Python 3.11 以上與 Node.js（只用 `npm run` 執行常用指令，沒有 Node 依賴）。

1. 建立 `.venv`，安裝依賴與擷取用的 Chromium：

   ```bash
   npm run setup
   ```

2. 設定 `.env`（只有下載或以原文 parse 時需要；只跑 `npm run check` 可以略過）：複製 `.env.example` 為 `.env`，填入兩項設定。`.env` 不進 Git，主 repo 與每個 worktree 各放一份。
   - `SEC_USER_AGENT`：姓名或組織加上聯絡 email。SEC 要求自動化請求註明身分，email 須是聯絡得到的真實地址；只讀本機快取（`--offline`）時不需要。
   - `SEC_DATA_DIR`：SEC 原文與下載索引的共用目錄，放在 repo 以外，例如 `~/sec-revenue-data`。原文可依記錄的 SEC URL 與 sha256 重建，不進 Git。

   ```bash
   cp .env.example .env
   ```

3. 確認環境。不需要 SEC 原文：unit test、對照資料驗證，以及以快照對全部上線公司跑 `parse --check`。

   ```bash
   npm run check
   ```

## 常用指令

指令定義在 `package.json`，額外參數接在 `--` 之後。

| 指令 | 用途 |
|---|---|
| `npm run setup` | 建立 `.venv`，安裝 `requirements.txt` 與擷取、截圖用的 Chromium |
| `npm run test` | unit test（`unittest discover -s tests -t .`） |
| `npm run validate` | 驗證 `tickers.csv` 與對照資料 |
| `npm run regression` | 以 `data/snapshots/` 的快照對全部上線公司跑 `parse --check`，不需要 SEC 原文 |
| `npm run check` | 依序執行以上三項（CI 在每個 PR 執行同樣三項） |
| `npm run tickers` | 列出有公司規格的 ticker |
| `npm run download -- ...` | 下載 SEC 申報包；目標期別有 10-K 時一併下載推算 Q4 所需的申報；`--dry-run` 只列出還沒下載的申報；`--from-manifest` 依申報清單重新下載並逐檔核對 |
| `npm run parse -- ...` | 依公司規格產生 `data/revenue/` 的正式輸出與證據，不連網；不指定 `--start` 時從預設起始日（2024-01-01）起；`--check` 與已提交的輸出比對，加 `--snapshots` 時不讀原文 |
| `npm run snapshot -- ...` | 由 SEC 原文產生 `data/snapshots/` 的快照與申報清單；`--check` 核對已提交的快照與原文一致 |
| `npm run capture:setup` | 開啟擷取用的專用瀏覽器，檢查並等待登入 |
| `npm run capture -- ...` | 擷取對照資料 |
| `npm run viewer` | 本機唯讀 viewer，<http://127.0.0.1:7290>：正式輸出（`data/revenue/`）的 Q／FY 數字與 SEC 證據 |

範例：

```bash
# 下載任何 ticker 自 2025 年起的申報包，並刷新到最新一期
npm run download -- --tickers AAPL PGR --start 2025-01-01 --latest

# 下載 tickers.csv 的全部公司；只用本機快取
npm run download -- --all --start 2025-01-01 --offline

# 一併下載 XBRL R 頁面（預設略過）
npm run download -- --tickers AAPL --start 2025-01-01 --include-r-pages

# 列出 tickers.csv 全部公司在範圍內還沒下載的申報，不連網
npm run download -- --all --start 2024-01-01 --dry-run

# 產生正式輸出，或與已提交的輸出比對
npm run parse -- --tickers AAPL
npm run parse -- --tickers AAPL --check

# 沒有 SEC 原文時：以快照比對；需要原文時依申報清單下載
npm run parse -- --all --check --snapshots
npm run download -- --all --from-manifest
```

`ALL` 是 Allstate 的 ticker；全部公司用 `--all`。操作步驟見 [本機操作](docs/guides/local-workflow.md)；下載規則、快取與回傳碼見 [SEC 下載](docs/architecture/download.md)；parser 的規格、檢核與輸出格式見 [Parser 與正式輸出](docs/architecture/parser.md)；頁面與 API 見 [Viewer](docs/architecture/viewer.md)。

## 擷取對照資料

擷取工具使用 Playwright 內建的 Chromium（`npm run setup` 已安裝）。先開啟專用瀏覽器登入三個網站，再擷取：

```bash
npm run capture:setup
npm run capture -- --source stockanalysis --tickers AAPL,MSFT
```

登入狀態保存在 repo 以外的專用 profile（預設 `~/.sec-revenue-capture/profile/`）。流程、登入判斷與證據規則見 [對照資料擷取工具](docs/architecture/capture.md)。
