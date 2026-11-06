# 本機操作

流程分三個階段，各自獨立執行：`download` 下載 SEC 申報包，不產生營收輸出；`parse` 不連網，只讀已下載的申報包，依公司規格產生 `data/revenue/` 的正式輸出與證據；`viewer` 唯讀顯示正式輸出。沒有前端編譯步驟，Python 3.11+ 與 lxml 即可執行；`parse` 截圖另需 Playwright 與 Chromium。

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

download 與 parse 都接受 `--tickers AAPL MSFT CVX`、`--tickers AAPL,MSFT`；download 另接受 `--ticker-file tickers.local.txt`。檔案一行一個 ticker，可加 `#` 註解；也接受逗號分隔，或 `.json` 的字串清單。`tickers.local.*` 已忽略，不會推上 Git。兩者同時提供時取去重後聯集。`ALL` 是 Allstate 的 ticker，不是保留字；選全部公司用 `--all`。

| 階段 | 接受的 ticker | `--all` | 省略 ticker |
|---|---|---|---|
| download | 任何格式正確的 ticker，不需要公司規格 | `data/universe/tickers.csv` 的全部公司 | 報錯，避免意外下載整份清單 |
| parse | 只有 `libs/sec_revenue/companies/` 有規格的公司 | 全部有規格的公司 | 同 `--all` |

`tickers` 子命令列出有公司規格的 ticker：

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

# 只讀本機 catalog 與 packages.json，列出範圍內還沒下載完整的目標與 Q4 依賴申報；不連網、不寫入
.venv/bin/python scripts/sec_pipeline.py download --all --start 2024-01-01 --dry-run
```

### CIK

`tickers.csv` 列出的公司以該列 CIK 為準，可以有多個（前身與繼受實體，例如 XOM 的 `2115436;34088`），各 CIK 的 submissions 合併成同一份申報清單。沒列在 `tickers.csv` 的 ticker 查 SEC `company_tickers.json`；原始 bytes 與取得時間保存在快取，快取超過 7 天或查不到該 ticker 時重新抓取。catalog 記錄抓取時的 CIK 清單；`tickers.csv` 的 CIK 與之不同時，線上捨棄舊 catalog 重抓，離線則拒絕執行。下載結果的 `cik.source` 註明 CIK 來自 `tickers_csv` 或 `sec_company_tickers`。

### 選擇申報

`--start`、`--end` 為包含邊界的 `YYYY-MM-DD`，依 SEC **實際 reportDate** 選擇 10-K／10-Q（含修訂），不能把零售 52／53 週季末硬改成曆季末。同一期有多個 accession 時採最新申報。沒有日期範圍時只選最新一期。`--latest` 在線上會刷新 SEC 索引；離線時只表示「本機已知最新」，輸出的 `catalog_source` 明列來源。一般未加 `--latest`／`--force` 時沿用本機 catalog；若指定範圍超出 recent 覆蓋，會補 SEC 歷史 submissions 分頁。沒有主文件的列（1990 年代純文字申報）不收入 catalog；其他不符 SEC 命名規則的 accession 或主文件名會讓該公司失敗。

下載目標期別的所有 10-K／10-Q 申報，原始與修訂版（`/A`）都包含；parse 自己決定每期的主申報（見 [parser.md](parser.md)）。

### Q4 依賴申報

parse 推算 Q4 需要年度減去同財年 Q1–Q3，「Q4 口徑一致」檢查需要上一財年的 10-K。所以目標期別中每份 10-K 另外下載：

- 上一份 10-K：catalog 中期末早於目標、最晚的一期 10-K；
- 同財年的 10-Q：期末介於上一份 10-K 與目標之間的各期。

這些期別的 10-K／10-Q（含修訂版）與目標期別一樣下載完整申報包，列在結果的 `dependency_periods`，不算使用者要求的目標期別，也不擴大 8-K 的窗口。catalog 中沒有上一份 10-K 時，改取目標前 370 天內的 10-Q，並在 `dependencies_unresolved` 註明。

`--dry-run` 只讀本機 catalog 與 `packages.json`，每家公司列出目標期別（`missing_targets`）與依賴期別（`missing_dependencies`）中沒有完整申報包的 10-K／10-Q：accession、表單、期末日、申報日，以及 `not_downloaded`（沒有申報包）或 `incomplete`（申報包未完成）。沒有本機 catalog 的公司列出錯誤。不連網、不寫入任何檔案，回傳碼為 0。

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

### 批次與速率

單次正常 GET，至多每秒八次（SEC 上限為每秒十次）；不重試、不換身分。已成功的 bytes 保留。

多家公司逐家下載，一家失敗（含非預期例外）不中止整批。結果列出 `succeeded`、`failed`（附錯誤原因）與 `not_attempted`。SEC 回應 403 或 429，或缺少合格的 `SEC_USER_AGENT` 時，代表身分或速率被拒，繼續送請求違反 SEC 規範，因此整批停止：該 ticker 列為失敗，其餘列為 `not_attempted`，`stopped` 註明原因。申報包未完成、離線時申報包不完整，或 8-K item 不明的公司也列在 `failed`。

回傳碼：`0` 全部公司成功；`1` 輸入或快取驗證失敗；`2` 有公司失敗或未執行。

## Parse

```bash
.venv/bin/python scripts/sec_pipeline.py parse --tickers AAPL
.venv/bin/python scripts/sec_pipeline.py parse --tickers AAPL --check
```

規格、檢核、證據、正式輸出格式與參數見 [parser.md](parser.md)。

## Viewer

```bash
.venv/bin/python scripts/sec_pipeline.py viewer --host 127.0.0.1 --port 7290
```

從同一台本機瀏覽器開啟 <http://127.0.0.1:7290>。viewer 唯讀，不執行 parser，顯示 repo 的 `data/revenue/`（可用 `--revenue` 指定其他目錄）。

**公司搜尋框**

- 輸入代碼或名稱即時篩選候選清單，兩者都比對、不分大小寫；代碼開頭相符的排在前面。
- 方向鍵上下移動、Enter 選定、Esc 取消並還原目前的公司。
- 候選清單只列 `tickers.csv` 中 `status=ok` 的公司，每筆是「代碼 公司名」。其他公司不在清單上，用 URL hash 開啟（例如 `#ticker=KO&series=Q`）。

**數字表**

一家公司一張表：列是分類，規格宣告調節項（`reconciling`，例如公司間抵銷）時接在分類之後，以斜體加「調節」標記區隔，最後一列是總營收；欄是期別，由舊到新。表上方的按鈕切換季度 Q 與年度 FY 兩個序列。期別取自 `status.json` 的 `periods`（格式見 [parser.md](parser.md)）與 `Q/`、`FY/` 下有 `revenue.json` 的目錄。

`status.json` 有 `comparison_errors` 時，表上方列出讀不到原文、沒有做比較欄比對的申報與原因。

- **單位**：百萬美元，標在表頭「分類」旁。原文以千為單位的公司（例如 PLD）顯示到小數三位。
- **欄名**：財年季別與期末日；不是 `published` 的期別加註狀態，有 `differs_from_published` 的期別加註「重算不同」。
- **列的順序**：取各期分類的聯集，依最新一期的順序排列，只在較舊期別出現的分類接在後面；調節項同樣取聯集。點調節項的格子與分類一樣顯示運算式與證據。
- **格子的標示**：

  | `status.json` 中該期的紀錄 | 格子顯示 |
  |---|---|
  | `not_derived`（Q4 留空） | 灰底「留空」，滑鼠停留顯示檢核名稱與原因 |
  | `failed` | 紅底「失敗」，滑鼠停留顯示檢核名稱與原因 |
  | `not_derived` 或 `failed`，且 `published_output_kept` | 同上底色，顯示保留的已上線值；欄名註明「保留已上線值」 |
  | `differences` | 橘底加 △，標在差異標記的分類或調節項那一列；分類是「總營收」的標在總營收列 |

**點一個格子**

表下方會顯示：

- **運算式**：例如「8,726 百萬 = ③ 10-K 年度（2024-09-29～2025-09-27）33,708 百萬 − ④ 10-Q 九個月（2024-09-29～2025-06-28）24,982 百萬」。
- 主申報與九個月申報的表單、accession、申報日。
- 結構檢核與加總的結果。
- 留空或失敗：檢核名稱與原因、是否保留先前上線的輸出。Q4 因分類集合不同而留空時，另列年度的分類與 Q1–Q3 期間各段的分類；因年報改了分類口徑而留空時，另列每個不同的分類、上一財年期間、先前的值與依據（已上線 FY 或上一份年報）及年報列示的值。保留了已上線輸出時，運算式與證據照常顯示。
- Q4 口徑無法判斷（`q4_basis`）：照常推算，另以提示列出無法判斷的原因。
- 重算不同（`differs_from_published`）：原因、各分類的已上線值與重算值、不同的欄位；只有中繼資料不同（`stale_fields`）時列出欄位。
- 差異標記的明細：分類、角色與期間、結果（數值不同或無法解析）、已上線值、申報列示值、來源申報與申報日、說明，以及雙方各自的加數清單（已上線的運算元編號、申報中的 fact id，各附 concept、維度、正負號與值）。
- 各運算元的 SEC 表格截圖：同一張表只顯示一次，表頭列出表內的運算元編號；每張表附 SEC 原文、XBRL viewer 與表格 HTML 連結。

**表格檔的核對**

表格檔以 `revenue.json` 記錄的 sha256 核對；同一張表由多個運算元引用時，每個運算元的紀錄都要相符。缺檔或 hash 不符時，不顯示截圖，改以紅色「無表格證據」區塊標示，並附原因。

**API 與安全**

- `/api/companies` 列出公司。
- `/api/company?ticker=` 回傳一家公司的兩個序列。
- 表格檔只經 `/revenue-evidence/TICKER/(Q|FY)/期末日/ACCESSION-SHA12-tN.(png|html)` 提供，並檢查路徑不超出輸出根目錄。表格 HTML 以 CSP sandbox 開啟。頁面本身的 CSP 只允許同源資源。

## 下載快取

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

表中的 `data/` 指資料根目錄（`SEC_DATA_DIR`）。以上產物皆不推 Git，可依記錄的 SEC URL 與 sha256 重新下載核對；不會拿第三方內容替代 SEC。
