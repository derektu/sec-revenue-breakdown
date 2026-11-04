# 缺季的補充參考核對：19 項相同，完成數不變

本輪在 Mac 離線時，正常讀取公司公開報表與申報副本，補核對 MCD 2024 Q3，以及 BRK-B 2024／2025 Q3。**共 19 項與 SEC 輸出精確相同；本研究不增加固定供應商八季完成數。** 沒有重做 XOM 工作。

整合時 main 已另合併本機的[富途缺季補回](reference-gap-completion.md)：MCD 已正式 OK，CVX 補回 2024 Q3 後仍缺兩季，因此最新完成數是 **24 / 30**。本分支合併並保留該成果，沒有用本研究的報表副本替代富途或計入新增家數。

這些新增參考與 SEC 申報有共同上游，不是獨立資料商交叉驗證，也沒有把富途七季加公司網站一季拼成完整八季。最新季及本輪歷史資料均已接觸，不稱盲測。

## 實際比對

| 公司／季度 | 新增參考 | 分類與口徑 | 結果 |
|---|---|---|---|
| MCD 2024 Q3 | [公開 CDN 的 2025 Q3 10-Q PDF 副本](https://d18rn0p25nwr6d.cloudfront.net/CIK-0000063908/8564664b-2af9-4960-b5d2-e8f8b30dc99f.pdf)，PDF 第 16 頁的 2024 比較欄 | 美國、國際營運市場、國際開發許可市場與公司；含其他收入的分部收入，排除營業利益、餐廳銷售與同店銷售率 | 三項相同，合計等於參考同表合併收入。使用後期比較欄，已明標。 |
| BRK-B 2024 Q3 | [公司網站 2024 Q3 10-Q 副本](https://www.berkshirehathaway.com/qtrly/3rdqtr24.pdf)，PDF 第 31 頁 | 保險、製造、Pilot、McLane、服務與零售、BHE、BNSF、公司／抵銷／其他 | 八項相同，含保險投資收入；八分類與同表合併收入對帳通過。 |
| BRK-B 2025 Q3 | [公司網站 2025 Q3 10-Q 副本](https://www.berkshirehathaway.com/qtrly/3rdqtr25.pdf)，PDF 第 31–33 頁 | 相同八分類；保險收入含承保與投資活動，分部對帳保留公司及抵銷項 | 八項相同；從分散表格讀取當季收入，排除稅前利益與累計欄。 |

MCD 的[原公司新聞稿](https://corporate.mcdonalds.com/content/dam/sites/corp/nfl/pdf/Q3_24_Earnings_Release.pdf)只有合併收入、收入型態及同店銷售率，沒有完整三個分部收入，故不拿它補分部。後來取得的 CDN 報表副本提供所需比較欄；本輪未證明該 CDN 檔案是由公司 IR 頁面直接連出的，因此明列實際主機及文件身分，不改標公司原始網站或 SEC。

2025 年 Berkshire 採用新增分部披露格式，八分類散在保險、其他業務與對帳表，不能把第一個數字列或稅前利益表當成收入。程式會檢查保險子項與合計、全部八分類與合併收入，同時確認季度與百萬美元單位。這些都是直接單季參考，不需要把 FY 當 Q；本輪沒有新增 Q4 推算。

## SEC 輸出與參考資料隔離

[執行程式](../../scripts/compare_missing_ir_references.py) 先核對既有凍結基準檔雜湊，從 SEC iXBRL 候選以完整 concept、dimensions、unit 及季度選取 19 個輸出；它不接受公司網站數字作為輸出值。MCD 只沿用原本已審閱的 2024 Q3 美國 member 名稱接合。每筆輸出保存 SEC URL、原始文件雜湊、accession、期間、unit、維度及 fact 位置。

參考數字只在完成 SEC 選取後用於比較。參考文字由正常 web 工具讀取，**保存的是帶行號的 PDF 文字摘錄，沒有保存原始 PDF bytes**；未把文字摘錄雜湊冒稱 PDF 雜湊。公司報表副本不改標 SEC。三份參考摘錄與含參考金額的逐筆比較均保存在 Git 忽略的 `data/vendor/local/cloud-ir-reference-20261104/`；repo 只保存來源／摘錄雜湊、分類及比對狀態與由 SEC 產生的輸出。

[公開結果](../../research/missing-ir-reference-20261104/summary.json) 記錄 19 項結果與 SEC facts；[存取與限制收據](../../research/missing-ir-reference-20261104/access-and-limitations.json) 記錄其餘來源嘗試。整合 main 後 151 項 `tests/` 離線測試通過，其中新增七項測試涵蓋季度／累計與年份欄序、錯誤單位、缺值、負數、重複摘錄衝突、保險合計及來源隔離。

## 仍欠資料

| 公司 | 本輪實際情況 | 尚未完成 |
|---|---|---|
| MCD | 2024 Q3 三分類可與上述申報副本比對 | 本機另補回富途 2024 Q3，已正式 OK；本研究只是補充證據。 |
| BRK-B | 2024／2025 Q3 各八分類可與公司網站副本比對 | 仍缺固定富途兩季；沒有合併來源補滿八季。 |
| CVX | [報告入口](https://www.chevron.com/investors/reports-and-filings)回 403，已停止該入口，沒有重試或繞過 | 本研究未新增參考比對；整合本機另補的富途 2024 Q3 後，現有六季相同，仍缺 2025 Q3、2025 Q4。 |
| LLY | 最新公司新聞稿可讀，但本輪未確認五個研究分類的完整數值 | 2026 Q3 仍未完成五分類新參考比對；不從總收入或少數藥品補推缺項。 |
| PGR | 公司財務及股東報告頁可讀，目前擷取文字沒有完整七分類 | 2026 Q3 尚未新增完整參考比對；不推論網站永久沒有資料。 |
| PLD | 前輪公司 IR 八季參考已完整，本輪未重抓 | 仍缺原約定三家之一完整八季參考。 |

重跑須已有上述三份本機參考摘錄，輸出目錄及同名本機明細目錄必須不存在：

```sh
python scripts/compare_missing_ir_references.py \
  --references data/vendor/local/cloud-ir-reference-20261104 \
  --out /tmp/新的補充參考研究
python -m unittest discover -s tests -p test_missing_ir_references.py -v
```

程式不連網。缺本機參考時會明確報錯；測試使用合成參考表與已保存 SEC 基準，不依賴被忽略的第三方明細。
