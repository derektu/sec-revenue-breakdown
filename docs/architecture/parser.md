# Parser 與正式輸出

本文件定義 SEC 營收 parser 的架構：每家公司的規格怎麼寫、引擎怎麼從 SEC 申報算出每季的 by segment 營收、怎麼自我檢核，以及正式輸出與證據的格式。

parser 的輸出就是正式資料，連同證據進 Git。新的期別不需要對照資料：結構檢核通過就上線；跨期異常不擋上線，寫成標註（`annotations`），PM 看新財報時一併看到。對照資料只用在公司初次上線時選定觀點（#46），以及客戶反映問題時判斷原因。

## 名詞

| 名詞 | 意義 |
|---|---|
| 觀點（view） | 一種產品或業務別的營收拆分。同一家公司可能有多個面向或多層細項，例如業務群與其下的產品線；每家公司採用一個觀點。地區拆分不是觀點：AAPL 的營運分部是 Americas、Europe 等地區，不採用，採用的是產品別（iPhone、Mac…） |
| 分類（category） | 觀點中的一項，例如 iPhone |
| 期別 | 一個財務季度，以期末日（SEC context 的 endDate）識別，例如 `2025-09-27`。財年與季次取自該期申報的 `dei:DocumentFiscalYearFocus`、`dei:DocumentFiscalPeriodFocus` |
| 運算元 | 一個 SEC 數字：inline XBRL fact（`xbrl_fact`），或沒有 XBRL 標記的 HTML 表格儲存格（`table_cell`） |
| 運算式 | 分類數值由運算元加權相加而成，例如 Q4 = 年度 − 九個月累計 |

## 新增一家公司

1. **確認對照資料**：擷取該公司的對照資料（Stock Analysis、富途、TradingView）。
2. **選定觀點**：比較各來源的分類。
   - 各來源一致：直接採用該觀點。
   - 各來源不一致（面向不同、細項層級不同、分類名稱或範圍不同）：開發者對照 SEC 原文能重現哪些分類，提出建議與理由，由人判斷後才開始寫 parser。
3. **寫規格與 `parser.md`**，以已下載的 SEC 原文跑 parse。
4. **與對照資料逐期比對**（#46），差異逐筆說明；通過後由人核准，`tickers.csv` 標為 `ok`。

## 目錄

```
libs/sec_revenue/revenue/              引擎
  spec.py          規格的資料結構（CompanySpec、Category、fact、table_cell、define、effective）
  xbrl.py          讀 inline XBRL：contexts、units、dei、fact 與所在表格
  filings.py       選主申報、讀原文並核對 sha256
  compose.py       組合數值與結構檢核
  review.py        跨期檢核與重編偵測
  engine.py        證據、寫入、status.json、--check 比對

libs/sec_revenue/companies/<首字母>/<目錄>/
  spec.py          公司規格（宣告式），定義 SPEC
  hooks.py         選用：規格無法表達的特例
  parser.md        觀點、分類對應、tag、適用期間、推算邏輯、已知例外、驗證結果

data/revenue/<首字母>/<TICKER>/
  status.json      每一期的處理結果（含沒有輸出的期別與原因）
  <period_end>/
    revenue.json   正式數字、運算式、運算元、檢核結果、標註
    evidence/      每張用到的 SEC 表格：<accession>-<sha12>-t<n>.html 與 .png
```

- 公司目錄名是 ticker 小寫，非英數字元改為底線，例如 `a/aapl`、`b/brk_b`；ticker 本身以 `SPEC.ticker` 為準。
- `companies/` 與 `data/revenue/` 都進 Git。SEC 原文在共用資料目錄（`SEC_DATA_DIR`），不進 Git；正式輸出記錄每份原文的 URL 與 sha256，可以重新下載核對。
- 下載（`download.py`）與證據元件（`evidence.py` 的找表、核對、清理、截圖）沿用既有程式。

## 公司規格

規格只描述「這家公司的數字在 SEC 的哪裡」，不寫流程。以 AAPL 為例：

```python
from sec_revenue.revenue.spec import Category, CompanySpec, fact

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
PRODUCT = "srt:ProductOrServiceAxis"

SPEC = CompanySpec(
    ticker="AAPL",
    view="product",
    categories=(
        Category("iPhone", fact(REVENUE, {PRODUCT: "aapl:IPhoneMember"})),
        Category("Mac", fact(REVENUE, {PRODUCT: "aapl:MacMember"})),
        Category("iPad", fact(REVENUE, {PRODUCT: "aapl:IPadMember"})),
        Category("Wearables, Home and Accessories",
                 fact(REVENUE, {PRODUCT: "aapl:WearablesHomeandAccessoriesMember"})),
        Category("Services", fact(REVENUE, {PRODUCT: "us-gaap:ServiceMember"})),
    ),
    total=Category("Total net sales", fact(REVENUE)),
)
```

- **觀點**：`view` 是 `product`（產品別）或 `business_segment`（業務分部）。
- **分類**：`Category(名稱, 定義...)`。每個定義指定 concept 與完整的 dimensions，dimensions 用帶前綴的 QName（軸與成員都帶前綴）。比對是精確的：fact 的 dimensions 必須與規格完全相同，多一個或少一個都不算。`fact(concept)` 不帶 dimensions，代表合計。
- **總營收**：`total` 是用於加總檢核的項目。分類加總與總營收之間若有合法差額（例如公司間抵銷、未分配項目），以 `reconciling=(Category(...),)` 宣告，參與加總但不輸出成分類。
- **權重**：`define(selector, weight=-1)` 讓運算元以負號參與，例如抵銷項。`weight` 只能以關鍵字傳入，值只能是 1 或 -1。
- **適用期間**：公司改 tag、改分類時，以 `define(selector, effective(start, end))` 宣告每個定義適用的申報期別（期末日，含首尾，`None` 不設限）；同一期別只能有一個定義生效。定義依運算元來源申報的期末日選取：Q1–Q3 與 Q4 的年度運算元是本期，Q4 的九個月運算元是 Q3 的期末日。公司在 10-K 才改名、同財年的 Q3 10-Q 仍用舊名時（例如 NVDA 的分部成員），Q4 的兩個運算元各用各的定義，`effective` 的界線寫在最後一份舊申報與第一份新申報的期末日之間。Q4 跨定義時該期寫標註（見跨期檢核），因為改名時若同時改了範圍，年度減九個月會錯，而加總檢核擋不住。分類的新增、合併或拆分，在 `parser.md` 記錄，並由跨期檢核在當期寫標註。
- **表格運算元**：沒有 XBRL 標記的數字（例如 8-K 新聞稿），以 `table_cell(文件, 表頭文字, 列標籤, 欄期間)` 宣告，表格定位用表頭文字與列標籤，不用表格編號。引擎目前不支援，規格用到時該期失敗並說明原因。
- **hook**：規格無法表達時才用，例如需要從兩份申報組合。每個 hook 都要在 `parser.md` 寫明理由，並有對應的測試。

載入規格時檢查以下規則，違反時直接報錯，不會進入解析：

| 規則 | 錯誤 |
|---|---|
| `view` 是允許的值 | `view 必須是 product、business_segment 之一` |
| 分類名稱不重複，總營收名稱不與分類重名 | `分類名稱重複`、`與分類重名` |
| 不使用地區軸 `srt:StatementGeographicalAxis` | `使用地區軸` |
| 適用期間重疊的兩個定義不使用同一個運算元 | `在重疊的期間使用同一個運算元` |
| `define` 的 weight 以關鍵字傳入且為 ±1 | `第二個參數必須是 effective(...)`、`只能是 1 或 -1` |
| 每家公司都有 `parser.md` | `缺少 parser.md` |
| 使用 `us-gaap:StatementBusinessSegmentsAxis` 時，`parser.md` 提到這個軸並說明成員是業務別 | `必須寫明這個軸的成員是業務別而不是地區` |

業務分部軸常被公司用於地區分部（例如 AAPL 的 Americas、Europe），所以允許使用但必須在 `parser.md` 說明。

## 引擎流程

一家公司、一個期別：

1. **選申報**：該期的主申報是 reportDate 等於該期的第一份 10-Q 或 10-K。10-K/A、10-Q/A 只要含有該期任一營收 fact（規格宣告的 concept、期末日等於該期）就取代原申報，有多份時取最晚的一份；修正申報缺少某個拆分時該期失敗，不回頭混用原申報的數字。輸出記錄被取代的申報，並把修正前後不同的運算元記入 `restatements`。8-K 只在規格宣告了表格運算元時使用。主文件必須是 inline XBRL，讀取時核對 sha256。
2. **讀 facts**：解析主申報的 inline XBRL，建立 fact 索引：concept、dimensions、期間、單位、decimals、sign、scale、format 與所在表格。數值依 format（`num-dot-decimal`、`fixed-zero`、`zerodash`）、scale 與 sign 算成整數美元；正負號只由 `sign` 屬性決定，顯示文字帶負號或括號、或數值不是有限數時，這個 fact 視為無法解析。證據核對使用同一套規則（`evidence.ix_number`）。
   - 規格與 fact 在同一份文件內以 namespace URI 比對：前綴依文件宣告的 `xmlns:*` 解析，所以文件用別的前綴指向同一個 namespace 也能對上；規格的前綴在文件中沒有宣告時該期失敗。重編比對以新申報期別生效的規格定義，在新申報內同樣以 namespace URI 查找同期間的 fact，不沿用已上線運算元的 QName：公司與 us-gaap 的 namespace URI 每年都帶不同日期，公司也可能改成員名稱。修正申報與原申報之間（同一期、同一定義）比對帶前綴的 QName。
3. **財年與季別**：主申報必須宣告 `DocumentFiscalYearFocus` 與 `DocumentFiscalPeriodFocus`（Q1、Q2、Q3、FY）；Q1–Q3 必須是 10-Q，FY 必須是 10-K。
4. **期間分類**：依 context 天數（含首尾）判斷單季（84–98 天）、六個月（175–189 天）、九個月（266–280 天）、年度（357–378 天）。
5. **組合數值**：
   - Q1–Q3：主申報中期末日為該期的單季 fact。
   - Q4：年度（10-K）減九個月累計。九個月取自年度期末前一季的 10-Q，它必須宣告同財年 Q3；九個月的起日必須等於年度起日，九個月迄日的隔天到年度期末必須是一個單季。
   - 同一個值出現多次（同 concept、dimensions、期間）時，以精度最高（decimals 最大）的 fact 為準；其他重複值只需在自己的精度內與它一致。同精度時選所在表格含最多其他項目的 fact，再平手取文件順序第一個，其餘記在 `duplicates`。這讓同一期的運算元盡量落在同一張表，證據截圖較少。
6. **結構檢核**：見下節。不通過就不寫入正式輸出，只在 `status.json` 記錄原因。
7. **證據**：每個運算元找到所在的 SEC 表格，核對 fact 與運算元一致，存清理過的 HTML 片段與標示儲存格的截圖（1 倍解析度）。表格 HTML 與已提交的相同、PNG hash 與截圖倍率都相符時沿用舊 PNG，不重新截圖。表格運算元的證據就是該儲存格所在的表格。
8. **跨期檢核**：與已上線的較早期別比較，異常時在 `revenue.json` 的 `annotations` 寫標註。
9. **已上線保護**：該期已有上線輸出時，一般 parse 不改動它。
   - 重算結果與已上線輸出完全相同：不寫入。
   - 數值或依據（分類、總營收、運算元、選用的申報、財年季別、觀點）不同：不寫入，`status.json` 記錄 `differs_from_published`（差異的分類、舊值、新值，原因是修正申報、選用的申報不同或規則與原文變更），並寫標註。由人確認後以 `--republish TICKER PERIOD` 覆寫，覆寫時 `revenue.json` 的 `republished` 記錄原值與原因。
   - 只有中繼資料不同（檢核紀錄、運算元的證據 hash）：不寫入，`status.json` 記錄 `stale_fields`。
   - `parser`（引擎與規格的 hash）記錄的是產生該輸出的版本，不列入比較：引擎或規格改動而內容相同時，視為相同。代價是已上線 `revenue.json` 的 `parser` 停在上線當時的版本，不代表目前的引擎；目前引擎的版本看 `status.json` 的 `parser`，兩者不同不代表輸出過時。
   - 跨期檢核每次都以目前已上線的資料重算。之後補上更早的期別時，已上線的期別才有去年同季可比；重算出已上線輸出沒有的標註時，記在 `status.json` 該期的 `new_annotations`。已上線的 `revenue.json` 仍保留上線當時的檢核結果與標註。
10. **寫入**：先寫暫存目錄，全部完成才換上 `data/revenue/.../<period_end>/`；換上失敗時還原舊輸出。開始處理前清理中斷寫入留下的目錄：`.staging-*` 刪除，`.retired-<期別>-*` 在該期目錄不存在時還原、否則刪除。只有以期末日命名的目錄算已上線輸出。

任何一期發生例外（包括非預期的程式錯誤）都記為該期失敗，附例外類型與訊息，繼續處理下一期；`status.json` 一定會寫入。

## 自我檢核

結構檢核（任一不通過，該期不輸出；已上線的該期輸出保留不動）。錯誤訊息以 `[檢核名稱]` 開頭：

| 檢核 | 內容 |
|---|---|
| 選申報 | 該期有 10-Q 或 10-K |
| 原文存在 | 主文件在共用資料目錄中，sha256 與申報包紀錄一致 |
| 財年與季別 | 申報宣告財年與季別，且與表單種類相符 |
| 定義唯一 | 每個分類在該期剛好有一個生效的定義；定義不是尚未支援的 `table_cell` |
| fact 存在且唯一 | 規格的前綴在文件中有宣告；每個運算元在原文中找得到、只有一個起日、數值可解析；重複出現時在各自精度內一致 |
| 單位與精度 | 單位是 USD；`decimals` 有記錄且不低於 `-6`（百萬位），誤差上限由精度推得（`-6` 為 ±50 萬）。精度更粗的數字誤差過大，不上線 |
| 加總 | 分類（含 `reconciling`）加總等於總營收，差距不超過所有運算元精度誤差的總和 |
| Q4 期間 | 年度期末前一季剛好有一份 10-Q，且宣告同財年 Q3；年度與九個月運算元首尾相接 |
| 證據完整 | 每個運算元都在 HTML 表格內；原文節點是 `ix:nonFraction`，name、contextref、scale、顯示文字與數值等於運算元；瀏覽器截到的表格與原文表格文字相同 |

跨期檢核（不擋上線，異常寫成標註）：

| 檢核 | 內容 | 寫標註 |
|---|---|---|
| 期別連續 | 上一個已上線期別與本期相隔一個單季，且其 dei 財年季別是本期的前一季 | 不符時 |
| 分類集合 | 與上一個已上線期別相同 | 不同時 |
| 去年同季 | 以 dei 財年季別配對去年同季，且在已上線輸出中唯一、兩期期末日相隔一年 | 不唯一、相隔不是一年、去年同季沒有某分類，或已有一年以上的歷史卻缺去年同季 |
| 占比變動 | 任一分類占總營收的比例，與去年同季相差超過 5 個百分點；任一期總營收為 0 時無法計算 | 是 |
| YoY | 任一分類與去年同季相比變動超過 ±50%，或去年同季為 0 | 是 |
| QoQ | 與上一個已上線期別相比的變動 | 只記錄 |
| 比較期 | 本期主申報涵蓋的已上線期間（申報中有該段期間的總營收），每個運算元以本期生效的定義找同期間的 fact，逐一記入 `checks.comparatives`：`consistent`、`restated`、`unparseable` 或 `not_found` | `restated`、`unparseable`、`not_found` |
| 比較期總營收 | 去年同季的總營收必須在本期主申報中比得到（10-Q 比單季、10-K 比年度）；沒有去年同季時不要求 | 比不到時 |
| 重編 | `checks.comparatives` 中 `restated`、`unparseable` 的項目，以及主申報是修正申報時修正前後不同的運算元，記入 `checks.restatements` | 是 |
| Q4 跨定義 | Q4 的年度與九個月運算元使用不同定義；`checks.q4_definitions` 記錄兩個定義，以及輔助證據：較晚的申報以年度定義標示的同一段九個月 fact，與九個月運算元是否在精度內一致 | 是，原因附輔助證據結果 |

- 占比與成長率都和去年同季比較：季節性強的公司（例如 AAPL 的 12 月季 iPhone 營收較前一季多七成以上）與上一季比較時，每年都會在相同季度觸發，無法分辨結構變化。完全沒有一年以上的歷史時只記錄。
- 門檻全部公司共用（占比 5 個百分點、YoY ±50%），以未捨入的值比較，輸出的變動值才捨入。高成長或季節性強的公司會固定出現標註，標註只供 PM 閱讀，不擋上線。
- 重編時本期照常上線並記錄 `restatements`（`kind` 為 `comparative` 或 `amendment`）；被重編的舊期 `revenue.json` 不改，`status.json` 在舊期記錄 `restated_by`。

## 正式輸出

`revenue.json`（AAPL 2025-09-27 節錄）：

```json
{
  "schema_version": 1,
  "ticker": "AAPL",
  "view": "product",
  "period_end": "2025-09-27",
  "fiscal_year": 2025,
  "fiscal_quarter": 4,
  "unit": "USD",
  "filings": {
    "primary": { "accession": "0000320193-25-000079", "form": "10-K", "report_date": "2025-09-27", "filing_date": "2025-10-31" },
    "nine_months": { "accession": "0000320193-25-000073", "form": "10-Q", "report_date": "2025-06-28", "filing_date": "2025-08-01" }
  },
  "categories": {
    "Mac": {
      "value": 8726000000,
      "expression": [ { "weight": 1, "operand": "op3" }, { "weight": -1, "operand": "op4" } ]
    }
  },
  "total": { "value": 102466000000, "expression": [ { "weight": 1, "operand": "op11" }, { "weight": -1, "operand": "op12" } ] },
  "operands": {
    "op3": {
      "kind": "xbrl_fact",
      "role": "annual",
      "accession": "0000320193-25-000079",
      "form": "10-K",
      "filing_date": "2025-10-31",
      "document": { "name": "aapl-20250927.htm", "sha256": "...", "url": "...", "ixviewer_url": "..." },
      "fact_id": "f-380",
      "duplicates": [],
      "context_id": "c-48",
      "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
      "dimensions": { "srt:ProductOrServiceAxis": "aapl:MacMember" },
      "period": { "start": "2024-09-29", "end": "2025-09-27" },
      "value": 33708000000,
      "raw": "33,708",
      "scale": "6",
      "decimals": "-6",
      "sign": null,
      "evidence": { "table": "0000320193-25-000079-dceb82ec4e10-t27", "html_sha256": "...", "png_sha256": "..." }
    }
  },
  "checks": {
    "structural": [ { "check": "定義唯一", "result": "pass" }, "..." ],
    "sum": { "categories": 102466000000, "total": 102466000000, "difference": 0, "tolerance": "6000000" },
    "cross_period": [ { "check": "去年同季", "category": "Mac", "flagged": false, "note": "沒有去年同季可比" }, "..." ],
    "restatements": []
  },
  "annotations": [],
  "parser": { "spec_sha256": "...", "engine_sha256": "..." }
}
```

- `role`：`quarter`、`annual` 或 `nine_months`。
- 規格宣告 `reconciling` 時另有同格式的 `reconciling` 欄位。
- 主申報是修正申報時，`filings.primary.replaces` 記錄被取代的原申報。
- 證據圖上的編號就是運算元編號（`op3` 標成 3）；`evidence.png_scale` 是截圖倍率。
- `annotations` 每筆有 `check`（檢核名稱）、`message`（說明）與 `detail`（相關數值，例如變動值、基準期別、比對結果）。
- `checks.comparatives` 是比較期比對清單（期別、分類、運算元、期間、結果）；`checks.q4_definitions` 只在 Q4 跨定義時出現。
- 以 `--republish` 覆寫過的期別有 `republished` 清單，每筆記錄原因與覆寫前的申報、分類數值、總營收與 `parser`。

`status.json` 列出每個處理過的期別：

| 欄位 | 內容 |
|---|---|
| `status` | `published` 或 `failed` |
| `check`、`reason` | 失敗時：不通過的檢核與原因 |
| `published_output_kept` | 失敗時：該期是否仍有先前上線的輸出 |
| `annotations` | 該期 `revenue.json` 標註的摘要（`check`、`message`） |
| `new_annotations` | 已上線期別重算時出現、已上線輸出沒有的標註，以及與已上線不同的提示 |
| `differs_from_published` | 重算結果與已上線輸出的數值或依據不同：原因、差異的分類與新舊值、不同的欄位 |
| `stale_fields` | 重算結果與已上線輸出只有中繼資料不同時，不同的欄位 |
| `restated_by` | 哪些較新的期別記錄了此期的重編 |

## 指令

```bash
npm run parse -- --tickers AAPL                     # 全部已下載的期別：解析、檢核、證據、寫入 data/revenue/
npm run parse -- --tickers AAPL --start 2025-01-01  # 只處理期末日在範圍內的期別
npm run parse -- --tickers AAPL --check             # 重跑並與已提交的輸出比對，不寫入
npm run parse -- --tickers AAPL --republish AAPL 2025-09-27   # 由人確認後覆寫已上線的期別
```

- `npm run parse` 即 `scripts/sec_pipeline.py parse`；省略 `--tickers` 或加 `--all` 處理全部有規格的公司。
- parse 只讀共用資料目錄的 SEC 原文，不連網；缺原文時提示先執行 download。
- `--check` 不啟動 Chromium。它在已提交輸出的副本上照一般 parse 執行（同樣受已上線保護），再與已提交的輸出比對；一般 parse 不會改動任何檔案、也不會改變 `status.json` 時才算一致：
  - `revenue.json` 逐欄比對（`parser` 欄位與 PNG hash、倍率除外）；
  - `status.json` 中這些期別的紀錄逐欄比對，包括失敗原因、標註、`differs_from_published`、`stale_fields`、`restated_by`（`published_output_kept` 除外）；
  - 證據 HTML 比對 bytes，證據目錄中沒有被 `revenue.json` 引用的檔案列為差異；
  - 已提交的 PNG 核對檔案 hash 與紀錄一致。

  省略期別時比對 `status.json` 列出的期別。有差異時回傳碼為 2。`--check` 不能與 `--republish` 同時使用。
- `--republish TICKER PERIOD` 可重複指定；ticker 與期別必須在這次處理的範圍內。
- 回傳碼：`0` 全部期別上線（含有標註的期別）；`2` 有期別失敗或 `--check` 有差異；`1` 輸入錯誤。

## 測試

- 引擎：`tests/lib/test_revenue_parser.py` 以合成的 inline XBRL 申報測試每個流程步驟與每項檢核，不連網、不啟動 Chromium。
- 公司：`data/revenue/` 中已提交的輸出就是回歸基準。`--check` 重跑 parser，與已提交的輸出逐欄比對；改某家公司的規格只重跑該家，改引擎則重跑所有上線公司（#49）。

## 與既有程式的關係

`issuers/` 的舊 parser、`workflow.py` 的萃取流程、`data/outputs/` 的輸出，以及它們的測試，都是先前的實驗。新程式依實際看到的 SEC 原文寫成，舊規則只作參考。新流程涵蓋全部 30 家後，舊程式與其測試刪除。
