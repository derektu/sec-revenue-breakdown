# PGR parser

## 觀點

業務分部（`view="business_segment"`）。分類是各期申報分部表的保險業務分部，加上分部表或營收調節表中分部以外的各項營收；各項加總等於損益表的 Total revenues，沒有調節項。

申報的分部營收有兩種口徑，分類跟著各期申報：

| 申報 | 分部營收的口徑 | 分類，依序 |
|---|---|---|
| FY2023 10-K、2024 年 Q1–Q3 10-Q | 已賺保費（net premiums earned）；Property 是獨立分部 | Personal Lines、Commercial Lines、Property、Other indemnity、Fees and other revenues、Service businesses、Investments |
| FY2024 10-K 起 | 已賺保費加手續費（total underwriting revenue）；Property 併入 Personal Lines | Personal Lines、Commercial Lines、Other indemnity、Investment income、Net realized gains (losses) on securities、Service revenues |

`us-gaap:StatementBusinessSegmentsAxis` 的成員是 Personal Lines、Commercial Lines、Property、Other indemnity 保險業務，不是地區。

| 對照來源 | 列出的分類 | 對應 |
|---|---|---|
| 富途（只有季度） | 個人保險、商業保險、物業（只到 2023 年）、其他、投資收益、Service revenues、費用和其他收入（只到 2023 年）、Net realized gains (losses) on security sales、Net holding period gains (losses) on securities；Q4 另有 Net realized gains (losses) on securities | 個人保險＝Personal Lines，商業保險＝Commercial Lines，物業＝Property，其他＝Other indemnity，投資收益＝Investment income，Service revenues＝Service revenues（舊口徑的 Service businesses），費用和其他收入＝Fees and other revenues；證券損益的各列相加＝Net realized gains (losses) on securities；舊口徑的 Investments＝投資收益加證券損益各列 |
| TradingView（只有年度） | Personal Lines、Commercial Lines、Property（只到 FY2023）、Other、Reconciliation | Other＝Other indemnity；Reconciliation＝分部以外各項營收的合計 |
| Stock Analysis | 沒有 PGR 的對照資料 | 不計入多數判斷 |

對照資料位於 `data/universe/references/P/PGR/reference.json`。兩個來源在預設起始日（2024-01-01）以後都列出分部以外的營收（富途逐項、TradingView 合為一列），所以這些項目列成分類，以申報表格的列標籤逐項輸出。

申報另有 Personal Lines 的 Agency／Direct 通路拆分（`us-gaap:SubsegmentsAxis`，只在舊口徑的分部表）與 Schedule III 的分部保費（主文件，`us-gaap:SupplementaryInsuranceInformationPremiumRevenue`），都不採用：前者是 Personal Lines 的下一層，後者不含分部以外的營收、無法與總營收相加核對。

### 為什麼讀附件 EX-13

10-K 的財務報表、附註（含分部表與營收調節表）都在附件 EX-13（年報 Annual Report to Shareholders 的附錄，檔名 `pgr-<期末>_d2.htm`）的 inline XBRL，主文件只有 Schedule III。因此 `parser.py` 宣告 `ATTACHMENTS = ("EX-13",)`，10-K 的 fact 清單是主文件加 EX-13。10-Q 沒有 EX-13，財報在主文件。主文件與 EX-13 都標了不帶維度的 `us-gaap:Revenues`，但主文件那一個帶 `srt:ConsolidatedEntitiesAxis=srt:ParentCompanyMember`（母公司單獨報表），不是合併數；parser 用的每個 fact 在 10-K 都只出現在 EX-13。

## 分類與 tag

### 已賺保費口徑

FY2023 10-K（0000080661-24-000007，期末 2023-12-31）與 2024 年 Q1–Q3 10-Q（0000080661-24-000018、0000080661-24-000031、0000080661-24-000045）。全部是 `us-gaap:Revenues`，取自分部表：

| 分類 | 完整 dimensions |
|---|---|
| Personal Lines | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`、`srt:ProductOrServiceAxis=pgr:UnderwritingOperationsMember`、`us-gaap:StatementBusinessSegmentsAxis=pgr:PersonalLinesSegmentMember` |
| Commercial Lines | 同上，分部成員 `pgr:CommercialLinesSegmentMember` |
| Property | 同上，分部成員 `pgr:PropertySegmentMember` |
| Other indemnity | 同上，分部成員 `pgr:OtherIndemnityMember` 或 `pgr:OtherIndemnitySegmentMember` |
| Fees and other revenues | `srt:ConsolidationItemsAxis=us-gaap:MaterialReconcilingItemsMember`、`srt:ProductOrServiceAxis=pgr:FeesAndOtherRevenuesMember` |
| Service businesses | `srt:ConsolidationItemsAxis=us-gaap:MaterialReconcilingItemsMember`、`srt:ProductOrServiceAxis=pgr:NonInsuranceServiceBusinessMember` |
| Investments | `srt:ConsolidationItemsAxis=us-gaap:MaterialReconcilingItemsMember`、`srt:ProductOrServiceAxis=pgr:InvestmentsMemberMember` 或 `pgr:Investments1Member` |

- Other indemnity 在 FY2023 10-K 是 `pgr:OtherIndemnityMember`，2024 年各 10-Q 是 `pgr:OtherIndemnitySegmentMember`；Investments 在 FY2023 10-K 是 `pgr:InvestmentsMemberMember`，2024 年各 10-Q 是 `pgr:Investments1Member`。兩者都以 `one_of` 找每一種寫法。
- 分類名稱取自分部表的列標籤（Total Personal Lines 去掉 Total）。

### 已賺保費加手續費口徑

FY2024 10-K（0000080661-25-000007，期末 2024-12-31）起的每一份申報。

| 分類 | concept | 完整 dimensions |
|---|---|---|
| Personal Lines | `pgr:PremiumsEarnedFeesAndOtherRevenue` | `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`、`srt:ProductOrServiceAxis=pgr:UnderwritingOperationsMember`、`us-gaap:StatementBusinessSegmentsAxis=pgr:PersonalLinesSegmentMember` |
| Commercial Lines | 同上 | 同上，分部成員 `pgr:CommercialLinesSegmentMember` |
| Other indemnity | 同上 | 同上，分部成員 `pgr:OtherIndemnityMember` 或 `pgr:OtherIndemnitySegmentMember` |
| Investment income | `us-gaap:InterestAndDividendIncomeOperating` | 不帶維度 |
| Net realized gains (losses) on securities | `us-gaap:DebtAndEquitySecuritiesGainLoss` | 不帶維度 |
| Service revenues | `pgr:NonInsuranceServiceRevenues` | 不帶維度 |

- 三個分部是分部表的 Total underwriting revenue 列（Net premiums earned 加 Fees and other revenues）。Other indemnity 在 FY2025 10-K 是 `pgr:OtherIndemnityMember`，FY2024 10-K 與各 10-Q 是 `pgr:OtherIndemnitySegmentMember`；以 `one_of` 找每一種寫法。FY2024 申報包裡的 `pgr:OtherIndemnityMember` 只出現在主文件 Schedule III 的 `SupplementaryInsuranceInformation*` concept，不在營收 fact 上。
- 分部以外的三項取自 10-K 的營收調節表（total underwriting revenue 到 consolidated revenues）與損益表；10-Q 沒有調節表，取自損益表。三項都是不帶維度的合併數。
- 分類名稱：三個分部取自分部表的欄標題；Other 欄的註腳說明是其他承保業務與 run-off，同一份申報的承保利潤率表與 XBRL 成員都稱 Other indemnity，所以兩種口徑都用 Other indemnity。其餘三項取自營收調節表的列標籤（Total net realized gains (losses) on securities 去掉 Total）。

### 總營收與寫法的選擇

- 總營收（Total revenues）是不帶維度的 `us-gaap:Revenues`，兩種口徑相同。
- parser 依這份申報、這段期間有沒有 Personal Lines 的 `pgr:PremiumsEarnedFeesAndOtherRevenue` fact 選擇口徑，不依日期。
- `categories` 在 2024-10-01（FY2024 10-K 涵蓋的 Q4 起日，也就是最後一份已賺保費口徑主申報 2024 Q3 10-Q 期末日的隔天）起回答加手續費口徑的六類，之前回答已賺保費口徑的七類。涵蓋下限是 2023-12-31（範圍內第一個財年的上一財年期末日）：FY2023 10-K 以已賺保費口徑組得出來。2023 年各 10-Q 沒有上表 Investments 成員的 fact，組不出來，在範圍外。

## 期別與推算

- 財年是曆年，季末日是 3、6、9、12 月底。
- Q1–Q3：10-Q 的單季 fact。
- Q4：10-K 年度減去同財年 Q3 10-Q 的九個月累計。
- FY：10-K 的年度 fact。
- 2024 年 Q4 不推算（`not_derived`，Q4 推算條件）：FY2024 10-K 是加手續費口徑的六類，2024 年 Q1–Q3 是已賺保費口徑的七類，分類集合不同。FY2024 照常輸出。
- 2025 年 Q4 推算，口徑依據是已上線的 FY2024。

## 數字在原文的位置

10-Q 的表格在主文件，10-K 的表格在 EX-13（`pgr-<期末>_d2.htm`），表格編號屬於所在的文件。

| 申報 | 分部表 | 損益表 | 其他 |
|---|---|---|---|
| 10-Q 0000080661-24-000018（2024-03-31） | t39：七類與總營收 | | |
| 10-Q 0000080661-24-000031（2024-06-30） | t40：七類與總營收 | | |
| 10-Q 0000080661-24-000045（2024-09-30） | t39：七類與總營收 | | |
| 10-K 0000080661-25-000007（2024-12-31），EX-13 `pgr-20241231_d2.htm` | t50：三個分部 | t0：分部以外三項與總營收 | |
| 10-Q 0000080661-25-000023（2025-03-31） | t39：三個分部 | t12：分部以外三項與總營收 | |
| 10-Q 0000080661-25-000051（2025-06-30） | t39：三個分部 | t12：Investment income、Service revenues 與總營收 | t25（證券損益附註）：Net realized gains (losses) on securities（t12 也標了同一個值，框架選用 t25 的 fact，t12 的記為重複） |
| 10-Q 0000080661-25-000129（2025-09-30） | t39：三個分部的單季；t41：三個分部的九個月累計（2025 年 Q4 用） | t12：分部以外三項與總營收（單季與九個月） | |
| 10-K 0000080661-26-000086（2025-12-31），EX-13 `pgr-20251231_d2.htm` | t51：三個分部 | t0：分部以外三項與總營收 | |
| 10-Q 0000080661-26-000177（2026-03-31） | t41：三個分部 | t12：分部以外三項與總營收 | |
| 10-Q 0000080661-26-000308（2026-06-30） | t39：三個分部 | t12：分部以外三項與總營收 | |
| 10-Q 0000080661-26-000379（2026-09-30） | t39：三個分部 | t12：分部以外三項與總營收 | |

10-K 的營收調節表（FY2024 EX-13 t53、FY2025 EX-13 t54）也標了分部以外三項與總營收，與損益表的 fact 數值相同；框架依文件順序選用損益表的 fact。

FY2023 10-K（0000080661-24-000007）的 EX-13 `pgr-20231231_d2.htm` t50 是已賺保費口徑的分部表，七類與總營收都在這張表。它只在以 `--start` 處理更早期別時用到，範圍內沒有證據檔。

## 已知的重複 fact

- 分部以外三項與總營收在 10-K 的損益表與營收調節表各標一次，數值相同（見上節）。`us-gaap:DebtAndEquitySecuritiesGainLoss` 在 10-K 的 EX-13 另有第三處，在證券損益附註（FY2024 t17 的 f-1350、FY2025 的 f-1314），數值相同。
- `us-gaap:DebtAndEquitySecuritiesGainLoss` 在 10-Q 的損益表（t12）與證券損益附註（t25）各標一次，數值相同。

## 重分類

FY2024 10-K 起，分部營收含手續費，Property 併入 Personal Lines，分部以外的營收改列 Investment income、Net realized gains (losses) on securities、Service revenues。2025 年各 10-Q 以新口徑列示 2024 年同季：

| 期別 | 原申報 Personal Lines（＋Property） | 2025 年 10-Q 的 Personal Lines | 原申報 Commercial Lines | 2025 年 10-Q 的 Commercial Lines | 來源 |
|---|---|---|---|---|---|
| 2024 Q1 | 12,878.2（＋712.8） | 13,787 | 2,557.4 | 2,598 | 0000080661-25-000023 t40 |
| 2024 Q2 | 13,808.9（＋735.9） | 14,761 | 2,664.5 | 2,708 | 0000080661-25-000051 |
| 2024 Q3 | 14,808.0（＋761.8） | 15,805 | 2,726.7 | 2,770 | 0000080661-25-000129 |

單位為百萬美元。例如 2024 Q1：已賺保費 Personal Lines 12,878.2 加 Property 712.8 等於 13,591，加上 Personal Lines 的手續費 196 等於 13,787；Commercial Lines 2,558 加手續費 40 等於 2,598（0000080661-25-000023 t40）。2024 年 Q1–Q3 的輸出照原申報的已賺保費口徑。

## 驗證

範圍是 2024 Q1 至 2026 Q3 共 11 季（2024 Q4 不推算）與 FY2024、FY2025。單位為百萬美元；富途顯示到 0.01 億美元（1 百萬美元）。

**富途（季度）**：以財年季別對齊。富途把證券損益拆成 security sales 與 holding period 兩列，比對時相加。

- 2025 Q1 至 2026 Q3 共 7 季，每一類都在顯示精度內。2025 Q4 富途另列 Net realized gains (losses) on securities 7.27 億（等於 FY2025 全年 727），security sales −0.32 億、holding period −4.38 億（等於 0 減前三季累計 32、438）；三列相加 257，等於 Q4 的 727 − 470。
- 2025 Q1、Q3 的 Other indemnity 是 0，富途沒有列其他，不比對。
- 2024 Q1–Q3 的 Personal Lines、Commercial Lines 有差異：富途是 2025 年 10-Q 以新口徑列示的值（13,787／2,598、14,761／2,708、15,805／2,770，見「重分類」），我們是原申報的已賺保費口徑。原因是重分類。
- 2024 Q1–Q3 的 Property、Fees and other revenues，富途沒有列（已含在它的 Personal Lines、Commercial Lines），不比對；Other indemnity（0.2）富途沒有列，不比對。
- 2024 Q3 的 Investments 1,026.9 等於富途投資收益 7.39 億加證券損益 0.68 億與 2.2 億（1,027），Service businesses 117.3 對富途 1.17 億，都在顯示精度內。2024 Q1、Q2 富途沒有分部以外的項目，不比對。

**TradingView（年度）**：FY2024、FY2025 的 Personal Lines、Commercial Lines、Other indemnity 都在顯示精度內（60,984／60.98B、10,878／10.88B、1／1.00M；71,838／71.84B、11,017／11.02B、2／2.00M）。Reconciliation 等於分部以外三項相加：FY2024 2,832＋264＋413＝3,509／3.51B，FY2025 3,583＋727＋504＝4,814／4.81B。

## 比較欄

2024 年 Q1–Q3 各有 2 筆差異標記，Personal Lines 與 Commercial Lines，來源分別是 2025 年 Q1、Q2、Q3 10-Q（0000080661-25-000023、0000080661-25-000051、0000080661-25-000129）以新口徑列示的同季值，數值與原因見「重分類」。其他期別沒有差異標記。
