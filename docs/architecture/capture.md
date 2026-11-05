# 對照資料擷取工具

`scripts/capture_references.py` 開啟一個專用的有視窗瀏覽器，確認網站都已登入後，擷取指定 ticker 的 by segment 營收，連同表格證據累積合併進 `data/universe/references/`。資料格式見 [ticker 清單與對照資料格式](universe.md)。

擷取不依賴 parser，也不讀 `tickers.csv`，可以先大量擷取。

## 使用方式

```bash
.venv/bin/playwright install chromium        # 第一次使用
.venv/bin/python scripts/capture_references.py setup
.venv/bin/python scripts/capture_references.py capture --source stockanalysis --tickers AAPL,MSFT
.venv/bin/python scripts/capture_references.py capture --source stockanalysis --tickers-file list.txt
```

- `setup [--sources ...]`：逐站檢查登入，預設檢查全部來源。
- `capture --source <來源>`：`--tickers` 以逗號分隔，`--tickers-file` 以空白、逗號或換行分隔、`#` 之後為註解，兩者可同時使用。`--universe-dir` 指定寫入位置，預設 `data/universe`。

## 瀏覽器與登入

- 使用 Playwright 內建的 Chromium，有視窗，固定視窗 1400×900、device scale 1。
- profile 在 repo 以外，預設 `~/.sec-revenue-capture/profile/`，可用環境變數 `SEC_REVENUE_CAPTURE_PROFILE` 指定。同一個 profile 同時只能由一個程式開啟。
- 三個網站都須登入才看得到完整資料。使用者在視窗中以 email 與密碼登入，登入狀態由瀏覽器自己保存在 profile。程式不經手帳密，不讀取、匯出或寫入 cookie 與 token。
- `requirements.txt` 鎖定 Playwright 小版本：Chromium 版本跟著套件，升級後舊 profile 可能失去登入狀態，此時重跑 `setup` 登入即可。

### `setup`

開啟各站的檢查頁（AAPL 的目標頁），逐站列出「已登入」或「未登入」。有未登入的站時，使用者在視窗中登入後按 Enter 重新檢查；全部登入才結束，輸入 `q` 放棄。

### 登入判斷

只看目標頁的 DOM，不看 cookie。每站定一個只有登入後才出現的元素，以及一個只有未登入時才出現的元素：

| 來源 | 已登入 | 未登入 |
|---|---|---|
| `stockanalysis` | 頁首的 Notifications 按鈕 | 頁首的 `/login/` 連結 |
| `futu` | 頁首頭像 `.hk-js-header-avatar` | 「註冊/登入」按鈕 `.hk-cs-log-in-btn` |
| `tradingview` | `<html class="is-authenticated">` | `<html class="is-not-authenticated">` |

看得到已登入元素、且沒有未登入元素，才算已登入。15 秒內判斷不出來視為未登入。`capture` 開始前也檢查該來源，未登入時照 `setup` 的方式等待使用者登入。

## 擷取

每個來源一個 adapter（`libs/sec_revenue/capture/sites/`），負責開到目標頁、切到正確的檢視、讀出表格文字與期別。外殼負責截圖、產生證據檔、合併與驗證。

- adapter 每產生一張表，外殼就建立一次擷取。一個畫面只顯示一期的來源（富途）一期一次擷取。
- capture_id 取到秒；同一來源的下一次擷取落在同一秒時，工具等到下一秒。寫入時若該來源已有相同的 capture_id，拒絕寫入。
- 兩檔之間間隔 3 秒，一次只處理一家公司。
- 一檔失敗不影響其他檔。結束時列出成功與失敗清單（失敗附原因，例如未登入、頁面不存在、找不到表格），並執行 `validate_universe()`；全部成功且驗證通過時回傳 0。

### Stock Analysis

目標頁為 `https://stockanalysis.com/stocks/<ticker>/metrics/revenue-by-segment/`，ticker 轉小寫，類別股以 `.` 分隔（`BRK-B` → `brk.b`）。

- 頁面預設顯示 TTM。擷取前切到 Quarterly 與 Latest（數值，而非成長率或占比），並確認圖表標題為 `(Quarterly)`。
- 表格內容連續兩次讀取相同才採用，避免讀到切換中的數值。
- 表頭第一欄為 `Date`，其餘為分類；每列一季，`label` 為頁面上的日期原文（例如 `Sep 30, 2026`），`period_end` 為該日期，`kind` 為 `Q`。
- 儲存格為 `-` 等空值時不寫入。數值帶 `B`、`M` 等單位，不設 `display_unit`。
- 擷取表格上顯示的全部期別。未登入時只顯示最近 20 期。
- 沒有 segment 頁的公司（例如 BRK-B）回應 404，列為失敗。

### 富途、TradingView

目前只有登入檢查；擷取以 #43 實作。

## 證據

三個證據檔都只涵蓋表格區塊：

- `table.png`：截圖前隱藏表格以外的 fixed／sticky 元素（例如帶有帳號頭像的頁首），並取消祖先元素的裁切；截取表格範圍四周各留 16 像素，表格右緣超出視窗時暫時加寬視窗。截圖轉成 256 色調色盤 PNG 並最佳化壓縮，表格顏色少，不 dither 可保持文字清楚。單檔超過 500 KB 時在輸出中警告。
- `table.html`：表格結構與文字，不是網頁原始 bytes。由 adapter 依網站結構選擇產生方式：
  - `clean`：保留原始片段中與表格有關的標籤（`table`、`tr`、`td`、`div`、`span` 等）與文字，刪除所有屬性（只留數字的 `colspan`、`rowspan`）；其他標籤只留文字；script、style、svg、圖片、按鈕、表單等連同內容刪除；註解刪除。適用以 `<table>` 呈現的表格。
  - `rebuild`：以表格文字重建只含 `<table><tr><th><td>` 的表格。適用以 div 排版的表格。

  Stock Analysis 暫用 `clean`。三個來源的擷取都完成後，再依各站的頁面結構決定最終做法（#43）。

  帳號名稱、追蹤參數與外部資源都在屬性或被刪除的標籤中，兩種方式都不需要逐項列舉。驗證程式不檢查這些內容，由擷取工具負責。
- `table.txt`：表格文字，一列一行，欄位以 tab 分隔，第一行為表頭。

## 合併與寫入

依 [保存模型](universe.md#保存模型) 累積合併：

- 新擷取涵蓋的期別以新值取代；同一來源內 `label` 相同或 `(kind, period_end)` 相同即視為同一期。未涵蓋的期別保留原值與原擷取。
- 不再被任何期別引用的擷取，連同證據目錄一併刪除；舊證據由 Git 歷史保存。
- `display` 以 `parse_display()` 換算美元，四捨五入為整數存入 `usd`。
- 期別依期末日新到舊排列，同日 FY 在 Q 前；沒有期末日的排在最後。

寫入先在 ticker 目錄旁以 `.` 開頭的暫存目錄完成，通過 `validate_reference()` 後才整個換上；任何錯誤都不改動既有的對照目錄。

## 程式結構

| 路徑 | 內容 |
|---|---|
| `scripts/capture_references.py` | CLI |
| `libs/sec_revenue/capture/browser.py` | 開啟專用 profile 的瀏覽器 |
| `libs/sec_revenue/capture/runner.py` | 登入檢查、逐檔擷取、截圖、結果清單 |
| `libs/sec_revenue/capture/sites/` | 各網站 adapter 與登入判斷 |
| `libs/sec_revenue/capture/evidence.py` | 截圖壓縮、`table.html`、`table.txt`、證據檔寫入 |
| `libs/sec_revenue/capture/merge.py` | 累積合併與寫入 |
| `libs/sec_revenue/capture/model.py` | adapter 與外殼交換的資料結構 |
| `tests/lib/test_capture.py` | 離線測試（不開瀏覽器、不連網） |
