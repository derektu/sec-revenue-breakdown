# Parser 與正式輸出

本文件定義 SEC 營收 parser 的架構：每家公司的規格怎麼寫、引擎怎麼從 SEC 申報算出每季與每年的 by segment 營收、怎麼自我檢核，以及正式輸出與證據的格式。

parser 的輸出就是正式資料，連同證據進 Git。新的期別不需要對照資料：結構檢核通過就上線。對照資料只用在公司初次上線時選定觀點（#46），以及客戶反映問題時判斷原因。

parser 的範圍：

- **只公布財報上寫的項目與數字**：不解讀財報內容、不追究差異原因、不自動修正。每一期照該期財報的項目與數字公布，項目與上一期不同也照列。
- **兩個序列**：季度（Q）的 Q1–Q3 取自 10-Q，Q4 由 10-K 年度減九個月累計推算；年度（FY）直接取 10-K 的全年數字。Q4 只在年度與 Q1–Q3 的分類相同、且年報沒有改分類口徑時推算，否則留空並記錄原因，不另做補救。
- **預設起始日**：所有公司共用一個預設起始日（`revenue/engine.py` 的 `DEFAULT_START`，目前是 2024-01-01，隨 Git 版本控制）。parse 沒有指定 `--start` 時，Q 與 FY 處理期末日不早於預設起始日的期別；要處理更早的期別時以 `--start` 指定，照常處理並發布。起日之前已下載的申報照常讀取，作為運算元（例如第一個 Q4 的九個月累計來自起日之前的 Q3 10-Q）與比較欄比對的來源，只是這次不處理成期別。已上線的較早期別是正常的已上線資料：保留 `status.json` 紀錄、照常作為比較欄比對的對象、照常受已上線保護。
- **Point in time**：一期的數字取自該期最早的原申報，處理時只使用申報日當天或更早公開的申報。例如處理 Q2 時，看得到今年 Q1、去年 FY 與去年各季，看不到之後的申報。之後的申報（包括修正申報）不改已上線的數字。
- **差異標記**：較晚的申報（包括修正申報）列出的較早期間數字，例如去年同季、去年九個月累計、去年全年，或修正申報的本期數字，與已上線的同一期不同時，在舊期別記錄標記；已上線數字不改，由 PM 視需要請人查明。

## 名詞

| 名詞 | 意義 |
|---|---|
| 觀點（view） | 一種產品或業務別的營收拆分。同一家公司可能有多個面向或多層細項，例如業務群與其下的產品線；每家公司採用一個觀點。地區拆分不是觀點：AAPL 的營運分部是 Americas、Europe 等地區，不採用，採用的是產品別（iPhone、Mac…） |
| 分類（category） | 觀點中的一項，例如 iPhone |
| 序列 | `Q`（季度：Q1–Q4）或 `FY`（年度） |
| 期別 | 一個序列中的一期，以期末日（SEC context 的 endDate）識別，例如 `2025-09-27`。10-K 的期末日同時有 FY 與 Q4 兩期。財年與季次取自該期申報的 `dei:DocumentFiscalYearFocus`、`dei:DocumentFiscalPeriodFocus` |
| 運算元 | 一個 SEC 數字：inline XBRL fact（`xbrl_fact`），或沒有 XBRL 標記的 HTML 表格儲存格（`table_cell`） |
| 運算式 | 分類數值由運算元加權相加而成，例如 Q4 = 年度 − 九個月累計 |
| 比較欄 | 申報中與本期並列的較早期間數字，例如 10-Q 的去年同季、10-K 的去年全年 |

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
  spec.py          規格的資料結構（CompanySpec、Category、fact、one_of、table_cell、sum_of、minus、define、effective）
  xbrl.py          讀 inline XBRL：contexts、units、dei、fact 與所在表格
  filings.py       選主申報、讀原文並核對 sha256
  compose.py       組合數值與結構檢核
  review.py        比較欄比對
  evidence.py      證據元件：找表、核對 fact、抽出表格 HTML、截圖
  engine.py        證據、寫入、status.json、--check 比對

libs/sec_revenue/companies/<首字母>/<目錄>/
  spec.py          公司規格（宣告式），定義 SPEC
  hooks.py         選用：規格無法表達的特例
  parser.md        觀點、分類對應、tag、適用期間、推算邏輯、已知例外、驗證結果

data/revenue/<首字母>/<TICKER>/
  status.json      兩個序列每一期的處理結果（含沒有輸出的期別與原因）與差異標記
  Q/<period_end>/  季度序列（Q1–Q4）
    revenue.json   正式數字、運算式、運算元、檢核結果
    evidence/      每張用到的 SEC 表格：<accession>-<sha12>-t<n>.html 與 .png
  FY/<period_end>/ 年度序列，期末日與同財年的 Q4 相同
    revenue.json
    evidence/
```

- 公司目錄名是 ticker 小寫，非英數字元改為底線，例如 `a/aapl`、`b/brk_b`；ticker 本身以 `SPEC.ticker` 為準。
- `companies/` 與 `data/revenue/` 都進 Git。SEC 原文在共用資料目錄（`SEC_DATA_DIR`），不進 Git；正式輸出記錄每份原文的 URL 與 sha256，可以重新下載核對。
- SEC 原文由 `download/` 下載成申報包（見 [download.md](download.md)），parser 只讀申報包。`engine_sha256` 是 `revenue/*.py` 的 hash，證據元件在其中。

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
- **多種寫法**：同一個運算元在不同申報中用不同的 concept、成員或 dimensions 組合時（例如 AMZN 10-K 用 `us-gaap:AdvertisingMember`、10-Q 用 `amzn:AdvertisingServicesMember`；UNH 10-K 的 `unh:OptumhealthMember` 與 10-Q 的 `unh:OptumHealthMember` 只差大小寫；HD 部分申報多一個 `srt:ConsolidationItemsAxis`；MCD 的 10-Q 之間來回換 concept），以 `one_of(fact(...), fact(...), ...)` 明列每一種寫法。
  - 比對仍是精確的：不忽略大小寫、不比對相近名稱，規格沒列出的寫法找不到。
  - 每份申報分別找：找得到一種寫法時用它；一種都找不到時該期失敗。寫法的前綴在申報中沒有宣告時，該寫法視為不存在；前綴宣告衝突（同一前綴對應多個 namespace）時無法確定寫法對應哪些 fact，該期失敗，與單一 `fact(...)` 相同。找到多種寫法時，所有 fact 視為同一個數字的重複標記，照重複 fact 的規則處理：數值必須在各自精度內一致，選精度最高、所在表格含最多其他項目的那一個，其餘記在 `duplicates`；數值不一致時該期失敗。
  - Q4 的年度與九個月累計各自在自己的申報中找，可以是不同寫法。
  - `one_of` 可以放在任何寫單一 `fact(...)` 的地方，包括 `sum_of` 的加數與 `minus(...)`；不可用於地區軸的加數。
  - 寫法在財年中途固定切換時，也可以用 `effective` 分段宣告；寫法在申報之間來回切換時用 `one_of`。
- **多個 fact 相加**：申報沒有分類所需的小計時，以 `sum_of(加數...)` 列出每個加數，例如 LIN 的 Industrial Gases ＝ Americas＋EMEA＋APAC 三個分部。加數是 `fact(...)`，以 `minus(fact(...))` 減去；`define(sum_of(...), weight=-1)` 把整個加總取負號。`sum_of` 至少兩個加數、不可重複。
  - 每個加數各是一個運算元，有自己的表格證據。任一加數在該期找不到時該期失敗，不會少一個加數照樣輸出。同一份申報中各加數的起日必須相同。
  - 加總只用規格明列的加數，不會自動找出某個軸的全部成員。
  - 加總檢核的容許誤差是所有運算元精度誤差的總和，所以隨加數個數線性放大（Q4 每個加數有年度與九個月累計兩個運算元，再加倍）。例如三個 `-6` 精度的加數，在單季為容許誤差貢獻 ±150 萬，在 Q4 貢獻 ±300 萬。這是已知的取捨：誤差上限依精度推得，不另設較緊的門檻。
- **地區軸**：觀點只取產品或業務別，地區軸 `srt:StatementGeographicalAxis` 不能單獨成為運算元，只能以「該軸全部成員相加」出現：分部營收只以美國＋非美國揭露時（XOM、CVX、LLY），分類＝ `sum_of` 列出該軸每個成員。各加數都是權重 1 的 fact，concept 與地區軸以外的 dimensions 相同，只差地區成員。引擎在每份申報中檢查：同 concept、同其他 dimensions、同期間的 fact 中，地區成員不得有規格沒列出的，否則該期失敗；同 concept、同期間的 fact 有 dimensions 前綴無法解析時，無法確認成員完整，該期也失敗。成員以 namespace URI 比對，不看前綴。輸出只有加總後的分類，沒有地區分類。
  - 地區成員有階層時（例如 Non-US 與其下的 Europe、Asia 並列為同一軸的成員），規格只能選一層。只列父成員會被成員完整檢核擋下（子成員沒列出）；父子都列會重複計算，被加總檢核擋下。
- **適用期間**：公司改 tag、改分類時，以 `define(selector, effective(start, end))` 宣告每個定義適用的申報期別（期末日，含首尾，`None` 不設限）。
  - 同一期別最多一個定義生效。分類在某期沒有生效的定義，代表該期沒有這個項目，輸出不列出；總營收每期都必須有定義。規格漏寫適用期間時，該期少了一個分類，加總檢核對不上而失敗，不會無聲少一個分類：調節項是指定的 fact，不會吸收漏掉的分類。
  - 定義依運算元來源申報的期末日選取：Q1–Q3、FY 與 Q4 的年度運算元是本期，Q4 的九個月運算元是 Q3 的期末日。公司在 10-K 才改名、同財年的 Q3 10-Q 仍用舊名時（例如 NVDA 的分部成員），以同一個分類的兩個定義宣告，Q4 的兩個運算元各用各的定義，`effective` 的界線寫在最後一份舊申報與第一份新申報的期末日之間。
  - 分類的新增、合併或拆分，以不同名稱的分類宣告，並在 `parser.md` 記錄。分類集合在財年中改變時，該年的 Q4 不推算（見引擎流程）。
- **表格運算元**：沒有 XBRL 標記的數字（例如 8-K 新聞稿），以 `table_cell(文件, 表頭文字, 列標籤, 欄期間)` 宣告，表格定位用表頭文字與列標籤，不用表格編號。引擎目前不支援，規格用到時該期失敗並說明原因。
- **hook**：規格無法表達時才用，例如需要從兩份申報組合。每個 hook 都要在 `parser.md` 寫明理由，並有對應的測試。

載入規格時檢查以下規則，違反時直接報錯，不會進入解析：

| 規則 | 錯誤 |
|---|---|
| `view` 是允許的值 | `view 必須是 product、business_segment 之一` |
| 分類名稱不重複，總營收名稱不與分類重名 | `分類名稱重複`、`與分類重名` |
| 地區軸 `srt:StatementGeographicalAxis` 只以 `sum_of` 列出同一地區軸的成員相加，各加數權重 1、concept 與其他 dimensions 相同 | `地區軸只能以 sum_of`、`每個加數都必須是帶地區軸、權重 1 的 fact`、`concept 與地區軸以外的 dimensions 必須相同` |
| 適用期間重疊的定義（含同一個定義的各加數）不使用同一個運算元 | `在重疊的期間使用同一個運算元`、`加數重複` |
| `sum_of` 至少兩個加數 | `至少要有兩個加數` |
| `one_of` 至少兩種寫法、不重複、每種都是 `fact(...)`；寫法不得與其他運算元（含同一個 `sum_of` 的其他加數）在重疊期間重複；地區軸的加數不用 `one_of` | `至少要有兩種寫法`、`寫法重複`、`必須是 fact`、`在重疊的期間使用同一個運算元`、`加數重複`、`地區軸的加數不可使用 one_of` |
| `define` 的 weight 以關鍵字傳入且為 ±1；加數的 weight 為 ±1 | `第二個參數必須是 effective(...)`、`只能是 1 或 -1` |
| 每家公司都有 `parser.md` | `缺少 parser.md` |
| 使用 `us-gaap:StatementBusinessSegmentsAxis` 時，`parser.md` 提到這個軸並說明成員是業務別 | `必須寫明這個軸的成員是業務別而不是地區` |

業務分部軸常被公司用於地區分部（例如 AAPL 的 Americas、Europe），所以允許使用但必須在 `parser.md` 說明。

## 引擎流程

一家公司依期末日順序處理指定範圍內的每個期別。期末日的第一份原申報是 10-Q 時只有 Q 序列；是 10-K 時先處理 FY、再處理 Q4。每一期：

1. **選申報**：該期的主申報是 reportDate 等於該期、申報日最早的 10-Q 或 10-K。修正申報（10-K/A、10-Q/A）在原申報之後才公開，不取代主申報，只參與差異標記的比對。8-K 只在規格宣告了表格運算元時使用。主文件必須是 inline XBRL，讀取時核對 sha256。主申報的申報日是這一期的時點：之後的步驟只看申報日不晚於它的申報。
2. **讀 facts**：解析主申報的 inline XBRL，建立 fact 索引：concept、dimensions、期間、單位、decimals、sign、scale、format 與所在表格。數值依 format（`num-dot-decimal`、`fixed-zero`、`zerodash`）、scale 與 sign 算成整數美元；正負號只由 `sign` 屬性決定，顯示文字帶負號或括號、或數值不是有限數時，這個 fact 視為無法解析。證據核對使用同一套規則（`evidence.ix_number`）。
   - 規格與 fact 在同一份文件內以 namespace URI 比對：前綴依文件宣告的 `xmlns:*` 解析，所以文件用別的前綴指向同一個 namespace 也能對上；規格的前綴在文件中沒有宣告時該期失敗。比較欄比對以該申報期別生效的規格定義，在申報內同樣以 namespace URI 查找同期間的 fact，不沿用已上線運算元的 QName：公司與 us-gaap 的 namespace URI 每年都帶不同日期，公司也可能改成員名稱。
3. **財年與季別**：主申報必須宣告 `DocumentFiscalYearFocus` 與 `DocumentFiscalPeriodFocus`（Q1、Q2、Q3、FY）；Q1–Q3 必須是 10-Q，FY 必須是 10-K。
4. **期間分類**：依 context 天數（含首尾）判斷單季（84–98 天）、六個月（175–189 天）、九個月（266–280 天）、年度（357–378 天）。
5. **分類集合**：該期有生效定義的分類與調節項。
6. **組合數值**：
   - Q1–Q3：主申報中期末日為該期的單季 fact。
   - FY：主申報（10-K）中期末日為該期的年度 fact。
   - Q4：年度（10-K）減九個月累計。九個月取自年度期末前一季的原 10-Q（申報日不晚於 10-K），它必須宣告同財年 Q3；九個月的起日必須等於年度起日，九個月迄日的隔天到年度期末必須是一個單季。
   - 多個加數的分類：每個加數各取一個 fact；Q4 的每個加數同樣是年度減九個月累計。年度與九個月累計依各自的定義選取，加數個數可以不同（例如公司在財年中改了揭露格式），Q4 ＝ 年度各加數之和 − 九個月各加數之和。運算式依規格的加數順序列出；Q4 為第一個加數的年度、九個月累計，接著第二個加數，依此類推。
   - Q4 依據的各期：同期末日的 FY，以及同財年在範圍內有申報的 Q1–Q3，都必須通過結構檢核（含加總）。任一期不通過時 Q4 失敗，原因指向不通過的那一期。
   - Q4 推算條件：依據的各期都通過時，年度期末的分類集合必須等於財年起日到 Q3 期末之間每一天的分類集合。判斷只依規格，不需要 Q1、Q2 的申報（範圍內第一個財年可能沒有）。不相同時 Q4 不推算，`status.json` 記為 `not_derived`，附年度與 Q1–Q3 期間的分類；FY 照常上線。同一個分類換定義（例如成員改名）不算不同。規格漏寫適用期間時，少了分類的那一期加總失敗，Q4 也跟著失敗，不會被當成分類集合不同。
   - Q4 口徑一致：分類集合相同，公司仍可能在年報改了分類口徑（同名分類、數字基礎不同，例如把業務在分類間搬移），這時年度與 Q1–Q3 的數字基礎不同，相減沒有意義。判斷方式是把年報列示的上一財年年度數字，與上一財年先前申報的值比對，比對規則與比較欄相同（每個分類 × 年度角色的加權和，以年報期別生效的定義組出列示值，差距超過雙方精度誤差總和才算不同）。
     - 先前申報的值：上一財年的 FY 已上線（運算元都來自申報日不晚於本年報的申報）時用已上線值；沒有時用上一份 10-K 本身依規格組出的年度值（起始日之前的 10-K 照常讀取，只讀 fact，不寫入）。
     - 任一分類（含調節項與總營收）不同：Q4 不推算，`status.json` 記為 `not_derived`，檢核名稱「Q4 口徑一致」，`basis_changes` 列出每個不同的分類、兩邊的值與加數、先前值的依據與 accession；FY 照常上線。
     - 無法判斷時 Q4 照常推算，`status.json` 的該期紀錄附 `q4_basis` 說明原因：上一財年沒有已上線的 FY、已下載的申報中也沒有申報日不晚於本年報的上一財年 10-K，上一份 10-K 依規格組不出年度值（結構檢核不通過），年報沒有列示上一財年的總營收，或有分類無法比較（`unparseable` 或找不到列示值）。補下載較早的申報後，無法判斷的期別可能得到判斷結果（一致，或 `not_derived`），`--check` 因此報出差異屬預期。
     - 上一份 10-K 的原文缺檔或 sha256 不符（「原文存在」不通過）是資料不完整，不當成無法判斷：Q4 失敗，原因指出那份 10-K。
     - 只比對兩邊都有的分類：年報期別沒有定義的分類不比對。分類在財年交界改名（新舊名稱是兩個分類）時，舊名只在上一財年、新名只在年報期別，兩側都不比對，口徑變更只能由總營收與其他分類的差異偵測。
     - 判斷只用本年報與更早的申報，數字只來自規格認得的 XBRL fact。上一財年在 Q1–Q3 的 10-Q 就已重編時，年報的上一財年數字同樣與先前申報不同，Q4 也不推算。
   - 同一個值出現多次（同 concept、dimensions、期間）時，以精度最高（decimals 最大）的 fact 為準；其他重複值只需在自己的精度內與它一致。同精度時選所在表格含最多其他項目的 fact，再平手取文件順序第一個，其餘記在 `duplicates`。這讓同一期的運算元盡量落在同一張表，證據截圖較少。
7. **結構檢核**：見下節。不通過就不寫入正式輸出，只在 `status.json` 記錄原因。
8. **證據**：每個運算元找到所在的 SEC 表格，核對 fact 與運算元一致，存清理過的 HTML 片段與標示儲存格的截圖（1 倍解析度）。表格 HTML 與已提交的相同、PNG hash 與截圖倍率都相符時沿用舊 PNG，不重新截圖；同一期末日的 FY 與 Q4 互相沿用。表格運算元的證據就是該儲存格所在的表格。
9. **已上線保護**：該期已有上線輸出時，一般 parse 不改動它。
    - 重算結果與已上線輸出完全相同：不寫入。
    - 數值或依據（序列、分類、總營收、運算元、選用的申報、財年季別、觀點）不同：不寫入，`status.json` 記錄 `differs_from_published`（差異的分類、舊值、新值，原因是選用的申報不同或規則與原文變更）。由人確認後以 `--republish TICKER SERIES PERIOD` 覆寫，覆寫時 `revenue.json` 的 `republished` 記錄原值與原因。
    - 只有中繼資料不同（檢核紀錄、運算元的證據 hash）：不寫入，`status.json` 記錄 `stale_fields`。
    - `parser`（引擎與規格的 hash）記錄的是產生該輸出的版本，不列入比較：引擎或規格改動而內容相同時，視為相同。代價是已上線 `revenue.json` 的 `parser` 停在上線當時的版本，不代表目前的引擎；目前引擎的版本看 `status.json` 的 `parser`，兩者不同不代表輸出過時。
10. **寫入**：先寫暫存目錄，全部完成才換上 `data/revenue/.../<序列>/<period_end>/`；換上失敗時還原舊輸出。開始處理前清理中斷寫入留下的目錄：`.staging-*` 刪除，`.retired-<期別>-*` 在該期目錄不存在時還原、否則刪除。只有以期末日命名的目錄算已上線輸出。
11. **差異標記**：每次執行結束時重建 `status.json` 的差異標記（見自我檢核的比較欄比對）。

任何一期發生例外（包括非預期的程式錯誤）都記為該期失敗，附例外類型與訊息，繼續處理下一期；`status.json` 一定會寫入。

## 自我檢核

結構檢核（任一不通過，該期不輸出；已上線的該期輸出保留不動）。錯誤訊息以 `[檢核名稱]` 開頭：

| 檢核 | 內容 |
|---|---|
| 選申報 | 該期有 10-Q 或 10-K；Q4 的九個月只看申報日不晚於 10-K 的申報 |
| 原文存在 | 主文件在共用資料目錄中，sha256 與申報包紀錄一致 |
| 財年與季別 | 申報宣告財年與季別，且與表單種類相符；FY 序列的主申報是 10-K |
| 定義唯一 | 每個分類在該期最多一個生效的定義，總營收剛好一個；定義不是尚未支援的 `table_cell` |
| fact 存在且唯一 | 規格的前綴在文件中有宣告（`one_of` 至少一種寫法有宣告）；每個運算元（含多個加數的每一個）在原文中找得到、只有一個起日、數值可解析；同一份申報中各加數的起日相同；重複出現（含多種寫法同時出現）時在各自精度內一致 |
| 地區成員完整 | 使用地區軸的加總：申報中同 concept、同其他 dimensions、同期間的地區成員都列在規格中（只在用到地區軸時檢查） |
| 單位與精度 | 單位是 USD；`decimals` 有記錄且不低於 `-6`（百萬位），誤差上限由精度推得（`-6` 為 ±50 萬）。精度更粗的數字誤差過大，不上線 |
| 加總 | 分類（含 `reconciling`）加總等於總營收，差距不超過所有運算元精度誤差的總和 |
| Q4 期間 | 年度期末前一季剛好有一份 10-Q，且宣告同財年 Q3；年度與九個月運算元（每個加數）首尾相接；Q4 依據的 FY 與 Q1–Q3 都通過結構檢核 |
| 證據完整 | 每個運算元都在 HTML 表格內；原文節點是 `ix:nonFraction`，name、contextref、scale、顯示文字與數值等於運算元；瀏覽器截到的表格與原文表格文字相同 |

Q4 推算條件（依據的各期都通過，但年度與 Q1–Q3 的分類集合不同）或 Q4 口徑一致（年報的上一財年數字與先前申報不同）不成立時不是失敗：該期記為 `not_derived`，不輸出 Q4。

比較欄比對（不擋上線，不改已上線輸出）：

- 每次執行結束時，每一份已下載的 10-Q、10-K 與修正申報，都與它申報當時看得到的已上線輸出比對：運算元全部來自申報日不晚於它的申報。比對使用目前的已上線值，所以覆寫（`--republish`）或補上較早的期別後，標記隨之更新；比對結果不存在 `revenue.json`。
- 比對單位是分類（含調節項與總營收）在一個角色的值。角色是已上線運算元的 `role`：Q1–Q3 為單季；FY 為年度；Q4 分別比年度與九個月累計。
  - 已上線值：該角色運算元的加權和（九個月累計以定義本身的符號計，與申報列示的九個月累計同號）。
  - 申報列示值：申報中同一期間、以該申報期別生效的規格定義組出的加權和，每個加數都要找得到該期間的 fact（`one_of` 的任一種寫法都算）。同一個加數有多個 fact（含多種寫法同時出現）時取精度最高者；數值彼此不一致時結果是 `unparseable`，`listed_addends` 列出該加數的每一個 fact（數值無法讀取時為 null）。運算元的前綴在申報中宣告衝突時，結果也是 `unparseable`。
  - 只比分類值，不比個別加數：加數的個數、順序或成員與已上線不同都無妨（例如公司把兩個項目併成一個重新列示，和相同即一致）。單一加數的分類就是運算元對運算元。以規格定義而不是已上線運算元的 QName 查找，公司改 tag 或改成員名稱後仍比得到。
- 申報有某段期間的總營收（總營收的每個加數都有該期間的 fact）時，視為涵蓋該期間，已上線輸出中期間相同的角色都比對：單季欄對 Q 輸出的單季（去年同季，或修正申報的本期）；全年欄對 FY 與 Q4 的年度；九個月欄對 Q4 的九個月累計。運算元來自同一份申報時不比。
- 已上線輸出沒有的期間長度（例如 10-Q 的六個月累計）不比對：把兩季相加再比屬於解讀。
- 結果：`consistent`（差距不超過雙方所有運算元的誤差上限總和）、`different`（超出）、`unparseable`（有 fact 無法解析或缺 decimals）、`not_found`（申報期別沒有這個分類的規格定義，或有加數在申報中找不到該期間的 fact）。
- 誤差上限：每個 fact 取 `decimals` 與顯示文字本身精度中較粗者。顯示精度是 fact 文字小數點後的位數減 scale（`15,436.5`、scale 6 為十萬位，`15,437`、scale 6 為百萬位）。公司有時宣告的 decimals 比顯示的位數細，數值實際只到顯示的位數，以宣告值計會把四捨五入誤判成不同。組合數值與加總檢核仍以 `decimals` 計。
- `different` 與 `unparseable` 寫成舊期別的差異標記（`status.json` 的 `differences`），列出分類、角色、期間、已上線值、申報列示值、來源申報，以及雙方各自的加數。`consistent` 與 `not_found` 不寫。
- 已上線輸出在 `status.json` 沒有紀錄時（例如紀錄被手動刪除），由輸出補上該期的紀錄，標記照樣寫入。原文讀不到的申報不比對，列在 `status.json` 的 `comparison_errors`。

## 正式輸出

`Q/<period_end>/revenue.json`（AAPL 2025-09-27 的 Q4，節錄）：

```json
{
  "schema_version": 1,
  "ticker": "AAPL",
  "view": "product",
  "series": "Q",
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
      "evidence": { "table": "0000320193-25-000079-dceb82ec4e10-t27", "html_sha256": "...", "png_sha256": "...", "png_scale": 1 }
    }
  },
  "checks": {
    "structural": [ { "check": "定義唯一", "result": "pass" }, "..." ],
    "sum": { "categories": 102466000000, "total": 102466000000, "difference": 0, "tolerance": "6000000" }
  },
  "parser": { "spec_sha256": "...", "engine_sha256": "..." }
}
```

`FY/<period_end>/revenue.json`（AAPL FY2025，節錄）格式相同，差別是：`series` 為 `FY`；沒有 `fiscal_quarter`；`filings` 只有 `primary`；每個分類只有一個 `role` 為 `annual` 的運算元。

```json
{
  "schema_version": 1,
  "ticker": "AAPL",
  "view": "product",
  "series": "FY",
  "period_end": "2025-09-27",
  "fiscal_year": 2025,
  "unit": "USD",
  "filings": { "primary": { "accession": "0000320193-25-000079", "form": "10-K", "report_date": "2025-09-27", "filing_date": "2025-10-31" } },
  "categories": { "Mac": { "value": 33708000000, "expression": [ { "weight": 1, "operand": "op2" } ] } },
  "total": { "value": 416161000000, "expression": [ { "weight": 1, "operand": "op6" } ] },
  "operands": { "op2": { "kind": "xbrl_fact", "role": "annual", "fact_id": "f-380", "...": "..." } },
  "checks": { "structural": [ "..." ], "sum": { "...": "..." } },
  "parser": { "spec_sha256": "...", "engine_sha256": "..." }
}
```

- `role`：`quarter`、`annual` 或 `nine_months`。
- `expression` 依規格的加數順序列出運算元；多個加數的分類有多個運算元，Q4 依加數交錯列出年度與九個月累計。
- 規格宣告 `reconciling` 時另有同格式的 `reconciling` 欄位。
- 證據圖上的編號就是運算元編號（`op3` 標成 3）；`evidence.png_scale` 是截圖倍率。
- 以 `--republish` 覆寫過的期別有 `republished` 清單，每筆記錄原因與覆寫前的申報、分類數值、總營收與 `parser`。

`status.json` 依序列列出每個處理過的期別（節錄；`differences` 與 `not_derived` 兩筆是格式示意，不是 AAPL 的實際紀錄）：

```json
{
  "ticker": "AAPL",
  "view": "product",
  "parser": { "spec_sha256": "...", "engine_sha256": "..." },
  "periods": {
    "Q": {
      "2025-06-28": {
        "status": "published", "fiscal_year": 2025, "fiscal_quarter": 3, "accession": "0000320193-25-000073",
        "differences": [
          {
            "category": "Mac", "role": "quarter",
            "period": { "start": "2025-03-30", "end": "2025-06-28" },
            "result": "different", "published_value": "<已上線值>", "listed_value": "<申報列示值>",
            "source": { "accession": "...", "form": "10-Q", "filing_date": "2026-07-31" },
            "published_addends": [
              { "operand": "op2", "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                "dimensions": { "srt:ProductOrServiceAxis": "aapl:MacMember" }, "weight": 1, "value": "<已上線值>" }
            ],
            "listed_addends": [
              { "fact_id": "...", "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                "dimensions": { "srt:ProductOrServiceAxis": "aapl:MacMember" }, "weight": 1, "value": "<申報列示值>" }
            ]
          }
        ]
      },
      "2025-09-27": { "status": "published", "fiscal_year": 2025, "fiscal_quarter": 4, "accession": "0000320193-25-000079" },
      "2026-09-26": {
        "status": "not_derived", "fiscal_year": 2026, "fiscal_quarter": 4, "check": "Q4 推算條件", "reason": "...",
        "fy_categories": [ "iPhone", "Mac", "..." ],
        "quarter_categories": [ { "start": "2025-09-28", "end": "2026-06-27", "categories": [ "iPhone", "Mac", "..." ] } ],
        "published_output_kept": true,
        "published_output": {
          "accession": "...", "categories": { "iPhone": "<已上線值>", "...": "..." }, "total": "<已上線值>",
          "note": "已上線輸出保留不動；以目前的申報與規格重算，此期不成立"
        }
      }
    },
    "FY": {
      "2025-09-27": { "status": "published", "fiscal_year": 2025, "accession": "0000320193-25-000079" }
    }
  }
}
```

| 欄位 | 內容 |
|---|---|
| `status` | `published`、`failed`，或 Q 序列的 `not_derived`（Q4 推算條件或 Q4 口徑一致不成立） |
| `fiscal_year`、`fiscal_quarter`、`accession` | 上線時：主申報宣告的財年與季別（FY 序列沒有季別）及主申報；不推算時：財年與季別 |
| `check`、`reason` | 失敗或不推算時：檢核名稱與原因 |
| `fy_categories`、`quarter_categories` | Q4 推算條件不成立時：年度的分類，以及財年起日到 Q3 期末之間依日期分段的分類 |
| `basis_changes` | Q4 口徑一致不成立時：每個不同的分類一筆，`category`、`period`（上一財年）、`previous_value`、`listed_value`、`previous`（`basis` 為 `published` 或 `filing`，與 `accession`）、`listed`（年報的 `accession`）、`previous_addends`（依據為 `published` 時是上一財年 FY 的運算元：`operand`、concept、dimensions、`weight`、`value`；依據為 `filing` 時是上一份 10-K 中的 fact：`fact_id`、concept、dimensions、`weight`、`value`）、`listed_addends`（年報中的 fact，格式同差異標記） |
| `q4_basis` | Q4 照常推算但無法判斷口徑時：`result`（`undetermined`）與 `reason` |
| `published_output_kept` | 失敗或不推算時：該期是否仍有先前上線的輸出 |
| `published_output` | 失敗或不推算而仍有先前上線的輸出時：它的申報、分類數值與總營收，說明已上線值保留不動 |
| `differences` | 差異標記：較晚申報的比較欄與此期已上線的分類值不同（`different`）或無法解析（`unparseable`）。每筆一個分類 × 角色：`category`、`role`（`quarter`／`annual`／`nine_months`）、`period`、`result`、`published_value`、`listed_value`（無法解析時為 null）、`source`（申報的 accession、form、filing_date）、`published_addends`（已上線運算元：`operand`、concept、dimensions、`weight`、`value`）、`listed_addends`（申報中的 fact：`fact_id`、concept、dimensions、`weight`、`value`）、選用的 `note` |
| `differs_from_published` | 重算結果與已上線輸出的數值或依據不同：原因、差異的分類與新舊值、不同的欄位 |
| `stale_fields` | 重算結果與已上線輸出只有中繼資料不同時，不同的欄位 |

`status.json` 頂層另有 `comparison_errors`（只在有時出現）：原文讀不到、無法做比較欄比對的申報與原因。

## 指令

```bash
npm run parse -- --tickers AAPL                     # 預設起始日起的全部已下載期別：解析、檢核、證據、寫入 data/revenue/（Q 與 FY）
npm run parse -- --tickers AAPL --start 2025-01-01  # 只處理期末日在範圍內的期別
npm run parse -- --tickers AAPL --check             # 重跑並與已提交的輸出比對，不寫入
npm run parse -- --tickers AAPL --republish AAPL Q 2025-09-27   # 由人確認後覆寫已上線的期別
```

- `npm run parse` 即 `scripts/sec_pipeline.py parse`；省略 `--tickers` 或加 `--all` 處理全部有規格的公司。
- parse 只讀共用資料目錄的 SEC 原文，不連網；缺原文時提示先執行 download。
- `--start` 省略時用預設起始日；指定時可以早於預設值。`--end` 省略時不設上限。
- 一次處理多期時依期末日順序執行，每期只看得到它的時點以前的申報與已上線輸出，與逐期分開執行的結果相同。
- `--check` 不啟動 Chromium。它在已提交輸出的副本上照一般 parse 執行（同樣受已上線保護），再與已提交的輸出比對；一般 parse 不會改動任何檔案、也不會改變 `status.json` 時才算一致：
  - 兩個序列的 `revenue.json` 逐欄比對（`parser` 欄位與 PNG hash、倍率除外）；
  - `status.json` 中這些期別的紀錄逐欄比對，包括失敗或不推算的原因、`differences`、`differs_from_published`、`stale_fields`（`published_output_kept` 除外），以及頂層的 `comparison_errors`；
  - 證據 HTML 比對 bytes，證據目錄中沒有被 `revenue.json` 引用的檔案列為差異；
  - 已提交的 PNG 核對檔案 hash 與紀錄一致。

  省略期別時比對 `status.json` 列出的期別。有差異時回傳碼為 2。`--check` 不能與 `--republish` 同時使用。
- `--republish TICKER SERIES PERIOD` 可重複指定；SERIES 是 `Q` 或 `FY`，ticker 與期別必須在這次處理的範圍內。
- 回傳碼：`0` 沒有期別失敗（Q4 不推算不算失敗）；`2` 有期別失敗或 `--check` 有差異；`1` 輸入錯誤。

## 測試

- 引擎：`tests/revenue/test_revenue_parser.py` 以合成的 inline XBRL 申報測試每個流程步驟與每項檢核，不連網、不啟動 Chromium。
- 公司：`data/revenue/` 中已提交的輸出就是回歸基準。`--check` 重跑 parser，與已提交的輸出逐欄比對；改某家公司的規格只重跑該家，改引擎則重跑所有上線公司（#49）。`--check` 需要本機的 SEC 原文，CI 不執行，只跑 unit test 與 `validate_universe.py`。
