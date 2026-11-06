# 對照資料擷取工具

`scripts/capture_references.py` 開啟一個專用瀏覽器，確認網站都已登入後，擷取指定 ticker 的 by segment 營收，連同表格證據累積合併進 `data/universe/references/`。資料格式見 [ticker 清單與對照資料格式](universe.md)。

擷取不依賴 parser，也不讀 `tickers.csv`，可以先大量擷取。

## 使用方式

```bash
.venv/bin/playwright install chromium        # 第一次使用
.venv/bin/python scripts/capture_references.py setup
.venv/bin/python scripts/capture_references.py capture --source stockanalysis --tickers AAPL,MSFT
.venv/bin/python scripts/capture_references.py capture --source stockanalysis --tickers-file list.txt
.venv/bin/python scripts/capture_references.py capture --source futu --tickers AAPL --periods 8 --headed
```

- `setup [--sources ...]`：逐站檢查登入，預設檢查全部來源。
- `capture --source <來源>`：
  - `--tickers` 以逗號分隔，`--tickers-file` 以空白、逗號或換行分隔、`#` 之後為註解，兩者可同時使用。
  - `--periods N`：一個畫面只顯示一期的來源（富途）每檔擷取最近 N 季範圍內的季度，預設 12（三年）。
  - `--pause 秒數`：兩檔之間的間隔，預設 10 秒。
  - `--headed`：開視窗擷取，便於觀察；預設不開視窗。
  - `--universe-dir` 指定寫入位置，預設 `data/universe`。

## 瀏覽器與登入

- 使用 Playwright 內建的 Chromium（`channel="chromium"`，有無視窗都是同一個瀏覽器），固定視窗 1400×900、device scale 1。
- `setup` 一律開視窗。`capture` 預設不開視窗，不干擾使用者的其他操作；開始前檢查該來源的登入，未登入時關閉無視窗瀏覽器，改開視窗走 `setup` 的登入流程，登入後再以無視窗繼續擷取。
- 無視窗瀏覽器的 User-Agent 帶有 `HeadlessChrome`，工具不偽裝。網站若拒絕無視窗瀏覽器，改用 `--headed`。
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

看得到已登入元素、且沒有未登入元素，才算已登入。15 秒內判斷不出來視為未登入。

## 擷取

每個來源一個 adapter（`libs/sec_revenue/capture/sites/`），負責開到目標頁、切到正確的檢視、讀出表格文字與期別。外殼負責截圖、產生證據檔、合併與驗證。

- adapter 每產生一張表，外殼就建立一次擷取。一個畫面只顯示一期的來源（富途）一期一次擷取。
- capture_id 取到秒；同一來源的下一次擷取落在同一秒時，工具等到下一秒。寫入時若該來源已有相同的 capture_id，拒絕寫入。
- 一次只處理一家公司，兩檔之間間隔 `--pause` 秒（預設 10 秒）。
- 截圖後視窗恢復成 1400×900。
- 一個 ticker 的所有表（富途一期一張）都截圖完成後，才一次合併寫入；中途任何一期失敗就整檔不寫，不留下部分期別。
- 一檔失敗不影響其他檔。結束時列出成功與失敗清單（失敗附原因，例如未登入、頁面不存在、找不到表格），並執行 `validate_universe()`；全部成功且驗證通過時回傳 0。

### Stock Analysis

目標頁為 `https://stockanalysis.com/stocks/<ticker>/metrics/revenue-by-segment/`，ticker 轉小寫，類別股以 `.` 分隔（`BRK-B` → `brk.b`）。

- 頁面預設顯示 TTM。擷取前切到 Quarterly 與 Latest（數值，而非成長率或占比），並確認圖表標題為 `(Quarterly)`。
- 表格內容連續兩次讀取相同才採用，避免讀到切換中的數值。
- 表頭第一欄為 `Date`，其餘為分類；每列一季，`label` 為頁面上的日期原文（例如 `Sep 30, 2026`），`period_end` 為該日期，`kind` 為 `Q`。
- 頁面上的日期是 Stock Analysis 顯示的日期，不一定是公司的期末日：財年季度不在曆年季底的公司（例如 HD、ORCL、COST、DIS、PG），日期對齊到曆年季底。`period_end` 照頁面保存，與 SEC 期間的對齊由比對工具（#46）處理。
- 儲存格為 `-` 等空值時不寫入。數值帶 `B`、`M` 等單位，不設 `display_unit`。
- 擷取表格上顯示的全部期別。未登入時只顯示最近 20 期。
- 沒有 segment 頁的公司（例如 BRK-B）回應 404，列為失敗。

### 富途

目標頁為 `https://www.futunn.com/hk/stock/<TICKER>-US/financials-revenue`，類別股以 `.` 分隔（`BRK-B` → `BRK.B-US`）。只取「業務」區塊，不取「地區」。

- 業務區一次只顯示一期，由期間選單切換。選單混有季度（`2026/Q3`）與年度（`2026/FY`），標籤為富途顯示的財年標籤。以選單中最新的一季為準，擷取往回 `--periods` 季範圍內選單有的季度，每期一次擷取。選單中的季度不一定連續（例如缺 2025/Q3，或只有每年 Q1、Q2），以時間範圍而非個數取，避免回推到很久以前。
- 切換後期間標籤先更新、數值較晚才更新，「暫無內容」也可能只是還在載入。開頁時先等列表非空且穩定。切換時記下點選前實際顯示的列表，等到標籤相符、列表與點選前不同、且連續兩次讀取相同，才採用；兩期數值完全相同時無法確認已刷新，明確失敗而不猜。頁面預設已選取目標期間時不切換，只等數值穩定。
- 連續切換時偶爾整區變成「暫無內容」且期間選單消失，但同一期重新載入後有資料。因此每次切換前停頓 2 秒；失敗時重新載入頁面再選同一期，最多重試 2 次。
- 表頭須為「名稱、營收、比例」，幣別須為「貨幣單位:美元」。`label` 為期間標籤，`kind` 為 `Q`；頁面沒有期末日，不寫 `period_end`。數值帶 `億`、`萬` 單位；`--` 為空值。
- 截圖涵蓋整個業務區塊：期間選單上目前選取的期間、幣別、圓餅圖與列表。`table.txt` 第一行與 `table.html` 的 `<caption>` 寫入「業務 <期間> <幣別>」，讓文字證據也能對應到哪一期。
- 部分 Q4 是富途以年度減前三季推算、且數值有誤，例如 UPS 2024/Q4 單一分部 910.7億、其餘分部為負；HD 2024/Q4、DIS 2023/Q4 出現負的分部；XOM 每個 Q4 合計約為其他季的 2.5 倍。數值照頁面原樣保存，差異說明由比對工具（#46）處理。
- 沒有財務頁或業務區塊的公司（例如 PLD）列為失敗。

### TradingView

目標頁為 `https://www.tradingview.com/symbols/<交易所>-<代號>/financials-segments/`，類別股以 `.` 分隔（`BRK-B` → `BRK.B`）。只取「By source」表，不取「By country」。

- URL 須有交易所前綴，但部分代號不帶前綴也會導向正確頁面。依序嘗試不帶前綴、`NASDAQ-`、`NYSE-`、`AMEX-`；只採用回應 200、實際 URL 的交易所為 NASDAQ、NYSE 或 AMEX、且頁面標題含相同 `<交易所>:<代號>` 的頁面。不帶前綴導向其他交易所時不採用，繼續嘗試明確的前綴。不需要 ticker 到交易所的對照表。
- 只取「By source」區塊；區塊內若同時出現「By country」標題則明確失敗。
- 表格欄為 TradingView 顯示的年度標籤（例如 `2026`），每欄一期，`kind` 為 `FY`，不寫 `period_end`。年度標籤不一定是公司財年：AAPL、MSFT 等為財年結束的年份，NVDA、ORCL、WMT、HD 等為財年結束年份減一。標籤照頁面保存，與 SEC 財年的對齊由比對工具（#46）處理。
- 表格可水平捲動，預設顯示最近的年度（1400 寬約 10 年）。只取完整顯示的年度欄（被固定首欄遮住或超出右緣的欄不取），讓每個數值都在截圖中。
- 數值原文含 bidi 控制字元與窄空白（例如 `\u202a123.00\u202fM\u202c`），寫入 `display` 前移除，成為 `123.00M`；`—` 為空值，整列皆空的舊分類不寫入。`table.txt` 與 `table.html` 保存頁面文字原樣，仍含這些字元。幣別須為 `Currency: USD`。
- 截圖涵蓋整個 By source 區塊：標題、圖表與表格。

## 證據

三個證據檔都只涵蓋表格區塊：

- `table.png`：截圖前隱藏表格以外的 fixed／sticky 元素（例如帶有帳號頭像的頁首），並取消祖先元素的裁切；截取表格範圍四周各留 16 像素，表格右緣超出視窗時暫時加寬視窗。截圖後復原這些樣式，不影響同一頁後續的操作。截圖轉成 256 色調色盤 PNG 並最佳化壓縮，表格顏色少，不 dither 可保持文字清楚。單檔超過 500 KB 時在輸出中警告。
- `table.html`：表格結構與文字，不是網頁原始 bytes。由 adapter 依網站結構選擇產生方式：
  - `clean`：保留原始片段中與表格有關的標籤（`table`、`tr`、`td`、`div`、`span` 等）與文字，刪除所有屬性（只留數字的 `colspan`、`rowspan`）；其他標籤只留文字；script、style、svg、圖片、按鈕、表單等連同內容刪除；註解刪除。適用以 `<table>` 呈現的表格。
  - `rebuild`：以表格文字重建只含 `<table><caption><tr><th><td>` 的表格。適用以 div 排版的表格。

  | 來源 | 做法 | 頁面結構 |
  |---|---|---|
  | `stockanalysis` | `clean` | 標準 `<table>`，屬性只有 `class` |
  | `futu` | `rebuild` | div 排版的列表，含顏色圖示與 `title` 屬性 |
  | `tradingview` | `rebuild` | 多層 div 排版，數值含 bidi 控制字元 |

  帳號名稱、追蹤參數與外部資源都在屬性或被刪除的標籤中，兩種方式都不需要逐項列舉。驗證程式不檢查這些內容，由擷取工具負責。
- `table.txt`：表格文字，一列一行，欄位以 tab 分隔。adapter 提供 caption 時（富途）為第一行，其後為表頭。

## 合併與寫入

依 [保存模型](universe.md#保存模型) 累積合併：

- 新擷取涵蓋的期別以新值取代；同一來源內 `label` 相同或 `(kind, period_end)` 相同即視為同一期。未涵蓋的期別保留原值與原擷取。
- 不再被任何期別引用的擷取，連同證據目錄一併刪除；舊證據由 Git 歷史保存。
- `display` 以 `parse_display()` 換算美元，四捨五入為整數存入 `usd`。
- 期別依期末日新到舊排列，同日 FY 在 Q 前；沒有期末日的期別（富途 `2026/Q3`、TradingView `2026`）依標籤由大到小排在後面。

同一 ticker、同一來源一次執行的所有擷取一起寫入：先在 ticker 目錄旁以 `.` 開頭的暫存目錄完成，通過 `validate_reference()` 後才整個換上；任何錯誤都不改動既有的對照目錄。

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
| `tests/capture/test_capture.py` | 離線測試（不開瀏覽器、不連網） |
