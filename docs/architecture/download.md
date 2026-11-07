# SEC 下載

`download` 取得 SEC 申報清單與完整申報包，存在資料根目錄（`SEC_DATA_DIR`，未設定時為 repo 的 `data/`）；不產生營收輸出。parse 只讀這裡下載的申報包。指令與參數見 [本機操作](../guides/local-workflow.md)。程式在 `libs/sec_revenue/download/`：`http.py`（SEC 請求）、`store.py`（快取）、`catalog.py`（CIK 與申報清單）、`plan.py`（要下載的申報與依賴期別）、`packages.py`（申報包）、`workflow.py`（單家公司與批次）。

## CIK

`tickers.csv` 列出的公司以該列 CIK 為準，可以有多個（前身與繼受實體，例如 XOM 的 `2115436;34088`），各 CIK 的 submissions 合併成同一份申報清單。沒列在 `tickers.csv` 的 ticker 查 SEC `company_tickers.json`；原始 bytes 與取得時間保存在快取，快取超過 7 天或查不到該 ticker 時重新抓取。catalog 記錄抓取時的 CIK 清單；`tickers.csv` 的 CIK 與之不同時，線上捨棄舊 catalog 重抓，離線則拒絕執行。下載結果的 `cik.source` 註明 CIK 來自 `tickers_csv` 或 `sec_company_tickers`。

## 選擇申報

`--start`、`--end` 為包含邊界的 `YYYY-MM-DD`，依 SEC **實際 reportDate** 選擇 10-K／10-Q（含修訂），不能把零售 52／53 週季末硬改成曆季末。同一期有多個 accession 時採最新申報。沒有日期範圍時只選最新一期。`--latest` 在線上會刷新 SEC 索引；離線時只表示「本機已知最新」，輸出的 `catalog_source` 明列來源。一般未加 `--latest`／`--force` 時沿用本機 catalog；若指定範圍超出 recent 覆蓋，會補 SEC 歷史 submissions 分頁。沒有主文件的列（1990 年代純文字申報）不收入 catalog；其他不符 SEC 命名規則的 accession 或主文件名會讓該公司失敗。

下載目標期別的所有 10-K／10-Q 申報，原始與修訂版（`/A`）都包含；parse 自己決定每期的主申報（見 [parser.md](parser.md)）。

## 財報新聞稿 8-K

8-K 只收 item 2.02（Results of Operations）的財報新聞稿：申報日晚於最早目標期的期末；有 `--end` 時不晚於最後目標期期末後 90 天。下一季的新聞稿必在下一季期末之後才發布，所以這個範圍只涵蓋所選各期的新聞稿。沒有 `--end` 時不設上限，包含最新一季尚未申報 10-Q 前的新聞稿。item 代碼來自 SEC submissions，記錄在 catalog 的 `eight_k_items`。窗口內有 8-K 缺 item 資料時，線上會重抓 submissions 與全部歷史分頁補齊；仍補不到的 accession 列在結果的 `eight_k_items_missing`，該公司列為失敗，不把缺資料當成非 2.02。

## Q4 依賴申報

parse 推算 Q4 需要年度減去同財年 Q1–Q3，「Q4 口徑一致」檢查需要上一財年的 10-K。所以期末日有 10-K 的目標期別（年報期別）另外下載：

- 上一份 10-K：catalog 中期末早於目標、最晚的一期 10-K；
- 同財年的 10-Q：期末介於上一份 10-K 與目標之間的各期。

這些期別的 10-K／10-Q（含修訂版）與目標期別一樣下載完整申報包，列在結果的 `dependency_periods`，不算使用者要求的目標期別，也不擴大 8-K 的窗口。catalog 中沒有上一份 10-K 時，改取目標前 370 天內的 10-Q，並在 `dependencies_unresolved` 註明。

依賴期別比目標期別早約 15 個月，可能不在只含 recent 分頁的 catalog 內：有無法確定的依賴、線上執行且 catalog 尚未含全部歷史分頁時，補抓全部歷史分頁再計算一次。仍無法確定時，該公司列為失敗。

## 10-Q 財年依賴申報

parse 可以用申報日不晚於 10-Q、與它相接的前一份 10-K 推算 10-Q 的財年（見 [parser.md](parser.md) 的 `FISCAL_YEAR`）。下載在寫 parser 之前，不讀公司 parser，所以期末日沒有 10-K 的目標期別（季報期別）一律另外下載上一份 10-K：

- 每份 10-Q 申報（原始與修訂版）各取申報日不晚於它、期末早於它的 10-K 中期末最晚的一期，也就是同財年開始前的最後一份 10-K。parse 只用申報日不晚於 10-Q 的申報，所以申報日較晚的 10-K 不算。
- 這份 10-K 的期末須在 10-Q 期末前 370 天內，與 Q4 依賴的同財年範圍相同；更早的 10-K 表示中間那份不在 catalog 中，不列為依賴。

這些期別與 Q4 依賴期別合併成同一份 `dependency_periods`，已是目標或已列為 Q4 依賴的期別只下載一次。範圍含該財年的 10-K 時，上一份 10-K 同時是 Q4 依賴；起日落在財年中段（例如 `--start 2026-07-01`）時，上一份 10-K 只因 10-Q 財年依賴下載。只選最新一期（含 `--latest`）時同樣列上一份 10-K 為依賴；資料目錄已有完整申報包時沿用，不重新下載。

依賴期別的申報包與目標一樣存在資料目錄，parse 讀得到。依賴 10-K 落在 parse 預設範圍內時（例如以財年中段的起日下載後，不帶 `--start` 執行 parse），parse 會多處理那一期的 FY 與 Q4，Q4 因缺同財年 Q1–Q3 失敗。Q4 依賴的上一份 10-K 也是如此。

找不到上一份 10-K 的 10-Q 期別列在結果的 `prior_annual_unresolved`，不算失敗：上市後的第一批 10-Q 沒有更早的 10-K，宣告財年的公司照常 parse，以前一份 10-K 推算財年的公司在 parse 時以「財年與季別」失敗。有日期範圍、線上執行且 catalog 尚未含全部歷史分頁時，補抓全部歷史分頁再計算一次。只選最新一期時不補抓：SEC 的 recent 分頁至少含最近一年的申報，最新 10-Q 的上一份 10-K 若存在必在其中。

## 完整申報包

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

申報包的申報資訊（`filing`）記錄 SEC 的實際表單：`form` 與 `original_form` 都是 10-K、10-Q、10-K/A 或 10-Q/A，parse 以此區分原申報與修正申報。catalog 的 `form` 則是表單類別（10-K、10-Q、8-K，修正申報歸入原表單），供選期別與依賴期別使用，實際表單在 `original_form`。申報包的申報資訊在每次線上下載時依 catalog 重寫（`--from-manifest` 時依申報清單）；`--offline` 不改寫。

`--offline` 只驗證快取 hash，不補抓：申報包未完成（`complete: false`），或加了 `--include-r-pages` 但 R 頁面尚未下載時，狀態為 `offline_incomplete`，該公司列為失敗。

## 批次與速率

單次正常 GET，至多每秒八次（SEC 上限為每秒十次）；不重試、不換身分。已成功的 bytes 保留。

多家公司逐家下載，一家失敗（含非預期例外）不中止整批。結果列出 `succeeded`、`failed`（附錯誤原因）與 `not_attempted`。SEC 回應 403 或 429，或缺少合格的 `SEC_USER_AGENT` 時，代表身分或速率被拒，繼續送請求違反 SEC 規範，因此整批停止：該 ticker 列為失敗，其餘列為 `not_attempted`，`stopped` 註明原因。

申報包未完成、離線時申報包不完整、8-K item 不明，或 Q4 依賴期別無法確定的公司都列在 `failed`；`prior_annual_unresolved` 只回報。

回傳碼：`0` 全部公司成功；`1` 輸入或快取驗證失敗；`2` 有公司失敗或未執行。

## 檢查缺漏（`--dry-run`）

`--dry-run` 只讀本機 catalog 與 `packages.json`，不連網、不寫入任何檔案。每家公司列出：

| 欄位 | 內容 |
|---|---|
| `missing_targets`、`missing_dependencies` | 目標期別、依賴期別中沒有完整申報包的 10-K／10-Q：accession、表單、期末日、申報日，以及 `not_downloaded`（沒有申報包）或 `incomplete`（申報包未完成） |
| `catalog_incomplete` | 本機 catalog 尚未含全部歷史分頁，且範圍起日早於 catalog 最舊的 10-K／10-Q 期別、有無法確定的 Q4 依賴期別，或有日期範圍時有找不到上一份 10-K 的 10-Q 期別；附原因 |
| `prior_annual_unresolved` | 找不到上一份 10-K 的 10-Q 期別（見「10-Q 財年依賴申報」） |
| `error` | 沒有本機 catalog，或範圍內沒有 10-K／10-Q |

任何一家有上述缺漏時，結果的 `complete` 為 false，回傳碼為 2；否則為 0。

## 依申報清單下載（`--from-manifest`）

`data/snapshots/<首字母>/<TICKER>/manifest.json` 是 `snapshot` 子命令產生的申報清單（見 [parser.md](parser.md) 的「快照」），列出正式輸出依賴的每份 10-K／10-Q（框架不讀 8-K，所以 8-K 不在清單內）：

- 申報資訊：accession、表單、期末日、申報日、CIK、主文件名。
- 申報包內每個檔案的 sha256 與 bytes。

`download --from-manifest` 依清單重建資料根目錄。它不查 SEC 申報清單、不選期別，只下載清單列出的每份申報包：

- 清單列了 R 頁面的申報，一併下載 R 頁面。
- 每個檔案都核對清單記錄的 sha256。缺檔或 sha256 不同時列在 `manifest_mismatches`，該公司列為失敗；這些檔案記成申報包的失敗檔案，申報包標為不完整，parse 不讀它，之後重跑 download 會重新下載。
- 申報包有、清單沒列的檔案列在 `manifest_extra`，只回報，不算失敗。
- `--all` 為 `data/snapshots/` 中有申報清單的公司。
- 加上 `--offline` 時只核對本機快取，不連網。核對不符時同樣改寫本機的 `packages.json`：把不符的檔案移到失敗清單、申報包標為不完整。

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

表中的 `data/` 指資料根目錄。收據（`*.receipt.json`）與原文同目錄、只記檔名，索引內的路徑都相對於資料根目錄，所以整個目錄可以直接搬移。以上產物皆不推 Git，可依記錄的 SEC URL 與 sha256 重新下載核對；不會拿第三方內容替代 SEC。
