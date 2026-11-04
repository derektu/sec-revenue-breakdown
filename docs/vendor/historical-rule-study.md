# 八季 parser 完成狀態：20 / 30 OK

截至 2026-11-04，依目前已保存資料與程式結果，**OK：AAPL、NVDA、AMZN、TSLA、NEE、LIN、DIS、JNJ、META、ORCL、GOOGL、MSFT、PG、JPM，另加 COST、KO、WMT、BAC、UNH、UPS，共 20 家；其餘 10 家 Fail。**

這裡的 OK 表示：每家公司固定選 Stock Analysis、富途或 TradingView 其中一家，八個目標季度的所有參考分類都由現有程式擷取結果加計算產生，期間已確認，而且逐項相同。不要求三家網站互相一致，也不要求三十家公司選同一家。新季度能否泛化不影響本次判定。

第一批 Fail 修復已完成 DIS、JNJ、META；第二批 ORCL、GOOGL、MSFT、PG、JPM 亦已完成，見 [第二批修復與裁決](priority-parser-repairs.md)。[修法、證據及剩餘 21 家處理方式](parser-fail-remediation.md)，[第一批 9 / 30 結果](../../research/parser-fail-resolution-20261104/eight-quarter-status.json)，[前批 14 / 30 結果](../../research/continued-parser-repairs-20261104/completion-status.json)。本批新增六家，見 [本批修復及剩餘十家](remaining-parser-repairs.md) 與 [最新 20 / 30 結果](../../research/completed-parser-repairs-20261104/extended-completion-status.json)。

若程式與參考不同，可以用公司財報證明差異原因，再明列為可接受例外。目前沒有未解釋的數值差異計入這 20 家；MSFT、PG 各有一項以 SEC 原表裁決來源錯誤，PG 另有可計算的精度解釋；UNH 三項差異依公司同表的 GAAP／adjusted 分別裁決；已確認不適用的舊分類空欄保留為 N/A，不補零。精度相容而未完成裁決、人工讀表補值、缺季、缺分類、日期未確認，都先算 Fail。**Fail 代表未達完成標準，可能是缺資料或工作尚未完成，不等於完全無法解析。**

| 公司 | 結論 | 固定參考來源 | 原因 |
|---|---|---|---|
| AAPL | **OK** | Stock Analysis | 八季五分類，40 個結果全部相同。 |
| MSFT | **OK** | Stock Analysis | 八季 22 項相同；一項來源錯誤：SA 將另一分部營業利益填入收入欄，採 SEC 正確收入，詳見裁決。 |
| NVDA | **OK** | Stock Analysis | 八季兩分類，16 個結果全部相同；歷史名稱差異已有程式規則。 |
| ORCL | **OK** | Stock Analysis | 八季 32 個收入結果相同；已限定二／五／八／十一月財季對應網站曆季標籤，新舊四分類依期間處理且合計等於總收入。 |
| GOOGL | **OK** | Stock Analysis | 八季 56 個收入結果相同；以 SEC 分部對帳補避險收入，2025 Q4 優先解析公司直接單季 PDF。 |
| META | **OK** | Stock Analysis | 八季三分類，24 個結果全部相同；Q4 改用程式擷取公司直接披露的單季表，取代有四捨五入差額的全年減九個月。 |
| DIS | **OK** | Stock Analysis | 八季三分類，24 個結果全部相同；日期確認為曆季標籤對週六財季，已停用的舊分部空欄有改組依據，保留 N/A。 |
| CMCSA | **Fail** | Stock Analysis | 已改成程式解析兩份完整 HTML，涵蓋三個目標季度；其餘五季原表未取得，仍不是完整八季 parser。 |
| AMZN | **OK** | Stock Analysis | 八季七分類，56 個結果全部相同；Q4 廣告名稱差異已有程式規則。 |
| TSLA | **OK** | Stock Analysis | 八季三分類，24 個結果全部相同。 |
| HD | **Fail** | Stock Analysis | 八季 32 項均能產出；30 項相同，2024 Q4 的 Hardlines／Other 仍有相反方向各 4.60 億美元差異。嘗試後期重分類比較欄仍不符，尚不能裁決來源錯誤。 |
| MCD | **Fail** | 富途 | 已修復 Q4 美國分部名稱，取得的七季 21 項全部相同；富途保存資料缺 2026 Q3，仍未完成目標八季。 |
| WMT | **OK** | 富途 | 八季四分類，32 項全部相同。corporate 改為有原表定義支持的程式殘差：總收入減三部門收入，保留每個運算元，不再人工補值。 |
| COST | **OK** | Stock Analysis | 八季兩分類，16 項全部相同；修正零售財年日期對應，不用最近曆季猜期間。 |
| PG | **OK** | Stock Analysis | 八季 12 項精確相同、35 項有申報／顯示精度解釋、一項依 SEC 原表裁決來源差異；沒有放寬通用容差。 |
| KO | **OK** | Stock Analysis | 八季 57 項收入結果全部相同；固定使用含分部間收入的 gross 口徑及獨立抵銷，七個不再適用的舊欄保留 N/A。 |
| JNJ | **OK** | Stock Analysis | 八季兩分類，16 個結果全部相同；日期確認為曆季標籤對週日財季，分拆後 Consumer Health 空欄保留 N/A。 |
| UNH | **OK** | Stock Analysis | 八季 21 項相同；三項差異有公司原表支持：參考採 adjusted Optum，另有混用 GAAP／adjusted 的抵銷。程式固定輸出一致 GAAP，逐筆記錄理由。 |
| LLY | **Fail** | Stock Analysis | 已修復全球產品合計，保存的八季有 39 項相同、一項精度解釋；但這是較舊八季，缺目標最新 2026 Q3，不能算目標八季通過。 |
| JPM | **OK** | Stock Analysis | 八季 32 個結果相同；2024 Q3 CIB member 受限接合修復 Q4，保留 managed／FTE 口徑。 |
| BAC | **OK** | Stock Analysis | 八季五分類，40 項全部相同；2025 Q4 依追溯會計方法變更後的九個月比較欄計算，不混用兩套會計版本。 |
| BRK-B | **Fail** | 富途 | 六季 48 筆相同，但缺兩季參考資料，沒有跑滿八季。 |
| PGR | **Fail** | 富途 | 只取得七季；投資／證券收益規則未完成，另有 Q4 缺漏。 |
| XOM | **Fail** | 富途 | 已修正 gross／抵銷規則，唯一對齊季度五項全部相同；舊 CIK 歷史申報尚缺，正常 SEC 請求回 403，未重試或繞過。 |
| CVX | **Fail** | 富途 | 取得的五季二十項已全部相同，2024 Q4 四項已修復；仍缺三季同一家參考，因此 Fail。 |
| CAT | **Fail** | Stock Analysis | 七季 42 項全部相同，歷史兩項缺漏已修好；仍缺最新 2026 Q3 原表。PDF 請求逾時，斷線前瀏覽器下載未確認；另一次正常 SEC 發行稿請求回 403，已停止。 |
| UPS | **OK** | Stock Analysis | 八季三分類，24 項全部相同；修復分類轉移與 Q4 重編比較欄，以公司 Q3 PDF 程式擷取補入最新季。 |
| NEE | **OK** | 富途 | 八季三分類，24 個結果全部相同；歷史 Q4 的法人／分部對應已寫成限定規則。 |
| LIN | **OK** | Stock Analysis | 八季五分類，40 個結果全部相同。 |
| PLD | **Fail** | 公司 IR（原三家缺資料） | 對公司 IR 的八季 32 個結果全部相同；但原本三家網站的八季參考仍缺，因此不計入本次 OK。 |

## CVX 那句話實際代表什麼

「八筆運算相同、兩筆 Q4 缺運算元」是在數個欄位計算上得到的局部結果，不能表示八季通過。CVX（Chevron）先前只取得富途五季參考，且 Q4 四項計算未完成；本輪已修好 Q4，所以現在是 **CVX Fail：取得的五季二十項全部相同，但仍缺三季參考。** 詳見 [Q4 修復收據](../../research/chevron-q4-repair-20261104/CVX-status.json)。

## 程式與驗證位置

- 三十家公司分類規則：[cohort_rule_catalog.py](../../scripts/cohort_rule_catalog.py)。共同抽取／季度計算基礎在 [recovered-sec](../../research/recovered-sec/)，本輪重播入口為 [cohort_rule_audit.py](../../scripts/cohort_rule_audit.py)。目前二十家共用引擎及各自規則，沒有為每家複製一份引擎。
- 第一版 6 / 30 的 OK／Fail 判定程式：[evaluate_eight_quarter_status.py](../../scripts/evaluate_eight_quarter_status.py)；[完整判定結果](../../research/cohort-rule-replay-20261104/eight-quarter-status.json) 含逐公司八季日期、欄位結果計數、固定來源及本機完整結果檔雜湊。
- 完整逐筆金額、原始 SEC facts、Q4 運算元和參考差額仍在本機 `data/vendor/local/cohort-adjudication-20261104/cohort-rule-replay-20261104/{TICKER}-detailed.json`，未發布第三方原始資料。
- 第一批修復入口：[resolve_parser_failures.py](../../scripts/resolve_parser_failures.py)。它重跑全部三十家公司，再套用有依據的日期／停用分類規則；META 另實際下載並解析公司公開 Q4 發行稿。原有 SEC HTML 未全部重新下載或重剖。
- 最新入口：[extend_issuer_repairs.py](../../scripts/extend_issuer_repairs.py)；最新逐筆結果位於本機 `data/vendor/local/cohort-adjudication-20261104/completed-parser-repairs-20261104/{TICKER}-extended.json`。原始比較列、舊 Q4 推算與新結果均保留；原始參考金額與顯示日期未改動。
- [本機驗證收據](../../research/completed-parser-repairs-20261104/local-verification.json)：111 項離線測試通過、30 家基準與原凍結收據通過、30 份逐筆結果及程式／證據雜湊通過。

重做第一批修復與判定（須已有本機來源）：

```sh
data/vendor/local/.venv/bin/python scripts/resolve_parser_failures.py \
  --out /tmp/新的修復實驗 \
  --meta-release data/vendor/local/parser-fixes-20261104/meta-q4-2025-release.html
```

輸出目錄及對應本機結果目錄必須不存在。此步用已下載來源重播並核對訓練收據，不新增網路請求。

更深入的來源裁決見 [三十家公司裁決](cohort-rule-adjudication.md)；前輪四家公司實驗與舊計數保留於 [歷史細節](historical-rule-study-details.md)，不作為目前 OK／Fail 的結論。
