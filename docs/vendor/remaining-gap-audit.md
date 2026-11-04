# 剩餘公司的精確參考缺口

本文件是 PR #23 的歷史盤點；後續 [MCD／CVX 缺季已部分補回](reference-gap-completion.md)，MCD 已 OK、CVX 剩兩季缺參考，最新總數為 24 / 30。

本輪接續 PGR 原始 HTML 工作，核對 main 已保存的 SEC 完成收據與六家凍結基準，沒有讀取或重做 Mac 尚未提交的 XOM。**沒有新增完成公司，仍為 23 / 30。**

查核找到 MCD 的文件期間錯誤：先前說缺最新 2026 Q3，但它目前凍結的八季窗口實際為 2024 Q3 至 2026 Q2；與收據的七個參考日期作差集後，缺的是 2024 Q3。更正文件及未來判定輸出的期間診斷欄，不改寫舊收據，也不擅自移動目標窗口。

| 公司 | 凍結目標窗口 | 真正缺少的目標期參考 | 其他障礙 |
|---|---|---|---|
| MCD | 2024 Q3 至 2026 Q2 | 2024 Q3 | 七季 21 項已由前輪 SEC 結果支持。 |
| LLY | 2024 Q4 至 2026 Q3 | 2026 Q3 | 參考雖有八季，2024 Q3 在窗口外，目標內只有七季。 |
| BRK-B | 2024 Q3 至 2026 Q2 | 2024 Q3、2025 Q3 | 六季 48 項已有前輪 SEC 結果。 |
| PGR | 2024 Q4 至 2026 Q3 | 2026 Q3 | SEC 最新季與原始 HTML 入口已完成，仍須固定富途參考。 |
| CVX | 2024 Q3 至 2026 Q2 | 2024 Q3、2025 Q3、2025 Q4 | 五季 20 項已有前輪 SEC 結果，Q4 scope 修復已完成。 |
| PLD | 2024 Q4 至 2026 Q3 | 沒有缺公司 IR 參考期 | 目前固定來源是公司 IR，仍欠原約定三家之一的完整八季參考；IR 不替代該條件。 |

這是已保存來源的盤點，沒有重新查詢網站，不代表供應商現在仍未更新。所有六家的現有數字在前輪收據中均標為 SEC 運算元已驗證；這次沒有原始財報解析失敗可據以修復，剩下的實際障礙是固定參考的覆蓋。重複下載 SEC 財報不會補出缺少的第三方參考。XOM 的期間與來源缺口留給 Mac 工作，沒有列入本次六家盤點。

雲端沒有被 Git 忽略的六家逐筆參考檔，不能重跑金額裁決。LLY／PLD／PGR 的基準已有 2026 Q3 SEC 候選；MCD／BRK-B／CVX 的凍結基準截至 2026 Q2。本輪沒有向 SEC 或供應商新增請求，沒有宣稱最新申報是否已發布，也沒有重新解析原始 HTML。

[盤點程式](../../scripts/audit_remaining_company_gaps.py) 會驗證各公司基準檔與既有凍結雜湊，確認目標日期等於完成收據，再明列窗口內覆蓋、缺期及窗口外參考。未來 `assess()` 除保留原本全部參考季數外，也輸出 `target_quarters_present`、`missing_target_periods` 與 `reference_periods_outside_target`；判定標準及既有 OK／Fail 不變。

完整日期、來源／程式雜湊及前輪 SEC 查核狀態見 [機器可讀盤點](../../research/remaining-gap-audit-20261104/gap-audit.json)。重跑不需要 Mac 或網路：

```sh
python scripts/audit_remaining_company_gaps.py --out /tmp/remaining-gap-audit.json
python -m unittest discover -s tests -p 'test_*quarter_status.py' -v
python -m unittest discover -s tests -p 'test_remaining_gap_audit.py' -v
```

輸出檔須尚不存在。後續要增加完成數，需正常取得表中缺少的固定來源參考，或先取得另一家完整八季再整組重跑；不能拼接來源、補零、把窗口外舊季算進目標，或把已接觸資料稱為盲測。
