# CVX net 共源核對：八項相同，完成數維持 29 / 30

雲端補充兩份公司申報 PDF 與 net 數字後，本機用既有凍結 SEC facts 實際擷取 2025 Q3、推算 Q4。**八個 net 數字均與雲端回報相同，但 CVX 仍是 Fail。** 它們與原富途 gross 四分類不同，且公司 PDF、年度研究頁明確共用 SEC 申報上游，不能稱獨立季度驗證。[SEC 輸出及全部運算元](../../research/cvx-net-scope-20261104/SEC-net-check.json) 與 [驗證收據](../../research/cvx-net-scope-20261104/verification.json) 分開保存，沒有修改前輪完成數。

## 本機實際擷取的 SEC net 數字

單位為百萬美元。net 是抵銷後的 Sales and Other Operating Revenues，不包含投資及其他收益，也不是 earnings。

| 期間 | 上游美國 | 上游國際 | 下游美國 | 下游國際 | All Other net | 合併 sales |
|---|---:|---:|---:|---:|---:|---:|
| 2025 Q3 | 5,623 | 9,542 | 16,587 | 16,393 | 24 | 48,169 |
| 2025 Q4 | 5,518 | 9,280 | 15,120 | 15,838 | 31 | 45,787 |

Q3 由 [SEC 10-Q](https://www.sec.gov/Archives/edgar/data/93410/000009341025000108/cvx-20250930.htm) 的單季欄取得。Q4 每一列都用 [SEC 10-K](https://www.sec.gov/Archives/edgar/data/93410/000009341026000078/cvx-20251231.htm) 同 scope 全年減上述 10-Q 九個月欄；四個地區數字、All Other 與總額均有完整運算元。例如上游美國為 19,608 − 14,090 = 5,518，下游國際為 65,545 − 49,707 = 15,838。四列加 All Other 等於合併 sales，沒有把空值當零。

新入口 [check_cvx_net_scope.py](../../scripts/check_cvx_net_scope.py) 依完整分類選值：四個 net 地區列的 scope 沒有 `ConsolidationItemsAxis`；原 gross 列另含 `OperatingSegmentsMember`。即使 concept 相同，兩者也不互相替換。缺任何 net 列、來源不是 SEC 或合併對帳不一致，程式會拒絕。

## 與原 gross 測試的差別

同樣單位為百萬美元；以下仍是 SEC 輸出，沒有從參考補值。

| 期間 | 上游 gross | 下游 gross | 所有其他 gross | 全體收入抵銷 | 合併 sales |
|---|---:|---:|---:|---:|---:|
| 2025 Q3 | 24,279 | 35,717 | 136 | −11,963 | 48,169 |
| 2025 Q4 | 23,047 | 33,740 | 176 | −11,176 | 45,787 |

原本欠參考的四類是「上游、下游、所有其他、部門間收入抵銷」，不是上方四個 net 地區列。不能用四個數字的數量恰好相同，就說原 gross 分類已核對完成；也不能在 net 再減一次抵銷。

## 參考取得與來源關係

- [公司 2025 Q3 10-Q 副本](https://chevroncorp.gcs-web.com/static-files/ec8ded16-05aa-4f92-9bc3-3f6b3a257f4d)：先前正常直接下載已回 403，本輪沒有再請求。本機八個單季參考值是雲端回報的共源數字，明標未在本機重新解析 Q3 公司 PDF bytes；不是新增獨立參考。
- [公司 2025 10-K 副本](https://chevroncorp.gcs-web.com/static-files/6beae4d6-142e-4a4d-bee9-1714cad041a3)：這個新網址以正常工具成功讀取。第 83 個 PDF 頁面的年度表同時有 gross、抵銷及 net；保存的是有行號的工具文字摘錄，未宣稱已取得 PDF bytes。本機另核對年度六個 net 欄與 SEC，全部相同。
- [Synthos 的年度分析](https://synthosresearch.com/CVX)：可讀，其資料檢查段明示使用同一份 10-K 表格，並列出抵銷後上游 53,452、下游 130,876、All Other 104，合計 184,432。這是另一網站的年度呈現，但不是另一獨立上游，也沒有直接提供兩個缺季的四分類 gross 參考。

參考文字、雲端回報原值與來源觀察留在 Git 忽略的本機目錄；repo 保存的數字表由 SEC 程式產生。所有期間已接觸，沒有盲測。

## 仍未驗證的範圍

目前已證明 SEC 可產生兩季 net 與 gross，net 八項與雲端共源回報相同、年度副本六欄相同；**尚未取得兩季原 gross 四分類的外部完整參考，亦沒有新增獨立季度驗證**。因此保留跨來源 29 / 30、原固定供應商 24 / 30，以及 CVX Fail。三家網站正常頁面的實際缺口見 [前輪查核](cvx-reference-followup.md)。

只重播 SEC、無須本機參考原值或網路：

```sh
data/vendor/local/.venv/bin/python scripts/check_cvx_net_scope.py \
  --out /tmp/新的CVX淨額核對.json
```

若加 `--reported-reference`，程式只把該檔用於比較，不能供應任何主要數字；它要求明標雲端回報且與 SEC 共源，結果不會提高獨立驗證數或 OK 家數。輸出必須是新檔。
