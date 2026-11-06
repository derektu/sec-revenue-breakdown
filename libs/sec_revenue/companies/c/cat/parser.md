# CAT parser

## 觀點

營運分部（`view="business_segment"`），每期 6 類：Construction Industries、Resource Industries、Energy & Transportation（2025 年 Q3 以前）或 Power & Energy（FY2025 10-K 起）、Financial Products、All Other、Corporate Items and Eliminations。

| 對照來源 | 列出的分類 | 口徑 |
|---|---|---|
| Stock Analysis | 四個分部、Other、Eliminations | 分部總營收（含分部間營收） |
| 富途 | 四個分部、所有其他分部、公司項目和抵銷 | 分部總營收 |
| TradingView | 四個分部、All Other | 對外營收（不含分部間營收），沒有抵銷項 |

兩個來源用分部總營收，所以採用這個口徑：
- Energy & Transportation／Power & Energy 有大量分部間營收（FY2025 為 50.58 億美元），所以抵銷項很大。
- All Other 三個來源都列出，列成分類。
- Corporate Items and Eliminations 有兩個來源列出，也列成分類。

分部取自 `us-gaap:StatementBusinessSegmentsAxis`。CAT 這個軸的成員是業務別：營建機械、礦業機械、動力與能源、融資服務。它們不是地區，所以採用。

## 分類與 tag

concept 是 `us-gaap:Revenues`。

| 分類 | 維度 |
|---|---|
| Construction Industries | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`＋分部 `cat:ConstructionIndustriesMember` |
| Resource Industries | 同上，分部 `cat:ResourceIndustriesMember` |
| Energy & Transportation | 同上，分部 `cat:EnergyandTransportationMember`（申報期末日 2025-09-30 以前） |
| Power & Energy | 同上，分部 `cat:PowerEnergyMember`（申報期末日 2025-10-01 起） |
| Financial Products | 同上，分部 `cat:FinancialProductsSegmentMember` |
| All Other | 同上，分部 `us-gaap:AllOtherSegmentsMember` |
| Corporate Items and Eliminations | `srt:ConsolidationItemsAxis=cat:EliminationsAndReconcilingItemsMember` 或 `cat:CorporateReconcilingItemsAndEliminationsMember`（2024 年 Q3 10-Q 以前），兩種寫法都找 |
| 總營收（Total sales and revenues） | 不帶維度 |

- 分類名稱照各期申報的列名，parser 依申報期末日（`filing.report_date`）切換：2025 年 Q3 10-Q（0000018230-25-000048，期末 2025-09-30）以前的申報只有 `cat:EnergyandTransportationMember`、列名 Energy & Transportation；FY2025 10-K（0000018230-26-000008，期末 2025-12-31）起是 `cat:PowerEnergyMember`、列名 Power & Energy。`categories` 在 2025-09-30 以前列 Energy & Transportation，2025-10-01 起列 Power & Energy，兩段首尾相接。
- Corporate Items and Eliminations 的兩個成員是分部表的同一列：2024 年 Q3 10-Q（0000018230-24-000053）以前的申報用 `cat:CorporateReconcilingItemsAndEliminationsMember`，FY2024 10-K（0000018230-25-000008，期末 2024-12-31）起用 `cat:EliminationsAndReconcilingItemsMember`。2024 年 Q4 的年度與九個月累計分別在兩種寫法的申報中，所以 parser 在每份申報都找這兩種寫法。
- 分部 fact 另有 `us-gaap:OperatingSegmentsExcludingIntersegmentEliminationMember`（對外營收）與 `us-gaap:IntersegmentEliminationMember`（分部間營收）的拆分，parser 用 `OperatingSegmentsMember` 的合計。
- 六類加總等於總營收，沒有調節項。
- 分類名稱取自分部營收表的列標籤（去掉 Segment 字樣）；總營收取自同表的 `Total Sales and Revenues`。

## 期別與推算

- 財年即曆年，季末日是 3、6、9、12 月的最後一天。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同年 Q3 10-Q 的九個月累計，前提是年度與 Q1–Q3 的分類相同，且口徑沒有改變。
- FY：10-K 的年度 fact。

## 數字在原文的位置

附註的分部營收表（Sales and Revenues by Geographic Region），各分部一列，數字在 `Total Sales and Revenues` 欄。Q1–Q3 與 FY 每期一張表；Q4 為 10-K 與 Q3 10-Q 各一張。

## 分部間的重分類

CAT 的申報多次在分部之間重分類，並重列比較數字（單位百萬美元）：

| 來源申報 | 重列的期別 | 主要變動 |
|---|---|---|
| 2025 年 Q3 10-Q | 2024 年 Q3、2024 年九個月 | Resource Industries 增加 20（單季）與 64（九個月），All Other 減少約相同金額 |
| FY2025 10-K | FY2024 | Resource Industries 12,389 → 12,471、All Other 425 → 344 |
| 2026 年 Q1–Q3 10-Q | 2025 年各季與九個月 | 每季約 800 由 Energy & Transportation（重列時稱 Power & Energy）移到 Resource Industries，例如 2025 年 Q1 6,568 → 5,783、Resource Industries 2,884 → 3,661 |

- 已上線的各期保留申報當時的數字，重列寫成差異標記。2025 年各季 Energy & Transportation 的重列不寫標記：parser 對 2026 年的申報不列這個分類（比對結果是 `not_found`），只有 Resource Industries 等分類的變動寫成標記。
- 2025 年 Q4 不推算：FY2025 的分類是 Power & Energy，2025 年 Q1–Q3 是 Energy & Transportation，分類不同。FY2025 10-K 也重列了 FY2024，口徑一致的條件同樣不成立。

## 驗證

11 季（2024-03-31 至 2026-09-30，2025 年 Q4 不推算）與 2 個年度，與對照資料逐期比對：

| 來源 | 結果 |
|---|---|
| Stock Analysis | 各季在顯示精度內 |
| 富途 | 2024 年 Q1、Q2 與 2025 年 Q3 起相同。2024 年 Q3 與 2025 年 Q1、Q2 是事後重列的數字（與差異標記的申報列示值相同）；2024 年 Q4 的 Resource Industries 與 All Other 也不同（富途 2,898／179，我們 2,962／116），變動方向與重列相反，原因未確認 |
| TradingView（只有年度） | 對外營收，口徑不同，不比對；Financial Products 沒有分部間營收，數字相同 |

- FY 序列：FY2024 等於同財年四季加總。FY2025 的 Q4 不推算，不比對。
