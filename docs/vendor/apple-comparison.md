# Apple 本機參考資料比對

2026-11-04 使用既有 Edge 頁面的 DOM，原始觀察及完整比對留在忽略追蹤的
`data/vendor/local/apple-20261104/`。本結果是回溯比對，最新季度已看過，不能稱為盲測。

| 查核 | 實際結果 |
| --- | --- |
| Stock Analysis 季度產品／服務資料 | 八季、40 筆 |
| 與已儲存 SEC 指定產品／服務成員相同 | 40/40 |
| 五分類合計與 SEC 合併營收相同 | 8/8 |
| 富途目標範圍內資料 | 五季、25 筆 |
| 富途與 Stock Analysis、SEC 相同 | 25/25 |
| 富途占比與 SEC 總額相容 | 25/25，容差 0.005 個百分點 |
| 富途選單缺少的目標季度 | FY2026 Q4、FY2026 Q2、FY2025 Q4 |
| 原生 CSV 格式、精度及內容已驗證 | 否 |

Stock Analysis 顯示日期介於 2024-12-31 與 2026-09-30，與 Apple 實際財季截止日不同。
程式採已覆核的 Apple 財季對照；不直接以顯示日期相等連接。FY 不當作 Q，缺季不補零。
Stock Analysis 使用圖表無障礙標籤的完整美元值，History 表格則縮寫十億；富途使用更新後的
「業務」DOM，`億` 為一億美元。富途各期會改變排序，因此依分類而非列位置對照，地區表另計。

SEC 證據來自凍結於 2026-11-03 的還原 `AAPL.json`。選取五個明確產品／服務成員，排除
Products 小計；Q4 使用已儲存的全年減九個月運算。本比對未獨立重查所有運算元是否重編，
也未重剖八份原始 HTML。數字相同不能推論跨公司準確率或完整揭露召回率。

## 離線重現

```sh
data/vendor/local/.venv/bin/python scripts/compare_apple_reference.py \
  --capture-dir data/vendor/local/apple-20261104 \
  --sec-evidence data/vendor/local/research-imports/eight_quarter_reproducible_results/sec_revenue_experiment/eight_quarter_eval/outputs/AAPL.json
```

程式不連網，檢查 issuer、schema、幣別、季標籤與五分類，拒絕缺漏或衝突的 SEC 值。
`comparison.json` 留在 capture 目錄且不覆寫既有結果；重跑須準備新的本機輸入目錄。
輸入 SHA-256、完整數值、財季對照與逐筆結果都在該忽略目錄。負控制將一筆改一美元，
數字一致與季度合計一致各少一筆；混入 FY 則被拒絕。

## 下載與後續研究

先前唯一一次 Download to CSV 未返回完成檔案，下載權限也未見可驗證的同意反應。
未重複點擊；`edge://downloads/all` 的工具限制仍有效，未使用替代方式繞過。
DOM 成果不是 CSV 成果。三十家後續成果見 [逐公司稽核](company-audit.md)，
Apple 的成功不可直接當成通用 scraper 或全產業正確性的證據。
