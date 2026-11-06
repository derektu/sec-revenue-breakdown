# Parser 與正式輸出

本文件定義 SEC 營收 parser 的架構：框架、utility 與公司 parser 怎麼分工，框架怎麼從公司 parser 交回的 fact 算出每季與每年的 by segment 營收、怎麼自我檢核，以及正式輸出、證據與快照的格式。

parser 的輸出就是正式資料，連同證據進 Git。新的期別不需要對照資料：結構檢核通過就上線。對照資料只用在公司初次上線時選定觀點（#46），以及客戶反映問題時判斷原因。

parser 的範圍：

- **只公布財報上寫的項目與數字**：不解讀財報內容、不追究差異原因、不自動修正。每一期照該期財報的項目與數字公布，項目與上一期不同也照列。
- **兩個序列**：季度（Q）的 Q1–Q3 取自 10-Q，Q4 由 10-K 年度減九個月累計推算；年度（FY）直接取 10-K 的全年數字。Q4 只在年度與 Q1–Q3 的分類相同、且年報沒有改分類口徑時推算，否則留空並記錄原因，不另做補救。
- **預設起始日**：所有公司共用一個預設起始日（`revenue/engine.py` 的 `DEFAULT_START`，目前是 2024-01-01，隨 Git 版本控制）。parse 沒有指定 `--start` 時，Q 與 FY 處理期末日不早於預設起始日的期別；要處理更早的期別時以 `--start` 指定，照常處理並發布。起日之前已下載的申報照常讀取，作為運算元（例如第一個 Q4 的九個月累計來自起日之前的 Q3 10-Q）與比較欄比對的來源，只是這次不處理成期別。已上線的較早期別是正常的已上線資料：保留 `status.json` 紀錄、照常作為比較欄比對的對象、照常受已上線保護。
- **Point in time**：一期的數字取自該期最早的原申報，處理時只使用申報日當天或更早公開的申報。例如處理 Q2 時，框架看得到今年 Q1、去年 FY 與去年各季，看不到之後的申報。之後的申報（包括修正申報）不改已上線的數字。
- **差異標記**：較晚的申報（包括修正申報）列出的較早期間數字，例如去年同季、去年九個月累計、去年全年，或修正申報的本期數字，與已上線的同一期不同時，在舊期別記錄標記；已上線數字不改，由 PM 視需要請人查明。

## 名詞

| 名詞 | 意義 |
|---|---|
| 觀點（view） | 一種產品或業務別的營收拆分。同一家公司可能有多個面向或多層細項，例如業務群與其下的產品線；每家公司採用一個觀點。地區拆分不是觀點：AAPL 的營運分部是 Americas、Europe 等地區，不採用，採用的是產品別（iPhone、Mac…） |
| 分類（category） | 觀點中的一項，例如 iPhone |
| 序列 | `Q`（季度：Q1–Q4）或 `FY`（年度） |
| 期別 | 一個序列中的一期，以期末日（SEC context 的 endDate）識別，例如 `2025-09-27`。10-K 的期末日同時有 FY 與 Q4 兩期。財年與季次取自該期申報的 `dei:DocumentFiscalYearFocus`、`dei:DocumentFiscalPeriodFocus` |
| 運算元 | 一個 SEC 數字，一定是 inline XBRL fact（`xbrl_fact`），以申報 accession 與 fact id 識別 |
| 運算式 | 分類數值由運算元加權相加而成，例如 Q4 = 年度 − 九個月累計 |
| 比較欄 | 申報中與本期並列的較早期間數字，例如 10-Q 的去年同季、10-K 的去年全年 |
| 框架 | 所有公司共用的處理流程：提供資料、檢核、寫入。不負責找數字 |
| utility | 公司 parser 可以呼叫的小工具函式，例如依 concept 與 dimensions 查 fact |
| 公司 parser | 一家公司自己的程式碼：決定這家公司的每個分類用哪些 fact |
| fact 清單 | 一份申報主文件的全部數值 fact，加上 namespaces 與 dei；公司 parser 唯一的數字來源 |

## 架構

parser 分三層。每家公司的 parser 各自獨立，新增或修改一家公司，不影響其他公司的輸出。

| 層 | 負責 | 誰可以改 |
|---|---|---|
| 框架 | 提供資料（每次交出一份申報的 fact 清單）、檢核（加總、單位、精度、證據）、寫入（`revenue.json`、`status.json`、證據、已上線保護） | 改框架等於改所有公司的處理規則，由人決定 |
| utility | 查 fact、判斷期間長度、加總等小工具；不含任何一家公司的知識 | 誰都可以新增；既有的 utility 只增不改 |
| 公司 parser | 這家公司的分類、tag、成員、寫法切換、加總方式 | 寫這家公司的人 |

### 框架

框架只做三件事，與任何一家公司的揭露方式無關：

1. **提供資料**：框架每次只把一份申報的 fact 清單交給公司 parser，請它組出一段期間的運算式。公司 parser 拿不到 HTML 原文，也拿不到其他申報。交給它哪一份申報由框架依時點選定（見框架流程的選申報），所以每個運算元都出自框架選定的一份申報：不會用到之後申報的數字，也不會用到 XBRL fact 以外的數字。寫 parser 的人在動手前看過的申報與對照資料，資料限制擋不住，由「時點與寫 parser 的人的知識」的規則與 review 處理。
2. **檢核**：公司 parser 交回的是「每個分類用了哪幾個 fact、權重多少」，不交數字。框架核對這些 fact 都在該申報的 fact 清單中，依 fact 自己算出數值，再做結構檢核。公司 parser 沒辦法交出 fact 清單以外的數字。
3. **寫入**：證據、正式輸出、`status.json`、已上線保護與差異標記。HTML 原文只有框架讀，用來找出 fact 所在的表格、截圖存證。

新增一家公司永遠不需要改框架。開發一家公司時覺得非改框架不可，代表要改的是所有公司共用的規則：停下來回報，由人決定。

### utility

- 一個 utility 做一件事，不含任何一家公司的 tag、成員或分類名稱。
- 只增不改：既有 utility 的行為一旦有公司在用，就不再修改。需要不同行為時新增一個 utility。修改既有 utility 等於修改框架，要由人決定，並重跑全部公司。
- 新增 utility 不改變任何既有公司的輸出，所以誰都可以加。
- utility 放在 `libs/sec_revenue/parser_utils/`，與框架分開；測試在 `tests/sec_revenue/parser_utils/`。

### 公司 parser

- 每家公司一個目錄，parser 是程式碼，不 import 其他公司的 parser。各家寫法相近時照樣各寫各的：重複程式碼是每家獨立的代價，換來改一家不會動到另一家。
- 公司 parser 自己決定分類、tag、成員、寫法在申報之間怎麼切換、哪些 fact 相加。這些都寫在公司自己的程式碼裡，不進框架或 utility。
- 新的申報是公司 parser 沒看過的資料。找不到需要的 fact 時，該期失敗並說明原因，不猜、不補。找錯 fact 多半由框架的結構檢核擋下（例如分類加總對不上總營收）；加總剛好對上的，靠上線前與對照資料逐期比對、以及較晚申報的差異標記發現。公司改 tag 或改分類後，由人修改那一家的 parser。

### 時點與寫 parser 的人的知識

寫 parser 之前，開發者（人或 agent）已經看過這家公司全部的申報與對照資料。框架只給一份申報，擋得住「用之後申報的數字」，擋不住「用之後才知道的事決定這一期怎麼組」。後者大多無害，例如知道公司用哪個 tag，那個 tag 本來就在該期申報裡；有害的是用後來的觀點改寫早期的呈現。公司 parser 遵守以下規則：

- **每一期照該期申報自己的呈現組**：分類名稱、分類結構、哪些項目相加，都要能從那份申報本身看出來。不用後來的分類結構組早期的期別（例如公司後來才合併的兩個分部，早期照分開輸出），也不用後來的名稱輸出早期的分類。
- **依申報內容判斷，不依日期判斷**：寫成「申報裡有 X 成員就用 X，沒有就用 Y」，換成任何一份申報都成立。必須依日期切換時，`parser.md` 寫明是哪一份申報開始改變，而且在那一份申報裡看得到這個改變。
- **不寫死 fact id、數值與沒有理由的特定期別例外**：對照資料常用重編後的數字，為了對上對照資料而改 parser，等於把之後申報的觀點帶進早期期別。與對照資料的差異照實記在 `parser.md`。

程式檢查不了這些規則，所以列為獨立 review 的必看項目。

## 新增一家公司

1. **確認對照資料**：擷取該公司的對照資料（Stock Analysis、富途、TradingView）。
2. **選定觀點**：比較各來源的分類。
   - 各來源一致：直接採用該觀點。
   - 各來源不一致（面向不同、細項層級不同、分類名稱或範圍不同）：開發者對照 SEC 原文能重現哪些分類，提出建議與理由，由人判斷後才開始寫 parser。
3. **寫公司 parser 與 `parser.md`**，以已下載的 SEC 原文跑 parse。只寫這家公司的目錄；需要的 utility 不存在時新增一個，不改既有的 utility 與框架。
4. **與對照資料逐期比對**（#46），差異逐筆說明。
5. **獨立 review**：除了程式與 `parser.md`，必看「時點與寫 parser 的人的知識」的三條規則與 utility 只增不改；通過後由人核准，`tickers.csv` 標為 `ok`。

## 目錄

```
libs/sec_revenue/revenue/              框架：讀申報、產生 fact 清單、組數值、檢核、證據、寫入、快照

libs/sec_revenue/parser_utils/         utility：公司 parser 可呼叫的工具函式，只增不改

libs/sec_revenue/companies/<首字母>/<目錄>/
  parser.py        公司 parser（程式碼）
  parser.md        觀點、分類對應、tag、寫法切換、已知例外、驗證結果

data/revenue/<首字母>/<TICKER>/
  status.json      兩個序列每一期的處理結果（含沒有輸出的期別與原因）與差異標記
  Q/<period_end>/  季度序列（Q1–Q4）
    revenue.json   正式數字、運算式、運算元、檢核結果
    evidence/      每張用到的 SEC 表格：<accession>-<sha12>-t<n>.html 與 .png
  FY/<period_end>/ 年度序列，期末日與同財年的 Q4 相同
    revenue.json
    evidence/

data/snapshots/<首字母>/<TICKER>/
  <accession>.jsonl 每份申報從原文抽出的內容：表頭一行，之後一行一個 fact 的原始欄位
  manifest.json    申報清單：正式輸出依賴的每份 10-K／10-Q 的申報資訊與申報包內每個檔案的 sha256、bytes
```

- 公司目錄名是 ticker 小寫，非英數字元改為底線，例如 `a/aapl`、`b/brk_b`；ticker 本身以公司 parser 宣告的為準。
- `companies/`、`data/revenue/` 與申報清單都進 Git；快照是否進 Git 依 CI 環境而定（見「快照」）。SEC 原文在共用資料目錄（`SEC_DATA_DIR`），不進 Git；正式輸出記錄每份原文的 URL 與 sha256，可以重新下載核對。
- SEC 原文由 `download/` 下載成申報包（見 [download.md](download.md)），框架只讀申報包。

## 公司 parser 的介面

框架以「一份申報、一段期間」向公司 parser 要運算式。Q1–Q3、FY、Q4 的年度與九個月累計、比較欄比對、Q4 口徑一致都用同一個問法，所以公司 parser 只需要回答「這份申報裡，這段期間的每個分類由哪些 fact 組成」。Q4 由框架分別向年報要年度、向 Q3 的 10-Q 要九個月累計，再相減，公司 parser 不需要同時看兩份申報。需要合併兩份申報才組得出來的公司，代表要改框架：停下來回報。

公司目錄的 `parser.py` 定義：

```python
TICKER = "AAPL"
VIEW = "product"                      # product 或 business_segment
TOTAL = "Total net sales"             # 總營收的名稱

def compose(filing, request):
    """filing：一份申報的 fact 清單（FilingFacts）；request：要組的期間（Request）。
    回傳 Composition：分類、調節項與總營收的運算式。"""

def categories(day):
    """這家公司在 day 這一天有哪些分類與調節項，依輸出順序。"""
```

介面的型別由框架提供（`revenue/contract.py`）：

| 型別 | 內容 |
|---|---|
| `FilingFacts` | 申報的 `accession`、`form`、`report_date`，與主文件的 `facts`、`namespaces`、`dei`；沒有 HTML 原文與表格 |
| `Request` | `end`（期末日）、`duration`（`quarter`、`nine_months`、`annual`）與選用的 `start`；`matches(fact)` 判斷 fact 的期間是否相符 |
| `Term` | 運算式的一項：`facts`（這個數字在申報中的 fact，多種寫法時每種寫法各有）、`weight`（1 或 -1）、`label`（錯誤訊息用的描述） |
| `Composition` | `categories`、`reconciling`（名稱 → 各項，依輸出順序，必須與 `categories(期末日)` 相同）、`total`（各項，組不出時為 None）、`missing`（申報中找不到的項目 → 原因）、`unparseable`（申報中有、但無法確定是哪些 fact 的項目 → 原因，例如前綴宣告衝突） |
| `ParserFailure` | 組不出這份申報時丟出，帶檢核名稱與原因 |

- **`compose` 的回傳**：分類、調節項與總營收各一個運算式，每一項指定 fact 與權重，數值由框架依 fact 計算。權重只能是 1 或 -1，依公司 parser 列出的順序輸出。分類加總與總營收之間的合法差額（例如公司間抵銷、未分配項目）列為調節項：參與加總檢核，不輸出成分類；組成有調節項的期別，`revenue.json` 有 `reconciling` 欄位。
- **框架核對交回的 fact**：交給公司 parser 的 fact 清單是唯讀副本；交回的每個 fact 必須在這份申報的 fact 清單中、期間與 `request` 相符；框架另外補上同 concept、同 dimensions、同期間的重複 fact，檢查數值一致後依重複值的規則選定運算元。
- **沒有這個分類**：這份申報沒有某個分類時，回傳中不列出它，原因記在 `missing`。比較欄比對時記為 `not_found`。總營收一定要有。
- **無法確定是哪些 fact**：某一項在申報中有、但無法確定（例如前綴宣告衝突）時記在 `unparseable`；整份申報都組不出來時丟出 `ParserFailure(檢核名稱, 原因)`，檢核名稱用自我檢核表中的名稱，無法確定 fact 時用「fact 存在且唯一」。主申報的呼叫記為該期失敗，`status.json` 的格式與其他失敗相同；比較欄比對時，該項（`ParserFailure` 時為這段期間的每一項）記為 `unparseable`，寫成差異標記；申報沒有起訖相同的 fact、也就是沒有列示這段期間時，不比對。
- **utility**：`parser_utils` 的 `find`（一種寫法的 fact）、`one_of`（多種寫法）與 `put`（放進組成，找不到時記在 `missing`）涵蓋依 concept 與 dimensions 精確查找的寫法；比對以 namespace URI 進行，前綴沒有宣告的寫法視為不存在。
- **依申報期末日切換寫法**：`FilingFacts.report_date` 是申報的期末日。依日期切換時，`parser.md` 寫明是哪一份申報開始改變（見「時點與寫 parser 的人的知識」）。
- **`categories`**：框架用來判斷 Q4 推算條件（年度期末的分類集合是否等於財年起日到 Q3 期末之間每一天的分類集合），不需要 Q1、Q2 的申報。框架向主申報要運算式時（Q1–Q3 的單季、FY 與 Q4 的年度、Q4 的九個月累計），核對回傳的分類與 `categories(該運算式的期末日)` 相同，不同時該期失敗：不列出的分類也必須不在 `categories` 中。比較欄比對與 Q4 口徑一致是用較晚的申報組較早的期間，較晚的申報可能已用新的分類結構重新列示，所以這兩種呼叫不核對。核對只發生在各期的期末日，期間中間的日子與範圍內沒有申報的 Q1、Q2，`categories` 的回答沒有被核對到，由 review 檢查。新申報出現 parser 不認得的分類時，parser 不會列出它，通常是加總對不上而失敗，由人更新那一家的 parser。`categories` 本身依日期回答，每個分類集合改變的日期同樣要在 `parser.md` 寫明是哪一份申報開始改變（見「時點與寫 parser 的人的知識」）。
- **公司 parser 自己處理的事**，寫在自己的程式碼並記錄在 `parser.md`：
  - 用哪個 concept、哪些 dimensions。
  - 同一個數字在不同申報用不同的 concept 或成員名稱，例如 AMZN 10-K 用 `us-gaap:AdvertisingMember`、10-Q 用 `amzn:AdvertisingServicesMember`；或在財年中途改名，例如 NVDA 的分部成員。
  - 申報沒有分類所需的小計時，列出要相加的 fact，例如 LIN 的 Industrial Gases ＝ Americas＋EMEA＋APAC。
  - 分類的新增、合併與拆分。
  - 文件用不同前綴指向同一個 namespace，或公司與 us-gaap 的 namespace URI 每年帶不同日期：以 namespace URI 辨認 concept 與成員，fact 清單附有文件宣告的 namespaces。
- **規則**：
  - 觀點只取產品或業務別。地區軸 `srt:StatementGeographicalAxis` 的 fact 只能以「該軸全部成員相加」出現在運算式中，每一項權重 1、不與其他寫法混合，例如 XOM、CVX、LLY 的分部營收只以美國＋非美國揭露。框架以 namespace URI 辨認地區軸，以「地區成員完整」檢核。
  - 使用 `us-gaap:StatementBusinessSegmentsAxis` 時，`parser.md` 寫明這個軸的成員是業務別而不是地區：公司常把這個軸用於地區分部，例如 AAPL 的 Americas、Europe。
  - 分類名稱不重複，總營收不與分類重名。
  - 每家公司都有 `parser.md`。

## 框架流程

一家公司依期末日順序處理指定範圍內的每個期別。期末日的第一份原申報是 10-Q 時只有 Q 序列；是 10-K 時先處理 FY、再處理 Q4。每一期：

1. **選申報**：該期的主申報是 reportDate 等於該期、申報日最早的 10-Q 或 10-K。修正申報（10-K/A、10-Q/A）在原申報之後才公開，不取代主申報，只參與差異標記的比對。框架不讀 8-K。主文件必須是 inline XBRL，讀取時核對 sha256。主申報的申報日是這一期的時點：之後的步驟只看申報日不晚於它的申報。
2. **讀 facts**：解析主申報的 inline XBRL，建立 fact 清單：concept、dimensions、期間、單位、decimals、sign、scale、format 與所在表格。數值依 format（`num-dot-decimal`、`fixed-zero`、`zerodash`）、scale 與 sign 算成整數美元；正負號只由 `sign` 屬性決定，顯示文字帶負號或括號、或數值不是有限數時，這個 fact 視為無法解析。證據核對使用同一套規則（`evidence.ix_number`）。
   - 公司 parser 交回的是 fact 清單中的 fact，框架核對它屬於這份申報，不以 QName 比對 fact。
3. **財年與季別**：主申報必須宣告 `DocumentFiscalYearFocus` 與 `DocumentFiscalPeriodFocus`（Q1、Q2、Q3、FY）；Q1–Q3 必須是 10-Q，FY 必須是 10-K。
4. **期間分類**：依 context 天數（含首尾）判斷單季（84–98 天）、六個月（175–189 天）、九個月（266–280 天）、年度（357–378 天）。
5. **分類集合**：公司 parser 對主申報與該期間交回的分類與調節項，必須與 `categories(期末日)` 相同。Q4 推算條件用的是 `categories`。
6. **組合數值**：
   - Q1–Q3：公司 parser 從主申報選出期末日為該期的單季 fact。
   - FY：公司 parser 從主申報（10-K）選出期末日為該期的年度 fact。
   - Q4：框架分別向公司 parser 要年度（10-K）與九個月累計的運算式，相減。九個月取自年度期末前一季的原 10-Q（申報日不晚於 10-K），它必須宣告同財年 Q3；九個月的起日必須等於年度起日，九個月迄日的隔天到年度期末必須是一個單季。
   - 多個加數的分類：每個加數各取一個 fact；Q4 的每個加數同樣是年度減九個月累計。年度與九個月累計各自向公司 parser 要，加數個數可以不同（例如公司在財年中改了揭露格式），Q4 ＝ 年度各加數之和 − 九個月各加數之和。運算式依公司 parser 列出的加數順序；Q4 為第一個加數的年度、九個月累計，接著第二個加數，依此類推；兩邊加數個數不同時，多出的依序接在後面。
   - Q4 依據的各期：同期末日的 FY，以及同財年在範圍內有申報的 Q1–Q3，都必須通過結構檢核（含加總）。任一期不通過時 Q4 失敗，原因指向不通過的那一期。
   - Q4 推算條件：依據的各期都通過時，年度期末的分類集合必須等於財年起日到 Q3 期末之間每一天的分類集合。分類集合由公司 parser 的 `categories` 提供。不相同時 Q4 不推算，`status.json` 記為 `not_derived`，附年度與 Q1–Q3 期間的分類；FY 照常上線。同一個分類換了 fact（例如成員改名）不算不同。公司 parser 漏了某個分類時，那一期在「定義唯一」或加總失敗，Q4 也跟著失敗，不會被當成分類集合不同。
   - Q4 口徑一致：分類集合相同，公司仍可能在年報改了分類口徑（同名分類、數字基礎不同，例如把業務在分類間搬移），這時年度與 Q1–Q3 的數字基礎不同，相減沒有意義。判斷方式是把年報列示的上一財年年度數字，與上一財年先前申報的值比對，比對規則與比較欄相同（每個分類 × 年度角色的加權和，由公司 parser 從年報組出列示值，差距超過雙方精度誤差總和才算不同）。
     - 先前申報的值：上一財年的 FY 已上線（運算元都來自申報日不晚於本年報的申報）時用已上線值；沒有時用公司 parser 從上一份 10-K 組出的年度值（起始日之前的 10-K 照常讀取，只讀 fact，不寫入）。
     - 任一分類（含調節項與總營收）不同：Q4 不推算，`status.json` 記為 `not_derived`，檢核名稱「Q4 口徑一致」，`basis_changes` 列出每個不同的分類、兩邊的值與加數、先前值的依據與 accession；FY 照常上線。
     - 無法判斷時 Q4 照常推算，`status.json` 的該期紀錄附 `q4_basis` 說明原因：上一財年沒有已上線的 FY、已下載的申報中也沒有申報日不晚於本年報的上一財年 10-K，上一份 10-K 組不出年度值（結構檢核不通過），年報沒有列示上一財年的總營收，或有分類無法比較（`unparseable` 或找不到列示值）。補下載較早的申報後，無法判斷的期別可能得到判斷結果（一致，或 `not_derived`），`--check` 因此報出差異屬預期。
     - 上一份 10-K 的原文缺檔或 sha256 不符（「原文存在」不通過）是資料不完整，不當成無法判斷：Q4 失敗，原因指出那份 10-K。
     - 只比對兩邊都有的分類：公司 parser 對年報沒有列出的分類不比對。分類在財年交界改名（新舊名稱是兩個分類）時，舊名只在上一財年、新名只在年報期別，兩側都不比對，口徑變更只能由總營收與其他分類的差異偵測。
     - 判斷只用本年報與更早的申報，數字只來自 fact 清單。上一財年在 Q1–Q3 的 10-Q 就已重編時，年報的上一財年數字同樣與先前申報不同，Q4 也不推算。
   - 公司 parser 指定的 fact 有重複值（同 concept、dimensions、期間）時，框架以精度最高（decimals 最大）的 fact 為準；其他重複值只需在自己的精度內與它一致。同精度時選所在表格含最多其他項目的 fact，再平手取文件順序第一個，其餘記在 `duplicates`。這讓同一期的運算元盡量落在同一張表，證據截圖較少。
7. **結構檢核**：見下節。不通過就不寫入正式輸出，只在 `status.json` 記錄原因。
8. **證據**：每個運算元找到所在的 SEC 表格，核對 fact 與運算元一致，存清理過的 HTML 片段與標示儲存格的截圖（1 倍解析度）。表格 HTML 與已提交的相同、PNG hash 與截圖倍率都相符時沿用舊 PNG，不重新截圖；同一期末日的 FY 與 Q4 互相沿用。
9. **已上線保護**：該期已有上線輸出時，一般 parse 不改動它。
    - 重算結果與已上線輸出完全相同：不寫入。
    - 數值或依據（序列、分類、總營收、運算元、選用的申報、財年季別、觀點）不同：不寫入，`status.json` 記錄 `differs_from_published`（差異的分類、舊值、新值，原因是選用的申報不同或規則與原文變更）。由人確認後以 `--republish TICKER SERIES PERIOD` 覆寫，覆寫時 `revenue.json` 的 `republished` 記錄原值與原因。
    - 只有中繼資料不同（檢核紀錄、運算元的證據 hash）：不寫入，`status.json` 記錄 `stale_fields`。
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
| 定義唯一 | 公司 parser 對每個分類最多交回一個運算式，總營收剛好一個；權重都是 1 或 -1；向主申報要的運算式，交回的分類與 `categories(期末日)` 相同 |
| fact 存在且唯一 | 每個運算元在該申報的 fact 清單中找得到、數值可解析；同一份申報中各加數的起日相同；重複出現時在各自精度內一致 |
| 地區成員完整 | 使用地區軸的加總：申報中同 concept、同其他 dimensions、同期間的地區成員都在運算式中（只在用到地區軸時檢查） |
| 單位與精度 | 單位是 USD；`decimals` 有記錄且不低於 `-6`（百萬位），誤差上限由精度推得（`-6` 為 ±50 萬）。精度更粗的數字誤差過大，不上線 |
| 加總 | 分類（含 `reconciling`）加總等於總營收，差距不超過所有運算元精度誤差的總和 |
| Q4 期間 | 年度期末前一季剛好有一份 10-Q，且宣告同財年 Q3；年度與九個月運算元（每個加數）首尾相接；Q4 依據的 FY 與 Q1–Q3 都通過結構檢核 |
| 證據完整 | 每個運算元都在 HTML 表格內；原文節點是 `ix:nonFraction`，name、contextref、scale、顯示文字與數值等於運算元；瀏覽器截到的表格與原文表格文字相同 |

Q4 推算條件（依據的各期都通過，但年度與 Q1–Q3 的分類集合不同）或 Q4 口徑一致（年報的上一財年數字與先前申報不同）不成立時不是失敗：該期記為 `not_derived`，不輸出 Q4。

比較欄比對（不擋上線，不改已上線輸出）：

- 每次執行結束時，每一份已下載的 10-Q、10-K 與修正申報，都與它申報當時看得到的已上線輸出比對：運算元全部來自申報日不晚於它的申報。比對使用目前的已上線值，所以覆寫（`--republish`）或補上較早的期別後，標記隨之更新；比對結果不存在 `revenue.json`。
- 比對單位是分類（含調節項與總營收）在一個角色的值。角色是已上線運算元的 `role`：Q1–Q3 為單季；FY 為年度；Q4 分別比年度與九個月累計。
  - 已上線值：該角色運算元的加權和（九個月累計以運算式中的權重符號計，與申報列示的九個月累計同號）。
  - 申報列示值：公司 parser 從該申報組出的同一期間運算式的加權和。同一個加數有重複值時取精度最高者；數值彼此不一致時結果是 `unparseable`，`listed_addends` 列出該加數的每一個 fact（數值無法讀取時為 null）。
  - 只比分類值，不比個別加數：加數的個數、順序或成員與已上線不同都無妨（例如公司把兩個項目併成一個重新列示，和相同即一致）。單一加數的分類就是運算元對運算元。列示值由公司 parser 從該申報重新組出，不沿用已上線運算元的 QName，所以公司改 tag 或改成員名稱後仍比得到。
- 公司 parser 能從申報組出某段期間的總營收時，視為涵蓋該期間，已上線輸出中期間相同的角色都比對：單季欄對 Q 輸出的單季（去年同季，或修正申報的本期）；全年欄對 FY 與 Q4 的年度；九個月欄對 Q4 的九個月累計。運算元來自同一份申報時不比。
- 已上線輸出沒有的期間長度（例如 10-Q 的六個月累計）不比對：把兩季相加再比屬於解讀。
- 結果：`consistent`（差距不超過雙方所有運算元的誤差上限總和）、`different`（超出）、`unparseable`（有 fact 無法解析或缺 decimals）、`not_found`（公司 parser 對該申報沒有列出這個分類，或組不出該期間的運算式）。
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
  }
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
  "checks": { "structural": [ "..." ], "sum": { "...": "..." } }
}
```

- `role`：`quarter`、`annual` 或 `nine_months`。
- `expression` 依公司 parser 列出的加數順序列出運算元；多個加數的分類有多個運算元，Q4 依加數交錯列出年度與九個月累計。
- 公司 parser 交回調節項時另有同格式的 `reconciling` 欄位。
- 證據圖上的編號就是運算元編號（`op3` 標成 3）；`evidence.png_scale` 是截圖倍率。
- 以 `--republish` 覆寫過的期別有 `republished` 清單，每筆記錄原因與覆寫前的申報、分類數值與總營收。
- 輸出不記錄程式版本。已上線保護讓內容相同的輸出不重寫，所以一份輸出最後由哪一版程式寫入，看 Git 中它最後一次改動的 commit；目前的程式是否仍算出相同的輸出，由 `--check` 確認。

`status.json` 依序列列出每個處理過的期別（節錄；`differences` 與 `not_derived` 兩筆是格式示意，不是 AAPL 的實際紀錄）：

```json
{
  "ticker": "AAPL",
  "view": "product",
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
          "note": "已上線輸出保留不動；以目前的申報與公司 parser 重算，此期不成立"
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
npm run parse -- --all --check --snapshots          # 不讀 SEC 原文，以快照重跑並比對（CI 執行這一項）
npm run parse -- --tickers AAPL --republish AAPL Q 2025-09-27   # 由人確認後覆寫已上線的期別
```

- `npm run parse` 即 `scripts/sec_pipeline.py parse`；省略 `--tickers` 或加 `--all` 處理全部有公司 parser 的公司。
- parse 只讀共用資料目錄的 SEC 原文，不連網；缺原文時提示先執行 download。
- `--start` 省略時用預設起始日；指定時可以早於預設值。`--end` 省略時不設上限。
- 一次處理多期時依期末日順序執行，每期只看得到它的時點以前的申報與已上線輸出，與逐期分開執行的結果相同。
- `--check` 不啟動 Chromium。它在已提交輸出的副本上照一般 parse 執行（同樣受已上線保護），再與已提交的輸出比對；一般 parse 不會改動任何檔案、也不會改變 `status.json` 時才算一致：
  - 兩個序列的 `revenue.json` 逐欄比對（PNG hash 與倍率除外）；
  - `status.json` 中這些期別的紀錄逐欄比對，包括失敗或不推算的原因、`differences`、`differs_from_published`、`stale_fields`（`published_output_kept` 除外），以及頂層的 `comparison_errors`；
  - 證據 HTML 比對 bytes，證據目錄中沒有被 `revenue.json` 引用的檔案列為差異；
  - 已提交的 PNG 核對檔案 hash 與紀錄一致。

  省略期別時比對 `status.json` 列出的期別。有差異時回傳碼為 2。`--check` 不能與 `--republish` 同時使用。
- `--snapshots` 只能與 `--check` 一起使用，申報與 fact 改讀 `data/snapshots/`，見「快照」。
- `--republish TICKER SERIES PERIOD` 可重複指定；SERIES 是 `Q` 或 `FY`，ticker 與期別必須在這次處理的範圍內。
- 回傳碼：`0` 沒有期別失敗（Q4 不推算不算失敗）；`2` 有期別失敗或 `--check` 有差異；`1` 輸入錯誤。

## 快照

快照保存每份申報一定要有 SEC 原文才拿得到的資料，讓沒有原文的環境（例如 GitHub 的 CI、剛 clone repo 的人）也能對上線公司跑 `--check`。能由這些資料算出來的（數值、QName 解析、期間分類、申報篩選），讀快照時以目前的程式重算，不存在快照中。

```bash
npm run snapshot -- --tickers AAPL           # 由原文產生 data/snapshots/A/AAPL/ 的快照與申報清單
npm run snapshot -- --all --check            # 核對已提交的快照與原文重新產生的結果相同，不寫入
```

回傳碼：`0` 成功；`2` 寫入時有原文讀不到的申報（快照記錄為錯誤，清單印到 stderr），或 `--check` 有不同；`1` 輸入錯誤。

- **內容**：每份申報（每份 10-K、10-Q，含修正申報與 Q4 依賴的較早申報）一個檔案：
  - 申報篩選用到的申報包欄位：表單、期末日、申報日、申報包是否完整，以及主文件的檔名、是否為 inline XBRL、sha256、URL。
  - 文件宣告的 namespaces 與衝突的前綴、全部 dei。
  - 主文件的全部數值 fact（`ix:nonFraction`），不依任何公司 parser 篩選。每個 fact 保留 XBRL 原始欄位（fact id、concept、dimensions、期間、unit、顯示文字 `raw`、`scale`、`decimals`、`sign`、`format` 屬性原文、context id），以及決定重複值選擇的 HTML 位置 `table_index` 與 `order`；nil fact 另有 `nil: true`。換算後的數值（`value`、`value_error`）不存，讀快照時以目前的數字規則算出。

  原文讀不到的申報記錄錯誤原因，快照模式重現同一個 `comparison_errors`。
- **格式**：一行一個 fact（JSON Lines）。縮排的 JSON 約大一倍，Git 壓縮後兩者相近，一行一個 fact 讓工作目錄小一半。
- **快照只由申報與抽取程式決定**：一份申報公開後內容不會變，快照只隨從原文抽資料的程式（抽取程式，`revenue/extract.py`）的行為改變。
  - 抽取程式涵蓋 HTML 解析與表格編號、xmlns 宣告與衝突的前綴、context 與 unit、dei、`ix:nonFraction` 的文字與屬性，以及申報篩選用到的申報包欄位。數字規則與 `format` 的正規化（`ixbrl.py`）、QName 解析、期間分類（`xbrl.py`）與申報篩選（`filings.py`）在讀快照時執行，不在其中。
  - 快照記錄抽取程式的 hash，依 `extract.py` 的語法樹計算，不含註解、docstring 與排版。hash 不同時快照模式直接報錯，不以過期的快照計算。
  - 快照檔的編排由快照格式版本表示；版本不同時同樣報錯。
  - 抽取結果也取決於 lxml 的 HTML 解析，lxml 在 `requirements.txt` 鎖定確切版本，不在 hash 內。升級 lxml 時，在有原文的環境跑 `snapshot --all --check`；有差異就重產全部快照，與升級放在同一個 PR。
  - 快照與申報清單的申報不一致時直接報錯，包括快照檔名與記錄的 accession 不同、申報資訊（表單、日期）與清單不同。
- **同一條程式路徑**：快照模式與原文模式以同一段程式篩選申報，並由同樣的抽取內容建立 fact 清單（換算數值、解析 QName）；之後的選申報、期別、公司 parser、檢核、比較欄比對與 Q4 口徑都相同。
- **驗得到與驗不到**：
  - 快照模式驗得到 `revenue.json` 的數字、運算式、運算元與表格鍵（accession、文件 hash、表格編號），以及 `status.json` 的全部紀錄。
  - 快照沒有原文。證據以 fact 的 `table_index` 算出表格鍵，沿用已提交的表格 HTML 與 PNG，所以驗不到表格 HTML 的內容，也驗不到 fact 在原文中的節點核對。
  - 已提交的證據中沒有該表格時，該期失敗。
  - 快照模式不能寫入正式輸出，只能 `--check`。
- **何時產生與重產**：需要在有原文的環境執行，產生的快照與造成它的改動放在同一個 PR。
  - 下載了新的申報：產生該份申報的快照。
  - 改動抽取程式的行為（抽哪些欄位、怎麼抽）：重產全部公司。這類改動本來就只能對照原文驗證。
  - 改動證據元件時，另以原文跑 `--check` 驗證表格 HTML。

  | 改動 | 是否重產快照 |
  |---|---|
  | 公司 parser、utility | 不需要 |
  | 框架（組數值、流程、檢核、證據） | 不需要 |
  | 數字規則與 `format` 的正規化、QName 解析、期間分類、申報篩選 | 不需要；快照模式以新規則重算 |
  | 抽取程式的註解、docstring、排版 | 不需要 |
  | 抽取程式的行為 | 全部公司 |
- **容量**：以 18 家上線公司、243 份 10-K／10-Q 實測，每份申報平均約 1,900 個 fact（HD、AAPL 約 700，JPM、BAC 約 7,000），一個快照檔平均約 0.76 MB，zlib 壓縮後約 50 KB。每家約 13 份申報、約 10 MB（壓縮後約 0.7 MB）；1500 家的工作目錄約 15 GB，Git 壓縮後約 1 GB，每家每年 4 份申報，每年新增約 4.6 GB（壓縮後約 0.3 GB）。

### 兩種 CI 環境

| 環境 | 快照 | CI 怎麼跑 |
|---|---|---|
| GitHub 代管的 runner | 進 Git | `parse --all --check --snapshots`，不需要 SEC 原文 |
| 自架 runner | 不進 Git，Git 只留申報清單 | runner 保存 SEC 原文（`SEC_DATA_DIR`），以 `download --from-manifest` 依申報清單補齊；CI 以原文跑 `parse --all --check` |

- 快照進 Git 適用於公司數不多的時候：每次重產全部快照，Git 歷史就多一份全部快照的壓縮大小，公司數越多越重。公司數達到幾百家之前，改用自架 runner。
- 自架 runner 的資料持續累積：`download --from-manifest` 依申報清單下載每份申報包並逐檔核對 sha256，已下載的申報包沿用、不重抓，每次只補新的申報。第一次建資料要下載全部申報，受 SEC 存取速度限制，1500 家可能要跑好幾個小時。runner 要設定 `SEC_USER_AGENT`。
- 以原文跑 `--check` 時連證據一併核對（表格 HTML、fact 在原文中的節點），這是快照模式驗不到的部分。

## 測試

- 框架：以合成的 inline XBRL 申報與合成的公司 parser，測試每個流程步驟與每項檢核，不連網、不啟動 Chromium。
- 快照：測試快照往返等價、快照不存換算後的數值、快照模式不讀原文、數字規則在讀快照時套用、申報篩選與地區成員檢查走同一段程式、抽取程式 hash 不隨註解與排版改變且隨行為改變、申報清單一致性、新上線期別沒有快照與缺已提交證據會被抓到，以及改動快照中的一個值會被 `--check` 抓到。
- utility：每個 utility 有自己的測試。既有 utility 的測試不修改，測試要改代表行為變了，等於修改框架。CI 以此判斷：PR 修改或刪除 `tests/sec_revenue/parser_utils/` 中既有的測試檔時，重跑全部上線公司；只新增測試檔時不在此限。
- 公司：`data/revenue/` 中已提交的輸出就是回歸基準。`--check` 重跑 parser，與已提交的輸出逐欄比對。檢查範圍依改動而定：

  | 改動 | 重跑 |
  |---|---|
  | 一家公司的 parser | 該家 |
  | 新增 utility | 用到它的公司 |
  | 框架或既有 utility | 全部上線公司 |

## 待決定

- **期間長度與財年**：期間分類以天數範圍判斷，COST 的 16 週 Q4（112 天）與 36 週九個月累計（252 天）不在範圍內（#75）；ORCL 申報宣告的財年與實際不符（#77）。由框架放寬規則，或由公司 parser 指定期間與財年、框架只檢查合不合理。
- **附件中的 fact**：PGR 10-K 的財報在 EX-13，主文件只有 Schedule III（#76）。fact 清單是否納入附件的 inline XBRL；納入時，申報清單的範圍跟著擴大。
- **沒有 XBRL 標記的數字**：GOOGL 2025-03-31 以前的「Hedging gains (losses)」列沒有 XBRL 標記（#73）。依「數字只來自 XBRL fact」，fact 清單不含這類數字，GOOGL 這些期別無法上線，除非原則另開例外。
- **框架檔名**：預設起始日所在的 `revenue/engine.py` 等檔名，隨框架實作調整。
- **申報清單的位置**：申報清單放在 `data/snapshots/` 下；快照不進 Git 時，清單仍要進 Git。
