# DELL parser

## 觀點

業務分部（`business_segment`），採用 TradingView 對照，分類順序依該來源。`us-gaap:StatementBusinessSegmentsAxis` 的成員是 ISG、CSG 與其他業務等業務別，不是地區。各期保留原申報結構，無調節項。

| 原申報 | 分類，依輸出順序 |
|---|---|
| FY2024、FY2025 Q1–Q3 | Infrastructure Solutions Group、Client Solutions Group、Unallocated transactions、Other businesses |
| FY2025 10-K 起 | Infrastructure Solutions Group、Client Solutions Group、Corporate and other |

TradingView 的 Unallocated、Other、Corporate and Other 分別對應以上最後三個名稱；ISG、CSG 同名。TradingView 只有年度。富途與 Stock Analysis 作季度輔助：富途「基礎設施解決方案組」「客戶解決方案組」及 Stock Analysis「Infrastructure Solutions」「Client Solutions Group」對應 ISG、CSG。Stock Analysis 的 Other、富途較近期的「公司和其他」，在舊結構合併 Other businesses 與 Unallocated transactions；新結構對應 Corporate and other。合併僅用於對照，不改 parser 的歷史分類。

不採 ISG 的 Servers and networking、Storage、AI-optimized servers、Traditional servers and networking，亦不採 CSG 的 Commercial、Consumer 或合併 Products／Services。這些是產品細項，與決定的分部層級不同。TradingView 的 VMware 只在範圍外歷史年度有值。

## 分類與 tag

所有分類與總營收的 concept 都是 `us-gaap:Revenues`。以下列出完整 dimensions，沒有省略其他軸。單位為 USD，所選 fact 的 `decimals=-6`，即百萬美元精度。

| 分類 | 完整 dimensions |
|---|---|
| Infrastructure Solutions Group | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；`us-gaap:StatementBusinessSegmentsAxis=dell:InfrastructureSolutionsGroupMember` |
| Client Solutions Group | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；`us-gaap:StatementBusinessSegmentsAxis=dell:ClientSolutionsMember` |
| Unallocated transactions，舊結構 | `srt:ConsolidationItemsAxis=us-gaap:CorporateNonSegmentMember` |
| Other businesses，舊結構 | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`；`us-gaap:StatementBusinessSegmentsAxis=us-gaap:AllOtherSegmentsMember` |
| Corporate and other，新結構 | `srt:ConsolidationItemsAxis=us-gaap:CorporateNonSegmentMember` |
| Total consolidated net revenue | 無維度 |

分類名稱取自分部附註的 Consolidated net revenue 表列標籤，去除註腳。總營收取無維度的合併 fact，不取 OperatingSegmentsMember 分部小計。FY2024 10-K 的 Impact of purchase accounting 營收列為零，不列調節項；分類加總直接核對合併營收。

`compose` 依該申報、該期間是否有 Other businesses 的完整維度 fact 選擇結構。有時列四類，沒有時列三類；找不到的必要 fact 交給框架報錯。它不以日期、fact id 或數值選 fact。

`categories` 的切換日為 `2024-11-02`，即最後一份舊結構主申報 FY2025 Q3 的期末日隔天，也是新結構第一份主申報 FY2025 10-K 所涵蓋 Q4 的起日。新結構始於 `0001571996-25-000034`，期末 `2025-01-31`。日期定義至少涵蓋 `2023-02-03`，供 FY2024 財年內分類檢查與上一財年口徑依據使用；更早期別不保證適用。

## 期別與推算

DELL 採 52／53 週制，財年於最接近 1 月 31 日的星期五結束。範圍內單季 91 天、半年 182 天、九個月 273 天，年度 364 天；作前置依據的 FY2023 年度為 371 天。使用預設期間範圍，不宣告 `DURATION_DAYS`。營收 fact 均在主文件，不宣告 `ATTACHMENTS`。財年數字宣告正確，不宣告 `FISCAL_YEAR`；該自訂點也不能修正下述季別錯誤。

Q1–Q3 取原 10-Q 單季 fact，FY 取原 10-K 年度 fact。Q4 由框架以年度減同財年原 Q3 10-Q 的九個月 fact，各運算元保留自己的期間、申報與 scope。

- FY2024 Q4（`2024-02-02`）為 `failed`，檢核「財年與季別」。框架檢查同財年 Q1–Q3 依賴時，FY2024 Q1 的 `0001571996-23-000019`（期末 `2023-05-05`）是 10-Q，卻將 `dei:DocumentFiscalPeriodFocus` 宣告為 `FY`。FY2024 Q2 的 `0001571996-23-000032`（期末 `2023-08-04`）也有同樣問題；框架先在 Q1 停止，所以 Q4 的 reason 只指出 Q1。兩份均宣告 `DocumentFiscalYearFocus=2024`。這不是缺營收 fact，且現有 parser 自訂點不支援季別更正。保留失敗，不人工補 Q4、不修改原文或框架。
- FY2025 Q4（`2025-01-31`）為 `not_derived`，檢核「Q4 推算條件」。全年為三類，財年起日 `2024-02-03` 至 Q3 期末 `2024-11-01` 為四類，集合不同。FY2025 照常組成。
- FY2026 Q4（`2026-01-30`）可推算。FY2026 10-K 雖將 ISG 產品細項再拆分，ISG／CSG 分部總數的定義與維度不變。

FY2024 Q1 錯誤 DEI 的原始來源為 [SEC 10-Q](https://www.sec.gov/Archives/edgar/data/1571996/000157199623000019/dell-20230505.htm)，主文件 SHA-256 為 `0cec7fc88e686387a885b5c660bfb32ff6863031d46c8f1de0f9638cd2a964df`。其 DEI context 期間為 `2023-02-04` 至 `2023-05-05`，`DocumentType=10-Q` 與 `DocumentFiscalPeriodFocus=FY` 同時存在於原始 inline XBRL。

FY2024 Q2 的 [SEC 10-Q](https://www.sec.gov/Archives/edgar/data/1571996/000157199623000032/dell-20230804.htm) 主文件 SHA-256 為 `88e44feca5e17224e1231093405eee06121d4725cf83f685f15fb8e409d64004`，抽出的 DEI 同樣為 `DocumentType=10-Q`、`DocumentFiscalPeriodFocus=FY`。即使處理 Q1 的問題，仍需處理 Q2，不能只豁免第一份失敗申報。

## 數字在原文的位置

下表依正式 `revenue.json` 的 `operands[*].evidence.table` 列出分類與總營收的證據。每列運算元都位於該申報分部附註的 Consolidated net revenue 表；表號是檔名末尾的 `t` 編號。

證據存於 `data/revenue/D/DELL/<系列>/<期末>/evidence/`；下列檔名主幹各有 `.html` 與 `.png`。HTML 是從 SEC 原文抽出的表格並標示運算元，PNG 是該證據表的截圖，兩者都不是原始申報 bytes；原始文件 URL 與 SHA-256、運算元期間、單位及完整 dimensions 保留在 `revenue.json`。

| 輸出期別 | 系列／期末 | 運算元期間 | evidence 檔名主幹 | 用途 |
|---|---|---|---|---|
| FY2024 | `FY/2024-02-02` | 2023-02-04～2024-02-02 | `0001571996-24-000036-5ab11816c1fc-t88` | 年度 |
| FY2025 Q1 | `Q/2024-05-03` | 2024-02-03～2024-05-03 | `0001571996-24-000062-871dfcbd8666-t52` | 單季 |
| FY2025 Q2 | `Q/2024-08-02` | 2024-05-04～2024-08-02 | `0001571996-24-000090-edbfab79d1c4-t55` | 單季 |
| FY2025 Q3 | `Q/2024-11-01` | 2024-08-03～2024-11-01 | `0001571996-24-000143-9252161c5038-t56` | 單季 |
| FY2025 | `FY/2025-01-31` | 2024-02-03～2025-01-31 | `0001571996-25-000034-a98175e3807e-t89` | 年度 |
| FY2026 Q1 | `Q/2025-05-02` | 2025-02-01～2025-05-02 | `0001571996-25-000063-b7c9a8715dd6-t49` | 單季 |
| FY2026 Q2 | `Q/2025-08-01` | 2025-05-03～2025-08-01 | `0001571996-25-000102-f0be0dfd5042-t52` | 單季 |
| FY2026 Q3 | `Q/2025-10-31` | 2025-08-02～2025-10-31 | `0001571996-25-000127-fbceee82223d-t52` | 單季 |
| FY2026 | `FY/2026-01-30` | 2025-02-01～2026-01-30 | `0001571996-26-000008-22dc64f7aac1-t84` | 年度 |
| FY2026 Q4 | `Q/2026-01-30` | 2025-02-01～2025-10-31 | `0001571996-25-000127-fbceee82223d-t52` | 九個月運算元 |
| FY2026 Q4 | `Q/2026-01-30` | 2025-02-01～2026-01-30 | `0001571996-26-000008-22dc64f7aac1-t84` | 年度運算元 |
| FY2027 Q1 | `Q/2026-05-01` | 2026-01-31～2026-05-01 | `0001571996-26-000030-04fefa50f5d3-t49` | 單季 |
| FY2027 Q2 | `Q/2026-07-31` | 2026-05-02～2026-07-31 | `0001571996-26-000046-11beac81937d-t46` | 單季 |

FY2026 Q4 同時使用 FY2026 10-K t84 的年度值與 FY2026 Q3 10-Q t52 的九個月值，兩張表各自保留在該季的 evidence 目錄。

FY2024 Q4 為 `failed`，FY2025 Q4 為 `not_derived`，兩季均無正式 `revenue.json` 或 evidence。範圍外 FY2023 10-K（`0001571996-23-000007`）t89 是上一財年口徑及「分類合併」的原文依據；FY2024 Q3 10-Q（`0001571996-23-000046`）t59 是下述 FY2024 Q4 原始 fact 對照的九個月來源，均不列作已發布季度的正式證據。

## 已知的重複 fact

ISG、CSG 在分部彙總表與產品細項表重複，總營收在損益表、分部表與其他營收拆分重複。同 concept、完整 dimensions、期間的重複 fact 由框架核對一致後，優先選同表含較多運算元者。所選表格為上表的分部彙總表。Other businesses、Unallocated transactions／Corporate and other 不需要跨表相加。

## 分類合併

FY2025 10-K t89 將其他項目合併為 Corporate and other，FY2024 比較欄為 5,624 百萬美元；FY2024 原 10-K t88 的 Other businesses 為 5,614、Unallocated transactions 為 10，合計 5,624。FY2023 比較欄亦為 5,732，等於 FY2023 原 10-K t89 的 5,721＋11。這是範圍合併，不是單一分類純改名，因此不宣告 `FORMER_NAMES`。

雖然 Unallocated transactions 與 Corporate and other 共用 CorporateNonSegmentMember，後者不能以原名稱輸出，也不能把後來的合併結構套回早期。較晚申報只作本節差異證據，不提供早期輸出的運算元。

## 驗證

正式輸出位於 `data/revenue/D/DELL/`，期別狀態以 `status.json` 為準，已發布數字與運算元以各期 `revenue.json` 為準。範圍自 `2024-01-01` 起，至最新期末 `2026-07-31`。

| 財年期別 | 實際期末 | 狀態 | 原因 |
|---|---|---|---|
| FY2024 | 2024-02-02 | published | 年度原始四類 |
| FY2024 Q4 | 2024-02-02 | failed | Q1 10-Q 宣告期別為 FY，Q4 依賴檢核失敗；Q2 同樣宣告錯誤 |
| FY2025 Q1 | 2024-05-03 | published | 單季四類 |
| FY2025 Q2 | 2024-08-02 | published | 單季四類，Unallocated transactions 是明確零 fact |
| FY2025 Q3 | 2024-11-01 | published | 單季四類，Unallocated transactions 是明確零 fact |
| FY2025 | 2025-01-31 | published | 年度新三類 |
| FY2025 Q4 | 2025-01-31 | not_derived | 年度與 Q1–Q3 分類集合不同 |
| FY2026 Q1 | 2025-05-02 | published | 單季三類 |
| FY2026 Q2 | 2025-08-01 | published | 單季三類 |
| FY2026 Q3 | 2025-10-31 | published | 單季三類 |
| FY2026 | 2026-01-30 | published | 年度三類 |
| FY2026 Q4 | 2026-01-30 | published | 年度減九個月 |
| FY2027 Q1 | 2026-05-01 | published | 單季三類 |
| FY2027 Q2 | 2026-07-31 | published | 單季三類 |

共 12 筆 `published`（9 季、3 年度）、1 筆 `not_derived`、1 筆 `failed`。12 期正式輸出的分類加總均與總營收完全相等，`checks.sum.difference` 均為 0；各期 `checks.structural` 的定義唯一、fact 存在且唯一、單位與精度、加總與證據完整檢核均為 `pass`，FY2026 Q4 的期間檢核亦為 `pass`。每個運算元的 evidence HTML／PNG 均存在，檔案 SHA-256 與 `revenue.json` 記錄一致。FY2024 Q4 的季別檢核失敗仍存在，不能將全範圍標為驗收通過。

### TradingView 逐期比對

對照檔為 `data/universe/references/D/DELL/reference.json`。TradingView 標籤按財年多數月份所在曆年對齊，`2023／2024／2025` 分別是 DELL FY2024／FY2025／FY2026。下列 SEC 數值與差額均為百萬美元，括號列 TradingView 顯示值，差額為 SEC 減來源。

| 財年 | ISG | CSG | Unallocated | Other／Corporate and Other | 結論 |
|---|---|---|---|---|---|
| FY2024 | 33,885（33.88B），+5 | 48,916（48.92B），−4 | 10（10.00M），0 | Other 5,614（5.61B），+4 | 四類均在顯示精度內 |
| FY2025 | 43,593（43.59B），+3 | 48,393（48.39B），+3 | 該結構不適用 | Corporate and Other 3,581（3.58B），+1 | 三類均在顯示精度內 |
| FY2026 | 60,826（60.83B），−4 | 50,984（50.98B），+4 | 該結構不適用 | Corporate and Other 1,728（1.73B），−2 | 三類均在顯示精度內 |

0.01B 的顯示半單位為 5 百萬美元，再加單一 SEC fact 的 0.5 百萬美元精度誤差。10.00M 的顯示半單位為 0.005 百萬美元。10 筆分類數值均在容許範圍；沒有超出顯示精度的差異。TradingView 未提供總營收列，總營收只做 SEC 分類加總檢核。

TradingView 沒有季度；FY2024 Q4、FY2025 Q1–Q4、FY2026 Q1–Q4、FY2027 Q1–Q2 均無主要來源季度比對，不能宣稱由 TradingView 逐季驗證。其更早年度在範圍外，不納入本次驗證。

### 季度輔助比對

Stock Analysis 用曆季底標籤，`Mar 31／Jun 30／Sep 30／Dec 31` 對應 DELL 實際約 5 月／8 月／11 月／隔年 1 月末的季度；例如 `Dec 31, 2023` 對應 `2024-02-02`。富途直接用 DELL 財年季別。

| 期別 | SEC 分類值，百萬美元，依輸出順序 | 富途／Stock Analysis |
|---|---|---|
| FY2025 Q1 | 9,227／11,967／1／1,049 | 合併後 Other=1,050；兩來源均在顯示精度內 |
| FY2025 Q2 | 11,646／12,414／0／966 | 合併後 Other=966；兩來源均在顯示精度內 |
| FY2025 Q3 | 11,368／12,131／0／867 | 合併後 Other=867；兩來源均在顯示精度內 |
| FY2026 Q1 | 10,317／12,509／552 | 兩來源均在顯示精度內 |
| FY2026 Q2 | 16,800／12,503／473 | 兩來源均在顯示精度內 |
| FY2026 Q3 | 14,107／12,478／420 | 兩來源均在顯示精度內 |
| FY2026 Q4 | 19,602／13,494／283 | 兩來源均在顯示精度內 |
| FY2027 Q1 | 29,009／14,609／224 | 兩來源均在顯示精度內 |
| FY2027 Q2 | 31,782／15,034／155 | 兩來源均在顯示精度內 |

舊結構合併核對不代表來源逐一驗證原始四類。FY2025 Q4 沒有 parser 值，不與兩來源的 11,352／11,881／698 作成功比對。

FY2024 Q4 也沒有通過檢核的 parser 輸出。以下為原始 fact 的對照算式，不能標為 published 或成功季度驗證：

| 分類 | FY2024 10-K t88 − FY2024 Q3 10-Q t59，百萬美元 | 富途 FY2024 Q4 |
|---|---|---|
| ISG | 33,885 − 24,553 = 9,332 | 9,332 |
| CSG | 48,916 − 37,201 = 11,715 | 11,715 |
| Unallocated transactions | 10 − 8 = 2 | −8，差額 +10 |
| Other businesses | 5,614 − 4,345 = 1,269 | −4,345，差額 +5,614 |
| Corporate and other | 原始結構沒有此分類 | 5,624，多出合併分類 |
| 合併總營收 | 88,425 − 66,107 = 22,318 | 上述五列合計 22,318，來源沒有獨立總營收列 |

富途三個其他項目合計 1,271，恰等於原始兩列合計。5,624 又等於 FY2025 年報 FY2024 比較欄的合併全年值，呈現跨結構全年值與舊結構九個月值的算術組合。逐類明確不符，原因仍未確認，不直接認定來源錯誤。Stock Analysis 的同季 9.33B／11.72B／1.27B 與原始 fact 對照算式在顯示精度內，但不能消除 Q4 的季別檢核失敗。

## 比較欄

12 期正式 `revenue.json` 均沒有 `differences` 標記，也沒有 `comparison_errors`。比較欄未標出已發布值與後續可比申報值超出精度的差異。

沒有 `FORMER_NAMES`，所以新結構沒有舊名稱時，不會把 Corporate and other 逐項接到 Other businesses 或 Unallocated transactions。沒有標記不代表這些分類未變；FY2024 比較欄合併的證據見「分類合併」。ISG、CSG 與總營收的可比值沒有超出精度差異。FY2024 Q4 失敗、FY2025 Q4 未推算，沒有該季輸出可作比較欄基準。
