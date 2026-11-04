# 瀏覽器資料取得與限制

查核日期：2026-11-04。使用者既有 Edge 登入狀態與正常可見頁面；不提取憑證、不更動登入、
不使用隱藏 API、不繞過驗證或存取限制，也不上傳原始參考資料。

## Stock Analysis

[Apple 頁面](https://stockanalysis.com/stocks/aapl/metrics/revenue-by-segment/)
的 Quarterly History 表與圖表無障礙標籤可讀，該頁顯示 48 期；八個目標顯示日期介於
2024-12-31 至 2026-09-30。History 縮寫十億，圖表標籤提供完整美元值。

原生 Download 選單包含 Excel、CSV、Google Sheets。唯一一次 CSV 點擊後，完成事件逾時，
未回傳檔案路徑。權限訊息為 `Allow download from`，目標是上述 Apple URL。
尚未見可驗證的同意反應，因此檔案 bytes、schema、精度及列數都未確認，不重複下載。

`edge://downloads/all` 被工具拒絕，原因是僅允許 HTTP／HTTPS；這不是網站 403 或登入失敗。
拒絕後未從替代介面繞過。原生 Edge 控制也曾出現權限提示，但讀取網頁 DOM 不需要原生控制。

## 富途

[Apple 頁面](https://www.futunn.com/hk/stock/AAPL-US/financials-revenue)
的業務區可讀期間、幣別、分類、營收與占比。地區區塊有獨立年度選單，不能沿用業務區的季標籤。
Apple 選單不是連續八季，FY 不能代替 Q；原頁已恢復初始 2026/Q3。
頁首 Download 是應用程式下載，不代表財務資料匯出。

切換季度時，期間標籤會先更新、數值較晚更新；必須確認資料已刷新才擷取。
第二輪查核更證明初次「暫無內容」可能只是載入中的狀態：WMT、BRK-B、XOM、NEE 正常導覽後
均有資料。這四家先前的缺資料結論已撤回，見 [更正與證據](evidence-review.md)。
先前公開 HTTP 取得的 403 只描述該次請求，不表示已開啟的 Edge 頁面無法讀取。

## TradingView

[Apple Segments](https://www.tradingview.com/symbols/NASDAQ-AAPL/financials-segments/)
在 Edge 的正常導覽逾時，後續 DOM 只有空白 document；公開網頁讀取則有年度摘要及 By source／
By country 標題，未取得可驗證的八季明細。這是本次實測狀態，不代表 TradingView 全站沒有資料。
未進行登入變更、隱藏端點呼叫或跨限制替代擷取；三家逐季完整比較尚未完成。

## 條款範圍與操作區別

[Stock Analysis 條款](https://stockanalysis.com/terms-of-use/)（頁示 2026-10-29）
的 Automated access 區限制機器、自動瀏覽與大量下載，同區另有遵循 robots.txt 的 AI crawler 例外；
Your account 區則限制讓機器或系統存取帳號。[robots.txt](https://stockanalysis.com/robots.txt)
已查閱，crawler 例外不自動證明付費帳號自動化權限。使用者手動原生匯出、一次明確要求的原生點擊、
以及批次收集是不同操作；條款疑慮不能被改寫成 DOM 技術上不可讀。

[富途協議](https://www.futunn.com/about/services?lang=zh-hk)（頁示 2024-08-13）
III(3)(6) 涉及未授權第三方工具登入或使用，III(3)(4) 涉及執行及傳輸資料的複製／修改；
V 與行情資料附錄涉及用途及再散布。這不構成已登入 DOM 不可讀的技術證據。

[TradingView 條款](https://www.tradingview.com/policies/)第 3 節包含 display-only 與 non-display
用途限制；可讀公開摘要不等於已取得批次處理或再散布授權。本研究的私人用途不被當成通用授權。
目前 CSV 的具體操作阻礙是待確認的下載結果；各來源的規模化使用條件須與此分開記錄。
