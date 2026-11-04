# 已執行的雲端 SEC 候選基準 — 2026-11-04

固定的 30 家公司名單已重新從原始 SEC submissions 與 inline XBRL 申報文件執行，使用 `3eaba53` 中未變更的復原解析器與季度稽核。截止日為 **2026-11-04**，依 SEC 申報日期判定，包含當日。每家發行公司選取最近八個不重複的 10-Q/10-K 報告期末；第九份申報支援全年減九個月的 Q4 算術。各公司財報季末不同。這是通用 XBRL 候選資料與算術基準，未輸入 Stock Analysis 或 Futu 資料。

工作 checkout 最初為尚無提交的 `work` 分支，沒有使用者檔案或變更。擷取指定遠端分支後，建立獨立的 `research/sec-30-baseline` 分支。未簽出或推送 main。當時沒有適用的 AGENTS.md 或 `.agents/skills`。

## 結果

| 觀察項目 | 數量 |
| --- | ---: |
| 嘗試處理的公司 | 30 |
| 要求的季度欄位 | 240 |
| 已選取並處理的季度 | 234 |
| 因發行公司歷史不足而缺少的欄位 | 6 |
| 原始申報 HTML 快照 | 263 |
| 全部來源快照（含 submissions JSON） | 309 |
| 來源位元組（由 Git 忽略的原始快取） | 890,476,285 |
| 下載／探索錯誤 | 0 |
| 數值解析例外 | 5 |
| 已拒絕的衝突重複分組 | 2 |
| 季度候選資料項 | 9,000 |
| 全年減九個月推導的候選資料項 | 1,732 |
| 單軸候選分組 | 524 |
| 至少符合一個候選總額的分組 | 258 |
| 至少有一組上述相符結果的季度（不限軸類別） | 138 |
| By source 啟發式分組 | 290 |
| 符合候選總額的 By source 啟發式分組 | 148 |
| 至少有一組 By source 啟發式相符結果的季度 | 114 |

除 XOM 外的 29 家發行公司都有完整八個期末。XOM 使用繼受公司 CIK 2115436，只有 2026-06-30 與 2026-09-30；刻意不與前身 CIK 34088 銜接。六個缺漏欄位有明確狀態且日期留白，沒有虛構歷史季度。若要在修訂的身分政策下取得實際 240 個期末，須先決定繼受公司／前身的連續性。

這裡的「By source」只包含依軸名稱啟發式判為產品／服務或營運部門的軸，排除依名稱判為地理的軸。這是候選子集，並非與供應商類別的語意對應。Apple 營運部門即使軸名稱不是地理，內容仍可能按地理區分。加總成功不證明階層、會計範圍、完整性或準確性。138 季的數字包含地理與未分類軸，不可說成 138 季成功擷取 By source。

## 保留的證據

結果位於 [`research/sec-30-baseline-2026-11-04`](../research/sec-30-baseline-2026-11-04)：

- `company_summary.csv`：每家發行公司、處理狀態、數量與歷史缺口。
- `quarter_summary.csv`：全部 240 個要求欄位；報告／申報日期、觀察到的候選起始日、accession、來源 URL/SHA-256、當期申報解析錯誤數、拒絕的重複數、Q4 推導與分組數。
- `TICKER.json.gz`：完整公開 SEC 衍生結果，含每份申報的原始候選資料項、解析錯誤、全部選取的季度資料項、精確全年／九個月 Q4 運算元與引用、候選總額與比較。可用 Python `gzip.open(path, 'rt')` 後接 `json.load(...)` 檢視。
- `quarter_candidates.csv.gz`：9,000 個候選觀察值，含期間、單位、維度、證據及 Q4 運算元。這不是乾淨的營收組成資料集。
- `manifest.json`：HTML 的 URL、accession、報告／申報日期，以及全部 309 個來源的大小與 SHA-256。路徑指向由 Git 忽略的復原稽核快取。
- `exceptions.json`：五個數值解析錯誤與兩組已拒絕的衝突重複資料。解析錯誤數包含支援用的第九份申報。
- `summary.json`、`verification.json`：整體／逐家公司指標、產物與可執行來源雜湊，以及已完成的重算／來源檢查數量。

整份衍生套件壓縮後約 2.6 MiB。大型 HTML/submissions 快取、原始封存檔、機密、瀏覽器狀態與供應商資料均排除於 Git 之外。來源清單支援重新取得與位元組一致性檢查；SEC 可能修改其提供的文件，若雜湊不符須審查。

[`sec-30-network-check.json`](../research/sec-30-network-check.json) 記錄修正後強制執行的政策下，兩個 SEC 主機均回傳 HTTP 200。使用繼承的 HTTPS 代理與 CA 信任設定，啟用 TLS 驗證。User-Agent 標明 Derek 的研究專案與真實公開 GitHub 聯絡頁面，未虛構電子郵件。只執行一個下載程序、兩個工作執行緒，共用請求開始時間最小間隔 0.22 秒（每秒低於五次），最多嘗試三次並有退避等待。無下載失敗。

## 重現方式

使用 Python 3.12 與 `lxml==6.1.1`，保留環境的代理／CA 設定。將 `SEC_USER_AGENT` 設為真實且可識別操作者／專案的聯絡資訊，不可使用復原執行器的預設佔位值。只啟動一個下載程序。

```sh
python3 -m pip install -r research/recovered-sec/requirements.txt
export SEC_USER_AGENT='Your actual operator/project identity and contact'
python3 research/recovered-sec/eight_quarter_eval/run.py --workers 2 --as-of 2026-11-04
python3 research/recovered-sec/eight_quarter_eval/summarize.py
python3 scripts/package_sec_baseline.py export research/new-sec-baseline-run
python3 scripts/package_sec_baseline.py verify research/new-sec-baseline-run
```

執行器會重用既有原始下載，並重寫由 Git 忽略的產生輸出。獨立取得資料應使用新的 checkout。匯出器要求新目的地，拒絕覆寫既有結果目錄；封裝前會驗證全部來源大小／雜湊，並重算每個已處理季度。驗證已提交套件不需網路或原始 HTML 快取：

```sh
python3 scripts/verify_recovered.py
python3 scripts/package_sec_baseline.py verify research/sec-30-baseline-2026-11-04
git diff --check
```

已執行檢查：18 項合成／安全測試全部通過；10 個復原來源雜湊符合復原清單；全部 309 個已下載來源的大小／雜湊相符；全部 234 季結果均從保留的候選資料項重算相符，包括精確 Q4 運算元與所有分組檢查；全部 36 個封裝資料產物均通過 SHA-256 驗證。重播驗證的是從已存解析結果重算的算術確定性，**不是重新解析全部原始 HTML，也不是獨立、符合完整標準的重新擷取**。獨立的 [`sec-30-tests.json`](../research/sec-30-tests.json) 僅記錄來源／合成測試，因此其歷史基準重算旗標仍為 false；新套件驗證記錄了已執行的資料重播。

## 例外與限制

Lilly 的 FY2024 支援申報有兩個營收字串顯示為 `no`，解析器未進行該轉換。Prologis 有兩個銷售代理人數字串顯示為 `twenty`；Tesla 有一個空白的備供出售證券資料項。後三者亦顯示廣泛 revenue/sales 正規表示式的誤收情形。未虛構零值。Berkshire 2024 與 2025 年底各有一組衝突重複資料，已由稽核拒絕；原始替代值仍保留於原始資料項中。

保留的基準對 Q4 使用精確概念／單位／成員／起始日比對，並拒絕名稱變更的成員；它不認證跨申報重編基礎一致。父子小計可能重疊；P&G 等多軸組成保留於候選資料，但排除於單軸分組檢查。概念允許清單尚未完整涵蓋銀行／保險合併總額。實體範圍、修正申報、所有 XBRL 轉換／延續、分類標準標籤與 linkbase 階層仍未解決。詳見已復原的[方法與限制（繁體中文譯文）](../research/recovered-sec/eight_quarter_eval/README.zh-TW.md)。

SEC 存取已解決。待辦為語意／標準層級驗證、任何經明確核准的繼受公司連續性對應，以及匯入獲授權的 Stock Analysis/Futu 參考資料，以進行更廣泛公司群組比對。透過 PR #3 合併的獨立[本機 Apple DOM 比對](vendor/apple-comparison.md)回報 Stock Analysis 40 個與 Futu 25 個數值符合已存 SEC 證據。原始輸入仍在 Mac，未用於此次雲端基準，也未由此次基準重新驗證。原生 CSV 匯出與跨公司供應商準確性仍未驗證。本基準不聲稱任何準確率或供應商一致率。
