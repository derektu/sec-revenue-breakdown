# Parser 開發指南

這份指南寫給為新的 ticker 寫 parser 的開發者，包括 Codex 這類 coding agent。看完之後，你應該能在只改這個 ticker 的 parser 目錄的前提下，寫出 `parser.py` 與 `parser.md`、自己驗證到可以送 review，也知道哪些情況要停下來交給人判斷。

寫 parser 是新增一個 ticker 的其中一段。完整流程見 [開發流程](dev-workflow.md)，每一步都寫明 agent 可以做什麼、哪些要人做：

| 步驟 | 內容 | 本指南 |
|---|---|---|
| 1–3 | 下載 SEC 申報、`tickers.csv`、擷取對照資料 | |
| 4 | 評估 ticker | 第 2 步的程式 |
| 5 | 觀點建議 | 第 1 步 |
| 6 | 人決定觀點 | |
| 7 | 寫 parser、驗證、比對、自我驗收 | 第 2–9 步 |
| 8–10 | 獨立 review、判斷上線、上線之後 | 第 8 步的驗收清單 |

收到的交辦是流程中的哪幾步，就照 [開發流程](dev-workflow.md) 對應的步驟做；寫 parser 的部分照本指南。規則本身以 [`docs/architecture/parser.md`](../architecture/parser.md) 為準，這份指南只說怎麼照著做，不重述規則。動手前先讀：

- [`AGENTS.md`](../../AGENTS.md)：研究約束，特別是 parser 的兩條硬原則。
- `parser.md` 的「架構」「時點與寫 parser 的人的知識」「公司 parser 的介面」「自我檢核」。
- 範例：`libs/sec_revenue/companies/a/aapl/`（單一寫法、沒有調節項）與 `libs/sec_revenue/companies/c/cmcsa/`（依申報切換寫法、多個 fact 相加、調節項）的 `parser.py` 與 `parser.md`。

## 交辦時應該拿到的資訊

| 項目 | 例子 | 沒有時 |
|---|---|---|
| ticker | `MSFT` | 不開始 |
| SEC 原文已下載 | `download --dry-run` 沒有缺漏 | 請人下載，或依 [開發流程](dev-workflow.md) 的指令自己下載 |
| 對照資料 | `data/universe/references/<首字母>/<TICKER>/reference.json` | 請人擷取；沒有對照資料無法提出觀點建議 |
| 採用的觀點與分類清單 | 業務分部，三類加 Other；或「採用 Stock Analysis 的觀點」 | 通常沒有：由你在第 1 步提出建議，人決定後再寫 parser |

## 可以改的範圍

| 位置 | 可以做的事 |
|---|---|
| `libs/sec_revenue/companies/<首字母>/<目錄>/` | 新增並自由修改這個 ticker 的 `__init__.py`、`parser.py`、`parser.md` |
| `libs/sec_revenue/companies/<首字母>/__init__.py` | 首字母目錄還不存在時新增（空檔） |
| `libs/sec_revenue/parser_utils/` | 新增 utility（新函式或新檔案），連同 `tests/sec_revenue/parser_utils/` 的新測試，並加進 `parser_utils/__init__.py` 的匯出 |
| `data/revenue/<首字母>/<TICKER>/`、`data/snapshots/<首字母>/<TICKER>/` | 由 `parse`、`snapshot` 產生，不手改 |

其餘都不改：框架（`libs/sec_revenue/revenue/`）、既有 utility 的行為與既有測試、其他 ticker、`docs/architecture/`、`data/universe/tickers.csv`。覺得非改不可時，**停下來回報**，說明想改什麼、為什麼這個 ticker 需要、不改的話會怎樣，由人決定。改框架或既有 utility 等於改所有 ticker 的處理規則，即使只是一行、即使現有測試都還會過。

parser 目錄名是 ticker 小寫、非英數字元改為底線，例如 `b/brk_b`；`data/` 下的目錄則是首字母大寫加原樣 ticker，例如 `data/revenue/B/BRK-B`。

## 步驟

### 1. 提出觀點建議，等人決定

交辦時通常還沒決定觀點。打開 `reference.json`，看每個來源每期列了哪些分類、名稱是什麼、哪幾期有值；再用第 2 步的程式看 SEC 申報中有哪些營收 fact，確認每個來源的分類能不能從 XBRL fact 重現。對照資料缺某個來源時，用現有的來源提出建議，回報缺哪個來源；缺的來源不計入下面的多數判斷。查核範圍是期末日在預設起始日以後的期別，加上推算第一個 Q4 需要的較早申報：同財年在起始日以前的 10-Q，以及上一財年的 10-K；對照資料更早的期別不必重現，回報時寫明在範圍外、未確認。

回報後停下來，等人決定再寫 parser。回報內容：

- 各來源的分類，以及哪些能從申報重現、哪些不能、為什麼。
- 建議的觀點（產品別或業務分部）、分類清單與理由。各來源一致時通常就採用；不一致（面向、層級、名稱或範圍不同）時說明為什麼選這一個。
- 分類加總與總營收之間的差額（Corporate、Other、Eliminations 等）列成分類或調節項：多數來源列出的列成分類，多數沒列的列成調節項。「多數」只計算拆分到建議觀點（同一面向，層級或口徑不同也算）的來源；只有單一業務、沒有拆分的來源不計（LLY 只有 Stock Analysis 拆分，它列出 Other，所以 Other 是分類）。沒有來源拆分到這個觀點，或列與不列的來源一樣多時，依申報的表格呈現提出建議，列為待決事項。人改選別的觀點時重新判斷。「列出」只看期末日在預設起始日以後的期別：只在這之前有值的不算（XOM 的 TradingView 只在 FY2023 及更早列 Corporate and Financing）。來源只有欄名、每期都沒有值（`-`）的不算列出。
- 來源之間的分部營收口徑不同（抵銷分部間交易之前或之後，例如 CVX 的富途列抵銷前分部營收加一列抵銷，TradingView 列抵銷後）時，口徑是觀點的一部分，先決定口徑；來源不一致時列為待決事項。採抵銷後口徑時，分類已含抵銷，沒有抵銷項。採抵銷前口徑時，抵銷列成分類或調節項仍依上一條判斷（DIS 的 Eliminations 是調節項，CAT 的 Corporate Items and Eliminations 是分類）。
- 有沒有「停下來交給人」列出的情況，例如需要改框架才做得出來。

交辦時已指定觀點，就直接確認它能從申報重現；不能時同樣回報。

分類名稱以 SEC 原文的列標籤或欄標題為準（去掉 `Total`、`(SCS)` 這類修飾）；10-K 的列標籤全大寫時，用 10-Q 的寫法。名稱可以讀原文表格的文字確認：「數字只來自 XBRL fact」管的是數值，不管名稱。分類的輸出順序照採用的對照來源。名稱與對照來源的對應寫在 `parser.md`。

### 2. 在申報裡找 fact

先列出申報中跟營收有關的 fact，看清每個 fact 的**完整 dimensions**。下面的程式只讀已下載的原文，不寫入任何檔案（參數：ticker、accession、concept 要包含的字）。它列出申報中每個期間的 fact，包括比較欄（上一年度、去年同季、九個月累計）：Q4 口徑一致與比較欄比對會用 parser 組這些期間，重列也要從比較欄看。

```bash
SEC_DATA_DIR=~/sec-revenue-data .venv/bin/python - UPS 0001628280-26-008432 Revenue <<'EOF'
import os, sys
from pathlib import Path
sys.path.insert(0, "libs")
from datetime import date
from sec_revenue.revenue.filings import FilingSet

ticker, accession, word = sys.argv[1:4]
root = os.environ.get("SEC_DATA_DIR", "").strip()
if not root:
    sys.exit("請設定 SEC_DATA_DIR：已下載 SEC 原文的資料根目錄")
# 宣告 ATTACHMENTS 的公司要帶同樣的附件類型，例如 FilingSet(..., ticker, ("EX-13",))，才看得到附件中的 fact。
filings = FilingSet(Path(root).expanduser(), ticker)
filing = next(f for f in filings.filings if f.accession == accession)
facts = [f for f in filings.document(filing).facts if word in f.concept and f.start]
for fact in sorted(facts, key=lambda f: (f.end != filing.report_date, f.end, f.start or "", f.order)):
    dims = " ".join(f"{a}={m}" for a, m in fact.dimensions) or "（無維度）"
    column = "本期" if fact.end == filing.report_date else "比較期"
    where = fact.document or "主文件"
    days = (date.fromisoformat(fact.end) - date.fromisoformat(fact.start)).days + 1
    print(column, f"{fact.start}~{fact.end}", f"{days} 天", fact.concept, dims, fact.value, where, f"表格 {fact.table_index}", sep="\t")
EOF
```

`SEC_DATA_DIR` 是 SEC 原文的資料根目錄，換成你 `.env` 中設定的路徑；程式不讀 `.env`，沒有設定時直接結束。財報在附件的公司（例如 PGR 10-K 的 EX-13），`FilingSet` 帶上 `parser.py` 的 `ATTACHMENTS`；每一列印出 fact 所在的文件（主文件或附件檔名），表格編號屬於那份文件。

worktree 中的 agent 以 heredoc（`<<'EOF'`）執行多行程式時常被權限規則擋下：把程式存成 scratchpad 中的檔案，以 `.venv/bin/python <檔案> UPS 0001628280-26-008432 Revenue` 執行。

每份申報的 accession、表單、期末日與申報日，可以把最後的迴圈換成 `for f in filings.filings: print(f.accession, f.form, f.report_date, f.filing_date)` 列出。

找 fact 的要點：

- **對著原文表格逐列找，不只用 concept 名稱搜**：concept 名稱可能與列標籤不符。GOOGL 在期末 2025-06-30 的 10-Q 之前的申報中，Hedging gains (losses) 列標的是 `us-gaap:GainLossOnOilAndGasHedgingActivity`（油氣避險），用 `Revenue` 搜不到。以 `table_index` 或 XBRL viewer 找到營收表，表上每一列的數字都要對到一個 fact；對不到才是沒有標記。
- **每一份申報都要看，包括 10-K**。只看最新一份 10-Q 選出的寫法，常在某一份 10-K 或較早的 10-Q 找不到。
- **範圍以前的上一份 10-K 也要組得出來**：判斷範圍內第一個 Q4 的口徑時，框架用 parser 從上一財年的 10-K 組出年度值（見 `parser.md` 的「Q4 口徑一致」）。那份 10-K 的寫法也要涵蓋；組不出來時口徑判斷為「無法判斷」，Q4 照常推算並註記，不會報錯，所以要自己確認。
- **dimensions 要完全相同**：`find` 是精確比對，fact 多一個或少一個維度都不算。例如 NVDA 的分部 fact 另帶 `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；UPS FY2025 10-K 的 `ups:SupplyChainSolutionsMember` 只出現在帶 `srt:ProductOrServiceAxis` 的細項 fact 上。
- **分部 fact 的寫法每份申報都不同時，找穩定的同值 fact**：NEE 分部表的 FPL 至少有四種維度組合，但子公司的法律實體 fact（`dei:LegalEntityAxis`）每份申報都有且數值相同。可以選這個穩定的 fact，在 `parser.md` 寫明每份申報兩者相等的依據；其他分類與總營收都取各自的 fact、沒有以總營收倒算的分類時，法律實體值與分部值將來不同會讓加總檢核失敗。
- **同一項在不同申報的加數組成不同時，要有等值證據**：例如 CVX 的上下游到 2024 Q3 10-Q 為止取帶產品軸的合計，FY2024 10-K 起取美國＋非美國相加；XOM 的 Corporate and Financing 銷售在 FY2024 10-K 起沒有自己的 fact，由合併銷售減 `ConsolidationItemsAxis=OperatingSegmentsMember` 的分部合計組成。成員或 concept 不同用 `one_of`；加數組成不同時，以 `isinstance(..., Missing)` 判斷這份申報有沒有那個 fact。Q4 的年度與九個月累計、第一個 Q4 的口徑依據、比較欄，都可能跨兩種寫法。兩種寫法不相等時，Q4 口徑一致會讓 Q4 不推算，比較欄比對會留下差異標記，但都不擋上線，Q4 的相減本身也不核對兩種寫法。所以 `parser.md` 要列出兩種寫法在重疊期別逐一相等的證據（accession 與數值，通常是較晚申報的比較欄對原申報的值）；較晚的申報只作證據，不作運算元。相減組成的調節項，加總檢核核對的是分類加總等於分部合計。
- **用表格編號對照原文**：同一個數字常在多張表各標一次；分類的 fact 與總營收的 fact 最好在同一張表，證據截圖較少。在 SEC 的 XBRL viewer（`revenue.json` 運算元的 `ixviewer_url`）可以看 fact 在原文中的位置。
- **總營收用合併 fact**，通常是不帶維度的那個，不是只帶 `ConsolidationItemsAxis=OperatingSegmentsMember` 的分部合計；申報有分部以外的營收時兩者不同。分類採用特殊口徑時，總營收跟著分類的口徑走（例如 BAC 的 FTE），與 GAAP 的差額寫在 `parser.md`。分類只取銷售營收、合併營收另含權益法收益或其他收入時（XOM），可以在第 1 步提議總營收改用同口徑的合併銷售 fact，即使它帶 `srt:ProductOrServiceAxis` 之類的維度；它必須是合併數，不能是分部合計；與不帶維度的合併營收的差額寫在 `parser.md`。

### 3. 寫 `parser.py`

以 AAPL 為起點。介面（`TICKER`、`VIEW`、`TOTAL`、`compose`、`categories`）與型別見 `parser.md` 的「公司 parser 的介面」；可用的 utility 見 `libs/sec_revenue/parser_utils/facts.py`。常見寫法：

| 情況 | 寫法 | 例子 |
|---|---|---|
| 一個分類一個 fact | `put(result, "category", 名稱, find(filing, request, concept, {軸: 成員}))` | AAPL |
| 同一個數字在不同申報用不同 concept 或成員 | `one_of(filing, request, (concept1, dims1), (concept2, dims2))`；每份申報都找每一種寫法，同一份申報兩種都有時數值必須一致 | AMZN、MCD、UNH、CAT |
| 申報沒有分類需要的小計 | `put` 傳多個 term：`put(result, "category", 名稱, find(...), find(...))` | LIN 的 Industrial Gases、CMCSA 的 Corporate and Other |
| 要減掉的項目 | `find(..., weight=-1)` | |
| 分類加總與總營收之間的合法差額 | `put(result, "reconciling", 名稱, ...)` | CMCSA 的 Eliminations、JPM 的 Reconciling items |
| 總營收 | `put(result, "total", TOTAL, find(filing, request, concept))` | 每個 ticker |
| 寫法在某份申報改變 | 優先用 `one_of` 讓兩種寫法在任何申報都成立；分類集合也不同時，依這份申報在該期間有沒有某一結構的 fact 選擇（見表下說明）；非依日期不可時，以 `filing.report_date` 切換 | CMCSA、UPS、JPM、MSFT、DIS |

依申報內容選結構時，用 `isinstance(find(filing, request, concept, {軸: 成員}), Missing)` 判斷（MSFT 查新結構的成員、DIS 查舊結構的成員）。`find` 經 namespace URI 比對；不要直接比 concept 或成員字串。

寫的時候注意：

- 檔頭 docstring 一句話說明觀點與分類；用到 `us-gaap:StatementBusinessSegmentsAxis` 時，寫明它的成員是業務別。
- 找不到的項目交給 `put` 記到 `missing`，不要自己補值、不要回傳 0。
- `categories(day)` 回答「這一天這個 ticker 有哪些分類與調節項，依輸出順序」。它和 `compose` 對主申報交回的分類必須一致。分類集合改變的日期，就是 `categories` 切換的日期：取新結構第一份主申報所涵蓋那一季的**起日**，也就是最後一份舊結構主申報期末日的隔天（UPS 的 `2025-01-01` 是 Q1 10-Q；JPM 的 `2024-04-01` 是 Q2 10-Q；CAT 新結構第一份是 FY2025 10-K，取 Q4 起日 `2025-10-01`）。不要用那份申報的期末日：框架判斷 Q4 推算條件時，逐日問財年起日到 Q3 期末的 `categories`；新結構從財年第一季開始時，切在期末日會讓第一季期末日之前的日子仍回答舊分類，那一年的 Q4 被誤判為不推算。`categories` 至少要涵蓋範圍內第一期所在財年的**上一財年期末日**以後：Q4 推算條件從財年起日問起；第一個財年沒有已上線的上一財年 FY 時，Q4 口徑一致以上一份 10-K 組年度值，並核對 `categories(上一財年期末日)`。以預設起始日處理時，更早的日期框架不會問；`categories` 對那些日期的回答不保證正確（可以照常回傳現行分類），以 `--start` 處理更早的期別前要先擴充涵蓋範圍。`parser.md` 寫明涵蓋的下限，以及現行結構從哪一份申報開始（例如 JNJ 的兩分部始於 2023 年 Q3 10-Q，更早是三分部）。
- 依日期切換時，常數旁註明是哪一份申報開始改變（accession 與期末日），`parser.md` 也寫。
- 不寫死 fact id、數值與沒有理由的特定期別例外；每一期照該期申報自己的分類結構與名稱組。詳見 `parser.md` 的「時點與寫 parser 的人的知識」。這條管的是 `parser.py`：`parser.md` 的查證與差異說明可以引用 accession、fact id 與數值作為證據。
- 不 import 其他 ticker 的 parser；寫法相近也各寫各的。

### 4. 寫 `parser.md`

照 AAPL、CMCSA 的章節：

```markdown
# <TICKER> parser

## 觀點
採用的觀點與分類；各對照來源列了什麼、怎麼對應；申報中不採用的其他拆分與原因（例如地區）。
用到 us-gaap:StatementBusinessSegmentsAxis 時，寫明成員是業務別而不是地區。

## 分類與 tag
每個分類（含調節項與總營收）的 concept 與完整 dimensions；寫法切換從哪一份申報（accession、期末日）開始；分類名稱取自原文哪裡。

## 期別與推算
財年與季末日（52／53 週制要寫）；Q1–Q3、Q4、FY 各自怎麼來；哪些 Q4 不推算與原因。

## 數字在原文的位置
10-Q、10-K 中是哪張表。同一個 fact 常標在多張表，框架選來當證據的表格（`data/revenue/` 各期 evidence 檔名的 `-t<編號>`）不一定是分部表；寫證據實際取自的表格，編號依正式輸出的 evidence 檔名，不寫「尚無截圖」這類暫時狀態。必列的是正式證據的表格，以及作口徑依據的上一份 10-K；後者沒有證據檔，編號取第 2 步程式列出的表格編號。比較欄的表格不必逐一列出，等值證據引用比較欄時寫明表格編號。一張表跨頁時各段有不同的編號，寫明證據所在的各段含哪些列（例如 JNJ 2024 年 Q1 10-Q 的分部銷售表跨五頁，Innovative Medicine 的合計在 t62，MedTech 與總營收在 t64）。

## 已知的重複 fact（有的話）

## <重列或重分類>（有的話）
哪一份申報、重列了哪些期別、數字怎麼變；對各期的影響。

## 驗證
與採用的對照來源逐期比對的結果；每一筆差異的原因與證據；來源沒有資料、沒有比對的期別。

## 比較欄
差異標記的來源與內容；沒有時寫明沒有。
```

`parser.md` 描述 parser 現在的做法：

- 不寫開發過程、改了什麼，也不寫 `--check` 是否通過這類執行結果（由 CI 判定）。
- 路徑照 Git 中的大小寫（`data/universe/references/L/LLY/`）。macOS 不分大小寫，寫錯看不出來，用 `git ls-files` 核對。
- 只作第一個 Q4 口徑依據的上一財年 10-K 沒有證據檔，列在「數字在原文的位置」時寫明它的用途。

### 5. 跑 parse，看每一期的結果

載入公司 parser 時框架要求目錄中有 `parser.md`，沒有時整個 ticker 載入失敗、一期都不處理。第一次跑 parse 時 `parser.md` 還沒寫完，先放一份只有標題的檔案。用到 `us-gaap:StatementBusinessSegmentsAxis` 時，這份檔案也要先寫明這個軸的成員是業務別。

```bash
.venv/bin/python scripts/sec_pipeline.py parse --tickers MSFT
```

`parse` 以 Chromium（Playwright）截取證據圖，執行環境必須能啟動瀏覽器；`--check` 不截圖，不需要。沙箱等環境擋住 Chromium 時，需要新截圖的期別在「證據完整」失敗，`reason` 是「Chromium 無法啟動」。這是環境問題，不是 parser 的結果：停下來回報，由能啟動瀏覽器的人或 agent 刪掉這個 ticker 未提交的輸出後重跑。`parser.md` 的「驗證」與「比較欄」以那次重跑的 `status.json` 為準，不寫環境錯誤。

`scripts/sec_pipeline.py` 讀 repo 根目錄的 `.env`；沒有 `.env` 的 worktree，在指令前加 `SEC_DATA_DIR=<資料根目錄>`（已設定的環境變數優先於 `.env`），或用 `--data` 指定。`parse`、`snapshot` 與以原文跑的 `--check` 都要讀原文；`--check --snapshots` 不需要。

stderr 每期印一行（`MSFT Q 2024-09-30 published`），stdout 是完整的 JSON。每一期的狀態與失敗原因在 `data/revenue/<首字母>/<TICKER>/status.json`，可以這樣看摘要（序列、期別、狀態、檢核名稱、差異標記數）：

```bash
jq -r '.periods | to_entries[] | .key as $s | .value | to_entries[] | [$s, .key, .value.status, (.value.check // ""), ((.value.differences // []) | length)] | @tsv' data/revenue/M/MSFT/status.json
```

失敗的期別看 `reason`。常見的訊息與原因：

| 檢核 | 訊息大意 | 多半是 | 怎麼查 |
|---|---|---|---|
| fact 存在且唯一 | 找不到某個分類或總營收（`put` 記在 `missing` 的項目） | dimensions 不完整、成員或 concept 在這份申報改名；數字在附件的 inline XBRL，公司 parser 沒有以 `ATTACHMENTS` 宣告這類附件 | 用第 2 步的程式看這份申報的 fact |
| 定義唯一 | 交回的分類順序或集合與 `categories(期末日)` 不同 | `categories` 的切換日期與 `compose` 不一致；漏列分類卻沒有記錄原因 | 對照 `categories` 與 `compose` 的切換條件 |
| 加總 | 分類加總不等於總營收 | 漏了調節項（Corporate、Eliminations、All Other）；總營收選到分部合計；分類選到另一組分部 fact | 對照原文分部表的每一列 |
| fact 存在且唯一 | 重複 fact 數值不一致，或前綴宣告衝突 | `one_of` 的兩種寫法其實是不同數字 | 看兩種寫法的 fact 各在哪張表 |
| 地區成員完整 | 地區軸的成員沒有全部列入 | 運算式只列了部分地區成員 | 把該軸同 concept、同其他 dimensions 的全部成員列入運算式 |
| 單位與精度 | decimals 缺漏或粗於百萬位 | 申報本身的標記 | 回報，不能在 parser 處理 |
| fact 清單合併 | 主文件與附件有同一個 context、unit 或 fact id | 宣告的附件與主文件不是同一組 inline XBRL 標記 | 回報，不能在 parser 處理 |
| Q4 期間、財年與季別、選申報 | 期間長度不合，或推不出財年 | 季度長度不在框架的預設範圍內（例如 COST 的 16 週 Q4）；自訂 `FISCAL_YEAR = "prior_annual"` 時，10-Q 之前沒有相接的上一財年 10-K | 期間長度：確認公司的季度長度，以 `DURATION_DAYS` 自訂（見 `parser.md` 的「預設與自訂」與「自訂點」），範圍多寬由這家公司決定，理由寫在 `parser.md`；缺 10-K 時下載後重跑 |

`not_derived` 不是失敗：Q4 推算條件或 Q4 口徑一致不成立時，Q4 依規則留空，FY 照常輸出（規則見 `parser.md` 的「框架流程」）。你要做的是在 `parser.md` 寫明是哪一份申報、哪些分類造成的。

開發期間每次修改 parser 後，先刪掉這個 ticker 尚未提交的輸出再重跑。已寫入的期別受已上線保護，不會被新的結果覆蓋，舊的失敗紀錄與標註也會留著：

```bash
rm -rf data/revenue/M/MSFT
.venv/bin/python scripts/sec_pipeline.py parse --tickers MSFT
```

只刪自己這個 ticker、而且還沒進 Git 的輸出。已提交的輸出要改，用 `--republish`，必須由人決定。

### 6. 與對照資料逐期比對

把每一期每個分類的值與**採用的來源**比，差異逐筆寫進 `parser.md` 的「驗證」。其他來源不必比對。採用的來源沒有某些期別（例如只有季度、沒有年度）時，那些期別不比對，在「驗證」寫明。比對工具（#46）完成前由開發者自己比對。對照資料的格式（來源、期別、`display` 與 `usd`）見 [對照資料格式](../architecture/universe.md#referencejson)。

- **在顯示精度內**：對照來源只顯示到某一位（例如 `7.39B` 到 0.01B、`202M` 到 1M）。我們的值與來源的 `usd` 相差不超過該顯示單位的一半，加上我們運算元的精度誤差（每個運算元 decimals 單位的一半；Q4 的每個加數有年度與九個月兩個運算元），就是一致；超過就是差異，要寫原因。

- **期別對齊**：Stock Analysis 用期末日（季底不是曆年季底的 ticker 會對齊到曆年季底）；富途用申報宣告的財年與季別；TradingView 用財年多數月份所在的曆年（NVDA FY2026 標 2025、ORCL FY2026 標 2025），財年在 6 月底結束、兩個曆年各占 6 個月時標結束的那一年（MSFT、PG 的 FY2026 標 2026）。
- **分類改名有沒有改範圍**：拿較晚申報的比較欄（新名稱）與原申報（舊名稱）的同一期比；較晚申報沒有列那一季時，用累計相減推回（例如半年減 Q2 得 Q1）。各分類的值在雙方運算元的精度誤差內相同，就是純改名（LLY 2024 年的 Cardiometabolic Health）。這些較晚的申報只在 `parser.md` 當證據，不用來組數字，也不改早期期別的分類名稱；名稱仍跟各期申報。
- **差異多半是重編**：對照來源常用事後重編的數字，我們用申報當時的原值。先查較晚的申報有沒有重列這一期（差異標記的申報列示值與對照來源相同，就是重編），再判斷是不是 parser 錯了。例子：UPS 2024 年 Q4、BAC 2025 年 Q1–Q3、CMCSA 2025 年各季。
- **對照來源本身的錯**：富途的 Q4 偶有錯值（UPS 2024 年 Q4 是負數），Stock Analysis 偶有期別錯置（CMCSA 2026 年 Q1、Q2 對調；GOOGL 2024-06-30 的 Hedging gains (losses) 填了 2023 年 Q2 的值）、單一數字錯值（MSFT 期末 2026-03-31 的 More Personal Computing）。富途的 Q4 也可能在同一季混用兩種算法：PGR 2025 Q4 的一列是全年值，另兩列是 0 減前三季累計，三列相加才等於 Q4。判定為來源錯誤，三條都要成立：(a) 當期申報的表格中，這個分類那一列的值等於我們的值（列標籤、concept、完整 dimensions 都對得上），而且本期加總檢核通過；業績新聞稿有列時也要一致，但它與申報同源，只作補充。(b) 較晚的申報沒有重列這一期。(c) 來源本身前後矛盾，而且矛盾的差額就是這筆差異（分類加總與總營收、或四季加總與年度，正好差這個數）；或另一個對照來源與我們的值一致。成立時寫明是來源錯誤與上述證據，來源為什麼錯（例如誤取了哪個數字）不必追；不成立時是「原因未確認」。
- **用其他 SEC 文件解釋差異**：差異的原因有時在業績新聞稿（8-K 附件 99.1）或同一份申報沒有 XBRL 標記的表格。`download` 不下載 8-K，直接在 sec.gov 讀原文。這些文件只用來解釋差異，不提供輸出的數字，也不存檔；在 `parser.md` 記 accession、附件與所列的數值。
- **不要為了對上對照資料改 parser**：差異照實記錄。

### 7. 產生快照

CI 以快照對全部 ticker 跑 `parse --check`，所以新的 ticker 要連同快照一起提交：

```bash
.venv/bin/python scripts/sec_pipeline.py snapshot --tickers MSFT
.venv/bin/python scripts/sec_pipeline.py parse --tickers MSFT --check --snapshots
```

只修改 parser 不需要重產快照。`--check --snapshots` 沿用 `data/revenue/` 中已有的證據（表格 HTML 與 PNG，不需要先 commit），所以要先有一次成功的正式 parse；沒有證據時它會失敗（見第 5 步的 Chromium 說明）。

### 8. 自我驗收

全部通過才送 review（還沒 commit 的改動，見 [從寫完到合併](dev-workflow.md#從寫完到合併)）：

```bash
.venv/bin/python scripts/sec_pipeline.py parse --tickers MSFT --check               # 以原文重跑，與輸出逐欄比對
.venv/bin/python scripts/sec_pipeline.py parse --tickers MSFT --check --snapshots   # 以快照重跑（CI 跑這一項）
npm run check                                                                         # unit test、對照資料驗證、全部 ticker 的快照回歸
```

兩種 `--check` 都要 `"differences": []`、`"complete": true`，回傳碼 0。

驗收清單：

- [ ] 只改了這個 ticker 的目錄、自己新增的 utility 與測試，`data/revenue/`、`data/snapshots/` 中這個 ticker 的產出，以及流程前段留下的這個 ticker 的 `wip` 列與對照資料。
- [ ] 範圍內每一期都是 `published` 或有理由的 `not_derived`；`failed` 的期別在 `parser.md` 寫明原因並回報。
- [ ] 每個分類、調節項與總營收在 `parser.md` 有 concept 與完整 dimensions；每個依日期的切換寫明從哪一份申報開始；同一項的加數組成在不同申報不同時，有重疊期別逐一相等的證據；分類改名時，有重疊期別新舊名稱同值的證據（第 6 步）。框架不檢查改名與加數組成是否改變範圍，只靠這些證據。
- [ ] 不依後來的申報組早期期別；沒有寫死的 fact id、數值或特定期別例外。
- [ ] 與採用的對照來源逐期比對，每一筆差異都有原因與證據；原因未確認的寫成未確認，不寫成一致。
- [ ] 差異標記（`differences`）都在 `parser.md` 的「比較欄」說明。
- [ ] 兩種 `--check` 與 `npm run check` 都通過。

### 9. PR

一個 ticker 一個 PR。獨立 review 修完、人核准後才 commit 並開 PR，CI 通過後合併（見 [從寫完到合併](dev-workflow.md#從寫完到合併)）。PR 說明附 review 摘要：

```markdown
Refs #<issue>

- 觀點與分類：<觀點>，<分類清單>；調節項：<有或無>
- 寫法切換：<哪一份申報開始改變，或「不切換」>
- 新增的 utility：<名稱與用途，或「無」>

## 結果
- 期別：<範圍>，published <n>、not_derived <n>（<原因>）、failed <n>
- 對照比對：<來源> 每期在顯示精度內／差異 <n> 筆（見 parser.md「驗證」）
- 差異標記：<n> 筆（見 parser.md「比較欄」）

## 驗證
- parse --check（原文）、parse --check --snapshots：沒有差異
- npm run check：通過

## 獨立 review
- 結論：<通過>；修正的問題：<清單，或「無」>

## 人的決定
- <核准前人決定的事項，或「無」>
```

寫 parser 時不改 `tickers.csv`。`status` 等欄位的值由人在判斷能上線時決定，人核准後由 agent 寫入，與 parser、這個 ticker 的對照資料在同一個 commit（見 [開發流程](dev-workflow.md) 第 9 步）。

## 常見陷阱

- **成員或 concept 在財年中途改名**：NVDA 的分部成員、CAT 的 Corporate Items 成員、UPS 2025 年的分部成員。逐份申報確認，用 `one_of` 或依申報切換。
- **10-K 與 10-Q 寫法不同**：AMZN 的 Advertising（10-K `us-gaap:AdvertisingMember`、10-Q `amzn:AdvertisingServicesMember`）、MCD 的直營餐廳營收、UNH 只差大小寫的成員。Q4 的年度與九個月累計分別來自 10-K 與 10-Q，兩種寫法都要找得到。
- **某個寫法只在 10-K 消失**：UPS 的 `ups:SupplyChainSolutionsMember` 在 2025 年各 10-Q 都有，FY2025 10-K 只剩 `us-gaap:CorporateNonSegmentMember`。
- **同一個 concept 有兩組分部 fact**：BRK-B 的 `us-gaap:Revenues` 有只帶分部軸的對外營收，也有帶 `ConsolidationItemsAxis=OperatingSegmentsMember` 的分部表數字。以分部表與對照來源確認用哪一組。
- **一個分類由多個分部相加**：LIN 的 Industrial Gases ＝ Americas ＋ EMEA ＋ APAC。地區軸 `srt:StatementGeographicalAxis` 只能以該軸全部成員相加出現（規則見 `parser.md` 的「公司 parser 的介面」）。
- **總營收的口徑**：BAC 用 FTE、JPM 的分部是 managed basis。總營收跟著分類口徑；分類與報告總營收之間的調整列為調節項。
- **年報改了分類口徑**：UPS 2024 年、BAC 2025 年、HD 每年的 10-K 重列上一財年，Q4 因口徑一致不成立而 `not_derived`，這是預期結果。年報沒有重列、新口徑要到之後的 10-Q 才看得出來時（KO 2025 年），Q4 照常推算，之後的差異標記會揭露。口徑在 10-Q 就改了、同財年的 10-Q 與年報都重列上一財年時（MSFT FY2025），年度與九個月累計雖然同口徑，Q4 仍因口徑一致不成立而 `not_derived`；這是規則的結果，不是 parser 錯，不要自己算 Q4 補值。
- **分類改名**：名稱跟各期申報，所以改名也改變 `categories` 的分類集合。財年內改名（LLY 2024 年 Q2 10-Q）或年報才改名（CAT FY2025 10-K，同時也有口徑變更），那一年的 Q4 都因 Q4 推算條件不成立而 `not_derived`。
- **10-K/A、10-Q/A**：主申報取同一期末日申報日最早的原申報，修正申報只參與差異標記（TSLA、DIS 的 Part III 10-K/A；DIS 2024-01-24 那份沒有營收 fact）。parser 不需要特別處理。
- **52／53 週制**：HD、NVDA、AAPL 的季末日不是月底，期別以實際期末日識別，不要改成曆季底。框架以天數判斷期間，預設範圍是單季 84–98 天（12–14 週，含 53 週年度的 14 週 Q4，例如 DIS FY2026）、六個月 175–189 天、九個月 266–280 天、年度 357–378 天。季度長度不在預設範圍內的公司，在 `parser.py` 以 `DURATION_DAYS` 自訂四種期間的範圍，並在 `parser.md` 寫明公司的季度長度：例如 COST 的 12／12／12／16 週季度（53 週年度的 Q4 為 17 週）宣告單季 84–119、六個月 168–189、九個月 252–280、年度 357–378。框架只檢查格式（四種期間都有、正整數、最短不大於最長、由短到長且互不重疊，見 `parser.md` 的「自訂點」）；範圍要多寬由這家公司決定，取能涵蓋實際季度長度的最窄範圍，並在 `parser.md` 寫明理由。
- **10-Q 宣告的財年錯了**：財年預設取申報宣告的值。公司在 10-Q 宣告錯財年時（ORCL 2026-08-31 的 10-Q 宣告 2026，實為 2027），在 `parser.py` 宣告 `FISCAL_YEAR = "prior_annual"`，由框架以前一份 10-K 推算 10-Q 的財年；推算需要上一財年的 10-K，所以範圍內第一季之前的 10-K 也要下載。
- **多個 CIK**：前身與繼受實體以 `tickers.csv` 的 `cik` 欄位 `;` 分隔，由人維護；parser 不處理 CIK。
- **分部軸的成員是地區**：AAPL 的 `us-gaap:StatementBusinessSegmentsAxis` 是 Americas、Europe 等地區，不能用。用這個軸時，`parser.md` 必須寫明成員是業務別：`parser.md` 沒提到這個軸時 parse 會報錯，說明內容由 review 檢查。

## 停下來交給人

以下情況不要自己決定，停下來回報現況、選項與你的建議：

- **觀點**：寫 parser 之前，觀點與分類一定由人決定（第 1 步）。
- **要改框架或既有 utility**：例如需要同時讀兩份申報才組得出一期。這是改變框架提供資料的方式，不能自訂。公司不符合框架的某個預設、而框架還沒有對應的自訂點時，建議的做法是新增自訂點、由這家公司的 parser 自訂，不放寬所有 ticker 共用的預設（見 [parser.md](../architecture/parser.md) 的「預設與自訂」）。數字在同一份申報附件的 inline XBRL（例如 PGR 10-K 的 EX-13）由自訂點 `ATTACHMENTS` 處理，不需要改框架。
- **只能違反兩條硬原則才做得出來**：例如需要的數字沒有 XBRL 標記、要用之後的申報決定早期期別怎麼組。判定沒有標記之前，先照第 2 步對著原文表格逐列找。不要繞過。
- **差異解釋不了**：與對照來源的差異不是重編、也不是來源錯誤，或你無法確認是哪一種。
- **已提交的輸出要改**：任何需要 `--republish` 的情況。
- **上線**：`tickers.csv` 的 `status`、`adopted_source`、`stability_score` 的值由人決定。
