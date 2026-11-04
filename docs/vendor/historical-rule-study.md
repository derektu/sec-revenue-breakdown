# 八季 parser 完成狀態：23 / 30 OK

截至 2026-11-04，依目前 SEC 擷取、計算與來源檢查，**OK：AAPL、MSFT、NVDA、ORCL、GOOGL、META、DIS、AMZN、TSLA、HD、WMT、COST、PG、KO、JNJ、UNH、JPM、BAC、UPS、NEE、LIN、CAT、CMCSA，共 23 家；其餘 7 家 Fail。**

**原始數字的擷取與計算只用 SEC 申報文件（含 8-K 附件）；公司 IR 與其他網站只作參考。** 最新 [SEC 來源檢查](../../research/comcast-sec-repair-20261104/completion-status.json) 及 [來源規則與修正](sec-primary-source-policy.md) 已涵蓋全部三十家。

這裡的 OK 表示：每家公司固定選 Stock Analysis、富途或 TradingView 其中一家，八個目標季度的所有參考分類都由現有程式擷取結果加計算產生，期間已確認，而且逐項相同，或有公司原表支持的具體差異解釋。不要求三家網站互相一致，也不要求三十家公司選同一家。新季度能否泛化不影響本次判定。

最新 CAT、Comcast、PGR 修復與剩餘缺口見 [本批 SEC 修復](sec-remaining-company-repairs.md)。現行來源規則、實際修正與重跑方式見 [SEC 原始來源檢查](sec-primary-source-policy.md)。修復歷程另保留於 [前批修復](remaining-parser-repairs.md)、[五家優先修復](priority-parser-repairs.md) 與 [剩餘公司續查](remaining-company-resolution.md)；舊收據與公司 IR 實驗不代表目前完成標準。

雲端另完成 [PGR 原始 HTML 重跑與 Q4 期間檢查](progressive-sec-html.md)：保存五份 SEC 原始文件，204 筆 facts 與既有 DOM 結果相同；未新增供應商參考季，PGR 仍 Fail，完成數維持 23 / 30。

[剩餘六家精確缺季盤點](remaining-gap-audit.md) 已核對收據與凍結基準：MCD 的目標窗口截至 2026 Q2，實際缺 2024 Q3 參考；先前寫成缺目標 2026 Q3 是文件錯誤。未改動凍結窗口或舊收據。

若程式與參考不同，可以用公司財報證明差異原因，再明列為可接受例外。目前沒有未解釋的數值差異計入這 23 家；MSFT、PG 各有一項以 SEC 原表裁決來源錯誤，PG、META、GOOGL 另有可計算的 SEC 申報精度解釋；UNH 三項差異依公司同表的 GAAP／adjusted 分別裁決；HD 兩項採公司原申報同口徑，另有完整年度與季間加總證據；已確認不適用的舊分類空欄保留為 N/A，不補零。精度相容而未完成裁決、人工讀表補值、缺季、缺分類、日期未確認，都先算 Fail。**Fail 代表未達完成標準，可能是缺資料或工作尚未完成，不等於完全無法解析。**

| 公司 | 結論 | 固定參考來源 | 原因 |
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
| MCD | **Fail** | 富途 | 已修復 Q4 美國分部名稱，取得的七季 21 項全部相同；目前凍結窗口為 2024 Q3 至 2026 Q2，缺 2024 Q3 參考，仍未完成目標八季。 |
| WMT | **OK** | 富途 | 八季四分類，32 項全部相同。corporate 改為有原表定義支持的程式殘差：總收入減三部門收入，保留每個運算元，不再人工補值。 |
| COST | **OK** | Stock Analysis | 八季兩分類，16 項全部相同；修正零售財年日期對應，不用最近曆季猜期間。 |
| PG | **OK** | Stock Analysis | 八季 12 項精確相同、35 項有申報／顯示精度解釋、一項依 SEC 原表裁決來源差異；沒有放寬通用容差。 |
| KO | **OK** | Stock Analysis | 八季 57 項收入結果全部相同；固定使用含分部間收入的 gross 口徑及獨立抵銷，七個不再適用的舊欄保留 N/A。 |
| JNJ | **OK** | Stock Analysis | 八季兩分類，16 個結果全部相同；日期確認為曆季標籤對週日財季，分拆後 Consumer Health 空欄保留 N/A。 |
| UNH | **OK** | Stock Analysis | 八季 21 項相同、三項差異有 GAAP／adjusted 口徑理由；數字輸出全部由 SEC facts 產生，公司表只作參考。 |
| LLY | **Fail** | Stock Analysis | 已修復全球產品合計，保存的八季有 39 項相同、一項精度解釋；但這是較舊八季，缺目標最新 2026 Q3，不能算目標八季通過。 |
| JPM | **OK** | Stock Analysis | 八季 32 個結果相同；2024 Q3 CIB member 受限接合修復 Q4，保留 managed／FTE 口徑。 |
| BAC | **OK** | Stock Analysis | 八季五分類，40 項全部相同；2025 Q4 依追溯會計方法變更後的九個月比較欄計算，不混用兩套會計版本。 |
| BRK-B | **Fail** | 富途 | 六季 48 筆相同，但缺兩季參考資料，沒有跑滿八季。 |
| PGR | **Fail** | 富途 | 五份 SEC 原表已解析，七季 43 項相同、六項 Q4 參考計算差異有證據；最新季 SEC 已擷取，但仍缺富途 2026 Q3 參考，未滿目標八季。 |
| XOM | **Fail** | 富途 | 已修正 gross／抵銷規則，唯一對齊季度五項全部相同；舊 CIK 歷史申報尚缺，正常 SEC 請求回 403，未重試或繞過。 |
| CVX | **Fail** | 富途 | 取得的五季二十項已全部相同，2024 Q4 四項已修復；仍缺三季同一家參考，因此 Fail。 |
| CAT | **OK** | Stock Analysis | 八季六分類共 48 項全部相同；最新季直接解析 SEC 8-K 原表，gross 收入及兩組抵銷另由地區表交叉核對，舊分類保留 N/A。 |
| UPS | **OK** | Stock Analysis | 八季 24 項全部相同；歷史資料採 SEC，最新 2026 Q3 由 SEC 8-K 附件擷取，不用公司 PDF 作原始數字。 |
| NEE | **OK** | 富途 | 八季三分類，24 個結果全部相同；歷史 Q4 的法人／分部對應已寫成限定規則。 |
| LIN | **OK** | Stock Analysis | 八季五分類，40 個結果全部相同。 |
| PLD | **Fail** | 公司 IR（原三家缺資料） | 對公司 IR 的八季 32 個結果全部相同；但原本三家網站的八季參考仍缺，因此不計入本次 OK。 |

## CVX 那句話實際代表什麼

「八筆運算相同、兩筆 Q4 缺運算元」是在數個欄位計算上得到的局部結果，不能表示八季通過。CVX（Chevron）先前只取得富途五季參考，且 Q4 四項計算未完成；本輪已修好 Q4，所以現在是 **CVX Fail：取得的五季二十項全部相同，但仍缺三季參考。** 詳見 [Q4 修復收據](../../research/chevron-q4-repair-20261104/CVX-status.json)。

## 程式與驗證位置

- 三十家公司分類規則：[cohort_rule_catalog.py](../../scripts/cohort_rule_catalog.py)。共同抽取／季度計算基礎在 [recovered-sec](../../research/recovered-sec/)，本輪重播入口為 [cohort_rule_audit.py](../../scripts/cohort_rule_audit.py)。目前二十三家共用引擎及各自規則，沒有為每家複製一份引擎。
- 第一版 6 / 30 的 OK／Fail 判定程式：[evaluate_eight_quarter_status.py](../../scripts/evaluate_eight_quarter_status.py)；[完整判定結果](../../research/cohort-rule-replay-20261104/eight-quarter-status.json) 含逐公司八季日期、欄位結果計數、固定來源及本機完整結果檔雜湊。
- 完整逐筆金額、原始 SEC facts、Q4 運算元和參考差額仍在本機 `data/vendor/local/cohort-adjudication-20261104/cohort-rule-replay-20261104/{TICKER}-detailed.json`，未發布第三方原始資料。
- 第一批修復入口：[resolve_parser_failures.py](../../scripts/resolve_parser_failures.py)。它重跑全部三十家公司，再套用有依據的日期／停用分類規則；META 另實際下載並解析公司公開 Q4 發行稿。原有 SEC HTML 未全部重新下載或重剖。
- 最新入口：[evaluate_comcast_sec.py](../../scripts/evaluate_comcast_sec.py)，串接 [PGR](../../scripts/evaluate_progressive_sec.py)、[CAT](../../scripts/evaluate_caterpillar_sec.py) 與原 SEC 來源檢查。逐公司本機明細路徑及雜湊以最新收據的 `local_detail_path` 為準，沒有把未改動公司複製成新明細。原始參考金額與顯示日期未改動。
- [本機驗證收據](../../research/comcast-sec-repair-20261104/local-verification.json)：140 項離線測試通過、30 家基準與原凍結收據通過、30 份逐筆結果及程式／證據雜湊通過。

重做第一批修復與判定（須已有本機來源）：

```sh
data/vendor/local/.venv/bin/python scripts/resolve_parser_failures.py \
  --out /tmp/新的修復實驗 \
  --meta-release data/vendor/local/parser-fixes-20261104/meta-q4-2025-release.html
```

輸出目錄及對應本機結果目錄必須不存在。此步用已下載來源重播並核對訓練收據，不新增網路請求。

更深入的來源裁決見 [三十家公司裁決](cohort-rule-adjudication.md)；前輪四家公司實驗與舊計數保留於 [歷史細節](historical-rule-study-details.md)，不作為目前 OK／Fail 的結論。
