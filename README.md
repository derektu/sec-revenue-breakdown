# SEC 營收組成

從 SEC 申報文件擷取美股公司每季的 by segment 營收拆分，範圍逐步擴大到 S&P 1500。以正確率優先，寧缺毋濫：每家公司有自己的 parser，每個數字都附 SEC 原文證據，通過對照資料驗證、格式穩定的公司才上線。

整體計畫與進度見 [#36](https://github.com/derektu/sec-revenue-breakdown/issues/36)。

## 原則

完整約束見 [`AGENTS.md`](AGENTS.md)，重點如下：

- **數字只來自 SEC**：營收的擷取與計算只用 SEC 申報（10-K、10-Q、8-K 附件）。Stock Analysis、富途、TradingView 等對照資料只用於比對與選擇分類觀點。
- **只做 by segment**，不做地區拆分。
- **每個數字有證據**：萃取結果連到 SEC 原文表格（HTML 與截圖）；推算的欄位附每個運算元的證據與運算式。
- **不補值**：缺值、歧義或驗證不過時輸出 null 與原因，不當作零，也不拿對照資料補。
- **公司互相隔離**：每家公司的 parser 在自己的資料夾，新增或修改一家不影響其他公司；測試範圍由改動推得。

## 流程

```
擷取對照資料（瀏覽器）──┐
                         ├─→ 開發 parser ─→ 驗證關卡 ─→ 上線
下載 SEC 財報 ───────────┘                       │
                    新一期財報 ─→ 萃取 ─→ 跨期比對 ─→ PM review
```

1. **擷取對照資料**：專用瀏覽器確認 Stock Analysis、富途、TradingView 都已登入後，擷取指定股票的 by segment 營收，並保存表格截圖、HTML 片段與文字作為證據。擷取不依賴 parser，可以先大量進行；多次擷取累積保存，逐步拉長期間。
2. **下載 SEC 財報**：任何 ticker 都能下載完整申報包，並保存每份文件的 SEC URL，必要時開啟原文或 SEC 的 XBRL viewer 比對。
3. **開發 parser**：parser 從 XBRL 找出與對照資料一致的數據，並由 fact 找到所在的 SEC 表格作為證據。每家 parser 附 `parser.md` 說明分類對應、tag 變動與推算邏輯。
4. **驗證關卡**：各分類與採用的來源觀點相符、加總等於總營收、每個數字都有證據，三者都通過才輸出。比對結果附穩定度評分（1–5），由使用者決定採用的觀點。
5. **上線**：使用者在 `tickers.csv` 將該公司標為 `ok`。
6. **新一期財報**：與先前各期比對，分類變動、占比或成長率異常時提醒 PM review，review 紀錄進 Git。

## 資料

| 路徑 | 內容 |
|---|---|
| `data/universe/tickers.csv` | 使用者維護的 ticker 清單：CIK、狀態（`wip` 研究中、`ok` 上線、`drop` 放棄）、採用的來源觀點、穩定度評分 |
| `data/universe/references/<首字母>/<TICKER>/` | 對照資料：`reference.json` 與每次擷取的證據 |
| `libs/sec_revenue/issuers/<首字母>/<ticker>/` | 每家公司的 parser |

格式規格見 [ticker 清單與對照資料格式](docs/architecture/universe.md)。

## Setup

需要 Python 3.11 以上與 Node.js（只用 `npm run` 執行常用指令，沒有 Node 依賴）。

1. 建立 `.venv`，安裝依賴與擷取用的 Chromium：

   ```bash
   npm run setup
   ```

2. 設定 SEC 身分：複製 `.env.example` 為 `.env`，填入 `SEC_USER_AGENT`（姓名或組織加上聯絡 email）。SEC 要求自動化請求註明身分，email 須是聯絡得到的真實地址。`.env` 不進 Git；只讀本機快取（`--offline`）時不需要。

   ```bash
   cp .env.example .env
   ```

3. 確認環境：

   ```bash
   npm run check
   ```

## 常用指令

指令定義在 `package.json`，額外參數接在 `--` 之後。

| 指令 | 用途 |
|---|---|
| `npm run setup` | 建立 `.venv`，安裝 `requirements.txt` 與擷取用的 Chromium |
| `npm run test` | unit test |
| `npm run regression` | 三十家凍結資料的引擎回歸 |
| `npm run validate` | 驗證 `tickers.csv` 與對照資料 |
| `npm run check` | 依序執行以上三項（CI 在每個 PR 執行前兩項） |
| `npm run tickers` | 列出有 parser 的 ticker |
| `npm run download -- ...` | 下載 SEC 申報包 |
| `npm run extract -- ...` | 從下載快取萃取營收，不連網 |
| `npm run capture:setup` | 開啟擷取用的專用瀏覽器，檢查並等待登入 |
| `npm run capture -- ...` | 擷取對照資料 |
| `npm run viewer` | 本機唯讀 viewer，<http://127.0.0.1:7290> |

範例：

```bash
# 下載任何 ticker 自 2025 年起的申報包，並刷新到最新一期
npm run download -- --tickers AAPL PGR --start 2025-01-01 --latest

# 下載 tickers.csv 的全部公司；只用本機快取
npm run download -- --all --start 2025-01-01 --offline

# 一併下載 XBRL R 頁面（預設略過）
npm run download -- --tickers AAPL --start 2025-01-01 --include-r-pages

# 萃取有 parser 的公司
npm run extract -- --tickers AAPL --start 2025-01-01
```

`ALL` 是 Allstate 的 ticker；全部公司用 `--all`。下載、萃取的完整參數、快取與回傳碼見 [本機分階段操作](docs/architecture/local-workflow.md)。

## 擷取對照資料

擷取工具使用 Playwright 內建的 Chromium（`npm run setup` 已安裝）。先開啟專用瀏覽器登入三個網站，再擷取：

```bash
npm run capture:setup
npm run capture -- --source stockanalysis --tickers AAPL,MSFT
```

登入狀態保存在 repo 以外的專用 profile（預設 `~/.sec-revenue-capture/profile/`）。流程、登入判斷與證據規則見 [對照資料擷取工具](docs/architecture/capture.md)。

## 先前的研究

先前研究階段的程式、操作方式與三十家公司的結果，整理在 [先前研究階段總覽](docs/legacy/overview.md)。這些內容尚未依上述流程驗證，僅供參考。
