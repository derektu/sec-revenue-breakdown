# ticker 清單與對照資料格式

`data/universe/` 保存使用者維護的 ticker 清單，以及每家公司的對照資料。整個目錄進 Git。

對照資料只用於與 SEC 萃取結果比對、選擇採用的來源觀點；營收數字的擷取與計算仍只用 SEC 申報（見 `AGENTS.md`）。

兩者的生命週期互相獨立：對照資料可以先大量擷取，不需要該公司已有 parser；parser 寫好並驗證通過後，公司才列入 `tickers.csv`（從 `wip` 開始）。因此有對照目錄的 ticker 不一定列在 `tickers.csv`，列在 `tickers.csv` 的 ticker 也不一定有對照目錄。

## 目錄結構

```
data/universe/
  tickers.csv
  references/
    <首字母>/<TICKER>/
      reference.json
      captures/<source>/<capture_id>/
        table.png     表格區塊截圖
        table.html    表格 HTML 片段
        table.txt     表格文字
```

- 對照目錄由 ticker 推得：`references/<ticker 首字母>/<TICKER>/`，TICKER 保留原樣，例如 `references/B/BRK-B/`。程式以 `sec_revenue.universe.reference_dir()` 計算。
- 每一層只放下列項目，其他檔案或目錄都是錯誤：
  - `references/`：單一大寫字母的目錄；
  - 首字母目錄：ticker 目錄；
  - ticker 目錄：`reference.json` 與 `captures/`；
  - `captures/`：來源名稱目錄（`stockanalysis`、`futu`、`tradingview`、`manual`）；
  - 來源目錄：capture_id 目錄；
  - capture 目錄：`table.png`、`table.html`、`table.txt`。
- 以 `.` 開頭的檔案（例如 `.gitkeep`、`.DS_Store`）不檢查。
- 沒有任何對照數值時不建立對照目錄：對照檔至少要有一個來源；每個來源至少一次擷取、至少一期；每期至少一個值。

## `tickers.csv`

UTF-8 CSV（可帶 BOM），一列一家公司。以 Excel 編輯時須另存為「CSV UTF-8」；cp950 等其他編碼會被拒絕。表頭與欄位順序固定：

```
ticker,cik,name,status,adopted_source,stability_score,stability_note,notes
```

| 欄位 | 值域 | 說明 |
|---|---|---|
| `ticker` | `^[A-Z][A-Z0-9]*(-[A-Z0-9]+)?$`，不可重複 | 交易代號，例如 `AAPL`、`BRK-B`；類別股一律以 `-` 分隔，不用 `.` |
| `cik` | 一或多個不含前導零的數字，以 `;` 分隔 | SEC CIK；多個值用於前身與繼受實體，例如 XOM 的 `2115436;34088` |
| `name` | 非空 | 公司正式名稱 |
| `status` | `wip`、`ok`、`drop` | `wip` 研究中、`ok` 上線、`drop` 放棄 |
| `adopted_source` | 空白，或 `stockanalysis`、`futu`、`tradingview`、`manual` | 採用的來源觀點；空白代表尚未決定。`status=ok` 時必填，且須是該 ticker 對照檔中實際存在的來源 |
| `stability_score` | 空白，或 1–5 的整數 | 5 為最穩定；空白代表尚未評分。`status=ok` 時必填 |
| `stability_note` | 任意文字 | 評分理由 |
| `notes` | 任意文字 | 自由備註 |

- 含逗號或換行的值以雙引號包住，例如 `"Meta Platforms, Inc."`。
- 各欄位前後的一般空格會被去掉；空白列略過。
- 數字只接受 ASCII 數字 `0`–`9`，空白只接受一般空格；全形數字與 NBSP 都視為錯誤。
- 驗證錯誤標示檔案的實際行號，空白列與引號內的換行都計入行數。

範例：

```csv
ticker,cik,name,status,adopted_source,stability_score,stability_note,notes
AAPL,320193,Apple Inc.,wip,,,,
BRK-B,1067983,Berkshire Hathaway Inc.,ok,stockanalysis,4,分部 tag 八季一致,
```

範例中 BRK-B 為 `ok`，因此 `references/B/BRK-B/reference.json` 須含 `stockanalysis` 來源。

## `reference.json`

每個 ticker 一份，內含多個來源觀點。一個來源觀點是該來源呈現的 by segment 營收拆分，不含地區拆分。

```json
{
  "schema_version": 1,
  "ticker": "AAPL",
  "sources": {
    "stockanalysis": {
      "captures": {
        "20261104T013829Z": {
          "url": "https://stockanalysis.com/stocks/aapl/statistics/revenue-by-segment/",
          "captured_at": "2026-11-04T01:38:29.259Z",
          "method": "browser_dom",
          "display_unit": "M",
          "files": {
            "png":  { "path": "captures/stockanalysis/20261104T013829Z/table.png",  "sha256": "..." },
            "html": { "path": "captures/stockanalysis/20261104T013829Z/table.html", "sha256": "..." },
            "txt":  { "path": "captures/stockanalysis/20261104T013829Z/table.txt",  "sha256": "..." }
          }
        }
      },
      "periods": [
        {
          "label": "Q3 2026",
          "period_end": "2026-09-30",
          "kind": "Q",
          "capture": "20261104T013829Z",
          "values": {
            "iPhone": { "display": "57,583", "usd": 57583000000 }
          }
        }
      ]
    }
  }
}
```

### 保存模型

每個來源累積保存多次擷取。有些來源一次只顯示部分期別（例如富途只顯示最近 8 季），只留最近一次擷取會讓較早的期別失去數值與證據。

- `captures` 記錄該來源的每一次擷取：時間、方式、單位與證據檔。
- `periods` 每期一筆，以 `capture` 指向數值來自哪一次擷取。
- 新的擷取若涵蓋已有的期別，該期以新值取代，`capture` 改指新擷取；未涵蓋的期別保留原值與原擷取。合併由擷取工具執行。
- 每次擷取至少被一期引用。不再被任何期別引用的擷取，連同其證據目錄一併刪除；舊證據由 Git 歷史保存。

### 欄位

| 位置 | 欄位 | 值域 | 說明 |
|---|---|---|---|
| 頂層 | `schema_version` | 整數 `1` | `1.0`、`true` 都不接受 |
| 頂層 | `ticker` | 同 `tickers.csv` 的格式 | 須與所在目錄的 ticker 相同 |
| 頂層 | `sources` | 非空物件 | 鍵為來源：`stockanalysis`、`futu`、`tradingview`、`manual` |
| 來源 | `captures` | 非空物件 | 鍵為 capture_id，值為擷取 |
| 來源 | `periods` | 非空陣列 | 該來源呈現的期間 |
| 擷取 | `url` | `https://` 開頭 | 擷取頁面；`browser_dom` 必填，其他方法選填 |
| 擷取 | `captured_at` | UTC 的 ISO 8601 時間 | 擷取時間，見「時間格式」 |
| 擷取 | `method` | `browser_dom`、`legacy_import`、`manual` | 取得方式 |
| 擷取 | `display_unit` | 選填；`K`、`M`、`B`、`萬`、`億` | 表格表頭標示的單位，例如表頭寫「Millions」、儲存格只有 `57,583` 時填 `M` |
| 擷取 | `files` | `{png, html, txt}`，各為 `{path, sha256}` | 證據檔；`browser_dom` 必填且三個都要，`legacy_import`、`manual` 不得有 |
| 期間 | `label` | 非空字串 | 來源上的期間標籤原文，例如 `Q3 2026`、`2026/Q3` |
| 期間 | `period_end` | 選填；`YYYY-MM-DD` | 來源上的期末日期；來源沒有日期時省略，不自行推算 |
| 期間 | `kind` | `Q`、`FY` | 單季或會計年度 |
| 期間 | `capture` | 同來源 `captures` 的鍵 | 數值來自哪一次擷取 |
| 期間 | `values` | 非空物件 | 鍵為分類名稱，值為 `{display, usd}` |
| 數值 | `display` | 非空字串 | 頁面原文 |
| 數值 | `usd` | 整數 | 由 `display` 換算的美元金額 |

不在上表的欄位一律視為錯誤，避免拼錯的欄位被默默忽略。同一個 JSON 物件內出現重複的鍵（例如同一期的 `values` 寫了兩次 `iPhone`）也是錯誤，因為一般 JSON 解析器會默默保留後者。

### 擷取與證據檔

capture_id 是擷取時間取到秒的 UTC 時間 `YYYYMMDDTHHMMSSZ`，例如 `20261104T013829Z`，須與該擷取的 `captured_at` 取到秒一致。程式以 `sec_revenue.universe.capture_id()` 計算。

`browser_dom` 擷取保存三個證據檔，位置固定為 `captures/<source>/<capture_id>/table.{png,html,txt}`（相對於 ticker 目錄），`files` 中的 `path` 須與此相同：

- `table.png`：營收拆分表格區塊的截圖；
- `table.html`：表格區塊的 HTML 片段；
- `table.txt`：表格區塊的文字。

三者都只涵蓋表格區塊，不保存整頁，以免存入登入帳號資訊、廣告與 script。`sha256` 是檔案 bytes 的 sha256，用來確認數值與證據屬於同一次擷取；驗證只比對雜湊與檔案是否存在，不解碼圖片。

`legacy_import` 與 `manual` 沒有證據檔。`captures/` 下每個 capture 目錄與證據檔都須被 `reference.json` 引用，未被引用的視為錯誤。

### 時間格式

`captured_at` 為 UTC 的 ISO 8601 時間：`YYYY-MM-DDTHH:MM:SS`，可帶任意位數的秒以下小數，結尾為 `Z` 或 `+00:00`。例如 `2026-11-04T01:38:29Z`、`2026-11-04T01:38:29.259Z`、`2026-11-04T01:38:29.259+00:00`。來源工具輸出的毫秒原樣保存。其他時區（包括 `-00:00`）不接受。

### 分類與期間

- 分類名稱保留來源原文，例如富途的「汽車分部」。與 SEC 分類的對應由比對工具處理，不寫進對照檔。
- 期間保留來源的標籤與日期。與 SEC `reportDate`（含 52/53 週制）的對齊由比對工具處理。
- 同一來源內 `label` 不可重複；有 `period_end` 的期別，`(kind, period_end)` 也不可重複。不同來源可有相同期間。

### 數值

`display` 保存頁面原文，`usd` 保存換算後的美元整數。`display` 的位數代表來源的顯示精度，比對時以此為準。

`display` 的寫法：

- 單位：`K`（10³）、`M`（10⁶）、`B`（10⁹）、`T`（10¹²）、`萬`（10⁴）、`億`（10⁸）。數字與單位之間可有一般空格。
- 不帶單位時套用該期 `capture` 所指擷取的 `display_unit`；該擷取沒有 `display_unit` 時代表美元原值。display 自己帶單位時，以自己的單位為準。
- 可含千位分隔符 `,` 與開頭的 `$`。
- 負數寫成 `-1.5B`、`−1.5B`（U+2212），或括號 `(1.5B)`、`(1.5)B`。
- 數字只接受 ASCII `0`–`9`，空白只接受一般空格。

`usd` 與 `display` 的差距不可超過 `display` 最後一位數字的半個單位，剛好等於半個單位也算吻合。例如 `57.58B` 容許 ±0.005B（±5,000,000）；`212.05億` 容許 ±0.005 億（±500,000）；`display_unit` 為 `M` 時，`57,583` 容許 ±0.5M。

`usd` 只能是整數美元。因此不帶單位、也沒有 `display_unit` 的 display 若帶小數（例如 `1,234.56`），容許誤差只有 ±0.005 美元，除非小數部分為零，否則任何整數 `usd` 都會超出誤差；這種表格須設定 `display_unit`。

空值不寫入：來源沒有呈現的分類或期間直接省略，不寫 `display: ""`，也不以 `usd: 0` 代表缺值。`usd` 為 0 與其他數值一樣依誤差判定：`display` 為 `0` 時吻合，`display` 為 `8.7B` 時超出誤差。

## 驗證

```
.venv/bin/python scripts/validate_universe.py [--universe-dir DIR]
```

逐項列出所有錯誤，全部通過回傳 0，有任何錯誤回傳 1。檢查項目：

- `tickers.csv` 的編碼、CSV 語法、表頭、欄位數，以及各欄位的值域；
- `status=ok` 的 `adopted_source` 與 `stability_score` 必填，且 `adopted_source` 存在於該 ticker 的對照檔；
- 目錄結構的白名單，以及對照目錄位置是否與 ticker 一致；
- `reference.json` 能否讀取、是否為 UTF-8 JSON、有無重複鍵、ticker 是否與所在目錄一致，以及欄位與值域；
- 對照檔、來源、擷取、期別不可為空；
- capture_id 的格式及與 `captured_at` 是否一致；每期的 `capture` 是否存在；每次擷取是否被引用；
- 證據檔的位置、是否存在、sha256 是否相符；`captures/` 下是否有未被引用的目錄或檔案；
- `display` 與 `usd` 的換算是否在容許誤差內；
- 同一來源內期間是否重複。

讀檔失敗（非 UTF-8、CSV 語法錯誤、對照檔是目錄等）也列為錯誤訊息，不中止驗證。

程式內讀取資料用 `sec_revenue.universe`：`load_tickers()` 回傳 `TickerEntry` 清單，`load_reference(ticker)` 回傳對照檔內容；資料有任何錯誤時兩者都丟出 `UniverseError`，其 `errors` 列出全部錯誤。`load_tickers()` 只檢查 CSV 本身；`adopted_source` 是否存在於對照檔屬於跨檔檢查，由 `validate_universe()` 執行。
