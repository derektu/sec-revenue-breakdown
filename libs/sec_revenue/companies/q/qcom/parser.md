# QCOM parser

## 觀點

採用業務分部（`business_segment`），順序為 QCT、QTL、QSI，再接當期申報的營收調節列。`us-gaap:StatementBusinessSegmentsAxis` 成員為 QCT、QTL、QSI 等業務別，不是地區。總營收為 Total revenues。

採用富途季度，TradingView 作年度輔助。對照資料見 [reference.json](../../../../../data/universe/references/Q/QCOM/reference.json)。

| 來源 | 分類與對應 |
|---|---|
| 富途 | Qualcomm Code Division Multiple Access (CDMA) Technologies (QCT)＝QCT；QUALCOMM Technology Licensing (QTL)＝QTL；Qualcomm Strategic Initiatives (QSI)＝QSI；對賬項目及調節明細依各期 scope 對應 |
| TradingView | Qualcomm CDMA Technologies＝QCT；Qualcomm Technology Licensing＝QTL；Qualcomm Strategic Initiatives＝QSI；FY2024 Reconciling Items 是調節合計，FY2025 同名欄是 Nonreportable segments，Unallocated 是 Unallocated revenues |
| Stock Analysis | Equipment and Services、Licensing，屬收入類型，不是本 parser 採用的觀點 |

按開發指南第 1 步，只計算拆分到業務分部的富途與 TradingView。兩者在起始日以後都列出有值的調節數字，故調節列全部列為分類，不另設 `reconciling`。以各期實際 scope 判斷，不能因網站欄名相同而把合計與明細當同一類。TradingView 全為空值的 Qualcomm Wireless and Internet 不計入。

QCT 的 Handsets、Automotive、IoT 是分部內的產品明細，不納入。Equipment and services、Licensing 與地區拆分亦不納入。QSI 的明列零值保留；來源省略 QSI 不代表公司取消分部。

## 分類與 tag

以下 dimensions 均為完整集合，沒有省略維度。所有輸入都是主文件的 XBRL fact，單位 USD。

| 分類 | concept | 完整 dimensions |
|---|---|---|
| QCT | 下述三種等值寫法 | `us-gaap:StatementBusinessSegmentsAxis=qcom:QctMember`，依寫法加下述 consolidation 軸 |
| QTL | 下述三種等值寫法 | `us-gaap:StatementBusinessSegmentsAxis=qcom:QtlMember`，依寫法加下述 consolidation 軸 |
| QSI | 下述三種等值寫法 | `us-gaap:StatementBusinessSegmentsAxis=qcom:QsiMember`，依寫法加下述 consolidation 軸 |
| Reconciling items | `us-gaap:Revenues` | `srt:ConsolidationItemsAxis=us-gaap:MaterialReconcilingItemsMember` |
| Nonreportable segments | `us-gaap:Revenues` | `srt:ConsolidationItemsAxis=us-gaap:MaterialReconcilingItemsMember`、`us-gaap:StatementBusinessSegmentsAxis=us-gaap:AllOtherSegmentsMember` |
| Unallocated revenues | `us-gaap:Revenues` | `srt:ConsolidationItemsAxis=us-gaap:MaterialReconcilingItemsMember`、`srt:LitigationCaseAxis=us-gaap:LicensingAgreementsMember` |
| Total revenues | `us-gaap:Revenues` | 無維度 |

三個分部各自用 `one_of` 查找下列寫法。同份申報同時找到多種寫法時，由框架確認數值一致，不相加。

| 寫法 | concept | 分部軸以外的 dimensions | 本次範圍最早確認的申報 |
|---|---|---|---|
| 1 | `us-gaap:Revenues` | 無 | FY2023 10-K，0000804328-23-000055，2023-09-24 |
| 2 | `us-gaap:Revenues` | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember` | FY2025 Q3 10-Q，0000804328-25-000045，2025-06-29 |
| 3 | `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax` | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember` | FY2025 10-K，0000804328-25-000085，2025-09-28 |

QCT 在新式分部表之外仍有 `Revenues` 的同值 fact；QTL、QSI 可只有寫法 3。選 fact 不依日期、不讀表格文字。分類名稱取自分部表的 QCT、QTL、QSI 欄標題及營收調節表的列標籤。

`compose` 先查有 consolidation 軸的 Nonreportable segments。沒有時取 Reconciling items 合計；有時取明細，並只在同份申報的該段期間有 Unallocated revenues fact 時列出該類。舊申報另有不帶 consolidation 軸的 Nonreportable segments 明細，但當時分部表列的是 Reconciling items 合計，不用明細改寫早期分類。

`categories(day)` 的分類集合如下。每個切點均為第一份新結構主申報所涵蓋季度的起日。

| 日期 | 分類集合 | 申報依據 |
|---|---|---|
| 2023-09-24 至 2025-06-29 | QCT、QTL、QSI、Reconciling items | FY2023 10-K 至 FY2025 Q3 10-Q |
| 2025-06-30 至 2025-09-28 | QCT、QTL、QSI、Nonreportable segments、Unallocated revenues | FY2025 10-K，0000804328-25-000085，2025-09-28，t60–61 |
| 2025-09-29 至 2025-12-28 | QCT、QTL、QSI、Nonreportable segments | FY2026 Q1 10-Q，0000804328-26-000017，2025-12-28，t37、t39 |
| 2025-12-29 起 | QCT、QTL、QSI、Nonreportable segments、Unallocated revenues | FY2026 Q2 10-Q，0000804328-26-000061，2026-03-29，t37、t39 |

FY2026 Q1 的 t39 營收調節表沒有 Unallocated revenues 這一列，也沒有該期對應 fact，因此不列、不補零。FY2026 Q2 的 t39 恢復此列，本期單季與半年皆明列零；FY2026 Q3 t40 亦明列零。這兩期保留分類與零值。

日期涵蓋下限為 2023-09-24，包含第一個範圍內財年的上一財年期末。更早日期雖回傳舊集合，不宣稱已驗證。調節合計改列明細不是純改名，不宣告 `FORMER_NAMES`。沒有新增 utility，也沒有自訂期間、財年或附件。

## 期別與推算

財年採 52／53 週制，於九月最後一個星期日結束。本次單季 91 天，FY2024 Q4 為 98 天；半年 182 天、九個月 273 天，年度 364 或 371 天，都在框架預設範圍內。財年及季別取申報宣告。

- Q1–Q3 取當期 10-Q 的單季 fact；FY 取當期 10-K 年度 fact。
- Q4 由框架以當年年度減當年 Q3 九個月累計。FY2024 分類與口徑一致，可推算。
- FY2025 Q4 因合計改列明細，年度分類集合不同於 Q1–Q3，為 `not_derived`。
- FY2026 Q4 因 Q1 未列 Unallocated revenues、Q2 起恢復，財年內分類集合不同，為 `not_derived`。即使年度與 Q3 都有該 fact，也不自行相減補季。
- FY2026 10-K 預告 FY2027 Q1 起將 Data Center 納入 QCT，不提前套用至本次期別。

## 數字在原文的位置

表號與證據檔名依 `data/revenue/Q/QCOM/` 各期 `revenue.json` 的 `operands[*].evidence.table` 列示。證據檔位於各期的 `evidence/`，下表檔名各有 `.html` 與 `.png`。全部來自各 accession 的 SEC 主文件；各運算元保留文件 URL、原始文件雜湊、期間、單位、完整 dimensions 與證據雜湊。FY2023 與 FY2024 Q1 僅為依賴申報，不是輸出期別，沒有對應的正式證據檔。

| 期別 | accession | 分部與調節列、總營收的表號 | 證據檔名（不含副檔名） |
|---|---|---|---|
| FY2023，首個 Q4 的上一財年口徑依據 | 0000804328-23-000055 | t60；表號取原文 fact 清單 | 無，僅作口徑依據 |
| FY2024 Q1，範圍外依賴 | 0000804328-24-000017 | t34；表號取原文 fact 清單 | 無，僅作同財年依賴查核 |
| FY2024 Q2 | 0000804328-24-000039 | t35 | `0000804328-24-000039-1fab7606cde1-t35` |
| FY2024 Q3 | 0000804328-24-000056 | t35 | `0000804328-24-000056-f439b0e1ad88-t35` |
| FY2024 | 0000804328-24-000075 | t60 | `0000804328-24-000075-03e24b7e3b2a-t60` |
| FY2024 Q4 | 0000804328-24-000075、0000804328-24-000056 | 年度 t60、九個月 t35 | `0000804328-24-000075-03e24b7e3b2a-t60`、`0000804328-24-000056-f439b0e1ad88-t35` |
| FY2025 Q1 | 0000804328-25-000011 | t36 | `0000804328-25-000011-955a7dc6f36c-t36` |
| FY2025 Q2 | 0000804328-25-000031 | t36 | `0000804328-25-000031-2b7d9c49862e-t36` |
| FY2025 Q3 | 0000804328-25-000045 | t37 | `0000804328-25-000045-ae1a279d27d9-t37` |
| FY2025 | 0000804328-25-000085 | 分部 t60；Nonreportable segments、Unallocated revenues、總營收 t61 | `0000804328-25-000085-839d8cccf9e7-t60`、`0000804328-25-000085-839d8cccf9e7-t61` |
| FY2026 Q1 | 0000804328-26-000017 | 分部 t37；Nonreportable segments、總營收 t39 | `0000804328-26-000017-9c12c92f8162-t37`、`0000804328-26-000017-9c12c92f8162-t39` |
| FY2026 Q2 | 0000804328-26-000061 | 分部 t37；Nonreportable segments、Unallocated revenues、總營收 t39 | `0000804328-26-000061-688fc4bf9395-t37`、`0000804328-26-000061-688fc4bf9395-t39` |
| FY2026 Q3 | 0000804328-26-000086 | 分部 t38；Nonreportable segments、Unallocated revenues、總營收 t40 | `0000804328-26-000086-6a310ab7a88f-t38`、`0000804328-26-000086-6a310ab7a88f-t40` |
| FY2026 | 0000804328-26-000128 | 分部 t62；Nonreportable segments、Unallocated revenues、總營收 t63 | `0000804328-26-000128-c4edb242f64c-t62`、`0000804328-26-000128-c4edb242f64c-t63` |

SEC 文件：[FY2023](https://www.sec.gov/Archives/edgar/data/804328/000080432823000055/qcom-20230924.htm)、[FY2024](https://www.sec.gov/Archives/edgar/data/804328/000080432824000075/qcom-20240929.htm)、[FY2025](https://www.sec.gov/Archives/edgar/data/804328/000080432825000085/qcom-20250928.htm)、[FY2026](https://www.sec.gov/Archives/edgar/data/804328/000080432826000128/qcom-20260927.htm)。本 parser 只讀已下載且核對雜湊的 SEC 原文。

## 已知的重複 fact

舊式申報的 QCT 常在分部表及產品營收表重複標記；總營收亦在損益表、分部表及營收拆分表重複。新式申報的 QCT 可同時有 `Revenues` 與合約營收 concept。框架核對同值後依證據選取規則擇一，沒有把重複標記加總。

## 驗證

依 `data/revenue/Q/QCOM/status.json`，範圍內為 FY2024 Q2 至 FY2026 Q4 共 11 季，以及 FY2024 至 FY2026 共 3 個年度。9 季與 3 個年度為 `published`，各有正式 `revenue.json` 與表格證據；FY2025 Q4、FY2026 Q4 因財年內分類集合不同而 `not_derived`，沒有季度營收輸出。沒有 `failed` 期別。下列 SEC 數值均與各期正式輸出一致。

富途季度逐期比對如下，單位百萬美元。QCT、QTL 與有資料的 QSI 均為精確同值；表中的「缺值」不視為零，也不宣稱已比對。

| 財年季別 | SEC 期末日 | QCT | QTL | QSI | 其他分類與來源的對應及差異 |
|---|---|---:|---:|---:|---|
| FY2024 Q2 | 2024-03-24 | 8,026 | 1,318 | 3 | Reconciling items 42＝富途對賬項目 42，全數同值 |
| FY2024 Q3 | 2024-06-23 | 8,069 | 1,273 | 2 | Reconciling items 49＝富途對賬項目 49，全數同值 |
| FY2024 Q4 | 2024-09-29 | 8,678 | 1,521 | 0，富途缺值 | Reconciling items 45；富途分列 Nonreportable segments 176 與對賬項目 −131，合計 45，層級與單列算法不同 |
| FY2025 Q1 | 2024-12-29 | 10,084 | 1,535 | 0，富途缺值 | Reconciling items 50＝富途 Nonreportable segments 50 |
| FY2025 Q2 | 2025-03-30 | 9,469 | 1,319 | 0，富途缺值 | Reconciling items 191＝富途 Nonreportable segments 48＋Unallocated revenues 143 |
| FY2025 Q3 | 2025-06-29 | 8,993 | 1,318 | 0，富途缺值 | Reconciling items 54＝富途 Nonreportable segments 54 |
| FY2025 Q4 | 2025-09-28 | 不推算 | 不推算 | 不推算 | 富途列 QCT 9,821、QTL 1,410、Nonreportable segments 40；本期 `not_derived`，沒有輸出可比 |
| FY2026 Q1 | 2025-12-28 | 10,613 | 1,592 | 0，富途缺值 | Nonreportable segments 47，同值；雙方均未列 Unallocated revenues |
| FY2026 Q2 | 2026-03-29 | 9,076 | 1,382 | 0，富途缺值 | Nonreportable segments 141，同值；本期 Unallocated revenues 明列 0，富途缺值 |
| FY2026 Q3 | 2026-06-28 | 8,504 | 1,278 | 0，富途缺值 | Nonreportable segments 165，同值；本期 Unallocated revenues 明列 0，富途缺值 |
| FY2026 Q4 | 2026-09-27 | 不推算 | 不推算 | 不推算 | 富途列 QCT 9,015、QTL 1,304、Nonreportable segments 123、Unallocated revenues −120；本期 `not_derived`，沒有輸出可比 |

調節列層級差異的 SEC 證據：

- FY2024 Q4：[FY2024 10-K](https://www.sec.gov/Archives/edgar/data/804328/000080432824000075/qcom-20240929.htm) t60–61 的調節年度合計及 Nonreportable segments 都是 176，Unallocated revenues 為明列零；[FY2024 Q3 10-Q](https://www.sec.gov/Archives/edgar/data/804328/000080432824000056/qcom-20240623.htm) t35、t37 的九個月調節合計及 Nonreportable segments 都是 131。合計單季為 176−131＝45。富途的兩列分別對上年度 176 與負九個月 −131，合計同值，但不能各自當作同名單季明細；本 parser 不採這種混合呈現。
- FY2025 Q1：[10-Q](https://www.sec.gov/Archives/edgar/data/804328/000080432825000011/qcom-20241229.htm) t36–37 的調節合計與 Nonreportable segments 都是 50。
- FY2025 Q2：[10-Q](https://www.sec.gov/Archives/edgar/data/804328/000080432825000031/qcom-20250330.htm) t36、t38 的單季調節合計 191＝Nonreportable segments 48＋Unallocated revenues 143。
- FY2025 Q3：[10-Q](https://www.sec.gov/Archives/edgar/data/804328/000080432825000045/qcom-20250629.htm) t37、t39 的單季調節合計 54＝Nonreportable segments 54＋Unallocated revenues 明列零。

上述是可由 SEC 原文重現的來源分類層級差異，不改 parser 去追隨網站的拆列。沒有超出顯示精度而原因未確認的可比數值。

TradingView 年度輔助比對如下，單位百萬美元。其 B 顯示至 0.01B，以顯示單位的一半 5 百萬，加每個 SEC fact 的半百萬精度判定。

| 財年 | 本 parser | TradingView | 結論 |
|---|---|---|---|
| FY2024，2024-09-29 | QCT 33,196；QTL 5,572；QSI 18；Reconciling items 176 | 33,200；5,570；18；176 | QCT 相差 −4、QTL ＋2，均在顯示精度內；另兩項同值 |
| FY2025，2025-09-28 | QCT 38,367；QTL 5,582；QSI 0；Nonreportable segments 192；Unallocated revenues 143 | 38,370；5,580；QSI 缺值；Reconciling Items 192；Unallocated 143 | QCT 相差 −3、QTL ＋2，均在顯示精度內；調節明細同值；QSI 未比 |
| FY2026，2026-09-27 | QCT 37,208；QTL 5,556；QSI 0；Nonreportable segments 476；Unallocated revenues −120 | 沒有該年度 | 未比對 |

富途沒有年度資料，年度不以其季度補作獨立年度驗證。FY2024 Q1 的期末日為 2023-12-24，雖然申報日在 2024 年，仍在預設起始日之前，不列為本次輸出或逐期驗證；原文作同財年依賴查核。FY2023 及更早的 TradingView 年度亦在範圍外，未作對照驗證。

## 比較欄

正式 `status.json` 沒有 `different` 或 `unparseable` 差異標記，也沒有 `comparison_errors`。

合計改列明細後，較晚申報沒有舊分類 Reconciling items，框架的 `not_found` 不列為差異標記；所以沒有標記不代表每個歷史分類在較晚申報都有同名可比值。這是分類拆分，沒有使用 `FORMER_NAMES` 將合計映射到單一明細。
