# MCD 補齊八季：24 / 30 OK

正常 Edge 視窗補回 MCD 與 CVX 的富途 2024 Q3 參考後，**MCD OK，正式完成數為 24 / 30**。最新 [三十家結果](../../research/reference-gap-completion-20261104/completion-status.json) 與 [逐公司結論](historical-rule-study.md) 已更新。公司固定參考來源仍是富途，沒有拼接供應商或移動凍結窗口。

| 公司 | 結論 | 實際結果 |
|---|---|---|
| MCD | **OK** | 新增 2024 Q3 三項，皆與 SEC 相同。凍結窗口 2024 Q3 至 2026 Q2 的八季，共 24 項全部相同。 |
| CVX | **Fail：缺兩季參考** | 新增 2024 Q3 四項，皆與 SEC 相同；現有六季 24 項全部相同，仍缺富途 2025 Q3、2025 Q4。 |
| XOM | **Fail：缺最新季參考** | [歷史八季](xom-sec-history.md) 已完成，42 項相同、16 項 Q4 有 SEC 證據解釋；缺目標 2026 Q3 參考，未計入 24 家。 |

另四家為 LLY、PGR 缺 2026 Q3 參考，BRK-B 缺 2024 Q3／2025 Q3，PLD 缺約定三家網站之一的完整八季參考。這些與 XOM、CVX 合計六家 Fail。缺參考不等於數字為零，也不表示 parser 全部失敗。

## 為何本次能補到

雲端 PR #23 發現先前 MCD「缺最新 2026 Q3」的文件說法錯誤；凍結窗口實際缺 2024 Q3。重新檢查正常選單時，MCD 與 CVX 的 2024 Q3 都可選，屬先前尚未擷取的資料，不能說供應商沒有提供。

本機恢復連線後，瀏覽器直接控制仍無法連線；正常 Edge 視窗可透過 accessibility 操作。研究開啟獨立分頁，正常進入 [MCD](https://www.futunn.com/hk/stock/MCD-US/financials-revenue) 與 [CVX](https://www.futunn.com/hk/stock/CVX-US/financials-revenue) 的主營構成頁，展開業務選單，選擇 2024/Q3，確認日期與數值均更新後保存該業務區的文字。未修改登入，也未繞過存取限制。研究分頁已關閉，使用者原有分頁保留。

實際保存格式為 `native_Edge_accessibility_business_text`，不是 DOM、HTML 或原生 CSV。只保存財務業務區，沒有將瀏覽器其他內容放入研究。原始第三方文字留在本機忽略的 `data/vendor/local/xom-legacy-sec-20261104/native-gap-references.json`，以 SHA-256 登錄；repo 不發布參考原值。

## 數字來源仍只用 SEC

參考文字 parser 檢查美元、唯一季度、完整分類順序、金額單位與比例，破折號不當零。它只提供比較值，不能成為主要數字輸入。

MCD 的三項由原凍結 SEC facts 和既有分部規則重播。CVX 則沿用已實作的 `normalize_old_scope()`，將 2024 Q3 舊披露的分類與地區範圍接到既有規則；全球 US／non-US 抵銷保留兩個獨立運算元，避免與分部內交易抵銷重複加總。沒有為新參考手填七個主要輸出。

[新補季度的 SEC 輸出](../../research/reference-gap-completion-20261104/new-SEC-outputs.json) 保留 SEC URL、期間、完整維度、原值與運算元。整體 24 家 OK 的 768 個數字輸出都有 SEC 來源；XOM 另有 58 個歷史對照輸出也已驗證 SEC 來源，但未混入完成家數或 768 筆。

## 驗證與重播

[驗證收據](../../research/reference-gap-completion-20261104/local-verification.json) 記錄 **156 項離線測試通過**，包括最新雲端 PGR 原始 HTML 與期間修正。全部三十份比較結果的雜湊已檢查；既有參考值與日期完整保留，MCD／CVX 各只新增缺期資料。XOM 仍保留真正的 16 項差異解釋，不把它們改寫成完全相等。

須有前輪本機參考與 XOM 正式收據；輸出及同名本機明細目錄必須不存在：

```sh
data/vendor/local/.venv/bin/python scripts/complete_reference_gaps.py \
  --observations data/vendor/local/xom-legacy-sec-20261104/native-gap-references.json \
  --out /tmp/新的參考補齊實驗
```

現有季度均已接觸，結果屬回溯。供應商缺期仍須正常取得資料或改用另一家完整八季後重新驗證；不冒稱未見季度的準確率。
