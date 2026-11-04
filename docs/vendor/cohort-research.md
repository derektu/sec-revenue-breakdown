# 三十家公司第一輪參考來源實驗

2026-11-04 依凍結的三十家公司名單與 SEC 基準執行。這份文件保留第一輪計數；
目前逐公司狀態以 [第二輪查核](evidence-review.md) 與 [日期稽核](company-audit.md) 為準。
**第一輪將四個載入中的空白判為缺資料，已更正；不是五家公司都沒有參考資料。**

| 第一輪來源 | 有數值公司數 | 期間觀察數 | 數值觀察數 |
| --- | ---: | ---: | ---: |
| Stock Analysis Quarterly DOM（含 Apple） | 22 | 176 | 728 |
| 富途補充 MCD、CVX、PGR | 3 | 19 | 90 |
| 另記的 Apple 富途樣本 | 1 | 5 | 25 |

Apple 重複於兩來源，第一輪有參考值的是 25 家。八個顯示期間不等於 SEC 最新八個財季。
Stock Analysis 的 MCD、WMT、PGR、XOM、CVX、NEE、PLD 標準 metrics 路徑回傳 404；
BRK-B 經站內搜尋解析為 BRK.B，公司頁未顯示 Metrics 導覽，不能據此認定沒有營收揭露。
富途第一輪取得 MCD 七季、CVX 五季、PGR 七季；第二輪新增 WMT、NEE、BRK-B、XOM。
PLD 的富途公司頁存在，但沒有財務導覽，earnings／revenue 路徑回傳 404；公司 IR 可作替代參考。

## 數字候選與已驗證限制

`scripts/compare_vendor_cohort.py` 只離線搜尋已存 SEC 季度 facts；
[cohort-diagnostics.json](cohort-diagnostics.json) 為不含原始數值的第一輪摘要。
Stock Analysis 728 筆中，642 筆有數字候選、68 筆沒有、18 筆期間無法對照。
富途補充三家 90 筆中，51 筆有候選、39 筆沒有。**這些不是語意通過數，也不是準確率。**

完整私人結果保留所有命中的 concept、完整 dimensions、unit、context、期間、來源與推算方式；
不任選一個相同數字當答案。名稱提示另列，不能認證語意。缺候選可能來自 parser 涵蓋、
階層、Q4 推算、重編、日期或真實差異，不能直接指控供應商錯誤。

日期完全相同、七日內近日期建議、45 日內財季標籤位移建議各自區分；建議不是核准對照。
超出範圍或距離相同則拒絕選期，不為了命中金額移動期間。逐家公司見日期稽核。

- **缺值與零：** 表格破折號即使在圖表顯示零仍保留缺值；共抑制 112 個這類圖表零。
- **分類變動：** MSFT、ORCL、KO、CAT 的有效分類集合改變，不自動把新舊名稱接成一列。
- **CMCSA：** 只針對明確 OperatingSegments 範圍，將住宅與商業 connectivity 相加；八期中五期相同、三期不同。
  另一大類仍未判定，不能宣布整家公司通過。
- **CVX：** 同一範圍的上／下游美國與非美國 gross sales 相加，十次運算八次相同；兩筆 Q4 缺明確運算元而棄權。
  保留負的分部間抵銷，不能將 gross/net 混用。
- **AMZN：** 兩年 Q4 廣告的年度成員為 `us-gaap:AdvertisingMember`，九個月為
  `amzn:AdvertisingServicesMember`，基準的精確成員推算拒絕合併；這是已證實的連續性缺口，不是零營收。
- **PGR：** 保險服務、投資收益與證券損益不能只依 revenue/sales 名稱過濾；實現與持有損益可能重疊，須查定義。

## 本機證據與重現

原始 DOM、缺值、正負號、時間、分類及倍率留在 `data/vendor/local/cohort-20261104/`。
數字圖表標籤明確以百萬美元倍率正規化；PG 使用縮寫表格值與半個顯示步階容差。
富途 `億` 使用經檢查的 0.01 億步階，`萬` 使用一萬步階，不以省略尾零放大容差。
原生下載精度尚未驗證。

```sh
data/vendor/local/.venv/bin/python scripts/compare_vendor_cohort.py \
  --captures data/vendor/local/cohort-20261104 \
  --private-report data/vendor/local/cohort-20261104/private-report-new.json \
  --summary data/vendor/local/cohort-20261104/shareable-summary-new.json
```

程式不連網，要求完整交代三十家公司（含失敗），不覆寫既有輸出，詳細結果只能寫入忽略的本機目錄。
`futu-gaps.json` 保留第一輪歷史，不能單獨用作最新缺漏清單；新增結果見第二輪摘要。
CSV 未確認成功，沒有重複下載、變更登入、提取憑證或繞過存取限制。所有來源均為參考，不能指定單一供應商為標準答案。
