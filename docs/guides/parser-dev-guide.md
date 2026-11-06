# Parser 開發指南

這份指南寫給為新的 ticker 寫 parser 的開發者，包括 Codex 這類 coding agent。看完之後，你應該能在只改這個 ticker 的 parser 目錄的前提下，寫出 `parser.py` 與 `parser.md`、自己驗證到可以送 review，也知道哪些情況要停下來交給人判斷。

寫 parser 是新增一個 ticker 的其中一段。完整流程見 [開發流程](dev-workflow.md)，每一步都寫明 agent 可以做什麼、哪些要人做：

| 步驟 | 內容 | 本指南 |
|---|---|---|
| 1–4 | 選 ticker、`tickers.csv`、下載 SEC 申報、擷取對照資料 | |
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

交辦時通常還沒決定觀點。打開 `reference.json`，看每個來源每期列了哪些分類、名稱是什麼、哪幾期有值；再用第 2 步的程式看 SEC 申報中有哪些營收 fact，確認每個來源的分類能不能從 XBRL fact 重現。

回報後停下來，等人決定再寫 parser。回報內容：

- 各來源的分類，以及哪些能從申報重現、哪些不能、為什麼。
- 建議的觀點（產品別或業務分部）、分類清單與理由。各來源一致時通常就採用；不一致（面向、層級、名稱或範圍不同）時說明為什麼選這一個。
- 分類加總與總營收之間的差額（Corporate、Other、Eliminations 等）列成分類或調節項：多數來源列出的列成分類，多數沒列的列成調節項。
- 有沒有「停下來交給人」列出的情況，例如需要改框架才做得出來。

交辦時已指定觀點，就直接確認它能從申報重現；不能時同樣回報。

分類名稱以 SEC 原文的列標籤或欄標題為準（去掉 `Total`、`(SCS)` 這類修飾），與對照來源的名稱對應寫在 `parser.md`。

### 2. 在申報裡找 fact

先列出申報中跟營收有關的 fact，看清每個 fact 的**完整 dimensions**。下面的程式只讀已下載的原文，不寫入任何檔案（參數：ticker、accession、concept 要包含的字）：

```bash
.venv/bin/python - UPS 0001628280-26-008432 Revenue <<'EOF'
import os, sys
from pathlib import Path
sys.path.insert(0, "libs")
from sec_revenue.common.dotenv import load_dotenv
from sec_revenue.revenue.filings import FilingSet

ticker, accession, word = sys.argv[1:4]
load_dotenv(Path(".env"))
filings = FilingSet(Path(os.environ.get("SEC_DATA_DIR") or "data").expanduser(), ticker)
filing = next(f for f in filings.filings if f.accession == accession)
for fact in filings.document(filing).facts:
    if word in fact.concept and fact.end == filing.report_date and fact.duration:
        dims = " ".join(f"{a}={m}" for a, m in fact.dimensions) or "（無維度）"
        print(fact.duration, fact.concept, dims, fact.value, f"表格 {fact.table_index}", sep="\t")
EOF
```

每份申報的 accession、表單、期末日與申報日，可以把最後的迴圈換成 `for f in filings.filings: print(f.accession, f.form, f.report_date, f.filing_date)` 列出。

找 fact 的要點：

- **每一份申報都要看，包括 10-K**。只看最新一份 10-Q 選出的寫法，常在某一份 10-K 或較早的 10-Q 找不到。
- **dimensions 要完全相同**：`find` 是精確比對，fact 多一個或少一個維度都不算。例如 NVDA 的分部 fact 另帶 `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；UPS FY2025 10-K 的 `ups:SupplyChainSolutionsMember` 只出現在帶 `srt:ProductOrServiceAxis` 的細項 fact 上。
- **用表格編號對照原文**：同一個數字常在多張表各標一次；分類的 fact 與總營收的 fact 最好在同一張表，證據截圖較少。在 SEC 的 XBRL viewer（`revenue.json` 運算元的 `ixviewer_url`）可以看 fact 在原文中的位置。
- **總營收用不帶維度的合併 fact**，不是只帶 `ConsolidationItemsAxis=OperatingSegmentsMember` 的分部合計；申報有分部以外的營收時兩者不同。分類採用特殊口徑時，總營收跟著分類的口徑走（例如 BAC 的 FTE），與 GAAP 的差額寫在 `parser.md`。

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
| 寫法在某份申報改變 | 優先用 `one_of` 讓兩種寫法在任何申報都成立；非依日期不可時，以 `filing.report_date` 切換 | CMCSA、UPS、JPM |

寫的時候注意：

- 檔頭 docstring 一句話說明觀點與分類；用到 `us-gaap:StatementBusinessSegmentsAxis` 時，寫明它的成員是業務別。
- 找不到的項目交給 `put` 記到 `missing`，不要自己補值、不要回傳 0。
- `categories(day)` 回答「這一天這個 ticker 有哪些分類與調節項，依輸出順序」。它和 `compose` 對主申報交回的分類必須一致。分類集合改變的日期，就是 `categories` 切換的日期。
- 依日期切換時，常數旁註明是哪一份申報開始改變（accession 與期末日），`parser.md` 也寫。
- 不寫死 fact id、數值與沒有理由的特定期別例外；每一期照該期申報自己的分類結構與名稱組。詳見 `parser.md` 的「時點與寫 parser 的人的知識」。
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
10-Q、10-K 中是哪張表。

## 已知的重複 fact（有的話）

## <重列或重分類>（有的話）
哪一份申報、重列了哪些期別、數字怎麼變；對各期的影響。

## 驗證
與每個對照來源逐期比對的結果；每一筆差異的原因與證據。

## 比較欄
差異標記的來源與內容；沒有時寫明沒有。
```

`parser.md` 描述 parser 現在的做法，不寫開發過程或改了什麼。

### 5. 跑 parse，看每一期的結果

```bash
.venv/bin/python scripts/sec_pipeline.py parse --tickers MSFT
```

stderr 每期印一行（`MSFT Q 2024-09-30 published`），stdout 是完整的 JSON。每一期的狀態與失敗原因在 `data/revenue/<首字母>/<TICKER>/status.json`，可以這樣看摘要（序列、期別、狀態、檢核名稱、差異標記數）：

```bash
jq -r '.periods | to_entries[] | .key as $s | .value | to_entries[] | [$s, .key, .value.status, (.value.check // ""), ((.value.differences // []) | length)] | @tsv' data/revenue/M/MSFT/status.json
```

失敗的期別看 `reason`。常見的訊息與原因：

| 檢核 | 訊息大意 | 多半是 | 怎麼查 |
|---|---|---|---|
| fact 存在且唯一 | 找不到某個分類或總營收（`put` 記在 `missing` 的項目） | dimensions 不完整、成員或 concept 在這份申報改名 | 用第 2 步的程式看這份申報的 fact |
| 定義唯一 | 交回的分類順序或集合與 `categories(期末日)` 不同 | `categories` 的切換日期與 `compose` 不一致；漏列分類卻沒有記錄原因 | 對照 `categories` 與 `compose` 的切換條件 |
| 加總 | 分類加總不等於總營收 | 漏了調節項（Corporate、Eliminations、All Other）；總營收選到分部合計；分類選到另一組分部 fact | 對照原文分部表的每一列 |
| fact 存在且唯一 | 重複 fact 數值不一致，或前綴宣告衝突 | `one_of` 的兩種寫法其實是不同數字 | 看兩種寫法的 fact 各在哪張表 |
| 地區成員完整 | 地區軸的成員沒有全部列入 | 運算式只列了部分地區成員 | 把該軸同 concept、同其他 dimensions 的全部成員列入運算式 |
| 單位與精度 | decimals 缺漏或粗於百萬位 | 申報本身的標記 | 回報，不能在 parser 處理 |
| Q4 期間、財年與季別、選申報 | 期間長度或財年宣告不合 | 非 13 週的季度、申報宣告錯財年 | 回報（框架的事） |

`not_derived` 不是失敗：Q4 推算條件或 Q4 口徑一致不成立時，Q4 依規則留空，FY 照常輸出（規則見 `parser.md` 的「框架流程」）。你要做的是在 `parser.md` 寫明是哪一份申報、哪些分類造成的。

開發期間每次修改 parser 後，先刪掉這個 ticker 尚未提交的輸出再重跑。已寫入的期別受已上線保護，不會被新的結果覆蓋，舊的失敗紀錄與標註也會留著：

```bash
rm -rf data/revenue/M/MSFT
.venv/bin/python scripts/sec_pipeline.py parse --tickers MSFT
```

只刪自己這個 ticker、而且還沒進 Git 的輸出。已提交的輸出要改，用 `--republish`，必須由人決定。

### 6. 與對照資料逐期比對

把每一期每個分類的值與採用來源的值比，差異逐筆寫進 `parser.md` 的「驗證」。比對工具（#46）完成前由開發者自己比對。

- **期別對齊**：Stock Analysis 用期末日（季底不是曆年季底的 ticker 會對齊到曆年季底）；富途用申報宣告的財年與季別；TradingView 用財年多數月份所在的曆年（NVDA FY2026 標 2025）。
- **差異多半是重編**：對照來源常用事後重編的數字，我們用申報當時的原值。先查較晚的申報有沒有重列這一期（差異標記的申報列示值與對照來源相同，就是重編），再判斷是不是 parser 錯了。例子：UPS 2024 年 Q4、BAC 2025 年 Q1–Q3、CMCSA 2025 年各季。
- **對照來源本身的錯**：富途的 Q4 偶有錯值（UPS 2024 年 Q4 是負數），Stock Analysis 偶有期別錯置（CMCSA 2026 年 Q1、Q2 對調）。寫明是來源錯誤，不追。
- **不要為了對上對照資料改 parser**：差異照實記錄。

### 7. 產生快照

CI 以快照對全部 ticker 跑 `parse --check`，所以新的 ticker 要連同快照一起提交：

```bash
.venv/bin/python scripts/sec_pipeline.py snapshot --tickers MSFT
.venv/bin/python scripts/sec_pipeline.py parse --tickers MSFT --check --snapshots
```

只修改 parser 不需要重產快照。

### 8. 自我驗收

全部通過才送 review（還沒 commit 的改動，見 [從寫完到合併](dev-workflow.md#從寫完到合併)）：

```bash
.venv/bin/python scripts/sec_pipeline.py parse --tickers MSFT --check               # 以原文重跑，與輸出逐欄比對
.venv/bin/python scripts/sec_pipeline.py parse --tickers MSFT --check --snapshots   # 以快照重跑（CI 跑這一項）
npm run check                                                                         # unit test、對照資料驗證、全部 ticker 的快照回歸
```

兩種 `--check` 都要 `"differences": []`、`"complete": true`，回傳碼 0。

驗收清單：

- [ ] 只改了這個 ticker 的目錄、自己新增的 utility 與測試，以及 `data/revenue/`、`data/snapshots/` 中這個 ticker 的產出。
- [ ] 範圍內每一期都是 `published` 或有理由的 `not_derived`；`failed` 的期別在 `parser.md` 寫明原因並回報。
- [ ] 每個分類、調節項與總營收在 `parser.md` 有 concept 與完整 dimensions；每個依日期的切換寫明從哪一份申報開始。
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

寫 parser 時不改 `tickers.csv`。`status` 等欄位的值由人在判斷能上線時決定，人核准後由 agent 寫入，與 parser 在同一個 commit（見 [開發流程](dev-workflow.md) 第 9 步）。

## 常見陷阱

- **成員或 concept 在財年中途改名**：NVDA 的分部成員、CAT 的 Corporate Items 成員、UPS 2025 年的分部成員。逐份申報確認，用 `one_of` 或依申報切換。
- **10-K 與 10-Q 寫法不同**：AMZN 的 Advertising（10-K `us-gaap:AdvertisingMember`、10-Q `amzn:AdvertisingServicesMember`）、MCD 的直營餐廳營收、UNH 只差大小寫的成員。Q4 的年度與九個月累計分別來自 10-K 與 10-Q，兩種寫法都要找得到。
- **某個寫法只在 10-K 消失**：UPS 的 `ups:SupplyChainSolutionsMember` 在 2025 年各 10-Q 都有，FY2025 10-K 只剩 `us-gaap:CorporateNonSegmentMember`。
- **同一個 concept 有兩組分部 fact**：BRK-B 的 `us-gaap:Revenues` 有只帶分部軸的對外營收，也有帶 `ConsolidationItemsAxis=OperatingSegmentsMember` 的分部表數字。以分部表與對照來源確認用哪一組。
- **一個分類由多個分部相加**：LIN 的 Industrial Gases ＝ Americas ＋ EMEA ＋ APAC。地區軸 `srt:StatementGeographicalAxis` 只能以該軸全部成員相加出現（規則見 `parser.md` 的「公司 parser 的介面」）。
- **總營收的口徑**：BAC 用 FTE、JPM 的分部是 managed basis。總營收跟著分類口徑；分類與報告總營收之間的調整列為調節項。
- **年報改了分類口徑**：UPS 2024 年、BAC 2025 年、HD 每年的 10-K 重列上一財年，Q4 因口徑一致不成立而 `not_derived`，這是預期結果。年報沒有重列、新口徑要到之後的 10-Q 才看得出來時（KO 2025 年），Q4 照常推算，之後的差異標記會揭露。
- **10-K/A、10-Q/A**：主申報取最早的原申報，修正申報只參與差異標記（TSLA 的 Part III 10-K/A）。parser 不需要特別處理。
- **52／53 週制**：HD、NVDA、AAPL 的季末日不是月底，期別以實際期末日識別，不要改成曆季底。季度不是 13 週（COST 的 16 週 Q4）時框架不支援，回報。
- **多個 CIK**：前身與繼受實體以 `tickers.csv` 的 `cik` 欄位 `;` 分隔，由人維護；parser 不處理 CIK。
- **分部軸的成員是地區**：AAPL 的 `us-gaap:StatementBusinessSegmentsAxis` 是 Americas、Europe 等地區，不能用。用這個軸時，`parser.md` 必須寫明成員是業務別：`parser.md` 沒提到這個軸時 parse 會報錯，說明內容由 review 檢查。

## 停下來交給人

以下情況不要自己決定，停下來回報現況、選項與你的建議：

- **觀點**：寫 parser 之前，觀點與分類一定由人決定（第 1 步）。
- **要改框架或既有 utility**：例如需要同時讀兩份申報才組得出一期、期間長度不在框架認得的範圍（COST）、申報宣告的財年錯誤（ORCL）、數字在附件的 inline XBRL（PGR）。
- **只能違反兩條硬原則才做得出來**：例如數字沒有 XBRL 標記（GOOGL 的避險損益列）、要用之後的申報決定早期期別怎麼組。不要繞過。
- **差異解釋不了**：與對照來源的差異不是重編、也不是來源錯誤，或你無法確認是哪一種。
- **已提交的輸出要改**：任何需要 `--republish` 的情況。
- **上線**：`tickers.csv` 的 `status`、`adopted_source`、`stability_score` 的值由人決定。
