# XOM parser

## 觀點

業務分部（`view="business_segment"`），採用 TradingView 的對外銷售觀點及分類順序，以 SEC 的名稱輸出：Energy Products、Upstream、Chemical Products、Specialty Products。Corporate and Financing 是調節項，參與加總但不輸出成分類。總營收為 Sales and other operating revenue。

| 對照來源 | 分類與處理 |
|---|---|
| TradingView | Energy、Upstream、Chemical、Specialty，分別對應上述四類。只有年度資料。Corporate and Financing 只在 FY2023 及更早有值，FY2024、FY2025 為空；Downstream 只在較早年度出現。 |
| 富途 | 四個主業務，以及依期別出現的企業與融資、Other revenues、其他收入、Income from equity affiliates、分部間收入。其各期分部值混用銷售加分部間收入、分部總收入與後來申報的比較欄，不採用作數值比對來源。 |
| Stock Analysis | 沒有 XOM 的對照資料，不計入多數判斷。 |

對照資料位於 `data/universe/references/X/XOM/reference.json`。只以期末日不早於預設起始日 2024-01-01 的期別判斷「列出」：兩個來源在範圍內都未列 Corporate and Financing 銷售，所以列為調節項，不因 FY2023 的歷史值改列分類。富途的 Other revenues 含較廣的收入，不等於 Corporate and Financing 的銷售，不能直接代入。

`us-gaap:StatementBusinessSegmentsAxis` 的成員是能源產品、上游、化工產品與特種產品業務，不是地區。每個業務的銷售以美國與非美國全部地區成員相加，輸出仍是業務別。其他只按國家或地區拆分的收入不採用。分部間交易已排除在採用的銷售值之外，不另外列抵銷分類或調節項。

## 分類與 tag

全部運算元的 concept 都是 `us-gaap:Revenues`。本節列出的 dimensions 是完整集合；不另加未列出的維度。

四個分類各取兩個 fact，相加後得到全球業務銷售。

| 分類 | `us-gaap:StatementBusinessSegmentsAxis` 成員 |
|---|---|
| Energy Products | `xom:EnergyProductsMember` |
| Upstream | `xom:UpstreamMember` |
| Chemical Products | `xom:ChemicalProductsMember` |
| Specialty Products | `xom:SpecialtyProductsMember` |

每個分類的兩個 fact 都另外帶以下維度：

- `srt:ProductOrServiceAxis=xom:SalesAndOtherOperatingRevenueMember`。
- `srt:StatementGeographicalAxis=country:US` 或 `srt:StatementGeographicalAxis=us-gaap:NonUsMember`。兩個地區各取一項，權重均為 1，不以 `one_of` 將不同地區當作重複值。

分類名稱取自分部表的欄標題或列標籤。總營收名稱取自損益表的 Sales and other operating revenue。

### Corporate and Financing 調節項

優先以 `one_of` 查找 Corporate 銷售的兩種成員寫法。完整 dimensions 是：

- `srt:ProductOrServiceAxis=xom:SalesAndOtherOperatingRevenueMember`。
- `us-gaap:StatementBusinessSegmentsAxis=xom:CorporateAndFinancingMember`，或 `xom:CorporateAndFinancingMemberMember`。

FY2023 10-K（`0000034088-24-000018`，期末 2023-12-31）使用 `CorporateAndFinancingMemberMember`；2024 Q1–Q3 10-Q 使用 `CorporateAndFinancingMember`。同份申報若同時有兩種寫法，兩者必須在精度內一致，不能任選一個。

FY2024 10-K（`0000034088-25-000010`，期末 2024-12-31）起，分部表不再單列 Corporate 銷售，改列各業務與 Segment Total 的銷售，以及較廣口徑的 Other revenues。這些申報中，調節項由同份申報的兩個 fact 組成：

| 運算元 | 完整 dimensions | 權重 |
|---|---|---:|
| 合併 Sales and other operating revenue | `srt:ProductOrServiceAxis=xom:SalesAndOtherOperatingRevenueMember` | 1 |
| Segment Total 的 Sales and other operating revenue | `srt:ProductOrServiceAxis=xom:SalesAndOtherOperatingRevenueMember`；`srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember` | -1 |

例如 FY2024 為 339,247 − 339,136 = 111 百萬美元，FY2025 為 323,905 − 323,820 = 85 百萬美元。這是合併銷售與營運分部銷售之間的調節，不是將 `Other revenues` 全額當作銷售，也不是以總營收倒算四個業務分類。兩種寫法在重疊的期別逐一相等（百萬美元）：FY2023 直接值 68，FY2024、FY2025 10-K 比較欄相減 334,697 − 334,629 = 68；2024 Q1 直接值 24，2025 Q1 10-Q 比較欄相減 80,411 − 80,387 = 24；FY2022、2024 Q2、Q3 與上半年、九個月同樣相等。用相減式的期別，加總檢核核對的是四個業務加總等於 Segment Total。

程式按這份申報、這段期間是否有直接 Corporate 銷售 fact 判斷寫法，不依日期、fact id 或數值切換。直接 fact 不存在時才使用合併銷售減分部銷售合計；任一必要 fact 缺少都交給 `put` 記錄為 missing，不補零。

### 總營收與較廣口徑合併營收

總營收只帶 `srt:ProductOrServiceAxis=xom:SalesAndOtherOperatingRevenueMember`，不帶分部軸、地區軸或 `ConsolidationItemsAxis`。這是合併銷售，不是僅四個業務的 Segment Total。四類加 Corporate and Financing 調節項等於這個總額。

損益表另有不帶維度的 `us-gaap:Revenues`，名稱是 Total revenues and other income。它與本觀點總額的差額，是同一份申報的 Income from equity affiliates 加 Other income。這兩項也各為 `us-gaap:Revenues`，完整 dimensions 分別只有：

- `srt:ProductOrServiceAxis=xom:IncomeFromEquityAffiliatesMember`。
- `srt:ProductOrServiceAxis=xom:OtherRevenueMember`。

以下各期單位為百萬美元；Q4 的兩項均由同財年 10-K 年度減 Q3 10-Q 九個月累計。它們只說明口徑差額，不加入本觀點的分類、調節項或總營收。

| 期別 | Income from equity affiliates | Other income | 較廣口徑合併營收減合併銷售 |
|---|---:|---:|---:|
| FY2023，較早年度依據 | 6,385 | 3,500 | 9,885 |
| 2024 Q1 | 1,842 | 830 | 2,672 |
| 2024 Q2 | 1,744 | 1,330 | 3,074 |
| 2024 Q3 | 1,481 | 743 | 2,224 |
| 2024 Q4 | 1,127 | 1,241 | 2,368 |
| FY2024 | 6,194 | 4,144 | 10,338 |
| 2025 Q1 | 1,369 | 703 | 2,072 |
| 2025 Q2 | 1,462 | 567 | 2,029 |
| 2025 Q3 | 1,267 | 696 | 1,963 |
| 2025 Q4 | 966 | 1,303 | 2,269 |
| FY2025 | 5,064 | 3,269 | 8,333 |
| 2026 Q1 | 1,369 | 608 | 1,977 |
| 2026 Q2 | 893 | 595 | 1,488 |
| 2026 Q3 | 1,126 | 1,535 | 2,661 |

## 期別與推算

- 財年即曆年，年末為 12 月 31 日，季末為 3、6、9、12 月的最後一天。
- Q1–Q3 取主 10-Q 的三個月 fact；FY 取主 10-K 的全年 fact。
- Q4 由框架將同財年 10-K 年度減 Q3 10-Q 的九個月累計。年度、單季與九個月各自從其申報組成運算式，不使用後來申報倒算原期數字。
- `categories` 在涵蓋範圍內固定為四個業務加 Corporate and Financing 調節項。直接 Corporate fact 與兩個 fact 的調節式是同一個調節項，分類集合相同。
- 涵蓋下限為 2023-12-31，包括 FY2023 10-K 作為首個範圍內 Q4 的較早年度口徑依據。現行四業務已見於該份申報；沒有查核更早原申報的分類結構，不保證以更早 `--start` 執行的結果。
- 前身與繼受申報人的 CIK 由申報清單及框架處理。2026 Q3 的主申報是 `0002115436-26-000020`，parser 不按 CIK 改組營收。

## 數字在原文的位置

表格編號為框架對 SEC 主文件的編號。分部銷售取附註的分部表，合併銷售取分部表或損益表。下表為各期正式證據實際取自的表格（`data/revenue/` 各期 evidence 檔名的 `-t<編號>`）。

| 主申報 | SEC 文件 | 分部銷售與調節項 | 合併銷售 |
|---|---|---|---|
| FY2023 | [0000034088-24-000018](https://www.sec.gov/Archives/edgar/data/34088/000003408824000018/xom-20231231.htm) | t154，四業務與直接 Corporate 銷售 | t154 |
| 2024 Q1 | [0000034088-24-000029](https://www.sec.gov/Archives/edgar/data/34088/000003408824000029/xom-20240331.htm) | t29，四業務與直接 Corporate 銷售 | t29 |
| 2024 Q2 | [0000034088-24-000050](https://www.sec.gov/Archives/edgar/data/34088/000003408824000050/xom-20240630.htm) | t36，四業務與直接 Corporate 銷售 | t36 |
| 2024 Q3 | [0000034088-24-000068](https://www.sec.gov/Archives/edgar/data/34088/000003408824000068/xom-20240930.htm) | t36，單季及九個月的四業務與直接 Corporate 銷售 | t36 |
| FY2024 | [0000034088-25-000010](https://www.sec.gov/Archives/edgar/data/34088/000003408825000010/xom-20241231.htm) | t155，四業務及 Segment Total 銷售；Corporate 另用合併銷售相減 | t110 |
| 2025 Q1 | [0000034088-25-000024](https://www.sec.gov/Archives/edgar/data/34088/000003408825000024/xom-20250331.htm) | t31，四業務及 Segment Total 銷售；Corporate 另用合併銷售相減 | t7 |
| 2025 Q2 | [0000034088-25-000042](https://www.sec.gov/Archives/edgar/data/34088/000003408825000042/xom-20250630.htm) | t36，四業務及 Segment Total 銷售；Corporate 另用合併銷售相減 | t7 |
| 2025 Q3 | [0000034088-25-000061](https://www.sec.gov/Archives/edgar/data/34088/000003408825000061/xom-20250930.htm) | 單季 t36、九個月 t38，四業務及 Segment Total 銷售；Corporate 另用合併銷售相減 | t7 |
| FY2025 | [0000034088-26-000045](https://www.sec.gov/Archives/edgar/data/34088/000003408826000045/xom-20251231.htm) | t190，四業務及 Segment Total 銷售；Corporate 另用合併銷售相減 | t173 |
| 2026 Q1 | [0000034088-26-000067](https://www.sec.gov/Archives/edgar/data/34088/000003408826000067/xom-20260331.htm) | t19，四業務及 Segment Total 銷售；Corporate 另用合併銷售相減 | t7 |
| 2026 Q2 | [0000034088-26-000093](https://www.sec.gov/Archives/edgar/data/34088/000003408826000093/xom-20260630.htm) | t20，四業務及 Segment Total 銷售；Corporate 另用合併銷售相減 | t8 |
| 2026 Q3 | [0002115436-26-000020](https://www.sec.gov/Archives/edgar/data/2115436/000211543626000020/xom-20260930.htm) | t12，四業務及 Segment Total 銷售；Corporate 另用合併銷售相減 | t5 |

FY2023 只作較早年度依據，不產生預設範圍內的輸出或證據檔。Q4 的年度運算元使用對應 10-K 的表格，九個月運算元使用同財年 Q3 10-Q 的表格。口徑差額中的權益法收益與其他收入在各主申報損益表，Q4 同樣取年度減九個月。

## 已知的重複 fact

合併 Sales and other operating revenue 在損益表、銷售收入附註與地區附註重複標記；FY2023 與 2024 Q1–Q3 另在分部表列出。這些 fact 同 concept、完整 dimensions 與期間。框架檢查精度與重複值一致性後，選取包含最多其他運算元的表格；相同時取文件順序第一個。

FY2024 起，分部表沒有本觀點使用的合併銷售 fact，所以分部表與損益表都會成為運算元來源。Corporate 調節項與總營收共用同一個合併銷售 fact，分部銷售合計只作調節項的減數，不作總營收。

## 揭露格式與繼受申報人

FY2024 10-K 起，分部表新增較完整的分部總收入及損益調節呈現。這個 parser 仍取 Sales and other operating revenue 列，沒有把新的 Segment revenues and other income 列當作銷售。直接 Corporate 銷售改為合併銷售與 Segment Total 銷售的差額；各比較期間也按承載該比較欄的申報內實際 fact 組成。

2026 Q3 改由繼受申報人申報，四個業務銷售的 concept 與 dimensions 沒有因此更換。較晚申報只供框架比對較早期別，不改寫原期數字。

## 驗證

正式輸出涵蓋 11 季（2024-03-31 至 2026-09-30）與 2 個年度（FY2024、FY2025）。`data/revenue/X/XOM/status.json` 的 13 期皆為 `published`，沒有 `failed` 或 `not_derived`；兩個 Q4 均由年度減同財年九個月累計推算。各期 `revenue.json` 的四類加 Corporate and Financing 調節項，均等於合併銷售總額。

採用來源 TradingView 的範圍內對照資料只有 FY2024、FY2025。以下逐筆比對正式 `revenue.json` 與 `data/universe/references/X/XOM/reference.json`，數值與差額單位為百萬美元；差額為 SEC 值減對照值。

| 年度 | 分類 | SEC 值 | TradingView 顯示值 | 差額 |
|---|---|---:|---:|---:|
| FY2024 | Energy Products | 260,856 | 260.86B | -4 |
| FY2024 | Upstream | 37,131 | 37.13B | 1 |
| FY2024 | Chemical Products | 22,896 | 22.90B | -4 |
| FY2024 | Specialty Products | 18,253 | 18.25B | 3 |
| FY2025 | Energy Products | 244,451 | 244.45B | 1 |
| FY2025 | Upstream | 39,389 | 39.39B | -1 |
| FY2025 | Chemical Products | 22,209 | 22.21B | -1 |
| FY2025 | Specialty Products | 17,771 | 17.77B | 1 |

8 筆均在顯示精度內，沒有超出容許精度而需要解釋的差異。TradingView 顯示到 0.01B，半個顯示單位為 5 百萬美元；每類的兩個 SEC 運算元均為 `decimals=-6`，各有 0.5 百萬美元精度誤差，因此每筆比對的容許差額為 6 百萬美元。SEC 值取自上述 FY2024、FY2025 10-K 的分部銷售 fact，完整 dimensions 及來源位置見前文。

季度序列 2024 Q1 至 2026 Q3 共 11 期為「來源沒有資料、沒有比對的期別」，不以富途替代。Corporate and Financing 調節項在這兩個年度的 TradingView 資料均為空值，不當作零；合併銷售總額也沒有來源對照值，兩者未與 TradingView 比對。FY2023 僅作較早年度口徑依據，不在預設輸出範圍，其餘更早的對照期間未比對。

## 比較欄

正式 `status.json` 的 13 期均沒有 `differences`，也沒有頂層 `comparison_errors`。已下載申報的比較欄與正式輸出，在框架比對到的分類、調節項及總營收角色上，沒有產生超出精度的差異或無法解析的標記。Q4 的年度與九個月累計角色均包含在比較欄比對範圍內。
