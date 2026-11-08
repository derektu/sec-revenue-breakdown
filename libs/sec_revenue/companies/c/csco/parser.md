# CSCO parser

## 觀點

產品與服務別，`view="product"`。採用富途 `futu`，依其順序輸出 Networking、Services、Security、Collaboration、Observability，沒有調節項。總營收稱為 Total revenue，取無維度合併營收。分類名稱取自 SEC 產品營收表，年度全大寫的名稱採 10-Q 的寫法。

對照資料位於 `data/universe/references/C/CSCO/reference.json`。富途的聯網、服務、安全、協作分別對應 Networking、Services、Security、Collaboration，Observability 同名。Stock Analysis 同樣列五類，但 FY2024 Q2–Q4 的 Security 是對照來源錯誤。TradingView 的 FY2024–FY2026 五類作年度輔助。

SEC 另有 Americas、EMEA、APJC 地區營運分部，不採用。其 fact 同時帶 `us-gaap:StatementBusinessSegmentsAxis` 與 `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`，不是本 parser 的產品觀點。訂閱營收則與產品、服務分類重疊，不另列分類。

## 分類與 tag

所有分類、舊結構調節項與總營收均使用 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`。下表成員的完整 dimensions 只有 `srt:ProductOrServiceAxis=成員`，沒有其他軸；總營收 dimensions 為 `{}`。單位 USD，原文以百萬美元顯示，`scale=6`、`decimals=-6`。

| 分類 | 成員 |
|---|---|
| Networking | `csco:NetworkingMember` 或 `csco:NetworkingRevenueMember` |
| Services | `us-gaap:ServiceMember` |
| Security | `csco:SecurityMember` 或 `csco:SecurityRevenueMember` |
| Collaboration | `csco:CollaborationMember` |
| Observability | `csco:ObservabilityMember` 或 `csco:ObservabilityRevenueMember` |
| Total revenue | 無維度 |

FY2024 Q1 10-Q（0000858877-23-000031，期末 2023-10-28）開始採五類，適用起日為 2023-07-30。`categories` 在該日起回答五類。`compose` 依所要求期間有沒有 Networking fact 選擇結構，不用後來申報回套舊期。

FY2024 10-K（0000858877-24-000017，期末 2024-07-27）的 Networking、Security、Observability 使用含 `Revenue` 的成員。FY2025 Q1 10-Q（0000858877-24-000030，期末 2024-10-26）起恢復另一變體。三組成員均以 `one_of` 查詢，每份申報有多種寫法時仍須通過框架同值檢核。

兩種 tag 的重疊證據如下，單位百萬美元。FY2024 10-K t60 本期欄使用 `*RevenueMember`；FY2025 10-K（0000858877-25-000111）t60 的 FY2024 比較欄使用不含 `Revenue` 的成員。其他兩類及總營收一併核對，均相同。後者只作查證，不作 FY2024 運算元。

| FY2024 分類 | FY2024 原年報 | FY2025 年報比較欄 |
|---|---:|---:|
| Networking | 29,229 | 29,229 |
| Services | 14,550 | 14,550 |
| Security | 5,075 | 5,075 |
| Collaboration | 4,113 | 4,113 |
| Observability | 837 | 837 |
| Total revenue | 53,803 | 53,803 |

FY2023 10-K（0000858877-23-000023，期末 2023-07-29）仍照原文舊結構，作第一個 Q4 的前年度口徑依據。成員完整 dimensions 同樣只有產品軸：

| 項目 | 類型 | 成員 | FY2023 百萬美元 |
|---|---|---|---:|
| Secure, Agile Networks | 分類 | `csco:SecureAgileNetworksMember` | 29,105 |
| Internet for the Future | 分類 | `csco:InternetForTheFutureMember` | 5,306 |
| Collaboration | 分類 | `csco:CollaborationMember` | 4,052 |
| End-to-End Security | 分類 | `csco:EndToEndSecurityMember` | 3,859 |
| Optimized Application Experiences | 分類 | `csco:OptimizedApplicationExperiencesMember` | 811 |
| Services | 分類 | `us-gaap:ServiceMember` | 13,856 |
| Other Products | 調節項 | `csco:OtherProductsMember` | 9 |
| Total revenue | 總營收 | 無維度 | 56,998 |

Other Products 只在舊結構列為調節項。現行五類已涵蓋合併營收。`categories` 支援下限為 2023-07-29，包含第一個處理財年的前年度期末及 FY2024 全部日期；更早日期不保證，若以 `--start` 擴大範圍需先補查。

## 期別與推算

財年在 7 月最後一個星期六結束，採 52／53 週制。範圍內單季 91 天、半年 182 天、九個月 273 天、年度 364 天；FY2022 比較年度為 371 天。均使用框架預設期間範圍，不宣告 `DURATION_DAYS`。財年與季別取申報宣告，不宣告 `FISCAL_YEAR`；所需 fact 全在主文件，不宣告 `ATTACHMENTS`。

Q1–Q3 取當期 10-Q 的單季 fact，FY 取當期 10-K 的年度 fact，Q4 由同財年年度減 Q3 10-Q 的九個月累計。所有運算元均來自當期申報日以前已公開的申報，數字不從 HTML 文字取得。

FY2024、FY2025、FY2026 的 Q4 正式輸出均為年度減九個月累計的推算值，`status.json` 均為 `published`，沒有 `not_derived`，也沒有口徑無法判斷的註記。FY2024 Q4 的前年度依據是 FY2023 原年報舊結構。框架只比兩側都有的 Collaboration、Services、Total revenue，以及經 `FORMER_NAMES` 對應的 End-to-End Security／Security，數值均相同；消失的舊分類不硬接到 Networking 或 Observability。FY2024 財年起日已是五類，因此沒有財年內分類集合改變。

## 數字在原文的位置

10-Q 與 10-K 的產品營收表同時列產品細項、Services 與合併營收。下表檔名取自正式 `revenue.json` 的 `operands[*].evidence.table`；每個檔名主體均有 `.html` 表格與 `.png` 截圖，位於 `data/revenue/C/CSCO/<序列>/<期末>/evidence/`。同一期所有分類與總營收使用同一張表，Q4 則使用年度與九個月累計各一張表。

| 期別 | accession | 證據檔名主體 |
|---|---|---|
| FY2024 Q2 | 0000858877-24-000003 | `0000858877-24-000003-599378dc2755-t16` |
| FY2024 Q3 | 0000858877-24-000007 | `0000858877-24-000007-a15f10823db1-t16` |
| FY2024 FY | 0000858877-24-000017 | `0000858877-24-000017-2898e349cfe3-t60` |
| FY2025 Q1 | 0000858877-24-000030 | `0000858877-24-000030-ce940acaa3c6-t14` |
| FY2025 Q2 | 0000858877-25-000007 | `0000858877-25-000007-73cc2bbc3671-t16` |
| FY2025 Q3 | 0000858877-25-000033 | `0000858877-25-000033-6c0ddf76bc90-t16` |
| FY2025 FY | 0000858877-25-000111 | `0000858877-25-000111-0012b3c6a9a8-t60` |
| FY2026 Q1 | 0000858877-25-000171 | `0000858877-25-000171-95dd912732c5-t14` |
| FY2026 Q2 | 0000858877-26-000021 | `0000858877-26-000021-2ddf11a22224-t16` |
| FY2026 Q3 | 0000858877-26-000078 | `0000858877-26-000078-4a86330d0e90-t16` |
| FY2026 FY | 0000858877-26-000132 | `0000858877-26-000132-2fc6235c6bda-t60` |

每個 Q4 的年度部分取同財年 t60，九個月部分取同財年 Q3 的 t16；兩組證據均保存在該 Q4 期末目錄。FY2023 原年報（0000858877-23-000023）t60 僅作前年度口徑依據，FY2024 Q1（0000858877-23-000031）t14 為範圍前依賴，兩期不在正式營收輸出範圍。

## 已知的重複 fact

總營收及 Services 在損益表與產品表重複，產品細項也在附註與 MD&A 的產品營收表重複。框架核對重複值後，選擇同表包含最多其他運算元的 fact，再依原文順序選第一筆，因此上述結果集中在較早出現的產品表。沒有以多張表的同值 fact 重複相加。

## 分類重組與改名

FY2024 Q1 起的重組沒有回寫 FY2023 原分類。`FORMER_NAMES = {"Security": ("End-to-End Security",)}` 只宣告同範圍改名。兩個重疊年度的新舊名稱同值證據如下，concept 與完整 dimensions 見前表，數字單位百萬美元：

| 年度 | FY2023 10-K t60 舊名稱 | FY2024 10-K t60 新名稱 |
|---|---|---|
| FY2023，2022-07-31～2023-07-29 | f-518，3,859 | f-511，3,859 |
| FY2022，2021-08-01～2022-07-30 | f-519，3,699 | f-512，3,699 |

FY2023 的 Optimized Application Experiences 在原年報 t60 f-521 為 811；FY2024 年報 t60 f-517 重編為 Observability 661。FY2022 也由 729 變為 581，因此不宣告純改名。Networking 是重組後類別，也不宣告與任一舊分類的一對一改名。

## 驗證

正式輸出位於 `data/revenue/C/CSCO/`。`status.json` 涵蓋 FY2024 Q2 至 FY2026 Q4 共 11 季，以及 FY2024–FY2026 共 3 年度，均為 `published`。各期 `revenue.json` 保留分類、總營收、全部運算元與證據，結構、單位精度、加總及證據完整性檢核均符合要求。

與富途按財年及季別逐期對齊的結果如下，單位百萬美元。五類次序與輸出一致；「來源減 parser」列的 0 表示該期全部五類完全相同。數值取自正式 `revenue.json`，對照 `reference.json`；參考來源不提供運算元。

| 財年季別 | SEC 期末 | Networking | Services | Security | Collaboration | Observability | Total revenue | 來源減 parser |
|---|---|---:|---:|---:|---:|---:|---:|---|
| FY2024 Q2 | 2024-01-27 | 7,081 | 3,559 | 973 | 989 | 188 | 12,791 | 五類均 0 |
| FY2024 Q3 | 2024-04-27 | 6,522 | 3,678 | 1,304 | 987 | 211 | 12,702 | 五類均 0 |
| FY2024 Q4 | 2024-07-27 | 6,804 | 3,784 | 1,787 | 1,020 | 248 | 13,642 | 五類均 0 |
| FY2025 Q1 | 2024-10-26 | 6,753 | 3,727 | 2,017 | 1,085 | 258 | 13,841 | 五類均 0 |
| FY2025 Q2 | 2025-01-25 | 6,850 | 3,757 | 2,111 | 996 | 277 | 13,991 | 五類均 0 |
| FY2025 Q3 | 2025-04-26 | 7,068 | 3,775 | 2,013 | 1,031 | 261 | 14,149 | 五類均 0 |
| FY2025 Q4 | 2025-07-26 | 7,633 | 3,787 | 1,952 | 1,042 | 259 | 14,673 | 五類均 0 |
| FY2026 Q1 | 2025-10-25 | 7,768 | 3,806 | 1,980 | 1,055 | 274 | 14,883 | 五類均 0 |
| FY2026 Q2 | 2026-01-24 | 8,294 | 3,707 | 2,018 | 1,054 | 277 | 15,349 | 五類均 0 |
| FY2026 Q3 | 2026-04-25 | 8,815 | 3,724 | 2,008 | 1,024 | 269 | 15,841 | 五類均 0 |
| FY2026 Q4 | 2026-07-25 | 9,791 | 3,793 | 2,226 | 1,167 | 275 | 17,252 | 五類均 0 |

範圍前依賴 FY2024 Q1（2023-10-28）的五類分別為 8,822、3,529、1,010、1,117、190，亦與富途五類完全相同。範圍內共 55 筆一致，加上此季為 60 筆。富途沒有 FY 資料，三個 FY 不與富途比對；FY2023 原結構只查核 SEC 口徑依據，不作採用來源的歷史驗證。更早對照資料未確認。

TradingView 年度輔助對照如下，五類皆在其顯示精度及 SEC 運算元精度內一致，合計 15 筆。來源減 parser 的向量依 Networking、Services、Security、Collaboration、Observability 排列，單位百萬美元。

| 年度／SEC 期末 | parser 五類 | TradingView 五類 | 來源減 parser |
|---|---|---|---|
| FY2024／2024-07-27 | 29,229；14,550；5,075；4,113；837 | 29,230；14,550；5,080；4,110；837 | +1；0；+5；−3；0 |
| FY2025／2025-07-26 | 28,304；15,046；8,094；4,154；1,055 | 28,300；15,050；8,090；4,150；1,050 | −4；+4；−4；−4；−5 |
| FY2026／2026-07-25 | 34,668；15,030；8,232；4,300；1,095 | 34,670；15,030；8,230；4,300；1,090 | +2；0；−2；0；−5 |

分類加總偶與總營收相差 1 百萬美元，落在單季或年度 3 百萬美元、Q4 6 百萬美元的運算元精度容許內，不倒算、不新增調節項。

Stock Analysis 的來源錯誤另列如下。來源日期 2024-01-31、04-30、07-31 分別對齊 SEC 01-27、04-27、07-27。

| FY2024 季別 | Security parser | Security 來源 | 來源減 parser | SEC 證據 |
|---|---:|---:|---:|---|
| Q2 | 973 | 989 | +16 | 0000858877-24-000003，t16，f-498 |
| Q3 | 1,304 | 987 | −317 | 0000858877-24-000007，t16，f-500 |
| Q4 | 1,787 | 1,020 | −767 | FY2024 10-K t60 f-510 的 5,075，減 Q3 t16 f-502 的 3,288 |

三筆均符合指南的來源錯誤條件。當期表格的 Security 列、concept 與單一產品軸完整對應，分類加總通過，較晚已下載申報的比較欄沒有重列這些值，富途三筆均與 SEC 相同。Stock Analysis 快照中三筆 Security 恰與同季 Collaboration 相同。這是錯值的觀察證據，不推定網站內部錯誤機制。

## 比較欄

正式 `status.json` 的 11 季、3 年度均無 `differences` 標記或 `comparison_errors`。比較範圍包含單季、Q4 的年度與九個月累計，以及 FY 年度運算元；較晚申報所列相同期間沒有超過精度的數值差異或無法解析項目。較晚申報僅供比較，不作原期運算元。FY2023 舊結構與 FY2024 新結構的變動見「分類重組與改名」，不屬於範圍內輸出重列。
