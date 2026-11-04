# CVX Fail：仍缺 2025 Q3、Q4 收入參考

本輪核查後，**總數維持 29 / 30 OK，CVX 維持 Fail**。八季四分類的 SEC 擷取已重播成功，共 32 個輸出；已保存六季富途參考的 24 項再次比對全部相同。缺的是 2025 Q3、Q4 的完整四分類收入參考，並非 SEC parser 缺值。[核查收據](../../research/cvx-reference-followup-20261104/status.json) 保留來源、結果及證據雜湊，沒有改寫前輪完成收據。

## 三家參考的正常頁面

| 來源 | 實際觀察 | 為何仍不能補齊 |
|---|---|---|
| [富途](https://www.futunn.com/hk/stock/CVX-US/financials-revenue) | 正常 Edge 的業務選單依序有 2026/Q2、2026/Q1、2025/FY、2025/Q2、2025/Q1、2024/FY、2024/Q4、2024/Q3。選擇 2025/FY 後日期與四分類數值確實更新，單位為美元。 | 沒有 2025/Q3、2025/Q4 選項。全年加前兩季不足以分別決定後兩季，不能將 FY 當作 Q4。 |
| [Stock Analysis 指標頁](https://stockanalysis.com/stocks/cvx/metrics/) | 正常頁面可讀，列出 Earnings by Segment、Net Oil Production by Geography、Refinery Input by Geography。表頭確有缺少兩季的日期；頁面來源標示 TipRanks。另查收入分類的既有路徑，顯示該頁型 404。 | 可讀的分部表標示為利益，不能因有日期與 Upstream／Downstream 名稱便改當收入；也不能從單一路徑 404 推論整個網站無資料。 |
| [TradingView 分類頁](https://www.tradingview.com/symbols/NYSE-CVX/financials-segments/) | 正常 Edge 從舊收入頁導向此頁，標題顯示 Revenue Breakdown，但內容維持空白；accessibility 與畫面皆未取得表格。讀取工具也回報此網址無法存取。 | 本輪沒有取得可核對的分類及季度。這是本次讀取未完成，不能宣稱 TradingView 沒有資料，亦沒有登入拒絕的證據。 |

瀏覽器使用新分頁，完成後已關閉，未變更登入或使用者既有分頁。富途年度原值與結構化觀察僅留 Git 忽略的本機目錄。這份觀察是代理從正常畫面整理的紀錄，不冒稱原始 HTML、DOM 快照或 PDF bytes。

## 其他公開參考的實際限制

前輪已正常讀取 Chevron Q3 發布稿的十頁 PDF；其中分部表是利益、資本支出及產量，合併收入也不能代替四分類收入，詳見[前輪紀錄](cross-source-adjudication.md)。本輪另查：

- [2025 年報補充](https://www.chevron.com/-/media/shared-media/documents/2025-chevron-annual-report-supplement.pdf)：讀取工具回 403，停止。
- [公司網站 2025 Q3 10-Q 副本](https://chevroncorp.gcs-web.com/static-files/ec8ded16-05aa-4f92-9bc3-3f6b3a257f4d)：讀取工具曾成功顯示 104 頁 PDF 文字預覽，含九個月收入表。正常直接下載回 403，未保存 PDF bytes，停止；未完成所需單季、分類及計算核對，不採搜尋摘要當完整參考。
- [公司網站 2025 年報](https://www.chevron.com/-/media/chevron/annual-report/2025/documents/2025-AnnualReport.pdf)：正常直接下載回 403，未保存 PDF bytes，停止。

公司 10-Q／年報副本與 SEC 申報有共同上游；即使後續能完整解析，也只能明列為另一格式的交叉核對，不能當作獨立於 SEC 的來源驗證。本輪沒有以 SEC 數字自己核對自己來提高完成數，也沒有為取得資料改變身分、登入或存取控制。

## 可重播的部分與下一步

使用既有入口重播 SEC 輸出，不需要參考網站或網路：

```sh
data/vendor/local/.venv/bin/python scripts/audit_remaining_sec_coverage.py \
  --out /tmp/新的SEC覆蓋重播.json
```

本輪產出的 CVX 八季結果與前輪 SEC coverage 完全相同；每項選值仍保留 SEC URL、期間、完整 scope、單位與推算運算元。既有六季參考逐項重新比較，24 項全部相同；Chevron scope／抵銷的三項測試通過。前輪 173 項離線測試成績保留，本輪沒有修改 parser。

下一個能消除缺口的證據，是合法取得 2025 Q3、Q4 四分類收入，或取得同口徑全年及九個月／半年參考、經程式計算拆出單季並保留全部參考運算元。只有 FY 或利益、產量資料都不足夠。現階段沒有需要使用者處理的登入提示，未要求操作；未取得參考以前維持 Fail。
