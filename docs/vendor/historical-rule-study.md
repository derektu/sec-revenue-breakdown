# 八季 parser 完成狀態：跨來源 29 / 30 OK

截至 2026-11-04，**跨來源逐期裁決為 29 / 30 OK；只有 CVX 尚未完成。** 原固定供應商八季測試的 **24 / 30** 保留為歷史基準，沒有回寫舊成績。

**所有主要數字的擷取與計算只用 SEC 申報文件（含 8-K 附件）；其他來源只作參考。** 最新 [跨來源結果](../../research/cross-source-final-20261104/completion-status.json) 與 [逐期裁決、來源、複雜度及投入紀錄](cross-source-adjudication.md) 涵蓋全部三十家。

依使用者接續指示，各期可使用已取得且合法、日期與口徑可確認的參考，不因固定供應商缺季而忽略公司報表副本。OK 仍要求八個目標季度及每季完整預定分類，逐項相同或有 SEC 原表支持的具體差異解釋。公司申報副本與 SEC 有共同上游，不當作獨立資料商準確率；目前全為已接觸的回溯驗證，不稱盲測。

原固定來源的 [24 家完成收據](../../research/reference-gap-completion-20261104/completion-status.json)、[MCD／CVX 缺季補回](reference-gap-completion.md)、[XOM 歷史八季](xom-sec-history.md) 與 [六家 SEC 指定欄位八季重播](remaining-sec-coverage.md) 均保留。舊公司 IR 解析不能取代 SEC 輸出；合法 IR 參考則可用來核對 SEC 數字。新季度能否泛化仍是另一項待測問題。

若程式與參考不同，可以用公司財報證明差異原因，再明列為可接受例外。目前沒有未解釋的數值差異計入這 29 家；MSFT、PG 各有一項以 SEC 原表裁決來源錯誤，PG、META、GOOGL 另有可計算的 SEC 申報精度解釋；UNH 三項差異依公司同表的 GAAP／adjusted 分別裁決；HD 兩項採公司原申報同口徑，另有完整年度與季間加總證據；已確認不適用的舊分類空欄保留為 N/A，不補零。精度相容而未完成裁決、人工讀表補值、缺季、缺分類、日期未確認，都先算 Fail。**Fail 代表未達完成標準，可能是缺資料或工作尚未完成，不等於完全無法解析。**

| 公司 | 結論 | 參考來源 | 原因 |
|---|---|---|---|
| AAPL | **OK** | Stock Analysis | 八季五分類，40 個結果全部相同。 |
| MSFT | **OK** | Stock Analysis | 八季 22 項相同；一項來源錯誤：SA 將另一分部營業利益填入收入欄，採 SEC 正確收入，詳見裁決。 |
| NVDA | **OK** | Stock Analysis | 八季兩分類，16 個結果全部相同；歷史名稱差異已有程式規則。 |
| ORCL | **OK** | Stock Analysis | 八季 32 個收入結果相同；已限定二／五／八／十一月財季對應網站曆季標籤，新舊四分類依期間處理且合計等於總收入。 |
| GOOGL | **OK** | Stock Analysis | 八季 55 項相同、一項 Q4 避險收入有 SEC 運算元精度解釋；所有數字由 SEC 分部對帳計算。 |
| META | **OK** | Stock Analysis | 八季 22 項相同、兩項有 SEC 全年減九個月的申報精度解釋；保留 SEC 計算值，不再用公司 IR 單季值替換。 |
| DIS | **OK** | Stock Analysis | 八季三分類，24 個結果全部相同；日期確認為曆季標籤對週六財季，已停用的舊分部空欄有改組依據，保留 N/A。 |
| CMCSA | **OK** | Stock Analysis | 七份 SEC 文件產生八季 16 項：十項相同、兩項 Q4 精度解釋、四項參考期別差異。兩分類在參考的 Q1／Q2 呈相反季度對應，保留 SEC 本季金額；詳見本批裁決。 |
| AMZN | **OK** | Stock Analysis | 八季七分類，56 個結果全部相同；Q4 廣告名稱差異已有程式規則。 |
| TSLA | **OK** | Stock Analysis | 八季三分類，24 個結果全部相同。 |
| HD | **OK** | Stock Analysis | 八季 30 項相同、兩項有公司同年度原表支持的差異解釋：參考前兩季分類加總偏差反向落入 Q4；保留公司原申報計算，不修改參考值。 |
| MCD | **OK** | 富途 | 正常 Edge 已補回 2024 Q3 同一家參考；凍結的 2024 Q3 至 2026 Q2 八季共 24 項全部相同，數字輸出只由 SEC 產生。 |
| WMT | **OK** | 富途 | 八季四分類，32 項全部相同。corporate 改為有原表定義支持的程式殘差：總收入減三部門收入，保留每個運算元，不再人工補值。 |
| COST | **OK** | Stock Analysis | 八季兩分類，16 項全部相同；修正零售財年日期對應，不用最近曆季猜期間。 |
| PG | **OK** | Stock Analysis | 八季 12 項精確相同、35 項有申報／顯示精度解釋、一項依 SEC 原表裁決來源差異；沒有放寬通用容差。 |
| KO | **OK** | Stock Analysis | 八季 57 項收入結果全部相同；固定使用含分部間收入的 gross 口徑及獨立抵銷，七個不再適用的舊欄保留 N/A。 |
| JNJ | **OK** | Stock Analysis | 八季兩分類，16 個結果全部相同；日期確認為曆季標籤對週日財季，分拆後 Consumer Health 空欄保留 N/A。 |
| UNH | **OK** | Stock Analysis | 八季 21 項相同、三項差異有 GAAP／adjusted 口徑理由；數字輸出全部由 SEC facts 產生，公司表只作參考。 |
| LLY | **OK** | Stock Analysis＋公司 PDF | 已補最新季全球五分類參考；目標八季 39 項相同、一項精度解釋，明標為治療領域收入分類。 |
| JPM | **OK** | Stock Analysis | 八季 32 個結果相同；2024 Q3 CIB member 受限接合修復 Q4，保留 managed／FTE 口徑。 |
| BAC | **OK** | Stock Analysis | 八季五分類，40 項全部相同；2025 Q4 依追溯會計方法變更後的九個月比較欄計算，不混用兩套會計版本。 |
| BRK-B | **OK** | 富途＋公司 PDF | 六季 48 項加公司副本兩季 16 項，八季 64 項相同；保險含投資收入，保留公司與抵銷範圍。 |
| PGR | **OK** | 公司 PDF，另保留富途差異 | 八季一致的合併／承保十二列共 96 項相同，主要輸出由 SEC 產生；原富途 Q4 六項差異仍保留，不混加證券總額與組成。 |
| XOM | **OK** | 富途＋公司 PDF | 目標最新季已補公司副本參考；八季 44 項相同、16 項歷史 Q4 有具體差異解釋。gross 與 all-income 範圍及最新季 700 萬差額分開保留。 |
| CVX | **Fail** | 富途 | 已補 2024 Q3，六季 24 項全部相同；仍缺 2025 Q3、2025 Q4 的同口徑收入參考。 |
| CAT | **OK** | Stock Analysis | 八季六分類共 48 項全部相同；最新季直接解析 SEC 8-K 原表，gross 收入及兩組抵銷另由地區表交叉核對，舊分類保留 N/A。 |
| UPS | **OK** | Stock Analysis | 八季 24 項全部相同；歷史資料採 SEC，最新 2026 Q3 由 SEC 8-K 附件擷取，不用公司 PDF 作原始數字。 |
| NEE | **OK** | 富途 | 八季三分類，24 個結果全部相同；歷史 Q4 的法人／分部對應已寫成限定規則。 |
| LIN | **OK** | Stock Analysis | 八季五分類，40 個結果全部相同。 |
| PLD | **OK** | 公司 IR | 既有八季參考與 SEC 輸出 32 項相同；三個合併收入列及總額，不當作完整營運分部揭露。 |

## CVX 那句話實際代表什麼

「八筆運算相同、兩筆 Q4 缺運算元」是在數個欄位計算上得到的局部結果，不能表示八季通過。CVX（Chevron）先前只取得富途五季參考，且 Q4 四項計算未完成；本輪已修好 Q4，所以現在是 **CVX Fail：目前六季 24 項全部相同，但仍缺 2025 Q3、2025 Q4 參考。** 詳見 [Q4 修復收據](../../research/chevron-q4-repair-20261104/CVX-status.json)。

後續已用正常 Edge 核實三家參考入口，仍未補齊兩季收入；SEC 八季 32 項重播成功，六季參考 24 項再次相同，完成數維持 29 / 30。各網站的具體結果及公開副本限制見 [CVX 最後缺口核查](cvx-reference-followup.md)。

另外已完成 [CVX net 共源核對](cvx-net-scope-check.md)：Q3／Q4 八個抵銷後地區收入與雲端回報相同，年度副本六欄也相同。這與原 gross 四分類不同，且不是獨立季度驗證，CVX 仍保留 Fail。

## 程式與驗證位置

- 三十家公司分類規則：[cohort_rule_catalog.py](../../scripts/cohort_rule_catalog.py)。共同抽取／季度計算基礎在 [recovered-sec](../../research/recovered-sec/)，本輪重播入口為 [cohort_rule_audit.py](../../scripts/cohort_rule_audit.py)。已完成公司共用引擎及各自規則，沒有為每家複製一份引擎。
- 第一版 6 / 30 的 OK／Fail 判定程式：[evaluate_eight_quarter_status.py](../../scripts/evaluate_eight_quarter_status.py)；[完整判定結果](../../research/cohort-rule-replay-20261104/eight-quarter-status.json) 含逐公司八季日期、欄位結果計數、固定來源及本機完整結果檔雜湊。
- 完整逐筆金額、原始 SEC facts、Q4 運算元和參考差額仍在本機 `data/vendor/local/cohort-adjudication-20261104/cohort-rule-replay-20261104/{TICKER}-detailed.json`，未發布第三方原始資料。
- 第一批修復入口：[resolve_parser_failures.py](../../scripts/resolve_parser_failures.py)。它重跑全部三十家公司，再套用有依據的日期／停用分類規則；META 另實際下載並解析公司公開 Q4 發行稿。原有 SEC HTML 未全部重新下載或重剖。
- 最新入口：[adjudicate_cross_source_references.py](../../scripts/adjudicate_cross_source_references.py)；原固定來源重播入口 [complete_reference_gaps.py](../../scripts/complete_reference_gaps.py)，接續 [XOM](../../scripts/evaluate_xom_sec.py)、 [Comcast](../../scripts/evaluate_comcast_sec.py)、 [PGR](../../scripts/evaluate_progressive_sec.py)、[CAT](../../scripts/evaluate_caterpillar_sec.py) 與原 SEC 來源檢查。逐公司本機明細路徑及雜湊以最新收據的 `local_detail_path` 為準，沒有把未改動公司複製成新明細。原始參考金額與顯示日期未改動。
- [本機驗證收據](../../research/cross-source-final-20261104/verification.json)：173 項離線測試通過、30 家基準與原凍結收據通過、30 份逐筆結果及程式／證據雜湊通過。

重做第一批修復與判定（須已有本機來源）：

```sh
data/vendor/local/.venv/bin/python scripts/resolve_parser_failures.py \
  --out /tmp/新的修復實驗 \
  --meta-release data/vendor/local/parser-fixes-20261104/meta-q4-2025-release.html
```

輸出目錄及對應本機結果目錄必須不存在。此步用已下載來源重播並核對訓練收據，不新增網路請求。

更深入的來源裁決見 [三十家公司裁決](cohort-rule-adjudication.md)；前輪四家公司實驗與舊計數保留於 [歷史細節](historical-rule-study-details.md)，不作為目前 OK／Fail 的結論。
