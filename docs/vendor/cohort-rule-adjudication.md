# 三十家公司分類規則與來源裁決實驗

**完成狀態：9 / 30 OK。** 請先看 [八季 parser 的逐公司 OK／Fail](historical-rule-study.md)。本文件保留細節計數；數值候選相同不等於 parser 已完成。

截至 2026-11-04，本輪已對完整 30 家執行明確 concept、完整 dimensions、USD unit 的分類候選重播。這是可稽核的回溯實驗，不是完成所有公司財報揭露的產品，也不是準確率報告。27 家最新季度已接觸；LLY、PGR、XOM 接觸未知，本輪排除其最新季度。嚴格未見測試為 **0**。

## 證據與重現

- 規則：[cohort_rule_catalog.py](../../scripts/cohort_rule_catalog.py)，重播：[cohort_rule_audit.py](../../scripts/cohort_rule_audit.py)。替代 scope 若同時有不同值，直接標示歧義，不依參考數字挑答案。
- 公開結果：[summary.json](../../research/cohort-rule-replay-20261104/summary.json)，同目錄每家公司 `*-freeze.json` 保留 training cutoff、Q/FY selectors、原始 SEC 基準及程式雜湊。freeze 僅是重現收據，不能證明未看過最新數據。新增 wrapper 與人工 SEC 表的雜湊在 summary 另存。
- 付費／第三方逐列參考、完整數字、差額、選中原始 facts 與來源路徑：本機 `data/vendor/local/cohort-adjudication-20261104/cohort-rule-replay-20261104/{TICKER}-detailed.json`，由 Git 忽略；各原始檔 SHA-256 記於公開 summary。未上傳原始 vendor 列。
- 重跑需既有本機參考資料：`data/vendor/local/.venv/bin/python scripts/cohort_rule_audit.py --out research/新的實驗名稱`。輸出及對應私有目錄必須不存在，不覆蓋舊結果。
- 本輪未重做 234 季 raw HTML 抽取。使用已保存的 SEC facts 重算季度，Q4 仍要求年度減九個月；缺完整同 scope 不能用零補足。銀行 managed/FTE、保險收益及 corporate reconciliation 的定義另行保留。
- 參考來源：22 家 SA 季表、七家第一／二輪富途替代樣本、四家新增富途 Q/FY 小樣本及 PLD 公司 IR。重複公司保留各源；Apple 舊富途小樣本未納入本輪計數。TradingView 仍只有部分未核定 FY 日期的年度摘要，並未取得 30 家完整三源季度資料。

## 數值候選與逐公司限制

每列計數為有數字的欄位，並非季度數。`精確／精度內` 只描述明確 scope 候選的數值，不等於語意、期間、完整分類已驗證；null 不計入數字分母。期間未獨立覆核的候選仍可出現數值相等。`歧義／缺 scope／未實作／期間不可用／不同` 分開呈現。FY 小樣本另列，不能代替季度驗證。

| 公司 | Q：精確／精度內／數字欄位 | Q：歧義／缺 scope／未實作／期間不可用／不同或標籤錯 | Q 期間未獨立覆核欄位 | FY：精確／數字欄位 | 規則數 Q+FY |
|---|---:|---:|---:|---:|---:|
| AAPL | 40／0／40 | 0／0／0／0／0 | 0 | 0／0 | 10 |
| MSFT | 22／0／23 | 0／0／0／0／1 | 0 | 0／0 | 12 |
| NVDA | 20／0／20 | 0／0／0／0／0 | 0 | 2／2 | 4 |
| ORCL | 32／0／32 | 0／0／0／0／0 | 32 | 0／0 | 22 |
| GOOGL | 53／1／56 | 0／2／0／0／0 | 0 | 0／0 | 14 |
| META | 22／2／24 | 0／0／0／0／0 | 0 | 0／0 | 6 |
| DIS | 24／0／24 | 0／0／0／0／0 | 24 | 0／0 | 6 |
| CMCSA | 24／2／30 | 0／0／0／0／4 | 0 | 7／7 | 14 |
| AMZN | 56／0／56 | 0／0／0／0／0 | 0 | 0／0 | 14 |
| TSLA | 26／0／26 | 0／0／0／0／0 | 0 | 2／2 | 10 |
| HD | 24／0／32 | 0／8／0／0／0 | 32 | 0／0 | 20 |
| MCD | 20／0／21 | 0／1／0／0／0 | 0 | 0／0 | 6 |
| WMT | 32／0／32 | 0／0／0／0／0 | 0 | 0／0 | 6 |
| COST | 8／0／16 | 0／0／0／4／4 | 16 | 0／0 | 4 |
| PG | 12／35／48 | 0／0／0／0／1 | 0 | 0／0 | 12 |
| KO | 10／0／57 | 28／19／0／0／0 | 42 | 0／0 | 58 |
| JNJ | 16／0／16 | 0／0／0／0／0 | 16 | 0／0 | 8 |
| UNH | 21／0／24 | 0／0／0／0／3 | 0 | 0／0 | 8 |
| LLY | 22／0／40 | 0／13／0／5／0 | 5 | 0／0 | 10 |
| JPM | 31／0／32 | 0／1／0／0／0 | 0 | 0／0 | 8 |
| BAC | 37／0／40 | 0／0／0／0／3 | 0 | 0／0 | 10 |
| BRK-B | 48／0／48 | 0／0／0／0／0 | 0 | 0／0 | 16 |
| PGR | 23／0／49 | 0／10／16／0／0 | 0 | 0／0 | 10 |
| XOM | 1／0／58 | 0／0／0／53／4 | 53 | 0／0 | 18 |
| CVX | 16／0／20 | 0／4／0／0／0 | 0 | 0／0 | 12 |
| CAT | 40／0／48 | 0／2／0／6／0 | 6 | 0／0 | 16 |
| UPS | 17／0／24 | 0／3／0／3／1 | 3 | 0／0 | 12 |
| NEE | 24／0／24 | 0／0／0／0／0 | 0 | 0／0 | 8 |
| LIN | 45／0／45 | 0／0／0／0／0 | 0 | 5／5 | 10 |
| PLD | 32／0／32 | 0／0／0／0／0 | 0 | 0／0 | 12 |

- **AAPL**：五項產品／服務完整 scope；本輪只重播 SA，既有 Apple 富途小樣本另見先前報告。維護產品 member 與季度顯示日期。
- **MSFT**：分類改組與舊欄位空值需分期；2026-03 More Personal Computing 一筆仍不同，不能用其他 scope 的同額值代替。
- **NVDA**：歷史 2024-10 member 別名限日期與完整維度；FY 與 Q 各自檢查。富途兩分部與 SA 相同粒度。
- **ORCL**：雲端／軟體拆分與舊授權／支援欄位並存；32 筆數值候選一致，但全部日期仍是鄰近日期提案，須公司財年表確認。
- **GOOGL**：產品加分部二軸；兩個歷史 Hedging Gains 缺精確 scope。避險不是客戶合約收入，應獨立保留。
- **META**：Family of Apps 下廣告／其他與 Reality Labs 分部混合；兩筆僅顯示精度相容，不是精確相等。
- **DIS**：三營運分部，八個舊／不存在欄位空值；24 筆皆仍需獨立確認曆日顯示與實際季末的對應。
- **CMCSA**：SEC 淨業務群與富途毛分部皆可合理。補齊 HQ 與內部抵銷後，SA 六筆舊差異消失；四筆確認季度標籤互換。人工文字表尚未成為泛用 HTML parser。
- **AMZN**：七產品；指定歷史年報 Advertising member 與九個月不同，僅兩份歷史報告允許別名，未全面移除維度。
- **TSLA**：SA 三產品與富途兩分部可同時保留；汽車分部含服務，不能一對一比 SA 的 Automotive 產品。另有富途 FY 兩值。
- **HD**：歷史三種完整 scope 變體已納入；八筆仍缺 scope，集中 Q4 與 Other。32 筆期間映射均待覆核，不以數值相等解除期間疑慮。
- **MCD**：更正舊文件：富途為美國、國際自營市場、國際發展授權市場及公司三類營運分部，並非直營／加盟產品分類。只有七季，2024 Q4 美國 scope 尚缺。
- **WMT**：三營運部門加 corporate membership/other income 對帳列。七個歷史 corporate 季值由 SEC 表格或 FY 減九個月支持，最新季仍只用殘差推算；不是四部門全部直接揭露。
- **COST**：Net Sales 與會員費口徑清楚，但四筆無對應期間、四筆不同；16 筆日期均未獨立覆核。需專用零售 12/16 週財年映射，不能先算來源錯誤。
- **PG**：五分部加 corporate；35 筆僅在來源顯示及 SEC 精度內相容，另有一筆不同，不能把近似都稱精確。
- **KO**：58 個 Q/FY 精確 selector 仍不足以單一裁決。custom reportable revenue 與 GAAP Revenues 同時存在且不同時退回 ambiguous；28 筆歧義、19 缺 scope，另有日期映射待查。
- **JNJ**：兩分部的帶／不帶 OperatingSegments 明確變體；16 筆日期皆仍待獨立確認，八空值保留。
- **UNH**：UnitedHealthcare 與總 Optum 保留不同 scope，不能把子部門與總部門重複加總；2026 Q2/Q3 Optum 及 Q2 Eliminations 共三筆不同。
- **LLY**：治療領域產品 scope；13 筆缺漏集中 Q4 與 Other，最新季五值刻意不重播，接觸狀態未知。須解年度與九個月格式，不能稱未見測試。
- **JPM**：net interest revenue 的分部 managed/FTE 口徑需與 GAAP 對帳；31 候選一致不證明全屬 GAAP。2024 Q4 CIB 缺 scope。
- **BAC**：明確採 FullTaxEquivalentBasis 自訂概念；2025 Q4 Global Banking、Global Markets、Other 三筆不同，應查重編／對帳，不混用 GAAP 概念湊數。
- **BRK-B**：八類集團／業務加 corporate 對帳；只有六季。48 候選一致不補足缺兩季，子公司與合併收入須分層。
- **PGR**：承保、服務、投資與證券損益不是互斥的同層收入分類；16 筆規則未實作、10 筆 Q4 缺 scope。收入關鍵字過濾會漏投資 income，需擴大抽取且處理父子損益重複。最新季未重播。
- **XOM**：現存 successor CIK 基準只有 2026 Q2/Q3，舊 CIK 橋接未解；僅 Q2 五值可比較，一相等、四不同。其餘 53 值屬基準期間不可用，不能報 parser 失敗或零。最新 Q3 未重播。
- **CVX**：上／下游 US 與 NonUS 的精確二地域合計，另列抵銷；2024 Q4 四值缺 scope。毛收入與抵銷需同一口徑。
- **CAT**：產業分部新舊名稱與金融收入混合；最新 SA 六值超出現有 SEC 季度基準，另兩個歷史 scope 缺漏。不能把最新來源資料較多稱成來源落後。
- **UPS**：本土／國際分部與地區雙軸、Supply Chain Solutions 的完整維度變體；三值期間不可用、三 scope 缺漏、一 Q4 不同。
- **NEE**：FPL/NEER/corporate；指定 2024 Q4 法人九個月與部門全年跨 scope 橋接有人工表格支持，需持續保留推算與原始兩側維度。
- **LIN**：五分部，SA 八季與富途一 Q、一 FY 候選相符；富途最新 Q 尚無樣本，不能外推八季兩源全覆蓋。
- **PLD**：三收入類加總收入的公司 IR 八季；32 候選一致，總收入不是第四收入組成。兩家 vendor 的 PLD 缺口並未因此消失。

## Comcast 裁決

[公開 SEC 業務群數字與來源](../../research/cohort-rule-adjudication/comcast-sec-business-groups.json) 為公司財報人工摘錄，並非 vendor 原表。原先只加 Media、Studios、Theme Parks 的 Content 規則漏了 Headquarters & Other 及業務群內抵銷；SEC 確實披露淨 Content & Experiences 與 Connectivity & Platforms。富途五毛分部、corporate、全公司抵銷與 SA 兩淨業務群可並存，不能強迫同一分類。

SA 原日期下 16 個業務群欄位現為 10 精確、2 在 Q4 年度減九個月的精度內、4 確認季度標籤錯置。2026-03-31 與 2026-06-30 的兩個業務群分別對應另一季的 SEC 金額。另用正常公開瀏覽器重新讀 Quarterly History，同日期的顯示支持已存檔數值，因此不是把舊擷取失誤直接怪給來源。新頁面證據路徑與 SHA-256 在 summary，原始列僅本機。程式保留原日期，另一季只作診斷，不改日期湊配對。

2025 as-filed 與 2026 分拆 Versant 後的 2025 comparative 定義不同；本輪保留 as-filed 的版本。Q4 用同年度原始全年減九個月，不任意混最新重編比較值。此裁決有人工 SEC 表格介入，尚不能宣稱現有 parser 已自動抽出全部業務群文字表。

## Walmart 裁決

[公開 SEC corporate income 及來源](../../research/cohort-rule-adjudication/walmart-corporate-income.json)。公司歷史部門表將 Corporate and support 列在 Membership and other income，含公司層級其他收入；三營運部門之外的對帳列須保留其角色。七個歷史季度可從直接列值或全年減九個月支持；2026-07-31 仍是 consolidated revenue 減三部門 revenue 的殘差推算，不把算術恆等式當原表驗證。

本輪正常 SEC 原檔下載 `wmt-20260731.htm` 曾回 403，已停止，不重試或替換手段繞過。同公司其他較早的公開 filing 正常文字頁可讀，支援歷史分類裁決，並不等於最新原檔已取得。最新完整字節／標籤仍缺。

## 規模化與後續

本輪所有公司都有規則或明確缺口，尚無完整揭露召回率、獨立人工覆核或人工分鐘數實測。新增的 HD、KO、UPS 完整 scope 變體取自歷史 training facts；未移除任意軸。KO 的替代值歧義與 XOM 的 CIK 缺口顯示，更多 selector 不保證更高可判定率。

可共用的是事實保存、單位／精度、Q/FY 分離、精確維度、別名日期限制、訓練收據與差異分類。需要逐公司工程的是財年對齊、分部改組、公司／部門抵銷、managed/FTE 對帳、保險 income 與損益父子關係、法人 scope 橋接、CIK succession 及無 iXBRL tag 的文字表。候選數值相等仍需定義裁決；不能把一個供應商當唯一標準。

1,500 家 × 8 季為 12,000 個公司季度槽位，尚未乘上分類、來源、重編版本及年度對照；本輪未測批次吞吐、授權可用性或每家公司人工時間，不能給可靠工期／成本。先解 COST／ORCL 等期間映射、KO 多口徑、PGR 非 revenue 概念、XOM 舊新 CIK、各家 Q4 缺漏，再用固定樣本測量人工介入次數和耗時。真正泛化需事前凍結規則、等候未接觸的新季度；目前不能用回溯命中預測新季度準確率。

離線測試與證據完整性另見同結果目錄的 `verification.json`。本輪未有獨立人工審閱；所有裁決為 agent 文件覆核。
