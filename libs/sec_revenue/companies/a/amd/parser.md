# AMD parser

## 觀點

業務分部（`view="business_segment"`）。`us-gaap:StatementBusinessSegmentsAxis` 的成員是業務別，不是地區。2024 年為 Data Center、Embedded、Client、Gaming；2025 Q1 起為 Data Center、Client and Gaming、Embedded。無調節項，總營收取無維度的 Total net revenue。

分類名稱取自原文分部表的 Net revenue 列，Client and Gaming 取 Total Client and Gaming 小計並去掉 Total；順序照採用來源 `tradingview`。TradingView 只有年度，FY2024 保留四分部，FY2025 為三分部。Stock Analysis 作季度輔助：它回溯把 2024 年 Client 與 Gaming 合併，只在對照時計算兩類之和，不影響輸出分類。富途的季度亦多為三類，兩個 Q4 混列全年值與負的累計值，不採用為主來源。

2025 年起 Client／Gaming 另有帶 `srt:ProductOrServiceAxis` 的產品細項，與 Client and Gaming 小計範圍重疊，不納入分類。地區營收的 `srt:StatementGeographicalAxis` 不採用。All Other 是費用與營業損益調節，沒有營收列；TradingView 的 All Other 也無有效數字，不新增分類或補零。

## 分類與 tag

所有營收使用 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`，USD；原文以百萬美元顯示，fact 的 scale 為 6、decimals 為 -6。下表縮寫是完整維度的別名：

- `S`：`us-gaap:StatementBusinessSegmentsAxis`
- `C`：`srt:ConsolidationItemsAxis`

| 適用申報 | 分類 | 完整 dimensions（以軸別名展開） |
|---|---|---|
| FY2023、FY2024 10-K | Data Center | `{S: amd:DatacenterMember}` |
| 同上 | Embedded | `{S: amd:EmbeddedMember}` |
| 同上 | Client | `{S: amd:ClientMember}` |
| 同上 | Gaming | `{S: amd:GamingMember}` |
| 2024 Q1–Q3 10-Q | Data Center | `{S: amd:ClientMember}` |
| 同上 | Embedded | `{S: amd:EmbeddedMember}` |
| 同上 | Client | `{S: amd:GamingMember}` |
| 同上 | Gaming | `{S: amd:DataCenterMember}` |
| 2025 Q1 起的 10-Q | Data Center | `{C: us-gaap:OperatingSegmentsMember, S: amd:DataCenterMember}` |
| FY2025 10-K | Data Center | `{C: us-gaap:OperatingSegmentsMember, S: amd:DatacenterMember}` |
| 2025 Q1 起的 10-Q、FY2025 10-K | Client and Gaming | `{C: us-gaap:OperatingSegmentsMember, S: amd:ClientAndGamingMember}` |
| 同上 | Embedded | `{C: us-gaap:OperatingSegmentsMember, S: amd:EmbeddedMember}` |
| 全部 | Total net revenue（總營收） | `{}`，無維度的合併營收 |

三分部以該份申報、該段期間有沒有帶合併軸的 `amd:ClientAndGamingMember` fact 判斷，因此較晚申報的比較欄也照該申報自己的三分部結構組。Data Center 的兩種大小寫寫法以 `one_of` 查找，若同時存在須同值；其他分類均為單一 fact，不加總產品細項。

四分部的錯位映射依 `filing.report_date` 的 2024-03-30 至 2024-09-28 範圍切換，原因是這三份申報自己的列標籤與 member 不一致，無法由 member 字面區分其業務含義。從 [2024 Q1 10-Q `0000002488-24-000056`](https://www.sec.gov/Archives/edgar/data/2488/000000248824000056/amd-20240330.htm) 開始，到 [Q3 `0000002488-24-000163`](https://www.sec.gov/Archives/edgar/data/2488/000000248824000163/amd-20240928.htm) 為止；[FY2024 10-K `0000002488-25-000012`](https://www.sec.gov/Archives/edgar/data/2488/000000248825000012/amd-20241228.htm) 回到年報映射。映射同時適用各份申報的本期與比較欄，不依 `request.end` 決定。

### 錯位 member 的原文證據

下列數字均為百萬美元，按 Data Center／Client／Gaming／Embedded 順序列示，已核對同份原文 Net revenue 各列及其 XBRL fact：

| 10-Q accession | 原文表格 | 本期單季 | 本期累計 | 去年同季比較欄 | 去年累計比較欄 |
|---|---|---|---|---|---|
| `0000002488-24-000056` | t17 | 2,337／1,368／922／846 | 同單季 | 1,295／739／1,757／1,562 | 同單季 |
| `0000002488-24-000123` | t18 | 2,834／1,492／648／861 | 半年 5,171／2,860／1,570／1,707 | 1,321／998／1,581／1,459 | 半年 2,616／1,737／3,338／3,021 |
| `0000002488-24-000163` | t18 | 3,549／1,881／462／927 | 九個月 8,720／4,741／2,032／2,634 | 1,598／1,453／1,506／1,243 | 九個月 4,214／3,190／4,844／4,264 |

上述每一欄的 Data Center 列標成 `amd:ClientMember`，Client 列標成 `amd:GamingMember`，Gaming 列標成 `amd:DataCenterMember`，Embedded 列標成 `amd:EmbeddedMember`。加總仍等於總營收，不能只靠加總檢核判定映射正確。Parser 只取指定的 XBRL fact；原文文字只作分類名稱與映射的查證依據，不在執行時解析文字數字。

## 期別與推算

AMD 採 52／53 週財年，財年末為接近 12 月底的星期六；本範圍 FY2024 為 2023-12-31 至 2024-12-28，FY2025 為 2024-12-29 至 2025-12-27，均 364 天。已下載單季 91 天、半年 182 天、九個月 273 天，使用框架預設期間範圍與申報宣告財年，不需要 `DURATION_DAYS`、`FISCAL_YEAR` 或 `ATTACHMENTS`。

`categories` 涵蓋下限為 2023-12-30（第一個範圍內財年的上一財年期末），此前日期的分類不保證正確。2024-12-29 起為三分部：依據 [2025 Q1 10-Q `0000002488-25-000047`，期末 2025-03-29](https://www.sec.gov/Archives/edgar/data/2488/000000248825000047/amd-20250329.htm) 明示自 FY2025 起將 Client 與 Gaming 合併以配合管理方式，切換日取該季起日。FY2024 與 2024 各季仍保留四分部。

- Q1–Q3：各期最早原 10-Q 的單季 fact。
- FY：各期最早原 10-K 的年度 fact；10-K/A 不替代原申報。
- Q4：年度減同財年 Q3 原 10-Q 九個月累計。兩個財年內分類集合都一致，2024、2025 Q4 均為 `published`，沒有 `not_derived`。
- 2024 Q4 的 Client＝7,054−4,741＝2,313；Gaming＝2,595−2,032＝563。年度用年報映射、九個月用 Q3 錯位映射，保留所有運算元。
- 2025 Q4 的 Client and Gaming＝14,550−10,610＝3,940。總營收＝34,639−24,369＝10,270。運算元均來自年報或更早的 Q3，未使用之後申報。

第一個 Q4 口徑依據為 FY2023 10-K `0000002488-24-000012`（期末 2023-12-30）t21：Data Center／Embedded／Client／Gaming／總營收為 6,496／5,321／4,651／6,212／22,680。FY2024 10-K t22 的 FY2023 比較欄逐項同值；只作查證與口徑依據，不把較晚申報作早期期別的運算元。

FY2025 10-K t19 的 FY2024 比較欄 Data Center／Embedded／總營收為 12,579／3,557／25,785，與 FY2024 原申報 t22 相同。Client and Gaming 為 9,649＝7,054＋2,595，屬兩分部合併，非純改名，因此不宣告 `FORMER_NAMES`。框架只比較兩側共有名稱的分類，這個結構變動本身不阻擋 2025 Q4。

## 數字在原文的位置

表格位置與證據檔名依各期正式 `revenue.json` 的 `operands[*].evidence.table`。下表列出分類與總營收共同使用的分部表；證據目錄相對於 `data/revenue/A/AMD/`，每個檔名主體均有 `.html` 與 `.png`。

| 申報 accession | 期末日 | 表格 | 證據目錄與檔名主體 | 用途 |
|---|---|---|---|---|
| `0000002488-24-000056` | 2024-03-30 | t17 | `Q/2024-03-30/evidence/0000002488-24-000056-65d9b77bf4f4-t17` | 2024 Q1 |
| `0000002488-24-000123` | 2024-06-29 | t18 | `Q/2024-06-29/evidence/0000002488-24-000123-3065cd88df2c-t18` | 2024 Q2 |
| `0000002488-24-000163` | 2024-09-28 | t18 | `Q/2024-09-28/evidence/0000002488-24-000163-7f6bc28a53bc-t18` | 2024 Q3；2024 Q4 的九個月累計（同名證據另存 Q/2024-12-28/evidence/） |
| `0000002488-25-000012` | 2024-12-28 | t22 | `FY/2024-12-28/evidence/0000002488-25-000012-1f27cfc6bb6d-t22`、`Q/2024-12-28/evidence/0000002488-25-000012-1f27cfc6bb6d-t22` | FY2024 與 2024 Q4 年度 |
| `0000002488-25-000047` | 2025-03-29 | t19 | `Q/2025-03-29/evidence/0000002488-25-000047-69fdd6a48454-t19` | 2025 Q1 |
| `0000002488-25-000108` | 2025-06-28 | t19 | `Q/2025-06-28/evidence/0000002488-25-000108-78433b79df6c-t19` | 2025 Q2 |
| `0000002488-25-000166` | 2025-09-27 | t19 | `Q/2025-09-27/evidence/0000002488-25-000166-86c979204730-t19` | 2025 Q3；2025 Q4 的九個月累計（同名證據另存 Q/2025-12-27/evidence/） |
| `0000002488-26-000018` | 2025-12-27 | t19 | `FY/2025-12-27/evidence/0000002488-26-000018-7e2c0631386f-t19`、`Q/2025-12-27/evidence/0000002488-26-000018-7e2c0631386f-t19` | FY2025 與 2025 Q4 年度 |
| `0000002488-26-000076` | 2026-03-28 | t18 | `Q/2026-03-28/evidence/0000002488-26-000076-6b5bc8b47f56-t18` | 2026 Q1 |
| `0000002488-26-000123` | 2026-06-27 | t18 | `Q/2026-06-27/evidence/0000002488-26-000123-3ad706b74e71-t18` | 2026 Q2 |
| `0000002488-26-000191` | 2026-09-26 | t19 | `Q/2026-09-26/evidence/0000002488-26-000191-901cc2f329b0-t19` | 2026 Q3 |

FY2023 10-K `0000002488-24-000012` 的 t21 是第一個 Q4 的上一財年口徑依據，位於正式輸出範圍外，不列作正式 evidence。

全部來源是 SEC 主文件原始 HTML，下載包保留 `source_format="original_html"`、SEC URL 與 sha256。運算元保留來源文件 URL 與雜湊、完整 dimensions、期間、單位、scale、decimals 與原始字串。正式 evidence 的 HTML 是標示所選 fact 的表格證據，PNG 是該表格的截圖；兩者雜湊分別記於 `html_sha256` 與 `png_sha256`，不等同 SEC 原始 HTML bytes 的雜湊。

## 已知的重複 fact

總營收同值出現在損益表與分部表，年報另有地區表。框架在同精度時選包含最多其他運算元的表格，故本範圍都選分部表。其餘同值 fact 由框架保存為 `duplicates`。2025 起產品細項因維度不同，不是 Client and Gaming 小計的重複 fact，也不列為候選。

## 驗證

正式 [status.json](../../../../../data/revenue/A/AMD/status.json) 列出 13 期 `published`（11 Q、2 FY），沒有 `not_derived` 或 `failed`。以下數字取自各期正式 `revenue.json`，單位百萬美元；每期分類加總均等於總營收，結構檢核與證據完整檢核均通過。

| 期別 | 期末日 | Data Center | Embedded | Client | Gaming | Client and Gaming | 總營收 | 正式狀態 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2024 Q1 | 2024-03-30 | 2,337 | 846 | 1,368 | 922 | 不適用 | 5,473 | published |
| 2024 Q2 | 2024-06-29 | 2,834 | 861 | 1,492 | 648 | 不適用 | 5,835 | published |
| 2024 Q3 | 2024-09-28 | 3,549 | 927 | 1,881 | 462 | 不適用 | 6,819 | published |
| 2024 Q4 | 2024-12-28 | 3,859 | 923 | 2,313 | 563 | 不適用 | 7,658 | published |
| FY2024 | 2024-12-28 | 12,579 | 3,557 | 7,054 | 2,595 | 不適用 | 25,785 | published |
| 2025 Q1 | 2025-03-29 | 3,674 | 823 | 不適用 | 不適用 | 2,941 | 7,438 | published |
| 2025 Q2 | 2025-06-28 | 3,240 | 824 | 不適用 | 不適用 | 3,621 | 7,685 | published |
| 2025 Q3 | 2025-09-27 | 4,341 | 857 | 不適用 | 不適用 | 4,048 | 9,246 | published |
| 2025 Q4 | 2025-12-27 | 5,380 | 950 | 不適用 | 不適用 | 3,940 | 10,270 | published |
| FY2025 | 2025-12-27 | 16,635 | 3,454 | 不適用 | 不適用 | 14,550 | 34,639 | published |
| 2026 Q1 | 2026-03-28 | 5,775 | 873 | 不適用 | 不適用 | 3,605 | 10,253 | published |
| 2026 Q2 | 2026-06-27 | 6,718 | 977 | 不適用 | 不適用 | 3,841 | 11,536 | published |
| 2026 Q3 | 2026-09-26 | 8,546 | 1,109 | 不適用 | 不適用 | 3,722 | 13,377 | published |

### 採用來源 TradingView

對照檔：[reference.json](../../../../../data/universe/references/A/AMD/reference.json)、[TradingView 表格快照](../../../../../data/universe/references/A/AMD/captures/tradingview/20261108T070546Z/table.txt)。年度按財年對齊，差額定義為 SEC−來源，單位百萬美元。

| 年度 | 分類 | SEC | TradingView | 差額 | 結論 |
|---|---|---:|---:|---:|---|
| FY2024 | Data Center | 12,579 | 12,580 | −1 | 0.01B 顯示精度內 |
| FY2024 | Embedded | 3,557 | 3,560 | −3 | 同上 |
| FY2024 | Client | 7,054 | 7,050 | ＋4 | 同上 |
| FY2024 | Gaming | 2,595 | 2,600 | −5 | 同上 |
| FY2025 | Data Center | 16,635 | 16,640 | −5 | 同上 |
| FY2025 | Client and Gaming | 14,550 | 14,550 | 0 | 精確相同 |
| FY2025 | Embedded | 3,454 | 3,450 | ＋4 | 0.01B 顯示精度內 |

7 值均在顯示單位的一半（5 百萬美元）內，加計 SEC fact 的精度誤差仍成立，無原因未確認的超差。FY2024、FY2025 各自四季逐分類加總等於年度值，因此四季加總對 TradingView 的差額也與上表相同。TradingView 沒有任何季度值，2024 Q1–2026 Q3 的 11 季不能宣稱已與採用來源直接比對；2026 FY 尚無範圍內 SEC 年報或對照值。FY2023 與更早的參考年度在本輪範圍外，不列為通過。

### 季度輔助 Stock Analysis

對照 [Stock Analysis 表格快照](../../../../../data/universe/references/A/AMD/captures/stockanalysis/20261108T070347Z/table.txt)，按 AMD 財年季次對齊曆季末日期。2024 年只為對照而計算 Client＋Gaming，正式輸出仍保留四類。以下順序均為 Data Center／Client and Gaming／Embedded，單位百萬美元；差額為 SEC−來源。

| 季度 | SEC 三類對照值 | Stock Analysis | 差額 |
|---|---|---|---|
| 2024 Q1 | 2,337／2,290／846 | 2,340／2,290／846 | −3／0／0 |
| 2024 Q2 | 2,834／2,140／861 | 2,830／2,140／861 | ＋4／0／0 |
| 2024 Q3 | 3,549／2,343／927 | 3,550／2,340／927 | −1／＋3／0 |
| 2024 Q4 | 3,859／2,876／923 | 3,860／2,880／923 | −1／−4／0 |
| 2025 Q1 | 3,674／2,941／823 | 3,670／2,940／823 | ＋4／＋1／0 |
| 2025 Q2 | 3,240／3,621／824 | 3,240／3,620／824 | 0／＋1／0 |
| 2025 Q3 | 4,341／4,048／857 | 4,340／4,050／857 | ＋1／−2／0 |
| 2025 Q4 | 5,380／3,940／950 | 5,380／3,940／950 | 0／0／0 |
| 2026 Q1 | 5,775／3,605／873 | 5,780／3,610／873 | −5／−5／0 |
| 2026 Q2 | 6,718／3,841／977 | 6,720／3,840／977 | −2／＋1／0 |
| 2026 Q3 | 8,546／3,722／1,109 | 8,550／3,720／1,110 | −4／＋2／−1 |

33 值均在來源顯示精度內：B 值到 0.01B、M 值到 0.01M；差額可由捨入解釋。這個合併對照不能單獨驗證 2024 年 Client 與 Gaming 的分配，各分類映射另依前述同份 SEC 原文逐列核對。

## 比較欄

正式 `status.json` 各期均無 `differences` 或 `comparison_errors` 紀錄。這不代表所有歷史分類均能逐一比較：2025 年起的比較欄使用三分部，沒有與舊四分部同 scope 的獨立 Client、Gaming 分類，不能把合併後小計分別與兩個舊分類比較。

| 比較申報 | 舊期別／角色 | 缺少同 scope 獨立分類 |
|---|---|---|
| 2025 Q1 `0000002488-25-000047` | 2024 Q1／quarter | Client、Gaming |
| 2025 Q2 `0000002488-25-000108` | 2024 Q2／quarter | Client、Gaming |
| 2025 Q3 `0000002488-25-000166` | 2024 Q3／quarter；2024 Q4／nine_months | Client、Gaming |
| FY2025 `0000002488-26-000018` | FY2024／annual；2024 Q4／annual | Client、Gaming |

這些申報的營收比較欄已是三分部，parser 不把新結構拆回兩個舊分類，也不把合併當作純改名；其產品細項不屬採用觀點。Data Center、Embedded、總營收及 2025 年同名分部的可比值均一致。FY2025 修正申報 `0000002488-26-000021` 沒有可用營收比較期間，不替代原年報，也不製造差異標記。
