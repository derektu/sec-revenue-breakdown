# LLY parser

## 觀點

採用 Stock Analysis 的治療領域產品別觀點（`view="product"`），五類依序為 Diabetes and obesity／Cardiometabolic Health、Oncology、Immunology、Neuroscience、Other。名稱依各期 SEC 申報；Stock Analysis 將第一類統一標為 Cardiometabolic。

Other 列為分類，沒有調節項。有治療領域拆分的來源只有 Stock Analysis，它列出 Other；富途與 TradingView 沒有拆分。

| 對照來源 | 分類 | 採用情形 |
|---|---|---|
| Stock Analysis | Cardiometabolic、Oncology、Immunology、Neuroscience、Other | 採用面向與順序；名稱照 SEC 各期原文 |
| 富途 | Discovery, development, manufacturing, marketing, and sales of pharmaceutical products worldwide | 單一業務，沒有營收組成拆分，不採用 |
| TradingView | Human Pharmaceutical Products | 範圍內只有單一業務，不採用 |

主要藥品的個別營收是治療領域的下一層，不另列為分類。美國與非美國只在年報合成全球產品類別營收，不作地區觀點。分部軸的單一製藥業務不採用。

## 分類與 tag

所有分類與總營收的 concept 均為 `us-gaap:Revenues`，單位 USD。

| 分類 | `srt:ProductOrServiceAxis` 成員 |
|---|---|
| Diabetes and obesity | `lly:DiabetesAndObesityMember` |
| Cardiometabolic Health | `lly:CardiometabolicHealthMember` |
| Oncology | `lly:OncologyMember` |
| Immunology | `lly:ImmunologyMember` |
| Neuroscience | `lly:NeuroscienceMember` |
| Other | `lly:OtherProductTotalMember` 或 `us-gaap:ProductAndServiceOtherMember` |
| 總營收 Revenue | 不帶任何 dimensions |

完整 scope 有兩種，依該申報、該期間的 fact 選擇。

- 有全球合計時，只帶表中一個產品軸與成員，沒有其他 dimensions。
- 沒有全球合計時，以兩個 fact 相加。兩者均帶表中產品軸與成員，另外各帶 `srt:StatementGeographicalAxis=country:US` 或 `srt:StatementGeographicalAxis=us-gaap:NonUsMember`，沒有其他 dimensions。這兩個地區是該產品成員同期間的全部地區成員，每項權重 1，不混用全球合計。

10-Q 的單季與九個月累計有全球合計；FY2023、FY2024、FY2025 10-K 的治療領域數值只有美國與非美國 fact，使用後者。總營收始終使用不帶維度的合併 fact。

第一類依申報內該期間的成員選擇名稱，優先找 Cardiometabolic Health；沒有時找 Diabetes and obesity。FY2023 10-K（0000059478-24-000065，期末 2023-12-31）與 2024Q1 10-Q（0000059478-24-000118，期末 2024-03-31）列 Diabetes and obesity。2024Q2 10-Q（0000059478-24-000187，期末 2024-06-30）首次列 Cardiometabolic Health，`categories` 從該季起日 2024-04-01 切換。名稱取自營收表的治療領域標題，去掉冒號或 Total 修飾。

Other 在 2026Q1 10-Q（0000059478-26-000045，期末 2026-03-31）改用 `us-gaap:ProductAndServiceOtherMember`，同表比較欄也用新成員。每份申報都以 `one_of` 找兩種成員，不依年份排除寫法。採治療領域的完整 Other 合計，不採較早申報中 Other 類別內的 `lly:OtherProductMember` 細項。

## 期別與推算

財年即曆年，季末為 3、6、9、12 月最後一天。期別範圍自預設起始日 2024-01-01 起；`categories` 的有依據下限是 2023-12-31，涵蓋 FY2023 作為第一個 Q4 的前一年口徑依據。更早的主申報不在支援範圍內，不能將較早日期的分類回答當作已驗證。2023Q1–Q3 10-Q（0000059478-23-000162、0000059478-23-000221、0000059478-23-000284）的第一類是 Diabetes（`lly:DiabetesMember`），parser 不涵蓋；以 `--start` 處理 2023 年各季前要先擴充。

- Q1–Q3 使用當期 10-Q 的三個月 fact。
- FY 使用當期 10-K 的年度 fact。
- Q4 由框架以年度減同財年 Q3 10-Q 九個月累計，並檢查分類集合與上一財年口徑。parser 每次只讀框架提供的一份申報。
- 2024Q4 的分類集合在財年內改變，依現行規則不推算。即使年度減九個月能得到候選數字，也不補入 Q4。
- 2025Q4 的年度、九個月與 Q1–Q3 均為同一組名稱，通過推算條件與口徑一致檢核，正常輸出。

## 數字在原文的位置

分類取自營收附註的治療領域與主要產品表。10-Q 使用 U.S.、Outside U.S.、Total 欄中的 Total；10-K 的該表只有 U.S.、Outside U.S. 欄，兩欄 fact 相加。下表依正式 `revenue.json` 的運算元及 `evidence/` 檔名末尾的 `-t<編號>` 列出實際證據位置。

| 正式輸出 | 五個分類的證據 | 總營收的證據 |
|---|---|---|
| 2024Q1 | 2024Q1 10-Q t14 | 同表 t14 的 Revenue 列 |
| 2024Q2 | 2024Q2 10-Q t15 | 同表 t15 的 Revenue 列 |
| 2024Q3 | 2024Q3 10-Q t15 | 同表 t15 的 Revenue 列 |
| FY2024 | FY2024 10-K t31 | 同份 10-K t24，合併損益表 Revenue 列 |
| 2025Q1 | 2025Q1 10-Q t13 | 同表 t13 的 Revenue 列 |
| 2025Q2 | 2025Q2 10-Q t14 | 同表 t14 的 Revenue 列 |
| 2025Q3 | 2025Q3 10-Q t14 | 同表 t14 的 Revenue 列 |
| 2025Q4 | FY2025 10-K t29 的年度值，減 2025Q3 10-Q t15 的九個月累計 | FY2025 10-K t23 合併損益表 Revenue 列，減 2025Q3 10-Q t15 的 Revenue 列 |
| FY2025 | FY2025 10-K t29 | 同份 10-K t23，合併損益表 Revenue 列 |
| 2026Q1 | 2026Q1 10-Q t12 | 同表 t12 的 Revenue 列 |
| 2026Q2 | 2026Q2 10-Q t12 | 同表 t12 的 Revenue 列 |
| 2026Q3 | 2026Q3 10-Q t12 | 同表 t12 的 Revenue 列 |

各張治療領域證據表都含完整五類，沒有五類分散在跨頁不同段表格的情形。2025Q3 的 t14 是三個月單季表，t15 是九個月累計表；它們是不同期間的完整表，不是同一張表的跨頁段。FY2024 的 t24、FY2025 的 t23 則是獨立的合併損益表，並非治療領域表的續頁。

2024Q4 不推算，沒有該季的 `revenue.json` 與證據檔。前一年口徑依據 FY2023 10-K 的分類 fact 位於 t30；它不在正式輸出範圍，沒有獨立發布的 FY2023 證據目錄。總營收雖在其他表重複標記，正式輸出採用的表格以上表為準。

## 第一類改名與範圍

2024Q2 10-Q（[0000059478-24-000187](https://www.sec.gov/Archives/edgar/data/59478/000005947824000187/lly-20240630.htm)）的營收附註以 Cardiometabolic Health 取代 Diabetes and obesity。該申報沒有單獨列出 2024Q1 比較欄；t15 是 2024Q2 與 2023Q2，t16 是 2024 與 2023 上半年。不能把半年欄稱為 Q1 比較欄。

查核大類範圍時，用同份 Q2 申報的半年累計減去 Q2，再與 Q1 申報（[0000059478-24-000118](https://www.sec.gov/Archives/edgar/data/59478/000005947824000118/lly-20240331.htm)，t14）直接列示的 Q1 比較。下表單位百萬美元，全部數值取自 `us-gaap:Revenues`，完整 dimensions 只有 `srt:ProductOrServiceAxis` 與本文件列出的對應成員。

| 分類 | Q2 申報半年累計 | Q2 申報單季 | 兩者相減推知 Q1 | Q1 原申報 |
|---|---:|---:|---:|---:|
| Diabetes and obesity／Cardiometabolic Health | 13,007.6 | 7,514.6 | 5,493.0 | 5,493.0 |
| Oncology | 3,968.7 | 2,158.7 | 1,810.0 | 1,810.0 |
| Immunology | 1,916.3 | 1,082.4 | 833.9 | 834.0 |
| Neuroscience | 728.6 | 339.5 | 389.1 | 389.1 |
| Other | 449.6 | 207.6 | 242.0 | 241.9 |

每個直接值的 `decimals=-5`，推知值與 Q1 的比較容許三個 fact 合計 0.15 百萬美元誤差；各類都在此範圍內。這是解釋口徑的研究計算，不是 parser 的 Q1 運算式。

Q2 申報將 2023Q2 比較欄也稱為 Cardiometabolic Health，其全球合計 5,010.9 與當時 Q2 原申報（0000059478-23-000221）的 Diabetes 合計相同。2024Q1、Q2 表中的主要產品仍在同一大類；Q2 另列 Baqsimi 子列，沒有從其他治療領域移入第一類的說明。營收附註未見明述此改名造成大類範圍變更的文字，也未找到相應的治療領域重分類說明。

另有兩筆直接列示的 XBRL 證據，單位均為百萬美元，concept 均為 `us-gaap:Revenues`，完整 dimensions 只有 `srt:ProductOrServiceAxis` 與下列成員。

- 2025Q1 10-Q（[0000059478-25-000132](https://www.sec.gov/Archives/edgar/data/59478/000005947825000132/lly-20250331.htm)）t13 的 2024Q1 比較欄，`lly:CardiometabolicHealthMember` 為 5,493.0，與原 2024Q1 10-Q t14 的 `lly:DiabetesAndObesityMember` 相同，期間均為 2024-01-01 至 2024-03-31。
- 2024Q2 10-Q t16 的 2023 上半年比較欄，`lly:CardiometabolicHealthMember` 為 9,201.3，與 2023Q2 10-Q（[0000059478-23-000221](https://www.sec.gov/Archives/edgar/data/59478/000005947823000221/lly-20230630.htm)）t16 的 `lly:DiabetesMember` 相同，期間均為 2023-01-01 至 2023-06-30。

據直接比較欄、半年減單季及產品列，判斷本次為大類改名，未發現伴隨跨大類範圍調整的證據。這項判斷不把不同名稱視為同一輸出分類：各期仍按當期申報命名，2024Q4 仍因分類集合改變而不推算。更早主申報的 Diabetes 名稱不納入本 parser 支援範圍。

## 驗證

正式範圍為 2024-03-31 至 2026-09-30。`status.json` 的 Q 序列共 11 期，10 期 `published`、2024-12-31 一期 `not_derived`；FY2024、FY2025 均為 `published`，沒有 `failed`。2024Q4 不推算的檢核為「Q4 推算條件」：2024-01-01 至 2024-03-31 的第一類為 Diabetes and obesity，與年度的 Cardiometabolic Health 不同。

與 `data/universe/references/L/LLY/reference.json` 中 Stock Analysis 的季度值逐期比對。下表是正式 `revenue.json` 的分類值，單位百萬美元；第一欄分類對應來源的 Cardiometabolic，2024Q1 的 SEC 名稱為 Diabetes and obesity，其後為 Cardiometabolic Health。

| 期別 | 第一類 | Oncology | Immunology | Neuroscience | Other | 比對結果 |
|---|---:|---:|---:|---:|---:|---|
| 2024Q1 | 5,493.0 | 1,810.0 | 834.0 | 389.1 | 241.9 | 五類均在顯示精度內 |
| 2024Q2 | 7,514.6 | 2,158.7 | 1,082.4 | 339.5 | 207.6 | 五類均在顯示精度內 |
| 2024Q3 | 7,407.0 | 2,231.8 | 1,185.7 | 351.8 | 262.8 | 五類均在顯示精度內 |
| 2025Q1 | 9,208.1 | 1,947.5 | 1,088.0 | 272.1 | 212.9 | 五類均在顯示精度內 |
| 2025Q2 | 11,342.9 | 2,413.6 | 1,255.6 | 344.0 | 201.5 | 五類均在顯示精度內 |
| 2025Q3 | 13,177.9 | 2,407.6 | 1,362.4 | 315.7 | 337.2 | 五類均在顯示精度內 |
| 2025Q4 | 14,492.1 | 2,607.3 | 1,541.0 | 459.2 | 191.4 | 五類均在顯示精度內 |
| 2026Q1 | 15,760.0 | 2,268.0 | 1,203.0 | 382.0 | 187.0 | 五類均在顯示精度內 |
| 2026Q2 | 18,353.0 | 2,570.0 | 1,417.0 | 429.0 | 205.0 | 五類均在顯示精度內 |

共比對 9 季、45 筆分類值，沒有超過精度容許範圍的差異或原因未確認的數值差異。容許範圍為來源顯示單位的一半，加上正式運算式每個 SEC 運算元 `decimals` 單位的一半；2025Q4 每個分類計入兩個年度地區運算元與一個九個月累計運算元的誤差。

未比對的期別與來源如下。

- 2024Q4：來源有值，但正式結果為 `not_derived`，不以候選算術值代替正式輸出比較。
- 2026Q3：正式輸出已發布，但 Stock Analysis 對照快照只到 2026Q2，沒有可比值。
- FY2024、FY2025：Stock Analysis 對照資料只有季度，沒有年度值，不以四季相加代替來源年度值。
- 2024-01-01 以前：不在正式輸出範圍，未逐期比對；FY2023 只作前一年口徑依據。
- 富途與 TradingView：不是採用來源，不作本觀點的逐期驗收比對。

## 比較欄

正式 `status.json` 各期均沒有 `differences`，沒有差異標記或比較錯誤紀錄。

比較欄依每份申報自己的成員與名稱組成。較晚申報將第一類改稱 Cardiometabolic Health 時，不會倒過來將已發布的 2024Q1 Diabetes and obesity 改名；同名分類找不到比較值時屬於 `not_found`，依框架規則不寫差異標記。因此，沒有差異標記不代表每份較晚申報都能提供每個早期分類的同名比較值。
