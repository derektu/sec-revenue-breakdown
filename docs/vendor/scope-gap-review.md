# WMT 與 NEE 的範圍缺口查核

2026-11-04 接續四家公司規則實驗，針對前輪 WMT 的 14 筆未判定與 NEE 的一筆未判定查核。
兩家公司最新季度都已接觸；本輪是回溯研究，沒有新增盲測或全揭露準確率。
原始參考值、占比、訓練包與逐筆證據全部留在 `data/vendor/local/`。
本輪判讀由本機 agent 完成，**沒有獨立人工覆核**。

## 實際結果

| 公司 | 原有指定範圍結果 | 本輪結果 | 尚未裁決 |
| --- | --- | --- | --- |
| NEE | 18 筆直接相同、5 筆 Q4 推算相同、1 筆未判定 | 18 筆直接相同、6 筆推算相同 | 新增一筆依賴受限的跨範圍證據；未獨立認證所有重編 |
| WMT | 15 筆直接相同、3 筆 Q4 推算相同、14 筆未判定 | 採截止日前的歷史比較欄後，18 筆直接相同、6 筆推算相同、8 筆未判定 | 八筆公司項目僅得到相同 residual 候選，未認證分類定義 |

NEE 比較八季三個指定分類共 24 筆；WMT 比較八季三個分部及公司項目共 32 筆。
最新回溯期的 NEE 三筆、WMT 三個分部均直接相同，WMT 最新公司項目仍未判定。
這些分母是已取得的指定參考列，不能解讀為公司全部揭露覆蓋或 1,500 家泛化表現。

## WMT：保留原申報與較晚歷史比較欄兩種版本

較舊的季度資料有 `RevenueFromContractWithCustomerExcludingAssessedTax` 的淨銷售及舊分部 member；
參考表採較廣的 `Revenues`，不能只改 member 名稱，就把 net sales 當 total revenues。
原 Q4 的嚴格運算也缺同一 `Revenues` 範圍的九個月 operand，因此棄權是合理行為。

截止日以前的 2025-10-31 申報，包含目標 2024-10-31 季度及九個月的比較欄；
2026-01-31 年報包含目標 2025-01-31 的年度比較欄。
這些資料均在 WMT 訓練申報截止日前，沒有使用最新 2026-07-31 保留申報。
以最新可用歷史比較欄的同概念、完整維度及期間重建，補上六筆舊季度分部數值。

- [2025-10-31 季度申報](https://www.sec.gov/Archives/edgar/data/104169/000010416925000191/wmt-20251031.htm)
- [2026-01-31 年度申報](https://www.sec.gov/Archives/edgar/data/104169/000010416926000055/wmt-20260131.htm)；accession、申報日期、operand 與雜湊保留於 receipt、manifest 及本機逐筆結果。

選擇規則是「截止日前、確實有目標季度 facts 的最新申報」，不按金額是否命中參考值挑版本。
原申報與比較欄結果分別保存；後者可能包含較晚重分類或重編，**不是舊季度當時的 point-in-time 資料**。
可支持目前研究參考的口徑，不能倒推原 parser 在舊季度當時本來就能取得相同資訊。

公司項目另算合併 `Revenues` 減三個指定範圍的分部 `Revenues`。
原申報有六期運算元齊全，比較欄版本八期齊全，八個 residual 均與已保存參考值相同。
但此差額可能涵蓋未辨明的公司、其他或抵銷項目，數字相同不證明參考分類的定義。
程式明確標記 `arithmetic_candidate_definition_unverified`，不改成直接揭露，也不把「分部＋餘額＝總額」
這種依構造必然成立的等式計為獨立驗證成功。缺任一分部時不補零、不用 net sales 替代。

## NEE：受限的 FPL 範圍接合與 Q4

[2024 年報](https://www.sec.gov/Archives/edgar/data/753308/000075330825000011/nee-20241231.htm)
的分部資訊，與 [2024 Q3](https://www.sec.gov/Archives/edgar/data/753308/000075330824000057/nee-20240930.htm)
的分部表，均列 FPL 與 NEER，並把公司及抵銷另列；年度亦說明 FPL 僅一個報導分部。
Q3 的 FPL 分部表同時給出三個月及九個月數字，與其單獨法人報表對應。

已保存 facts 的年度 FPL 有法人軸、營運分部軸及 OperatingSegments 範圍；九個月只有 FPL 法人軸。
精確維度相減因而棄權。本輪不是把所有法人軸視為分部，而是依上述**兩份指定申報的同名分部表**，
只接合 2024-01-01 至 2024-12-31 的年度與 2024-01-01 至 2024-09-30 的九個月，
產生 2024-10-01 至 2024-12-31 的一個推算值。

保留兩個 operand 的原始維度、來源與 context，另加 scope bridge 規則 ID；原基準與 parser 不變。
錯概念、錯期間、缺 operand、不同完整範圍或衝突值均棄權，沒有通用移除維度或名稱模糊匹配。
該推算與已保存富途 FPL 值相同，並標為 `needs_derivation`；不能稱直接申報或獨立人工認證。
最新季度不需此歷史接合，原三筆直接相同比較不變。

## 來源取得的實際限制

本機以既有單檔 SEC 工具、真實專案及公開 GitHub 聯絡頁，向
`https://www.sec.gov/Archives/edgar/data/104169/000010416926000154/wmt-20260731.htm`
發送一次 GET，回傳 HTTP 403。未重試，原排定的後續原始 HTML 下載未執行，也沒有取得該檔 bytes。
這是 SEC 回應，並非自動核准審查拒絕；不能泛化為所有 SEC 或已登入 vendor 頁面不可讀。

NEE 的兩份不同歷史申報另以正常公開網頁文字閱讀成功，用於本輪範圍判讀；這不等於取得原始 HTML，
也沒有重新驗證其 HTML 雜湊。本輪程式使用既有凍結基準的 facts；本機有的檔案雜湊與原來源 manifest 分開記錄。
仍需原始 HTML 或更多概念的 WMT 公司項目調查保持未完成，未繞過存取限制。

## 重現與協調

```sh
data/vendor/local/.venv/bin/python scripts/review_scope_gaps.py \
  --out /tmp/scope-gap-review-new
```

選新的輸出目錄。本機逐筆結果另寫入 `data/vendor/local/scope-gaps-20261104/` 的同名目錄，不覆寫既有產物。
repo 的 [`scope-gap-review-20261104`](../../research/scope-gap-review-20261104/) 保存兩份 temporal receipts、
計數與程式／輸入雜湊；wrapper 的比較欄選擇、跨範圍推算與 residual 不由未修改的 temporal replay 自動執行，
須使用此 wrapper 並核對其及相依程式雜湊。NEE 額外運算只用歷史 training pack；WMT 最新期仍由原保留申報執行回溯。

前輪四家公司及完整三十家現況見 [歷史規則研究](historical-rule-study.md)；本輪只新增 WMT 與 NEE 查核，
其餘 28 家沒有冒稱重新執行。TradingView 完整季度／年度明細、八筆 WMT 公司項目定義、
其他公司既有差異與真正未見季度實驗仍待研究。

驗證：50 個測試通過，10 個來源 manifest 檔案、兩份 receipt、wrapper／相依程式及原始參考雜湊通過；
原始參考資料受 Git 忽略，公開 JSON 不含原始 vendor 欄位。
逐公司最新狀態見 [`cohort-status.json`](../../research/scope-gap-review-20261104/cohort-status.json)。
