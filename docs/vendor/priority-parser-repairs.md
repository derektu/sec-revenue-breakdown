# 第二批五家公司：14 / 30 OK

ORCL、GOOGL、MSFT、PG、JPM 已完成八季重播；原九家不變，現共 **14 家 OK、16 家 Fail**。每家公司固定使用 Stock Analysis，同一家公司未按欄位切換參考來源。全為已接觸期間的回溯，未見測試為零。

| 公司 | 程式修復／裁決 | 八季結論 |
|---|---|---|
| ORCL | 明確二／五／八／十一月實際季末對應網站三／六／九／十二月標籤；舊 License／Support 與新 Cloud／Software 分期。每期四個現行分類須齊備、相同且合計等於 SEC 總收入，才將另一版本空欄標 N/A | 32 項相同，OK |
| GOOGL | SEC Note 2 披露總收入減 Google Services、Google Cloud、Other Bets 等於避險；以完整 scope 計算補兩個缺漏。2025 Q4 用實際下載的公司 PDF 單季表，避免年度減九個月的精度差額 | 56 項相同，OK |
| JPM | 2024 Q3 的 CorporateAndInvestmentBankMember 與年度 CommercialAndInvestmentBankMember 需有明確、受來源日期限制的接合；公司 2024 Q2 已重組。Q/FY 仍分開，保留 managed basis 與 Corporate，不混 GAAP 總額 | 32 項相同，OK |
| MSFT | parser 原收入正確；SA 2026-03 More Personal Computing 欄實際等於另一分部 Intelligent Cloud 的營業利益。新正常 Quarterly 頁確認不是舊擷取錯誤。保留收入值並明列此一來源錯誤 | 22 項相同、1 項有來源錯誤證據，OK |
| PG | 35 項的網站 B／M 步階與 SEC 報告精度相容；Q4 傳播 FY 與九個月兩側誤差。2026-09 Fabric & Home Care 顯示超出該界限，依 SEC 直接分部表採公司收入，不推測網站內部原因、不擴大其他欄位界限 | 12 項相同、35 項精度解釋、1 項公司原表裁決，OK |

## 選定口徑與證據

- ORCL 以當期披露的產品收入組成為準；不同期間的新舊分類都保存，不加在一起。[公司 FY2026 原表](https://www.sec.gov/Archives/edgar/data/1341439/000119312526277521/orcl-20260531.htm)及每季既有 facts／原來源支持四分類對帳。
- GOOGL 採 Note 2 的收入組成，避險是對帳項，不假造一個客戶合約產品。[FY2024 Note 2 與分部附註](https://www.sec.gov/Archives/edgar/data/1652044/000165204425000014/goog-20241231.htm)；直接 Q4 表頭、符號與兩欄年份已核對，[官方單季發行稿](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000012/googexhibit991q42025.htm)。PDF parser 驗證廣告小計、Google Services 小計、總收入，不能把年度、營業利益或錯誤欄位當季度收入。
- JPM 的 [2024 10-K](https://www.sec.gov/Archives/edgar/data/19617/000001961725000270/jpm-20241231.htm)明列 2024 Q2 合併原 CIB 與 Commercial Banking，並說明 managed basis。僅接合指定舊 filing 的完整收入 scope，沒有模糊字串改名。
- MSFT [2026-03 10-Q 分部表](https://www.sec.gov/Archives/edgar/data/789019/000119312526191507/msft-20260331.htm)直接支持 MPC 收入與 IC 營業利益的區別。新舊分部空欄另以當期 SEC facts 的現行分部合計等於公司總收入確認。
- PG [2026-09 10-Q Note 3 分部表](https://www.sec.gov/Archives/edgar/data/80424/000008042426000256/pg-20260930.htm)直接支持 Fabric & Home Care 收入。這個單期單格裁決不適用於其他差額。其餘精度解釋保留原差額、網站步階、SEC 精度及 Q4 運算元。

MSFT／PG 的裁決證據為 agent 檢視原 SEC 表建立，尚無獨立人類覆核。[公開公司披露證據](../../research/issuer-repair-evidence/primary-adjudications.json)不含 vendor 原始列。原始 SA 畫面重讀與八季完整差額仍僅本機。

## 重現

入口：[continue_parser_repairs.py](../../scripts/continue_parser_repairs.py)。重跑原九家與三十家公司基準，再施加本批規則；不改原 parser 檔案或舊收據。需已有本機 Meta HTML、Alphabet PDF 與參考資料：

```sh
data/vendor/local/.venv/bin/python scripts/continue_parser_repairs.py --out /tmp/新的第二批實驗
```

目的地及對應本機目錄必須不存在。新程式及來源雜湊在 [completion-status.json](../../research/continued-parser-repairs-20261104/completion-status.json)；同目錄原 `eight-quarter-status.json` 是第一批九家結果，`summary.json` 是未裁決的候選計數，均保留作歷史，不混用為最新完成數。

本機逐筆結果：`data/vendor/local/cohort-adjudication-20261104/continued-parser-repairs-20261104/{TICKER}-repaired.json`。新 SA 重讀檔、公司 PDF 及原始 vendor 金額不發布。base freeze 只固定原規則；新修復與裁決另以本輪 code／evidence 雜湊固定，不冒稱原 freeze 已包含後來規則。

雲端 taxonomy bridge（PR #14）只涵蓋 TSLA、CMCSA、UNH、NEE 的固定來源；本輪沒有把其中 23 組有條件支持當成本批五家的已認證語意或盲測。
