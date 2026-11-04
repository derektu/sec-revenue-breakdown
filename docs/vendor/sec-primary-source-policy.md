# 原始數字來源只用 SEC

營收數字的擷取與計算輸入必須來自 **SEC 申報文件**，包括 10-K、10-Q 及 8-K 附件。Stock Analysis、富途、TradingView 與公司 IR 可以作參考或解釋差異，不能代替 SEC 原始數字。公司發行稿即使內容相同，也不能直接把其公司網站網址改標為 SEC。

目前最新為 **24 / 30 OK、6 / 30 Fail**，見 [三十家公司結果](../../research/reference-gap-completion-20261104/completion-status.json) 與 [CAT、Comcast、PGR 最新修復](sec-remaining-company-repairs.md)。完成的 768 個數字輸出都有 SEC 運算元；N/A 不補零。最新 [MCD／CVX 參考補齊](reference-gap-completion.md) 與 [XOM 歷史八季](xom-sec-history.md) 已整合。以下保留前輪 21 家來源修正的實際過程。

## 本輪實際修正

| 公司 | 改為 SEC 擷取／計算的方式 | 現在判定 |
|---|---|---|
| META | 不再使用公司 IR 的直接單季 HTML 數字。2025 Q4 改由 SEC 原申報 FY 減九個月；廣告及其他收入各有 100 萬美元差額，保留 SEC 結果及兩個原始申報運算元，明列申報精度解釋。 | **OK**：八季 22 項相同、兩項精度解釋。 |
| GOOGL | 不再使用公司 PDF 的 Q4 避險數字。改用 SEC 合併收入減三分部收入對帳；Q4 保留 SEC 計算值及 100 萬美元差額，所有年度／九個月運算元精度合計為 400 萬美元。 | **OK**：八季 55 項相同、一項精度解釋。 |
| UNH | 兩季六個結果恢復成既有 SEC facts，數值與先前公司表相同。公司 GAAP／adjusted 表只作參考差異解釋，並明標 `company_table_is_reference_only`。 | **OK**：八季 21 項相同、三項參考口徑差異。 |
| UPS | 最新 2026 Q3 改為解析 SEC 的 8-K Exhibit 99.1 三個分部收入列，不再以公司 PDF 作原始資料。 | **OK**：八季 24 項相同。 |
| PGR | 前輪公司 PDF 成果不計為 SEC 輸出；最新一批已另取得五份真正 SEC 原表並寫 parser。 | **Fail：缺最新季參考**。SEC 七季現有 43 項相同、六項有參考差異證據；最新季 SEC 也已擷取，仍未滿固定參考八季。 |

META／GOOGL 的差額沒有改成參考數字，也沒有改寫原始參考。這些項目計為有計算依據的精度例外，並非完全相等。歷史年度／九個月的申報值各自四捨五入，差額保留在完整結果中。

UPS 的 SEC 文件為 [8-K 申報索引](https://www.sec.gov/Archives/edgar/data/1090727/000162828026067381/0001628280-26-067381-index.htm) 與 [Exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1090727/000162828026067381/exhibit991-earningspressre.htm)，accession 為 `0001628280-26-067381`。索引描述誤寫 first quarter，附件正文實際為 **3Q 2026**；程式檢查正文季度與表頭，不依索引短描述猜期間。

已保存的是正常 web 工具成功讀取 SEC 附件後的頁面文字快照，不是公司網站副本，也不是原始 HTML bytes。之後 CLI 單次正常 GET 回 403，未重試或更換驗證／標頭；使用先前已正常取得的 SEC 文字進行解析。快照保留文件網址、原表行號、單位及 SHA-256。[程式擷取的三個收入值](../../research/sec-only-completion-20261104/UPS-SEC-quarter.json) 可直接覆核，原始快照留本機。

## 執行與來源檢查

前輪來源檢查入口為 [enforce_sec_primary_source.py](../../scripts/enforce_sec_primary_source.py)：

```sh
data/vendor/local/.venv/bin/python scripts/enforce_sec_primary_source.py \
  --ups-sec-page data/vendor/local/sec-source-enforcement-20261104/UPS-2026Q3-sec-web.txt \
  --out /tmp/新的SEC來源檢查
```

須已有前輪本機詳細資料與 SEC 頁面文字快照，輸出目錄及同名詳細目錄須不存在。此入口不呼叫公司 IR parser，不下載資料，也不依公司 PDF 決定數字輸出；前輪資料內的 IR 比對證據可以保留作參考。

程式對每個數字要求非空 SEC facts，檢查 HTTPS 的實際 SEC host 與 EDGAR Archives 路徑，並遞迴檢查全年、九個月及合計運算元。只有標題網址像 SEC、卻沒有 SEC 運算元，或父層是 SEC、子運算元來自 IR，都不接受。來源缺漏不得標 OK。

[前輪驗證收據](../../research/sec-only-completion-20261104/local-verification.json)：125 項離線測試通過、三十家結果及來源快照雜湊通過、原始參考值與日期未改，680 個完成輸出全數有 SEC 出處。沿用已保存並驗證的 SEC facts，沒有宣稱本輪重新下載或重剖全部 SEC 原始 HTML。所有季度仍為回溯驗證。

最新三十家明細路徑及 SHA-256 以 [24 家收據](../../research/reference-gap-completion-20261104/completion-status.json) 為準。CAT／Comcast 的正常 SEC 瀏覽器讀取已成功，原先 CLI 403 與公司 PDF 逾時不再代表這兩家的 SEC 原表缺口。剩餘六家及具體處理方式見 [最新修復報告](reference-gap-completion.md)。
