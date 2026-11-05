# 本機分階段操作

這條正式路徑將下載與萃取分開。`download` 不產生營收輸出；`extract` 不連網，只讀已下載的 SEC 原文；`evidence` 不連網，由萃取輸出回到 SEC 原文產生表格證據；`viewer` 只讀正式輸出、萃取輸出與證據。沒有前端編譯步驟，Python 3.11+ 與 lxml 即可執行；`evidence` 另需 Playwright 與 Chromium。

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

來源集合、filing metadata 與規則 fingerprint 相同且上次成功時，顯示 `cache_hit` 並跳過萃取。原文／accession／規則變動會失效，缺輸出會重建；hash 不符則拒絕。公司自己的規則指紋不包含其他公司的模組，改 AAPL 不會使 MSFT 的 cache 失效。共用引擎或該公司可用比較欄變動時可使該公司的既有萃取失效，避免沿用過時 Q4／重編口徑。下載程式（`download.py`、`tickers.py`）與證據程式（`evidence.py`）不在規則指紋內，修改這兩個流程不會使既有萃取失效。

一家公司有多個 basis 時逐一產生。CVX 預設 net，gross 與抵銷另存。新原文流程的 XOM 固定使用可完整對帳的 all-income 分部及扣回欄，另存 `basis_description`；舊研究為參考網站 Q2 使用的 gross 欄位例外只留在歷史重播，不暗中套用於新的資料。

CVX net 與 XOM all-income 另有明確成分對帳：差額只在所有 SEC 申報運算元的精度界限內接受，保留差額與允許精度，不修改原始數字。

缺值、歧義、未知表頭／scope、缺 Q4 運算元或原文解析失敗時，輸出保留 null、錯誤與風險，不以舊研究答案或零補齊。CLI 回傳碼：`0` 成功或 cache hit；`1` 輸入或快取驗證失敗；`2` download 有公司失敗或未執行，或萃取已有可供檢查的部分結果，但仍有缺值或失敗。失敗結果不視為成功 cache，下一次仍會嘗試萃取。

## SEC 表格證據

```bash
# 指定期別範圍；省略範圍時只處理最新一期
.venv/bin/python scripts/sec_pipeline.py evidence --tickers AAPL --start 2024-01-01

# 強制重新產生
.venv/bin/python scripts/sec_pipeline.py evidence --tickers AAPL --start 2024-01-01 --force
```

目前只以 AAPL 驗證；程式只依 XBRL fact id 找表格，不含公司規則，其他有萃取輸出的公司也能執行。

每個萃取欄位的運算元展開成 SEC fact：一般季度直接取該 fact；Q4 推算為「+ 年度 − 九個月累計」，兩個 fact 各自附證據；多表加總逐項列出。展開後的加權總和必須等於萃取值。每個 fact 以來源文件（sha256）與 fact id 在 SEC 原文找到節點，核對它是 `ix:nonFraction`，且 name、contextref、scale、顯示文字與依 sign 算出的數值都和運算元相同，再往上找所在的 `<table>`；表格編號須與萃取紀錄的 `table_index` 相同。

| fact 狀態 | 意義 | 欄位結果 |
|---|---|---|
| `in_table` | 找到所在表格，產生 HTML 與 PNG | 正常 |
| `not_in_table` | fact 在原文中但不在 HTML 表格內 | `not_in_table`，該運算元無證據，不產生替代證據 |
| `fact_not_found` | 原文找不到 fact id，或運算元沒有 fact id | `failed` |
| `fact_mismatch` | 節點不是 `ix:nonFraction`、屬性或數值與運算元不同，或所在表格與萃取紀錄不同 | `failed` |
| `source_missing` | 申報包找不到運算元的 SEC 原文（sha256），或 `source_format` 不是 `original_html`（含缺值） | `failed` |
| `evidence_failed` | 抽表格 HTML 或截圖失敗，包括瀏覽器中的表格與原文表格對不上 | `failed` |

萃取值為空、權重與運算元數量不同，或運算式總和不等於萃取值時，欄位也是 `failed`，並附原因。任何欄位不是正常狀態時，這一期的證據不算完成，下一次會重新產生。錯誤只影響所在的期別，其他期照常產生。

每期證據放在 `outputs/TICKER/PERIOD/evidence/`，同一期內同一張表只產生一份，該期引用這張表的所有 fact 一起標示。檔名 `ACCESSION-SHA12-tN` 中的 `SHA12` 是來源文件 sha256 的前 12 碼，同一申報包有多份 inline 文件時不會混淆：

- `ACCESSION-SHA12-tN.html`：只含該表格的獨立 HTML。保留 inline style，移除 script、圖片、連結、外部資源與事件屬性；含 `url(`、`expression(`、`@import` 或反斜線的 style 屬性整個移除；XBRL 標籤改成一般 `span`，並加上 CSP。被引用的儲存格有紅框與編號，所在列有淡底色，頁首列出每個編號對應的欄位。
- `ACCESSION-SHA12-tN.png`：headless Chromium 以 `set_content` 載入本機快取的 SEC 原文，沒有導覽請求。context 設為 offline、關閉頁面 script，所有資源請求都被中止；標示由 Playwright 的 evaluate 注入。截圖前核對瀏覽器中的表格文字與 lxml 的同一張表相同（忽略空白），保留 SEC 原排版，以 2 倍解析度截圖。表格高於 3000px 時只保留前 4 列表頭與標示列上下 600px 內的列，略過的列以紅色虛線的「✂ 已裁切」列標示，並記錄 `cropped: true`。
- `evidence.json`：綁定的萃取輸出路徑與 sha256、各欄位的運算式（權重、角色、fact）與狀態、各 fact 的 SEC 原文 URL、XBRL viewer URL、filing index URL、期間與編號，以及各表格檔的 sha256、證據程式的 sha256 與 Playwright 版本。

每期先在同一目錄下的暫存資料夾寫好全部表格檔與 `evidence.json`，完成後整組換上 `evidence/`，不會出現新舊檔案混用。產生過程發生未預期錯誤時，`evidence/` 只留一份 `status: failed` 並附原因的 `evidence.json`。

萃取輸出不寫入證據欄位；運算元的來源文件與 fact id 就是對應 `evidence.json` 的鍵。萃取輸出 hash、運算元來源原文 hash 與其 SEC URL、`evidence.py` 與 Playwright 版本都沒變，且表格檔 hash 相符時，顯示 `cache_hit` 並跳過。證據可由 SEC 原文與萃取輸出重建，不進 Git。

## Viewer

```bash
.venv/bin/python scripts/sec_pipeline.py viewer --host 127.0.0.1 --port 7290
```

從同一台本機瀏覽器開啟 <http://127.0.0.1:7290>。viewer 唯讀，不執行 parser，有兩個頁面：

- `/`：正式輸出（repo 的 `data/revenue/`，可用 `--revenue` 指定其他目錄）。
- `/legacy`：舊流程的萃取輸出（`--data` 下的 `outputs/`）。

### 正式輸出頁面

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
- 留空或失敗：檢核名稱與原因、是否保留先前上線的輸出；Q4 留空另列年度的分類與 Q1–Q3 期間各段的分類。保留了已上線輸出時，運算式與證據照常顯示。
- 重算不同（`differs_from_published`）：原因、各分類的已上線值與重算值、不同的欄位；只有中繼資料不同（`stale_fields`）時列出欄位。
- 差異標記的明細：分類、角色與期間、結果（數值不同或無法解析）、已上線值、申報列示值、來源申報與申報日、說明，以及雙方各自的加數清單（已上線的運算元編號、申報中的 fact id，各附 concept、維度、正負號與值）。
- 各運算元的 SEC 表格截圖：同一張表只顯示一次，表頭列出表內的運算元編號；每張表附 SEC 原文、XBRL viewer 與表格 HTML 連結。

**表格檔的核對**

表格檔以 `revenue.json` 記錄的 sha256 核對；同一張表由多個運算元引用時，每個運算元的紀錄都要相符。缺檔或 hash 不符時，不顯示截圖，改以紅色「無表格證據」區塊標示，並附原因。

**API 與安全**

- `/api/companies` 列出公司。
- `/api/company?ticker=` 回傳一家公司的兩個序列。
- 表格檔只經 `/revenue-evidence/TICKER/(Q|FY)/期末日/ACCESSION-SHA12-tN.(png|html)` 提供，並檢查路徑不超出輸出根目錄。表格 HTML 以 CSP sandbox 開啟。頁面本身的 CSP 只允許同源資源。

### 舊流程頁面

ticker、期間與 basis 選單來自現有輸出，不限制固定八期。未下載／未萃取的公司回報無資料；已有成功歷史期不因本次只萃取某一季而從索引消失。頁面可看完整 SEC 運算元、申報精度、風險及來源格式。

已產生證據的期別，每個欄位下方會列出運算式，例如「8,726,000,000 = ① 10-K 年度（2024-09-29～2025-09-27）33,708 百萬 − ② 10-Q 9M（2024-09-29～2025-06-28）24,982 百萬」，並逐一顯示各 fact 的表格截圖，以及 SEC 原文、XBRL viewer 與表格 HTML 連結。

以下情況會以紅色「無證據」區塊標示，並附原因：

- 尚未產生證據。
- 證據產生失敗。
- `evidence.json` 無法讀取。
- 證據過期：萃取輸出 hash、表格檔 hash 或證據程式版本與紀錄不同。

部分運算元不在 HTML 表格內時，以黃色區塊標示「部分運算元無證據」。萃取值為空的欄位不寫成「值 = 運算式」，只標「萃取值為空，替代式僅供參考」。

表格檔只經 `/evidence/TICKER/PERIOD/ACCESSION-SHA12-tN.(png|html)` 提供，表格 HTML 以 CSP sandbox 開啟。

可選 Playwright UI 測試（舊流程頁面；先安裝 `playwright`，並使用本機 Chromium 或執行 `python -m playwright install chromium`）：

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
| `data/outputs/TICKER/PERIOD/evidence/evidence.json` | 該期證據：運算式、fact 狀態與 SEC URL、表格檔 hash |
| `data/outputs/TICKER/PERIOD/evidence/ACCESSION-SHA12-tN.{html,png}` | 該期引用的 SEC 表格 HTML 與截圖 |

以上產物皆不推 Git。一般 SEC 下載不依賴 `data/vendor/local`；不會拿第三方內容替代 SEC。舊 `replay_sec.py` 與 30 家／240 期凍結回歸繼續保留，與新原文流程分開測試；歷史重播請指定 `--out data/engine-check`，不要用相同 `data/outputs` 覆蓋新的原文萃取結果。先前「250 份缺 HTML」指雲端 checkout 沒有保存原文，不代表 SEC 沒有該申報；這個新 download 流程就是用來取得並持久保存原文。
