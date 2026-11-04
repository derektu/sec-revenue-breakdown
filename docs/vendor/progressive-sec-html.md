# PGR：由 SEC 原始 HTML 重跑

本輪獨立雲端工作以 main `5af00b9` 為基礎，沒有讀取、修改或重做離線 Mac 上的 XOM 工作。**完成的是 PGR 原始 HTML 入口與 Q4 期間檢查；公司完成數仍為 23 / 30，PGR 仍 Fail。**

## 實際取得與重跑

正常 HTTPS GET 成功取得五份 SEC 文件：FY2025 合併報表 Exhibit 13、2025 Q3 10-Q，以及 2026 Q1／Q2／Q3 10-Q。全部直接來自 SEC，沒有以公司網站副本替代，也沒有遭拒後重試或繞過。

原始 bytes 以可還原的 gzip 保存在 [來源目錄](../../research/progressive-sec-html-20261104/manifest.json)。manifest 同時記錄原始 HTML 與 gzip 檔雜湊、URL、取得時間及先前 DOM 快照雜湊。原始 HTML 約 15 MB，壓縮後合計約 738 KB；內容是公開 SEC 文件，沒有加入第三方參考明細。

[新入口](../../scripts/parse_progressive_sec_html.py) 從 HTML 表格直接擷取文字，不執行網頁程式，也不連網載入外部資源；數值、年度欄序、季度／累計欄、單位、分部及收入對帳沿用既有檢查。每筆 fact 的 `source_format` 明標 `SEC_raw_HTML_bytes`，雜湊指向解壓後的原始 HTML。既有 DOM 快照仍維持原本格式與雜湊。

五份文件產出 **204 筆 facts**。排除本來就不同的來源格式與檔案雜湊後，所有 facts（含金額、日期、完整 scope、文件 URL 及表格 index）與先前 DOM 結果相同；204 筆包含同期間在後期申報的比較欄，不代表 204 個獨立參考項目。

## Q 與 FY

年報仍限定 Exhibit 13 的合併報表，不接受母公司附表取代。季報分開解析 Q 與 YTD；2024、2025 的 Q4 各產生 12 筆 FY 減 YTD9 結果，保存 [全部 SEC 運算元](../../research/progressive-sec-html-20261104/Q4-derived-SEC-facts.json)。選版本依既有最早可用申報規則，不以供應商數值挑版本。

原 Q4 程式只比對年度／九個月的共同起日、unit 與 scope，未確認實際終日。現在另外要求 FY 為該年 1 月 1 日至 12 月 31 日，YTD9 為同年 1 月 1 日至 9 月 30 日；錯誤期間直接拒絕。既有五份文件的 Q4 結果保持相同。

## 驗證與界限

[驗證收據](../../research/progressive-sec-html-20261104/verification.json) 記錄來源、程式及測試雜湊。145 項離線測試通過：`tests/` 133 項、原抽取器 3 項、八季引擎 9 項。新測試實際讀取五份保存的原始 HTML，核對 DOM 與 Q4，並拒絕被修改的壓縮檔／原始雜湊、manifest URL 不符、錯誤單位與年報母公司文件。

雲端沒有 Git 忽略的富途逐筆明細，因此**本輪沒有重跑供應商比對**。最新 main 的 PGR 結果是七季 43 項相同、六項有 Q4 參考差異證據；既有紀錄仍缺富途 2026 Q3。本輪沒有重新查詢供應商，不宣稱其目前仍未更新，也不宣稱取得第八季參考。最新季已接觸，這些工作是回溯解析，不是盲測。

重跑不需要 Mac、瀏覽器或網路：

```sh
python -m pip install -r research/recovered-sec/requirements.txt
python scripts/parse_progressive_sec.py \
  --manifest research/progressive-sec-html-20261104/manifest.json \
  --out /tmp/PGR-raw-html-facts.json
python -m unittest discover -s tests -p 'test_progressive_sec*.py' -v
```

輸出檔必須尚不存在。原供應商比較入口 `evaluate_progressive_sec.py` 也已支援這份 manifest，但仍需要 Mac 上的前輪逐筆資料，不可把原始 HTML 重跑成功當成八季參考比對完成。
