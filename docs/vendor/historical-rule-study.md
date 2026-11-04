# 八季 parser 完成狀態：14 / 30 OK

截至 2026-11-04，依目前已保存資料與程式結果，**OK：AAPL、NVDA、AMZN、TSLA、NEE、LIN、DIS、JNJ、META、ORCL、GOOGL、MSFT、PG、JPM，共 14 家；其餘 16 家 Fail。**

這裡的 OK 表示：每家公司固定選 Stock Analysis、富途或 TradingView 其中一家，八個目標季度的所有參考分類都由現有程式擷取結果加計算產生，期間已確認，而且逐項相同。不要求三家網站互相一致，也不要求三十家公司選同一家。新季度能否泛化不影響本次判定。

第一批 Fail 修復已完成 DIS、JNJ、META；第二批 ORCL、GOOGL、MSFT、PG、JPM 亦已完成，見 [第二批修復與裁決](priority-parser-repairs.md)。[修法、證據及剩餘 21 家處理方式](parser-fail-remediation.md)，[第一批 9 / 30 結果](../../research/parser-fail-resolution-20261104/eight-quarter-status.json)，[最新 14 / 30 結果](../../research/continued-parser-repairs-20261104/completion-status.json)。

若程式與參考不同，可以用公司財報證明差異原因，再明列為可接受例外。目前沒有未解釋的數值差異計入這 14 家；MSFT、PG 各有一項以 SEC 原表裁決來源錯誤，PG 另有可計算的精度解釋；已確認不適用的舊分類空欄保留為 N/A，不補零。精度相容而未完成裁決、人工讀表補值、缺季、缺分類、日期未確認，都先算 Fail。**Fail 代表未達完成標準，可能是缺資料或工作尚未完成，不等於完全無法解析。**

| 公司 | 結論 | 固定參考來源 | 原因 |
|---|---|---|---|
| AAPL | **OK** | Stock Analysis | 八季五分類，40 個結果全部相同。 |
| MSFT | **OK** | Stock Analysis | 八季 22 項相同；一項來源錯誤：SA 將另一分部營業利益填入收入欄，採 SEC 正確收入，詳見裁決。 |
| NVDA | **OK** | Stock Analysis | 八季兩分類，16 個結果全部相同；歷史名稱差異已有程式規則。 |
| ORCL | **OK** | Stock Analysis | 八季 32 個收入結果相同；已限定二／五／八／十一月財季對應網站曆季標籤，新舊四分類依期間處理且合計等於總收入。 |
| GOOGL | **OK** | Stock Analysis | 八季 56 個收入結果相同；以 SEC 分部對帳補避險收入，2025 Q4 優先解析公司直接單季 PDF。 |
| META | **OK** | Stock Analysis | 八季三分類，24 個結果全部相同；Q4 改用程式擷取公司直接披露的單季表，取代有四捨五入差額的全年減九個月。 |
| DIS | **OK** | Stock Analysis | 八季三分類，24 個結果全部相同；日期確認為曆季標籤對週六財季，已停用的舊分部空欄有改組依據，保留 N/A。 |
| CMCSA | **Fail** | Stock Analysis | 已證實 SA 四筆季度標籤錯置，可以解釋來源錯誤；但其餘業務群金額仍靠人工讀表補入，尚不是完整 parser。 |
| AMZN | **OK** | Stock Analysis | 八季七分類，56 個結果全部相同；Q4 廣告名稱差異已有程式規則。 |
| TSLA | **OK** | Stock Analysis | 八季三分類，24 個結果全部相同。 |
| HD | **Fail** | Stock Analysis | 八筆分類結果取不出來，且日期對應尚未確認。 |
| MCD | **Fail** | 富途 | 富途只取得七季，另有一筆 Q4 美國分部收入取不出來。 |
| WMT | **Fail** | 富途 | 八季數字可以對上，但 corporate 收入仍靠人工補表，最新季殘差尚待原表驗證；尚未完成程式化。 |
| COST | **Fail** | Stock Analysis | 只有六個期間能提出對應，且四筆數值不同；財年日期規則未完成。 |
| PG | **OK** | Stock Analysis | 八季 12 項精確相同、35 項有申報／顯示精度解釋、一項依 SEC 原表裁決來源差異；沒有放寬通用容差。 |
| KO | **Fail** | Stock Analysis | 28 筆有多種不同收入口徑、19 筆取不出指定分類，日期也未全部確認。 |
| JNJ | **OK** | Stock Analysis | 八季兩分類，16 個結果全部相同；日期確認為曆季標籤對週日財季，分拆後 Consumer Health 空欄保留 N/A。 |
| UNH | **Fail** | Stock Analysis | 三筆 Optum／抵銷收入不同，尚未完成差異解釋。 |
| LLY | **Fail** | Stock Analysis | 13 筆分類結果取不出來；最新季未重播，目前只有七季參與比較。 |
| JPM | **OK** | Stock Analysis | 八季 32 個結果相同；2024 Q3 CIB member 受限接合修復 Q4，保留 managed／FTE 口徑。 |
| BAC | **Fail** | Stock Analysis | 2025 Q4 有三筆結果不同，尚未裁決。 |
| BRK-B | **Fail** | 富途 | 六季 48 筆相同，但缺兩季參考資料，沒有跑滿八季。 |
| PGR | **Fail** | 富途 | 只取得七季；投資／證券收益規則未完成，另有 Q4 缺漏。 |
| XOM | **Fail** | 富途 | 新舊 CIK 尚未銜接，目前只比較到一季，而且四個分部結果不同。 |
| CVX | **Fail** | 富途 | 只取得五季參考資料，且其中 2024 Q4 四項收入都取不出來；不是八季通過。 |
| CAT | **Fail** | Stock Analysis | 目前只能對照七季，另有兩個歷史分類取不出來及參考空值。 |
| UPS | **Fail** | Stock Analysis | 目前只能對照七季，三筆分類取不出來，另有一筆 Q4 不同。 |
| NEE | **OK** | 富途 | 八季三分類，24 個結果全部相同；歷史 Q4 的法人／分部對應已寫成限定規則。 |
| LIN | **OK** | Stock Analysis | 八季五分類，40 個結果全部相同。 |
| PLD | **Fail** | 公司 IR（原三家缺資料） | 對公司 IR 的八季 32 個結果全部相同；但原本三家網站的八季參考仍缺，因此不計入本次 OK。 |

## CVX 那句話實際代表什麼

「八筆運算相同、兩筆 Q4 缺運算元」是在數個欄位計算上得到的局部結果，不能表示八季通過。CVX（Chevron）目前只取得富途五季參考，其中一季 Q4 的四個分類都沒有完整計算結果。因此結論是 **CVX Fail：缺三季參考，而且 Q4 計算未完成。**

## 程式與驗證位置

- 三十家公司分類規則：[cohort_rule_catalog.py](../../scripts/cohort_rule_catalog.py)。共同抽取／季度計算基礎在 [recovered-sec](../../research/recovered-sec/)，本輪重播入口為 [cohort_rule_audit.py](../../scripts/cohort_rule_audit.py)。目前十四家共用引擎及各自規則，沒有為每家複製一份引擎。
- 第一版 6 / 30 的 OK／Fail 判定程式：[evaluate_eight_quarter_status.py](../../scripts/evaluate_eight_quarter_status.py)；[完整判定結果](../../research/cohort-rule-replay-20261104/eight-quarter-status.json) 含逐公司八季日期、欄位結果計數、固定來源及本機完整結果檔雜湊。
- 完整逐筆金額、原始 SEC facts、Q4 運算元和參考差額仍在本機 `data/vendor/local/cohort-adjudication-20261104/cohort-rule-replay-20261104/{TICKER}-detailed.json`，未發布第三方原始資料。
- 第一批修復入口：[resolve_parser_failures.py](../../scripts/resolve_parser_failures.py)。它重跑全部三十家公司，再套用有依據的日期／停用分類規則；META 另實際下載並解析公司公開 Q4 發行稿。原有 SEC HTML 未全部重新下載或重剖。
- 最新逐筆結果位於本機 `data/vendor/local/cohort-adjudication-20261104/parser-fail-resolution-20261104/{TICKER}-resolved.json`；原始比較列、舊 Q4 推算與新結果均保留，沒有覆寫舊研究。

重做第一批修復與判定（須已有本機來源）：

```sh
data/vendor/local/.venv/bin/python scripts/resolve_parser_failures.py \
  --out /tmp/新的修復實驗 \
  --meta-release data/vendor/local/parser-fixes-20261104/meta-q4-2025-release.html
```

輸出目錄及對應本機結果目錄必須不存在。此步用已下載來源重播並核對訓練收據，不新增網路請求。

更深入的來源裁決見 [三十家公司裁決](cohort-rule-adjudication.md)；前輪四家公司實驗與舊計數保留於 [歷史細節](historical-rule-study-details.md)，不作為目前 OK／Fail 的結論。
