# 八季 parser 完成狀態：6 / 30 OK

截至 2026-11-04，依目前已保存資料與程式結果，**OK：AAPL、NVDA、AMZN、TSLA、NEE、LIN，共 6 家；其餘 24 家 Fail。**

這裡的 OK 表示：每家公司固定選 Stock Analysis、富途或 TradingView 其中一家，八個目標季度的所有參考分類都由現有程式擷取結果加計算產生，期間已確認，而且逐項相同。不要求三家網站互相一致，也不要求三十家公司選同一家。新季度能否泛化不影響本次判定。

若程式與參考不同，可以用公司財報證明差異原因，再明列為可接受例外。目前尚未把任何例外計入這 6 家：精度相容而未完成裁決、人工讀表補值、缺季、缺分類、日期未確認，都先算 Fail。**Fail 代表未達完成標準，可能是缺資料或工作尚未完成，不等於完全無法解析。**

| 公司 | 結論 | 固定參考來源 | 原因 |
|---|---|---|---|
| AAPL | **OK** | Stock Analysis | 八季五分類，40 個結果全部相同。 |
| MSFT | **Fail** | Stock Analysis | 一筆收入不同尚未解釋，另有參考欄位空值；尚未完成八季分類確認。 |
| NVDA | **OK** | Stock Analysis | 八季兩分類，16 個結果全部相同；歷史名稱差異已有程式規則。 |
| ORCL | **Fail** | Stock Analysis | 數值候選相同，但八季日期對應尚未確認，另有新舊分類空值，不能判 OK。 |
| GOOGL | **Fail** | Stock Analysis | 兩個歷史避險收入結果取不出來，另有一筆僅精度相容及空值。 |
| META | **Fail** | Stock Analysis | 2025 Q4 廣告與其他收入各差 100 萬美元；可能是全年減九個月的四捨五入，但尚未完成裁決，先不算 OK。 |
| DIS | **Fail** | Stock Analysis | 八季數值候選相同，但網站日期與實際財季的對應尚未確認，另有分類空值。 |
| CMCSA | **Fail** | Stock Analysis | 已證實 SA 四筆季度標籤錯置，可以解釋來源錯誤；但其餘業務群金額仍靠人工讀表補入，尚不是完整 parser。 |
| AMZN | **OK** | Stock Analysis | 八季七分類，56 個結果全部相同；Q4 廣告名稱差異已有程式規則。 |
| TSLA | **OK** | Stock Analysis | 八季三分類，24 個結果全部相同。 |
| HD | **Fail** | Stock Analysis | 八筆分類結果取不出來，且日期對應尚未確認。 |
| MCD | **Fail** | 富途 | 富途只取得七季，另有一筆 Q4 美國分部收入取不出來。 |
| WMT | **Fail** | 富途 | 八季數字可以對上，但 corporate 收入仍靠人工補表，最新季殘差尚待原表驗證；尚未完成程式化。 |
| COST | **Fail** | Stock Analysis | 只有六個期間能提出對應，且四筆數值不同；財年日期規則未完成。 |
| PG | **Fail** | Stock Analysis | 一筆數值不同尚未裁決，其餘多筆也僅精度相容。 |
| KO | **Fail** | Stock Analysis | 28 筆有多種不同收入口徑、19 筆取不出指定分類，日期也未全部確認。 |
| JNJ | **Fail** | Stock Analysis | 16 個數值候選相同，但八季日期對應尚未確認，另有分類空值。 |
| UNH | **Fail** | Stock Analysis | 三筆 Optum／抵銷收入不同，尚未完成差異解釋。 |
| LLY | **Fail** | Stock Analysis | 13 筆分類結果取不出來；最新季未重播，目前只有七季參與比較。 |
| JPM | **Fail** | Stock Analysis | 2024 Q4 的 Commercial and Investment Bank 收入取不出來，另有參考空值。 |
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

- 三十家公司分類規則：[cohort_rule_catalog.py](../../scripts/cohort_rule_catalog.py)。共同抽取／季度計算基礎在 [recovered-sec](../../research/recovered-sec/)，本輪重播入口為 [cohort_rule_audit.py](../../scripts/cohort_rule_audit.py)。目前六家共用引擎及各自規則，沒有為每家複製一份引擎。
- OK／Fail 判定程式：[evaluate_eight_quarter_status.py](../../scripts/evaluate_eight_quarter_status.py)；[完整判定結果](../../research/cohort-rule-replay-20261104/eight-quarter-status.json) 含逐公司八季日期、欄位結果計數、固定來源及本機完整結果檔雜湊。
- 完整逐筆金額、原始 SEC facts、Q4 運算元和參考差額仍在本機 `data/vendor/local/cohort-adjudication-20261104/cohort-rule-replay-20261104/{TICKER}-detailed.json`，未發布第三方原始資料。
- 本次重新判定使用已保存的抽取結果，沒有重新下載／重剖所有原始 HTML；這個限制不以八季數值一致掩蓋。

重做判定：

```sh
data/vendor/local/.venv/bin/python scripts/evaluate_eight_quarter_status.py --out /tmp/新的判定結果.json
```

輸出路徑必須不存在。此步只讀既有結果並核對訓練收據，不新增網路請求。

更深入的來源裁決見 [三十家公司裁決](cohort-rule-adjudication.md)；前輪四家公司實驗與舊計數保留於 [歷史細節](historical-rule-study-details.md)，不作為目前 OK／Fail 的結論。
