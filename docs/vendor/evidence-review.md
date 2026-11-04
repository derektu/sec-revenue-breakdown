# 第二輪參考來源與可行性查核

2026-11-04 本機實驗更正第一輪缺漏判定，並對全部三十家公司建立
[日期與分類稽核](company-audit.md)。原始第三方資料與完整數值保留本機，repo 僅保存程式、
方法、公開來源定位及查核計數。這是可行性與回溯驗證，尚未完成三來源、三十家公司全部最新八季的語意認證。

## 已更正的四家與真正缺漏

第一輪富途的「暫無內容」是未等候資料完成載入的觀察，不能據此判定來源無資料。
正常從公司頁進入財務／主營構成，再確認季度與營收更新後，取得以下結果：

| 公司 | 實際取得 | 指定 SEC 定義結果 | 未完成部分 |
| --- | --- | --- | --- |
| WMT | 八個目標季度、32 筆 | 15 筆直接相同、3 筆 Q4 推算相同 | 8 筆公司項目未定義、6 筆缺指定範圍；不可拿 net sales 補 Revenues |
| BRK-B | 六個目標季度、48 筆 | 32 筆直接相同、16 筆 Q4 推算相同 | 選單缺 2025/Q3、2024/Q3；BRK.B 是供應商符號 |
| NEE | 八個目標季度、24 筆 | 18 筆直接相同、5 筆 Q4 推算相同 | 2024/Q4 的 FPL 只有法人層級候選，未認定等同分部 |
| XOM | 八個可見季度、58 筆 | 仍全數未判定 | 最新顯示為 2026/Q2，基準僅兩季；不能跨 CIK 或期間強配 |
| PLD | 富途公司頁存在但無財務導覽；財務路徑 404 | 改查公司 IR 八季 | 兩家 vendor 入口仍缺；公司 IR 不冒稱第三家 vendor |

WMT 的 FY2027/Q2 對應 2026-07-31；FY2026/Q4 對應 2026-01-31。
NEE、BRK-B、XOM 使用已檢查的曆年季末標籤。FY 選項全部排除。
XOM 擷取的第八個可見季度 2024/Q3 比理想最新八季範圍更舊；不能用它掩蓋 2026/Q3 未取得。

第二輪共新增四家公司、30 個期間、162 筆數值觀察，29 家已有第三方參考值。
[數字候選摘要](second-round-diagnostics.json) 和 [指定定義覆核](second-round-review.json)
刻意分開：前者的 91 個數字命中不是後者的通過數。
`exact_match` 表示已指定概念、完整維度、期間與顯示精度相容；
`needs_derivation` 表示仍依賴已儲存的全年減九個月，並未獨立認證重編一致性。
未判定不代表錯誤，缺季也不代表零。

## PLD 的公司原始參考

[公司季度結果目錄](https://ir.prologis.com/financials/quarterly-results) 提供各季發表資料。
本輪實際讀取以下四份發布稿的 Three Months Ended 表格，利用當期及比較期覆蓋八季：
[2026 Q3](https://ir.prologis.com/news-events/press-releases/detail/1055/prologis-reports-third-quarter-2026-results)、
[2026 Q2](https://ir.prologis.com/news-events/press-releases/detail/1044/prologis-reports-second-quarter-2026-results)、
[2026 Q1](https://ir.prologis.com/news-events/press-releases/detail/1036/prologis-reports-first-quarter-2026-results)、
[2025 Q4](https://ir.prologis.com/news-events/press-releases/detail/1029/prologis-reports-fourth-quarter-and-full-year-2025-results)。

採「千美元」財務報表明細，非百萬美元摘要：Rental、Strategic capital、Development management and other，
加上 Total revenues。三個類別及總額共 32 筆與 SEC 指定的無維度 concept 相同，八個分類合計均相同。
Q4 參考本身是明列的三個月數，不以 FY 冒充；SEC Q4 證據仍可能是年度減九個月。
`ManagementFeesRevenue`／`OtherRealEstateRevenue` 的帶 `1` 名稱版本逐期保留，未以模糊名稱任選。
[摘要](pld-ir-review.json) 與完整本機數值可重查。本結果驗證的是合併收入列項，並非全營運分部階層。

## XOM 身分與參考品質

[2026-07-01 的 8-K12B](https://www.sec.gov/Archives/edgar/data/2115436/000119312526291990/d71068d8k12b.htm)
說明 successor 與 predecessor 的關係，支持調查 CIK 2115436 與 34088 的銜接，
但不自動證明所有歷史分部會計口徑連續。本輪未修改凍結 SEC 基準或默默合併兩個 CIK。
富途部分 Q4 的抵銷符號和合計與其他季度明顯不同，須用原報表裁決；不能因為來源畫出占比就當作合理組成。

## 全部 22 家的日期與分類檢查

已逐期檢查本機保存的日期、非空分類集合、SEC 截止日、命中概念與完整維度。
176 個日期觀察中，119 個日期字串相同、30 個近日期建議、22 個月份位移建議、5 個無法對照。
這只是期間診斷。Apple 已有獨立財季對照，其餘建議不升格為確認。
ORCL、HD 的月位移與 COST 的非曆季期間須另外取公司財季證據；CAT、UPS 的參考最新期反而比
凍結 SEC 基準新，不能籠統說供應商資料落後。分類層級、口徑與各公司待決問題見逐公司表。

## Training、測試與資料洩漏

依使用者要求，歷史季度／年報用於調整規則，最新一季應在規則凍結後才測試。
本輪先前已看過最新季度，也檢查過最新金額，因此 **不能稱為嚴格盲測或泛化準確率**。
[切分紀錄](training-test-split.json) 逐公司列出擬用歷史期間、最新回溯測試期、已接觸狀態、
洩漏標記與凍結程式 SHA-256；不是宣稱已依此完成無洩漏訓練。

下一次獨立測試須事先指定尚未看過的期間，保存來源與規則版本；先完成歷史 Q／FY 解析及人工覆核，
再揭露測試期。測試失敗後的修正另開規則版本，不回寫原測試成績。
Q、FY、九個月 YTD 的格式及上下文分開檢查；若年度資料包含測試季，不能讓年度推算運算元洩漏進訓練。
Q4 另查起訖日、週數、單位、概念、完整維度、重編狀態及正負號，保留運算元。

三家皆為參考，不預設 Stock Analysis 是 ground truth。公司財報也須確認報表版本及口徑。
逐 ticker 的裁決依期間、分類定義、gross/net、單位、合併範圍與原始表格證據；合理的多種口徑並存。
目前 AAPL、BRK-B、NEE、WMT、PLD 的特定範圍已有較具體證據；其餘不因命中數字就強選供應商。

TradingView 的 Apple 正常頁面導覽逾時、DOM 空白，公開讀取只有年度摘要與分類區塊標題。
未取得八季明細，也未完成另外 29 家 TradingView 查核；這是本研究尚缺的一個來源維度。
沒有以登入變更或隱藏端點補取。操作與條款細節見 [瀏覽器紀錄](live-browser-check.md)。

## 擴展到 1,500 家的實測複雜度

1,500 家 × 八季是 12,000 個公司季度，但不是 12,000 個可直接相加的相同表格。
三十家刻意跨產業取樣，並非隨機代表樣本，不能將命中比例外推到 1,500 家。
實測已出現：來源路徑／符號差異、四個載入誤判、缺季、財季月份位移、資料先於基準、
至少一個 successor CIK、分類改名、公司及抵銷範圍、兩層以上維度、銀行 FTE、保險投資損益、Q4 運算元缺漏。

現有離線候選搜尋逐筆掃描 facts，計算量約為各公司季度的「參考列數 × SEC facts 數」之和；
這尚不是規模瓶頸的實測效能結論。可先用 concept／完整維度／期間索引縮小候選，但本輪不為風格重構。
更大的未確定成本是每家公司與每次重分類所需的定義裁決、三來源取得條件，以及乾淨測試集的人工覆核。
本輪沒有量測可外推的端到端工時、吞吐、費用或盲測準確率，故不給假精確的 1,500 家時程。

可行結論是：SEC 數字與證據的可重現取得有基礎，第三方 DOM 可提供反例和比對，但還不能宣稱通用規則已穩定。
下一個可驗證里程碑是補 TradingView、逐 ticker 解決待決口徑，再對未見季度跑凍結規則；不能以改成較好看的程式架構取代研究。

## 本機重現

原始資料：`data/vendor/local/evidence-review-20261104/futu-second-round.json`。
完整判斷：同目錄 `semantic-review.json`；PLD 原始參考與指定 concept 查核：`pld-ir-review.json`。
第二輪富途轉錄保留營收原值；占比沒有納入這份轉錄或準確度測量。

```sh
python3 scripts/review_vendor_evidence.py \
  --captures data/vendor/local/evidence-review-20261104/futu-second-round.json \
  --private-report data/vendor/local/evidence-review-20261104/semantic-review-new.json \
  --summary data/vendor/local/evidence-review-20261104/shareable-review-new.json
python3 scripts/build_vendor_audit.py
```

第一個命令拒絕覆寫既有結果，完整原始列只能寫入忽略目錄；第二個只產生不含原始列的 repo 稽核摘要，
並更新規則凍結時間，正式比較應保留已提交的切分版本。測試不代表已解決所有真實財報定義。

最終驗證：28 個測試通過（本機 16、還原 pilot 3、還原季度 9），10 個來源檔雜湊符合 manifest，
30 筆切分紀錄及凍結規則雜湊通過，公開摘要不含原始觀察欄位，原始資料仍受 Git 忽略。
這次未重新執行 234 季原始基準，既有重播結果不冒稱為本輪新增驗證。記錄見 `evidence-review-verification.json`。
