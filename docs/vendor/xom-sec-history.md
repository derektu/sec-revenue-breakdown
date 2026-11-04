# XOM：歷史八季已完成，最新目標仍缺參考

目前正式完成數為 **24 / 30 OK**，MCD 已另 [補回缺季](reference-gap-completion.md)。[XOM 收據](../../research/xom-sec-verified-20261104/completion-status.json) 將 XOM 的兩個結果分開：

- **已保存歷史八季 OK**：2024 Q3 至 2026 Q2，固定富途參考的 58 項中，42 項相同、16 項 Q4 有具體參考計算差異證據；所有輸出均由 SEC 擷取與計算，沒有未解差異。
- **最新目標八季 Fail**：2024 Q4 至 2026 Q3，缺富途 2026 Q3 參考，不能用較舊的 2024 Q3 補位。因此沒有提高正式完成數。

這是已接觸資料的回溯驗證，不是盲測，也不保證下一季成功。參考原值與日期未改，第三方原始內容仍留本機忽略目錄。

## 已實作的 SEC 規則

四份 [SEC DOM 表格快照](../../research/xom-sec-dom-20261104/manifest.json) 產生 130 筆分部、合併及對帳資料，包含 Q、YTD6、YTD9、FY；另兩份正常 web 工具讀取的 SEC 頁面文字，解析出 16 個分部 gross sales 對照值。DOM 與頁面文字都明標實際格式，不冒稱原始 HTML。每份有 SHA-256，四份 DOM 另與原瀏覽器物件的 canonical FNV32 核對。

來源為 SEC [2025 年報](https://www.sec.gov/Archives/edgar/data/34088/000003408826000045/xom-20251231.htm)、[2025 Q3](https://www.sec.gov/Archives/edgar/data/34088/000003408825000061/xom-20250930.htm)、[2026 Q1](https://www.sec.gov/Archives/edgar/data/34088/000003408826000067/xom-20260331.htm)、[2026 Q2](https://www.sec.gov/Archives/edgar/data/34088/000003408826000093/xom-20260630.htm)。比較欄用於歷史期間，明確保留來源申報日及原期間；不是宣稱取回每一期最初版本。Q4 使用相同 CIK、分類、單位及年度起點的 FY 減 YTD9，不跨 CIK 相減。

[2026-07-01 的 SEC 8-K12B](https://www.sec.gov/Archives/edgar/data/2115436/000119312526291990/d71068d8k12b.htm) 說明新公司為 predecessor 股票的 successor registrant。這支持查找舊 CIK 34088 的文件，不代表所有會計分類自然連續。舊基準與凍結程式未改；2026 Q2 原表擷取另與既有 successor 路徑的同 accession XBRL 結果獨立核對。

通常季度的四分部使用 `Segment revenues and other income`，加 corporate `Other revenues`、扣分部間收入，再扣合併投資收益與其他收益，對回 sales。合併表的投資與其他收益因此呈負數扣回；不能一概判為錯誤。程式分開保留這些扣回列與分部收入，並核對分部地區加總、分部對帳及合併原表。

2025／2026 Q2 的富途只列五欄，四分部採 `Sales and other operating revenue + Intersegment revenue`，加獨立抵銷。這與其他季度的 all-income 口徑不同，規則依已審查期間明訂，不按哪個候選較接近參考臨時選值。2026 Q2 五項與既有 SEC XBRL 獨立結果一致。五欄未涵蓋全部 corporate 項目，不能把「參考全部欄位相同」稱為完整財報揭露覆蓋率。

## 兩個 Q4 的 16 項差異

2024／2025 Q4 各八欄符合相同、可重現的錯誤公式：

- 四分部的參考值等於 **全年 gross sales 減九個月 all-income 分部收入**，兩個運算元口徑不同。
- 另四欄的參考值等於 **負九個月值**，沒有正確的全年運算元。

程式逐年同時核對八欄符合這個公式，才將差異列為有證據的參考計算問題；單一數字巧合不會通過。輸出保留同口徑 SEC FY 減九個月的正確結果及全部運算元，不用錯誤公式產生對外結果，也不宣稱知道供應商內部程式原因。

例如 2025 Q4 Upstream 正確 all-income 結果為 **107,151 − 82,664 = 24,487 百萬美元**。參考卻等於全年另一種 gross sales 口徑 101,795 減 82,664。兩個全年口徑及九個月數字皆由 SEC 原表程式擷取，並非為了湊數手填結果。

## 剩餘七家的缺口分類

| 公司 | SEC／parser 狀態 | 參考缺口 | 結論 |
|---|---|---|---|
| XOM | 已補舊 CIK 八季規則及 Q4 裁決；最新 SEC 基準已有，但該期參考口徑待確認 | 缺 2026 Q3 | 最新目標 Fail；歷史八季 OK |
| MCD | 2024 Q3 至 2026 Q2 八季 24 項相同 | 本批用正常 Edge 補回 2024 Q3 | **OK** |
| LLY | 舊八季 39 項相同、一項精度解釋 | 重新切至 Stock Analysis Quarterly，最新仍 2026-06-30，頁面標示更新日 2026-08-25 | Fail：目標最新季參考缺 |
| PGR | SEC 五文件 parser 已完成；七季 43 相同、六項有差異理由 | 重新開啟富途選單，最新仍 2026 Q2 | Fail：最新季參考缺 |
| CVX | 本批補回 2024 Q3，六季 24 項相同 | 凍結窗口內仍缺 2025 Q3、2025 Q4；Stock Analysis 此入口顯示 specific page 404 | Fail：兩季參考缺 |
| BRK-B | 已有六季 48 項相同 | 重看富途選單，目標的 2025 Q3、2024 Q3 不在清單中 | Fail：兩季參考缺 |
| PLD | SEC 對公司 IR 八季已有 32 項相同，IR 只作參考 | 原三家完整八季參考尚缺；最新一次 PLD 頁面檢查遇瀏覽器連線中斷，沒有結果 | Fail：約定參考缺；不能宣稱本次重新確認無資料 |

以上參考選單重看發生於斷線前，屬本次研究接續的實際觀察，不冒稱重新登入或下載。恢復後本機檔案與終端可用，瀏覽器直接控制連線失敗，先以正常 web 工具補足 XOM SEC 原表；其後正常 Edge 視窗的 accessibility 操作可用，已補 MCD／CVX 的 2024 Q3。沒有改驗證、重試遭拒的 CLI 請求或繞過登入。參考缺口尚未消失，不能靠 parser 調整補出參考資料。

## 程式與驗證

- [SEC 表格 parser](../../scripts/parse_xom_sec.py) 同時處理 DOM cell 與 web 頁面文字兩種真實格式。
- [八季重播與裁決](../../scripts/evaluate_xom_sec.py) 只輸出 SEC 選值；固定目標八季與較舊八季分別判定。
- [離線測試](../../tests/test_xom_sec.py) 檢查年份、單季／累計、地區順序、單位、獨立對帳、跨 CIK Q4 拒絕與空值不當零。
- [本機驗證收據](../../research/xom-sec-verified-20261104/local-verification.json) 保存測試數、全部三十份結果及來源／程式雜湊核對。

須先有前輪本機參考及正式收據；輸出目錄及其同名本機明細目錄必須不存在：

```sh
data/vendor/local/.venv/bin/python scripts/evaluate_xom_sec.py \
  --manifest research/xom-sec-dom-20261104/manifest.json --out /tmp/新的XOM實驗
```

下一步是取得同一家 2026 Q3 參考並確認分類口徑，再對最新八季重跑；除已完成的 MCD，其餘五家須補同源缺季，或取得另一家完整八季後整組重驗，不能混來源補季。
