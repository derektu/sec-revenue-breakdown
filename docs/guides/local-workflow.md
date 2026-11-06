# 本機操作

流程分三個階段，各自獨立執行：`download` 下載 SEC 申報包，不產生營收輸出；`parse` 不連網，只讀已下載的申報包，依公司 parser 產生 `data/revenue/` 的正式輸出與證據；`viewer` 唯讀顯示正式輸出。`snapshot` 由原文產生 `data/snapshots/` 的 XBRL fact 快照與申報清單，讓沒有原文的人也能驗證正式輸出。沒有前端編譯步驟，Python 3.11+ 與 lxml 即可執行；`parse` 截圖另需 Playwright 與 Chromium。

## 拉取與安裝

在本機 repo 先檢查 `git status`，保留既有未提交工作，再安全切至 main 並同步：

```bash
git fetch origin
git switch main
git pull --ff-only origin main
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

以下命令都從 repo 根目錄執行；`--data` 省略時使用資料根目錄（`SEC_DATA_DIR`，未設定時為 repo 的 `data/`）。macOS 可直接用 `.venv/bin/python`，不需啟動 Node／npm。

## 接手或第一次 clone

不需要 SEC 原文就能確認環境與全部正式輸出：

```bash
npm run setup
npm run check        # unit test、對照資料驗證，以及以快照對全部上線公司跑 parse --check
```

需要原文時（產生證據、修改公司 parser 或框架、處理新一期財報），先設定 `.env` 的 `SEC_USER_AGENT` 與 `SEC_DATA_DIR`，再依申報清單下載並逐檔核對 sha256：

```bash
.venv/bin/python scripts/sec_pipeline.py download --all --from-manifest
.venv/bin/python scripts/sec_pipeline.py parse --all --check     # 原文模式：另外驗證表格 HTML
```

## 選擇 ticker

download 與 parse 都接受 `--tickers AAPL MSFT CVX`、`--tickers AAPL,MSFT`；download 另接受 `--ticker-file tickers.local.txt`。檔案一行一個 ticker，可加 `#` 註解；也接受逗號分隔，或 `.json` 的字串清單。`tickers.local.*` 已忽略，不會推上 Git。兩者同時提供時取去重後聯集。`ALL` 是 Allstate 的 ticker，不是保留字；選全部公司用 `--all`。

| 階段 | 接受的 ticker | `--all` | 省略 ticker |
|---|---|---|---|
| download | 任何格式正確的 ticker，不需要公司 parser | `data/universe/tickers.csv` 的全部公司 | 報錯，避免意外下載整份清單 |
| parse | 只有 `libs/sec_revenue/companies/` 有公司 parser 的公司 | 全部有公司 parser 的公司 | 同 `--all` |

`tickers` 子命令列出有公司 parser 的 ticker：

```bash
.venv/bin/python scripts/sec_pipeline.py tickers
.venv/bin/python scripts/sec_pipeline.py tickers > tickers.local.txt
```

## 下載 SEC 申報

連網下載需要 **SEC_USER_AGENT**，內容為真實姓名／組織與聯絡 email（SEC 規範）。設定放在 repo 根目錄的 `.env`（格式見 `.env.example`，`.env` 不進 Git），`sec_pipeline.py` 啟動時讀取；終端已設定的環境變數優先。程式不提供預設身分、不保存帳密，也不把身分寫入快取。`--offline`、`--dry-run` 與 parse 不需要此設定；線上 `--latest` 刷新仍需要。

SEC 原文（`sec/`）與下載索引（`pipeline/`）放在資料根目錄。資料根目錄由 `.env` 的 **SEC_DATA_DIR** 指定，建議放在 repo 以外，讓主 repo 與各 worktree 共用同一份、不重複下載；未設定時為 repo 的 `data/`，`--data` 參數優先。原文可依 `packages.json` 的 SEC URL 與 sha256 重建，不進 Git。收據（`*.receipt.json`）與原文同目錄、只記檔名，索引內的路徑都相對於資料根目錄，所以整個目錄可以直接搬移。ticker 清單與對照資料（`data/universe/`）一律留在 repo 並進 Git。

```bash
# 任何 ticker：下載指定實際申報期範圍內的完整申報包；已有且 hash 正確的檔案直接沿用
.venv/bin/python scripts/sec_pipeline.py download --tickers AAPL ALL --start 2025-01-01 --end 2026-11-04

# tickers.csv 的全部公司，刷新 SEC submissions，下載每家公司最近一期
.venv/bin/python scripts/sec_pipeline.py download --all --latest

# 從指定起日更新到最新：抓取該範圍內所有期別，不只最後一期
.venv/bin/python scripts/sec_pipeline.py download --tickers AAPL MSFT --start 2025-01-01 --latest

# 一併下載 XBRL R 頁面；先前略過的 R 頁面在既有申報包上補抓
.venv/bin/python scripts/sec_pipeline.py download --tickers AAPL --latest --include-r-pages

# 強制刷新索引並重抓所有檔案；不同 bytes 留存為不同 hash 版本
.venv/bin/python scripts/sec_pipeline.py download --tickers AAPL --start 2025-01-01 --end 2026-11-04 --force

# 完全不連網，只驗證並沿用既有索引與檔案；缺任何必要檔案即失敗
.venv/bin/python scripts/sec_pipeline.py download --tickers AAPL --latest --offline

# 只讀本機 catalog 與 packages.json，列出範圍內還沒下載完整的目標與 Q4 依賴申報；不連網、不寫入，有缺漏時回傳 2
.venv/bin/python scripts/sec_pipeline.py download --all --start 2024-01-01 --dry-run
```

目標期別有 10-K 時，會一併下載推算 Q4 所需的同財年 10-Q 與上一份 10-K。選擇申報、依賴期別、申報包內容、快取格式與回傳碼見 [SEC 下載](../architecture/download.md)。

## Parse

```bash
.venv/bin/python scripts/sec_pipeline.py parse --tickers AAPL
.venv/bin/python scripts/sec_pipeline.py parse --tickers AAPL --check
```

架構、公司 parser 的介面、檢核、證據、正式輸出格式與參數見 [parser.md](../architecture/parser.md)。

## 快照

```bash
.venv/bin/python scripts/sec_pipeline.py parse --all --check --snapshots   # 不讀原文，以快照比對
.venv/bin/python scripts/sec_pipeline.py snapshot --tickers AAPL           # 由原文重產該公司的快照與申報清單
.venv/bin/python scripts/sec_pipeline.py snapshot --all --check            # 核對已提交的快照與原文一致
```

快照是每份申報主文件的全部數值 fact，與公司 parser 無關：每份申報一個 `<accession>.jsonl`，第一行是表頭（快照格式版本、解析器 hash、申報資訊、namespaces 與衝突的前綴、dei；原文讀不到時是錯誤原因），之後一行一個 fact。

以下改動要產生快照，並和改動放在同一個 PR：

| 改動 | 執行 | 結果 |
|---|---|---|
| 下載了新的申報 | `snapshot --tickers <該公司>` | 多出該份申報的快照；既有申報的快照內容不變 |
| 決定快照內容的程式（`revenue/xbrl.py`、`ixbrl.py`、`filings.py`、`snapshot.py`）改動 | `snapshot --all` | 全部公司重產 |

修改公司 parser（分類、concept、寫法切換）不需要重產快照。

快照與申報清單不一致或由不同版本的程式產生時，`--snapshots` 直接報錯並指出要重產的公司。`snapshot` 寫入時若有原文讀不到的申報，快照記錄為錯誤並回傳 2，先補下載再重產。快照模式驗得到與驗不到的內容見 [parser.md](../architecture/parser.md) 的「快照」。

## Viewer

```bash
.venv/bin/python scripts/sec_pipeline.py viewer --host 127.0.0.1 --port 7290
```

從同一台本機瀏覽器開啟 <http://127.0.0.1:7290>。viewer 唯讀，不執行 parser，顯示 repo 的 `data/revenue/`（可用 `--revenue` 指定其他目錄）。

頁面內容、格子標示與 API 見 [Viewer](../architecture/viewer.md)。
