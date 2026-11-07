# CVX parser

## 觀點

採用 TradingView 的業務分部觀點（`view="business_segment"`），取部門間交易抵銷後的銷售營收。分類名稱照 SEC，順序照 TradingView：Downstream、Upstream、All Other。

| 對照來源 | 分類與口徑 | 對應方式 |
|---|---|---|
| TradingView | Downstream、Upstream、All Other；抵銷後，只有年度資料 | 三類直接對應同名 SEC 分部 |
| 富途 | 下游、上游、所有其他、部門間收入抵銷；範圍內列抵銷前營收及抵銷額 | 上下游與其他業務的面向相同，數值口徑不同，不作採用來源 |
| Stock Analysis | 沒有 CVX 對照資料 | 不納入來源計票與比對 |

All Other 在兩個現有來源都有實際值，因此列成分類。抵銷後的分類已包含部門間抵銷，沒有獨立的 Eliminations 分類或調節項；三類加總等於合併的 Sales and Other Operating Revenues。

`us-gaap:StatementBusinessSegmentsAxis` 的 Upstream、Downstream 與 All Other 成員是業務別，不是地區。FY2024 10-K 以前的分部表只在抵銷前與抵銷列按 United States、International 拆分，抵銷後合計不分地區；FY2024 10-K 起的分部表把抵銷後的上下游營收以 U.S.、Int'l. 兩欄列示。地區只作全球業務分部的加總運算元，不輸出成分類。申報另列的抵銷前分部營收、地區拆分、Other income (loss) 與 Total Revenues and Other Income 均不採用。

## 分類與 tag

所有分類與總營收的 concept 都是 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`。所選 fact 只帶下表所列的維度；同表另有帶 `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember` 或 `IntersegmentEliminationMember` 的抵銷前與抵銷 fact，不採用。

### 帶產品軸的抵銷後合計

| 分類 | 完整 dimensions |
|---|---|
| Downstream | `srt:ProductOrServiceAxis=us-gaap:OilAndGasMember`；`us-gaap:StatementBusinessSegmentsAxis=cvx:DownstreamMember` 或 `cvx:DownstreamSegmentMember` |
| Upstream | `srt:ProductOrServiceAxis=us-gaap:OilAndGasMember`；`us-gaap:StatementBusinessSegmentsAxis=cvx:UpstreamMember` 或 `cvx:UpstreamSegmentMember` |
| All Other | `srt:ProductOrServiceAxis=us-gaap:OilAndGasMember`；`srt:ConsolidationItemsAxis=cvx:CorporateAndEliminationsMember` |

2024 年 Q1–Q3 的 10-Q 分別為 `0000093410-24-000021`（期末 2024-03-31）、`0000093410-24-000040`（2024-06-30）、`0000093410-24-000059`（2024-09-30），上下游合計用 `cvx:DownstreamMember` 與 `cvx:UpstreamMember`。

FY2023 10-K `0000093410-24-000013`（期末 2023-12-31）也有帶產品軸的抵銷後合計，但成員是 `cvx:DownstreamSegmentMember` 與 `cvx:UpstreamSegmentMember`。All Other 同樣取抵銷後的 `cvx:CorporateAndEliminationsMember`，不是抵銷前的 `us-gaap:CorporateNonSegmentMember`。

### 地區 fact 相加的抵銷後分部

| 分類或加數 | 完整 dimensions |
|---|---|
| Downstream，美國 | `us-gaap:StatementBusinessSegmentsAxis=cvx:DownstreamSegmentMember`；`srt:StatementGeographicalAxis=country:US` |
| Downstream，非美國 | `us-gaap:StatementBusinessSegmentsAxis=cvx:DownstreamSegmentMember`；`srt:StatementGeographicalAxis=us-gaap:NonUsMember` |
| Upstream，美國 | `us-gaap:StatementBusinessSegmentsAxis=cvx:UpstreamSegmentMember`；`srt:StatementGeographicalAxis=country:US` |
| Upstream，非美國 | `us-gaap:StatementBusinessSegmentsAxis=cvx:UpstreamSegmentMember`；`srt:StatementGeographicalAxis=us-gaap:NonUsMember` |
| All Other | `us-gaap:StatementBusinessSegmentsAxis=us-gaap:AllOtherSegmentsMember` |

上下游各自把同一分部的美國與非美國兩個 fact 相加，權重均為 1，包含該 concept、其他 dimensions 與期間下的全部地區成員。All Other 是獨立的抵銷後 fact，不從總營收倒算。

這種寫法自 FY2024 10-K `0000093410-25-000009`（期末 2024-12-31）起出現，該申報的年度比較欄也採此寫法。2025 年 Q1–Q3（`0000093410-25-000019`、`0000093410-25-000062`、`0000093410-25-000108`）、FY2025 10-K（`0000093410-26-000078`）及 2026 年 Q1–Q2（`0000093410-26-000113`、`0000093410-26-000167`）同樣如此。

### 選擇寫法與總營收

每次組合只看這份申報、這段期間的 fact。上下游先以 `one_of` 找帶產品軸的兩種合計成員；找不到才取不帶產品軸的美國與非美國兩個 fact 相加。All Other 以 `one_of` 找上述兩種獨立 fact。沒有依日期、accession 或 fact id 切換；找不到的項目交由 `put` 記錄為缺漏。

總營收名稱為 Sales and Other Operating Revenues，取同 concept、不帶任何維度的合併 fact。`us-gaap:Revenues` 對應另含其他收益的 Total Revenues and Other Income，不是此觀點的總營收。

舊表分類名稱來自 `Total Downstream`、`Total Upstream`、`Total All Other` 列，去掉 `Total`；新表名稱來自 Downstream、Upstream、All Other 欄。總營收名稱取自 Sales and Other Operating Revenues 列。

## 期別與推算

財年即曆年，季末日為 3 月 31 日、6 月 30 日、9 月 30 日及 12 月 31 日。`categories` 在涵蓋範圍內固定為 Downstream、Upstream、All Other，沒有調節項。分類定義涵蓋下限為 2023-12-31，包含預設起始日 2024-01-01 所需的上一財年期末；更早期別不在本 parser 的保證範圍。

- Q1–Q3 取該期原始 10-Q 的單季 fact。
- FY 取該財年原始 10-K 的年度 fact。
- Q4 由框架以年度減同財年 Q3 原始 10-Q 的九個月累計推算。年度與九個月運算式各按承載申報內實際存在的寫法組成，不要求兩邊的加數個數相同。
- 第一個 Q4 的上一年度口徑依據為 FY2023 10-K；該年度不在預設輸出範圍，不另發布 FY2023。
- Q4 只在框架的分類集合、前期口徑及其他檢核成立時推算；範圍內 FY2024、FY2025 的 Q4 均推算，沒有不推算的期別。

FY2024 10-K 起上下游以地區欄呈現，分類仍是同一組業務。比較期間也按承載該比較欄的申報內實際 fact 組成；不以後來申報的地區欄改組早期主申報。

2024 Q4 由 FY2024 10-K 的地區相加與 `AllOtherSegmentsMember`，減 2024 Q3 10-Q 的產品軸合計與 `CorporateAndEliminationsMember`；第一個 Q4 的口徑依據則比較 FY2023 10-K 的舊寫法與 FY2024 10-K 比較欄的新寫法。兩種寫法在重疊期別逐一相等（百萬美元，Downstream／Upstream／All Other）：

| 期間 | 舊寫法（原申報） | 新寫法（較晚申報的比較欄） |
|---|---|---|
| FY2023 | `0000093410-24-000013`：151,038／45,742／133 | `0000093410-25-000009` t190：74,774＋76,264／13,808＋31,934／133；`0000093410-26-000078` t196 同值 |
| FY2022 All Other | `0000093410-24-000013`：116 | `0000093410-25-000009` t191：116 |
| 2024 Q1 | `0000093410-24-000021`：35,117／11,436／27 | `0000093410-25-000019` t20：同值 |
| 2024 Q2 | `0000093410-24-000040`：38,995／10,546／33 | `0000093410-25-000062` t20：同值 |
| 2024 Q3 | `0000093410-24-000059`：37,016／11,883／27 | `0000093410-25-000108` t20：同值 |
| 2024 九個月 | `0000093410-24-000059`：111,128／33,865／87 | `0000093410-25-000108` t22：54,164＋56,964／10,273＋23,592／87 |

兩種 All Other 都是抵銷後的值：舊的 `CorporateAndEliminationsMember` 等於 `CorporateNonSegmentMember` 加 `IntersegmentEliminationMember`（FY2023 為 597 − 464 = 133）；新的 `AllOtherSegmentsMember` 等於抵銷前減抵銷（FY2024 為 617 − 485 = 132）。

## 數字在原文的位置

原文分部表的抵銷後合計列或 Sales and Other Operating Revenues 列提供分類數字。各期正式證據取自下表每列的本期表格（evidence 檔名的 `-t<編號>`），2025 Q4 的九個月累計取 2025 Q3 10-Q 的 t21；比較期間的表格供查核，不是發布期別的證據。總營收有重複標記時，框架依重複 fact 規則選用與其他運算元同表者。

| 申報 | 分類 fact | 同 scope 總營收 fact |
|---|---|---|
| FY2023 10-K `0000093410-24-000013` | 分部銷售表 t160 的 Total Downstream、Total Upstream、Total All Other | 合併損益表 t115；僅作第一個 Q4 的上一年度口徑依據，沒有正式證據檔 |
| 2024 Q1–Q3 10-Q | 分部銷售表 t21 的三個抵銷後合計列；Q3 同表含單季與九個月累計 | 合併損益表 t7 |
| FY2024 10-K `0000093410-25-000009` | t188 的本年分部表；前兩年度比較欄分別在 t190、t191 | t188、t190、t191 的 Total 欄；同值亦標在合併損益表 t147 |
| 2025 Q1、2026 Q1 10-Q | t19 本季、t20 去年同季 | 同一分部表的 Total 欄；同值亦標在合併損益表 t7 |
| 2025 Q2、2026 Q2 10-Q | t19 本季、t20 去年同季；六個月累計在 t21、t22 | 各分部表的 Total 欄；同值亦標在合併損益表 t7 |
| 2025 Q3 10-Q | t19 本季、t20 去年同季；t21 本年九個月累計、t22 去年九個月累計 | 各分部表的 Total 欄；同值亦標在合併損益表 t7 |
| FY2025 10-K `0000093410-26-000078` | t193 本年分部表；前兩年度比較欄分別在 t195、t196 | t193、t195、t196 的 Total 欄；同值亦標在合併損益表 t152 |

新分部表的數字取 Sales and Other Operating Revenues 列，不取上方 Sales and other operating revenues before elimination 列，也不取下方 Total Revenues and Other Income 列。Q4 的證據分別對應年度與九個月累計的兩份申報。

## 已知的重複 fact

FY2024 10-K 起，不帶維度的總營收同時標在合併損益表與各期間的分部表，同 concept、完整 dimensions、期間的數值與精度一致。框架選擇與分類 fact 同表的版本，其餘 fact 記入 `duplicates`。2024 年各 10-Q 與 FY2023 10-K 的分部表總營收另帶產品軸，不是 parser 採用的無維度總營收；兩者不當作相同 dimensions 的重複 fact。

## 驗證

正式輸出位於 `data/revenue/C/CVX/`，涵蓋 10 季（2024-03-31 至 2026-06-30）及 2 個年度（FY2024、FY2025）。`status.json` 的 12 期皆為 `published`，沒有 `failed` 或 `not_derived`。兩個 Q4 均由年度減同財年九個月累計推算；各期 `revenue.json` 的三類加總均等於 Sales and Other Operating Revenues，沒有調節項。

採用來源為 `data/universe/references/C/CVX/reference.json` 的 TradingView，只提供年度資料。以下逐筆比對 FY2024、FY2025 正式 `revenue.json` 的三個分類，SEC 值與差額單位為百萬美元；差額為 SEC 值減對照值。

| 年度 | 分類 | SEC 值 | TradingView 顯示值 | 差額 |
|---|---|---:|---:|---:|
| FY2024 | Downstream | 146,434 | 146.43B | 4 |
| FY2024 | Upstream | 46,848 | 46.85B | -2 |
| FY2024 | All Other | 132 | 132.00M | 0 |
| FY2025 | Downstream | 130,876 | 130.88B | -4 |
| FY2025 | Upstream | 53,452 | 53.45B | 2 |
| FY2025 | All Other | 104 | 104.00M | 0 |

6 筆均在顯示精度內，沒有超出容許精度而需要解釋的差異。上下游顯示到 0.01B，半個顯示單位為 5 百萬美元；每類兩個 SEC 運算元均為 `decimals=-6`，各有 0.5 百萬美元精度誤差，所以容許差額為 6 百萬美元。All Other 顯示到 0.01M，半個顯示單位為 0.005 百萬美元；單一 SEC 運算元有 0.5 百萬美元精度誤差，所以容許差額為 0.505 百萬美元。SEC 值取自上述 FY2024、FY2025 10-K 的抵銷後分部營收 fact，完整 dimensions 與原文位置見前文。

季度序列 2024 Q1 至 2026 Q2 共 10 期為「來源沒有資料、沒有比對的期別」，不以抵銷前口徑的富途替代。TradingView 沒有此三類加總之外的獨立總營收對照值，總營收未作來源比對；FY2023 僅作上一年度口徑依據，更早對照期間不在本次比對範圍。

## 比較欄

正式 `status.json` 的 12 期均沒有 `differences`，也沒有頂層 `comparison_errors`。已下載申報的比較欄與正式輸出，在框架比對到的分類及總營收角色上，沒有產生超出精度的差異或無法解析的標記。Q4 的年度與九個月累計角色均包含在比較欄比對範圍內；較晚申報不改寫原期數字。
