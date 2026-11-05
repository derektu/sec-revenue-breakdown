# 本機分階段操作

這條正式路徑將下載與萃取分開。`download` 不產生營收輸出；`extract` 不連網，只讀已下載的 SEC 原文；`viewer` 只讀萃取輸出。沒有前端編譯步驟，Python 3.11+ 與 lxml 即可執行。

## 拉取與安裝

在本機 repo 先檢查 `git status`，保留既有未提交工作，再安全切至 main 並同步：

```bash
git fetch origin
git switch main
git pull --ff-only origin main
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

以下命令都從 repo 根目錄執行；省略 `--data` 時使用 `data`。macOS 可直接用 `.venv/bin/python`，不需啟動 Node／npm。

## 選擇 ticker

download 與 extract 都接受 `--tickers AAPL MSFT CVX`、`--tickers AAPL,MSFT` 或 `--ticker-file tickers.local.txt`。檔案一行一個 ticker，可加 `#` 註解；也接受逗號分隔，或 `.json` 的字串清單。`tickers.local.*` 已忽略，不會推上 Git。兩者同時提供時取去重後聯集。`ALL` 是 Allstate 的 ticker，不是保留字；選全部公司用 `--all`。

| 階段 | 接受的 ticker | `--all` | 省略 ticker |
|---|---|---|---|
| download | 任何格式正確的 ticker，不需要 parser | `data/universe/tickers.csv` 的全部公司 | 報錯，避免意外下載整份清單 |
| extract | 只有 `libs/sec_revenue/registry.json` 有 parser 的公司 | 全部有 parser 的公司 | 同 `--all` |

`tickers` 子命令列出有 parser 的公司：

```bash
.venv/bin/python scripts/sec_pipeline.py tickers
.venv/bin/python scripts/sec_pipeline.py tickers > tickers.local.txt
```

## 下載 SEC 申報

連網下載需要 **SEC_USER_AGENT**，內容為真實姓名／組織與聯絡 email（SEC 規範）。設定放在 repo 根目錄的 `.env`（格式見 `.env.example`，`.env` 不進 Git），`sec_pipeline.py` 啟動時讀取；終端已設定的環境變數優先。程式不提供預設身分、不保存帳密，也不把身分寫入快取。`--offline` 與萃取不需要此設定；線上 `--latest` 刷新仍需要。

SEC 原文（`sec/`）、下載與萃取索引（`pipeline/`）和萃取輸出（`outputs/`）放在資料根目錄。資料根目錄由 `.env` 的 **SEC_DATA_DIR** 指定，建議放在 repo 以外，讓主 repo 與各 worktree 共用同一份、不重複下載；未設定時為 repo 的 `data/`，`--data` 參數優先。原文可依 `packages.json` 的 SEC URL 與 sha256 重建，不進 Git。收據（`*.receipt.json`）與原文同目錄、只記檔名，索引內的路徑都相對於資料根目錄，所以整個目錄可以直接搬移。ticker 清單與對照資料（`data/universe/`）一律留在 repo 並進 Git。

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
```

### CIK

`tickers.csv` 列出的公司以該列 CIK 為準，可以有多個（前身與繼受實體，例如 XOM 的 `2115436;34088`），各 CIK 的 submissions 合併成同一份申報清單。沒列在 `tickers.csv` 的 ticker 查 SEC `company_tickers.json`；原始 bytes 與取得時間保存在快取，快取超過 7 天或查不到該 ticker 時重新抓取。catalog 記錄抓取時的 CIK 清單；`tickers.csv` 的 CIK 與之不同時，線上捨棄舊 catalog 重抓，離線則拒絕執行。下載結果的 `cik.source` 註明 CIK 來自 `tickers_csv` 或 `sec_company_tickers`。

### 選擇申報

`--start`、`--end` 為包含邊界的 `YYYY-MM-DD`，依 SEC **實際 reportDate** 選擇 10-K／10-Q（含修訂），不能把零售 52／53 週季末硬改成曆季末。同一期有多個 accession 時採最新申報。沒有日期範圍時只選最新一期。`--latest` 在線上會刷新 SEC 索引；離線時只表示「本機已知最新」，輸出的 `catalog_source` 明列來源。一般未加 `--latest`／`--force` 時沿用本機 catalog；若指定範圍超出 recent 覆蓋，會補 SEC 歷史 submissions 分頁。沒有主文件的列（1990 年代純文字申報）不收入 catalog；其他不符 SEC 命名規則的 accession 或主文件名會讓該公司失敗。

申報包層下載目標期別的所有 10-K／10-Q 申報，原始與修訂版（`/A`）都包含；parser 層照上述規則每期只選一份。

8-K 只收 item 2.02（Results of Operations）的財報新聞稿：申報日晚於最早目標期的期末；有 `--end` 時不晚於最後目標期期末後 90 天。下一季的新聞稿必在下一季期末之後才發布，所以這個範圍只涵蓋所選各期的新聞稿。沒有 `--end` 時不設上限，包含最新一季尚未申報 10-Q 前的新聞稿。item 代碼來自 SEC submissions，記錄在 catalog 的 `eight_k_items`。窗口內有 8-K 缺 item 資料時，線上會重抓 submissions 與全部歷史分頁補齊；仍補不到的 accession 列在結果的 `eight_k_items_missing`，該公司列為失敗，不把缺資料當成非 2.02。

### 完整申報包

每個選中的 accession 下載 `index.json`（機器可讀檔案清單）與 filing index 頁 `ACCESSION-index.htm`（提供每份文件的 Type，例如 `EX-99.1`，以及 Description），再下載清單中的所有檔案：主文件、所有附件與圖檔、XBRL instance（inline XBRL 申報為 SEC 抽出的 `*_htm.xml`）、schema 與 linkbase、`FilingSummary.xml`。

不下載的檔案記在 `skipped` 並註明原因：

| 原因 | 檔案 |
|---|---|
| `complete_submission_text` | 完整申報 `ACCESSION.txt`，內容與個別檔案重複 |
| `filing_index_page` | `ACCESSION-index.htm` 等 index 頁（filing index 另外保存） |
| `archive_zip` | `.zip` 封裝 |
| `r_page_not_requested` | XBRL R 頁面（`R*.htm`，較舊申報為 `R*.xml`）及其呈現檔（`Financial_Report.xlsx`／`.xls`、`report.css`、`Show.js`、`MetaLinks.json`）。這類檔案占申報包請求數的大宗；需要時以 `--include-r-pages` 重跑補抓 |
| `unsupported_name` | `.`、`..`，或檔名含 SEC 檔名規則以外的字元 |
| `directory` | `index.json` 中 `type` 為 `dir` 的子目錄 |

略過不算失敗，不影響申報包是否完成。

每份文件保存 sha256、bytes、快取路徑與三個 URL：

| 欄位 | 內容 |
|---|---|
| `filing_index_url` | `https://www.sec.gov/Archives/edgar/data/<CIK>/<ACC>/<ACCESSION>-index.htm` |
| `source_url` | 文件原址 |
| `ixviewer_url` | `https://www.sec.gov/ix?doc=/Archives/edgar/data/<CIK>/<ACC>/<doc>.htm`；只有 inline XBRL 文件（根元素宣告 inline XBRL namespace，且含 `ix:header`）才有，其他為 null |

另記 `type`、`description`、`primary`（是否為主文件）與 `inline_xbrl`。單一檔案下載失敗只記在該申報包的 `failures`，其他檔案照常下載，申報包標示 `complete: false`；之後重跑只補抓缺的檔案。packages.json 在每個申報包結束或中斷時寫入一次；中斷（SEC 拒絕、Ctrl-C 等）時也保存已下載檔案的收據。

`--offline` 只驗證快取 hash，不補抓：申報包未完成（`complete: false`），或加了 `--include-r-pages` 但 R 頁面尚未下載時，狀態為 `offline_incomplete`，該公司列為失敗。

### parser 指定文件

registry 有 parser 的公司，另依 parser 宣告挑出萃取需要的文件（以 role 命名，例如 `primary`）寫入 `downloads.json`。申報包已有的檔案直接沿用同一份 bytes，不重複請求 SEC。萃取只讀 `downloads.json`，所以申報包多下載的檔案不影響萃取 fingerprint。

「最新」一般以已申報的 10-K／10-Q（含修訂）為準。CAT、UPS 已審閱的 2026Q3 8-K earnings exhibit 另有公司規則，把事件日與實際收入季度分開。並非所有新 8-K 都可自動視為新季度財報；未建立規則的披露不能冒稱已支援。新 tags 或表格架構不符時會拒絕萃取。

年度 Q4 自動納入同一實體的上一季 YTD9。BAC 2025 與 UPS 2024 的已審閱比較欄依賴由各自 parser 額外宣告。PGR 年報會從 filing index 找到唯一合併 Exhibit 13，不能拿 parent-only 10-K 代替。輔助申報會標 `dependency: true`，不會因下載了依賴檔就把它變成使用者要求的目標期別。

### 批次與速率

單次正常 GET，至多每秒八次（SEC 上限為每秒十次）；不重試、不換身分。已成功的 bytes 保留。

多家公司逐家下載，一家失敗（含非預期例外）不中止整批。結果列出 `succeeded`、`failed`（附錯誤原因）與 `not_attempted`。SEC 回應 403 或 429，或缺少合格的 `SEC_USER_AGENT` 時，代表身分或速率被拒，繼續送請求違反 SEC 規範，因此整批停止：該 ticker 列為失敗，其餘列為 `not_attempted`，`stopped` 註明原因。申報包未完成、離線時申報包不完整，或 8-K item 不明的公司也列在 `failed`。

parser 文件組下載中斷時會明標未完成，萃取拒絕混用新舊附件；之後重跑可續用已完成的同組檔案。

## 萃取營收

```bash
# 只萃取下載快取中指定 ticker／實際期別範圍
.venv/bin/python scripts/sec_pipeline.py extract --ticker-file tickers.local.txt --start 2025-01-01 --end 2026-11-04

# 只萃取每家公司已下載的最新目標期；這一步不查 SEC
.venv/bin/python scripts/sec_pipeline.py extract --ticker-file tickers.local.txt --latest

# 強制重新讀原文、解析與計算，不重抓原文
.venv/bin/python scripts/sec_pipeline.py extract --tickers AAPL --start 2025-01-01 --end 2026-11-04 --force
```

來源集合、filing metadata 與規則 fingerprint 相同且上次成功時，顯示 `cache_hit` 並跳過萃取。原文／accession／規則變動會失效，缺輸出會重建；hash 不符則拒絕。公司自己的規則指紋不包含其他公司的模組，改 AAPL 不會使 MSFT 的 cache 失效。共用引擎或該公司可用比較欄變動時可使該公司的既有萃取失效，避免沿用過時 Q4／重編口徑。下載程式（`download.py`、`tickers.py`）不在規則指紋內，修改下載流程不會使既有萃取失效。

一家公司有多個 basis 時逐一產生。CVX 預設 net，gross 與抵銷另存。新原文流程的 XOM 固定使用可完整對帳的 all-income 分部及扣回欄，另存 `basis_description`；舊研究為參考網站 Q2 使用的 gross 欄位例外只留在歷史重播，不暗中套用於新的資料。

CVX net 與 XOM all-income 另有明確成分對帳：差額只在所有 SEC 申報運算元的精度界限內接受，保留差額與允許精度，不修改原始數字。

缺值、歧義、未知表頭／scope、缺 Q4 運算元或原文解析失敗時，輸出保留 null、錯誤與風險，不以舊研究答案或零補齊。CLI 回傳碼：`0` 成功或 cache hit；`1` 輸入或快取驗證失敗；`2` download 有公司失敗或未執行，或萃取已有可供檢查的部分結果，但仍有缺值或失敗。失敗結果不視為成功 cache，下一次仍會嘗試萃取。

## Viewer

```bash
.venv/bin/python scripts/sec_pipeline.py viewer --host 127.0.0.1 --port 7290
```

從同一台本機瀏覽器開啟 <http://127.0.0.1:7290>。ticker、期間與 basis 選單來自現有輸出，不限制固定八期。未下載／未萃取的公司回報無資料；已有成功歷史期不因本次只萃取某一季而從索引消失。頁面可看完整 SEC 運算元、申報精度、風險及來源格式。

可選 Playwright UI 測試（先安裝 `playwright`，並使用本機 Chromium 或執行 `python -m playwright install chromium`）：

```bash
.venv/bin/python scripts/check_sec_viewer_ui.py --tickers AAPL MSFT CVX
```

## Cache 與版本

| 路徑 | 內容 |
|---|---|
| `data/sec/TICKER/PERIOD/ACCESSION/HASH.html` | 真正下載的原始 HTML bytes（主文件、附件、R 頁面、filing index 頁）與 hash 收據 |
| `data/sec/TICKER/PERIOD/ACCESSION/HASH.<副檔名>` | 其他申報包檔案（`.xml`、`.xsd`、`.jpg` 等），保留原副檔名 |
| `data/sec/TICKER/_metadata/CIK/HASH.json` | SEC submissions 原始 JSON |
| `data/sec/TICKER/PERIOD/ACCESSION/HASH.json` | SEC filing index 等原始 JSON，格式明列 `sec_json` |
| `data/sec/_sec/company_tickers/HASH.json` | SEC `company_tickers.json` 原始 bytes |
| `data/pipeline/_sec/company_tickers.json` | 目前採用的 company_tickers 收據與取得時間 |
| `data/pipeline/TICKER/catalog.json` | 可驗證的申報清單、8-K item 代碼與 metadata 來源收據 |
| `data/pipeline/TICKER/packages.json` | 各 accession 的申報包：檔案清單、每份文件的 sha256 與三個 URL、略過與失敗 |
| `data/pipeline/TICKER/downloads.json` | 有 parser 的公司：目標期別、依賴檔及各 role 選用的原文版本 |
| `data/pipeline/TICKER/extractions.json` | 各期 fingerprint、成功／失敗與輸出 hash |
| `data/outputs/TICKER/PERIOD/TICKER_PERIOD_BASIS_revenue.json` | 固定命名的目前輸出 |
| `data/outputs/TICKER/PERIOD/versions/FINGERPRINT/...` | 不同來源／規則的歷史萃取版本 |

以上產物皆不推 Git。一般 SEC 下載不依賴 `data/vendor/local`；不會拿第三方內容替代 SEC。舊 `replay_sec.py` 與 30 家／240 期凍結回歸繼續保留，與新原文流程分開測試；歷史重播請指定 `--out data/engine-check`，不要用相同 `data/outputs` 覆蓋新的原文萃取結果。先前「250 份缺 HTML」指雲端 checkout 沒有保存原文，不代表 SEC 沒有該申報；這個新 download 流程就是用來取得並持久保存原文。
