# SEC 雲端網路複查 — 2026-11-04 UTC

## 結果

從乾淨 checkout 的 `research/cloud-baseline` 提交 `528adb7` 開始，建立獨立的 `research/cloud-sec-recheck` 分支。當時沒有適用的 AGENTS.md 或 `.agents/skills` 指令。未變更 main 與本機供應商分支。本紀錄取代 `CLOUD_HANDOFF.md` 中較早的網路觀察，但不改寫其歷史結果。

執行環境回報觀察資訊為最新、限制性政策已強制執行，自訂允許主機為 **`data.sec.org` 與 `www.sec.gov`**。必要 API 主機 **`data.sec.gov` 不在清單中**。這是網域拼字錯誤，並非缺少 SEC 憑證。未設定機密、執行環境變數或對外身分。

經由繼承的 HTTPS 代理、啟用 CA 驗證後的實際探測：

| 請求 | 觀察結果 |
| --- | --- |
| `https://www.sec.gov/about/developer-resources` | HTTP 200；68,453 位元組 |
| `https://data.sec.gov/submissions/CIK0000320193.json` | 代理通道 403 Forbidden（`URLError`） |
| 先導 manifest 中 Apple FY2024 10-K URL | HTTP 200；1,503,895 位元組；已解析 |

`research/cloud-sec-network-check.json` 記錄前兩個探測、時間戳記與雜湊。其 `downloaded_filings: 0` 只描述初始探測；後續獨立先導 manifest 記錄一份成功下載的申報。API 遭拒後未重試。已檢查最新使用者訊息證據，未發現對此網路設定的修正。未嘗試繞過限制或替代 API 主機名稱。這是代理政策拒絕，並非自動核准審查拒絕，也未觀察到 SEC 速率限制回應。

## 實際完成的有限申報先導實驗

已下載明確指定的歷史 Apple 申報：

`https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm`

未變更的復原解析器產生 **91 個營收／銷售候選資料項，數值解析錯誤為零**。已存資料項包含原始概念、維度、期間、原始文字、單位、decimals/scale、context/fact ID、列／表格位置、來源 URL 與來源雜湊。它們仍是廣泛候選，並非乾淨的營收觀察值或經驗證的組成資料集。解析器範圍、階層、轉換、nil 值與延續限制仍適用。

已追蹤的可重用產物：

- `scripts/sec_single_filing.py`：以單一明確 URL 取得並解析的入口；要求可識別操作者的 User-Agent、不重試，並拒絕覆寫既有報告目錄。
- `research/cloud-sec-pilot-aapl-2024/manifest.json`：URL、擷取時間戳記、HTTP 結果、位元組、SHA-256 與精確解析器雜湊。
- `research/cloud-sec-pilot-aapl-2024/candidates.json`：公開 SEC 衍生候選資料，並非第三方訂閱資料。
- `research/cloud-sec-recheck-tests.json`：新執行的離線來源／測試驗證。
- `research/cloud-sec-cohort-status.json`：因 submissions 探索遭封鎖，全部 30 家發行公司在最近八季重跑中均明確標示未嘗試。

完整 HTML 仍在由 Git 忽略的 `data/cache/sec-single-filing/`，不在儲存庫中。記錄的申報比歷史先導 README 所載 1,503,892 位元組快照大三個位元組，因此這是具有獨立雜湊的新擷取，沒有聲稱位元組完全相同的復原。新候選輸出可見的歷史年度為 FY2022、FY2023 與 FY2024。未進行季度推導、人工篩選核對或與已存歷史資料項比對。

若要在雲端或本機重做此小型先導實驗，從儲存庫根目錄執行：

```sh
python3 -m pip install -r research/recovered-sec/requirements.txt
# Set SEC_USER_AGENT to your genuine operator identity and contact first.
python3 scripts/sec_single_filing.py \
  --url https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm \
  --report-dir research/a-new-pilot-directory
```

這三次有限且依序的探測，以 User-Agent 標明 Derek 的研究專案與已知公開 GitHub 個人頁面 `https://github.com/derektu`，未虛構電子郵件。此身分未重用於大量爬取。已檢查 SEC [開發者規則](https://www.sec.gov/about/developer-resources)：識別自動化存取、僅取得必要內容，且跨機器合計低於每秒 10 次請求。請求依序發送，沒有重試迴圈；初始連線探測至少間隔一秒。

## 完整基準仍待執行

可重現性截止日仍固定為 **2026-11-03**；本次檢查發生於 **2026-11-04 UTC**。未取得 submissions JSON、未選取近期報告期末，完整基準要求的 **240 個發行公司季度欄位中，嘗試數為零**。它們不是 240 次已觀察到的擷取失敗。單一歷史 Apple 下載不計入該基準。

復原的期間規則未變：選取截止日前最多九個不重複的 10-Q/10-K 報告期末，以第九份支援 Q4 運算元，保留直接揭露的 70–126 天季度，僅在概念／單位／維度／起始日與九個月資料項精確相符時推導 Q4。重編、修正申報處理、實體範圍、階層與 XOM 前身連續性仍未解決。已存的本機 234 季實驗尚未在此重現。未取得或比對 Stock Analysis、Futu 與 TradingView 資料。未聲稱任何算術一致性結果或供應商準確率。

下一個受支援步驟：在雲端環境 Additional allowed domains 將 `data.sec.org` 改為 **`data.sec.gov`**，保留 `www.sec.gov`，儲存並重新發布。以更新的環境與此分支啟動工作，確認有效且強制執行的政策，探測 API 一次。完整執行前，透過 `SEC_USER_AGENT` 提供真實操作者聯絡資訊，並只用一個下載程序。復原下載器仍會對任意錯誤重試，且有預設佔位值；不要直接啟動其 30 家公司網路路徑。應使用獨立版本的擷取包裝程式，在存取遭拒時停止、限制速率並記錄擷取時間戳記，同時保留復原來源雜湊。

**18 項既有測試全部通過**，包含十個復原檔案的來源雜湊驗證與固定的 30 家公司名單。測試會停用網路連線。新增的單份申報命令已對實際 Apple 申報執行；亦已檢查 JSON 完整性、引用雜湊與拒絕覆寫行為。未提交第三方付費資料、機密或大型快取。
