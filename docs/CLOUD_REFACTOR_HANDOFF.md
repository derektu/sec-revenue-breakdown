# 雲端重構工作與驗收條件

使用者於 2026-11-04 要求把實驗程式與資料整理成 RD 可維護的 base 架構，並明確要求盡量在雲端開發，因為 local 稍後離線。這是實作工作，不只提交設計文件。repo 為 `derektu/sec-revenue-breakdown`，既有程式 PR 與合併已授權。使用隔離分支，保護已合併研究證據，測試後整合。

## 使用者要求

- Python，程式分成 `libs`、`tests`、`scripts`。採物件寫法，盡量不寫 module level 的 global function。
- 共用 class 包含 SEC download engine、XBRL parser engine，以及 parser base class。
- 每個 ticker 有自己的獨立 parser。新增或修改一家不能修改其他公司的規則或共用 ticker switch。
- 所有已下載 SEC 資料依 ticker、期別整理，保留可供事後驗證的原文及實際格式。
- 每 ticker 每期輸出固定檔名 convention。用明確表格設定每家參考來源，參考檔名需看得出公司、來源、期別、口徑；跨來源例外逐期記錄。
- 每家有風險評等，依近期相對歷史的 tag、維度、架構異動與特殊規則負擔，附評等理由。
- 有 viewer，輸入 ticker 能看到 revenue breakdown、期間、來源、口徑與風險。
- parsing logic 可以重跑。程式需 RD 能閱讀，清楚命名，合適 comment，尤其解釋財報規則的理由與期間限制。
- 盡量在雲端開發，local 離線不能使主要開發、測試或 viewer 停止。

## 研究邊界與目前狀態

先讀 repo `AGENTS.md`。來源僅 SEC；IR 及資料商僅比較。每個值保留 SEC URL、期間、幣別、單位、完整 scope，以及 Q4 或合計全部運算元。文字快照不能改稱 HTML bytes。既有回溯不是盲測，不能因整理程式提高研究完成數。

最新研究完成是跨來源 29 / 30、原固定供應商 24 / 30。30 家八季的指定 SEC 欄位可產生，不代表完整披露召回率。看 `docs/vendor/historical-rule-study.md`、`feasibility-conclusion.md`、`feasibility-inventory.md`。

CVX 對外營收建議以 net 主系列、gross 與抵銷另存。原 gross 八季僅六季參考，net 目前兩季核對。不可把公司副本當獨立驗證，也不為湊完成數改分類。新架構可支援兩個具名 basis，切換需明列覆蓋與狀態。

## 雲端可用的資料

`research/refactor-baseline-sec-20261104/manifest.json` 索引 30 家、240 期、1,092 項 SEC 回歸期望值，每家公司及日期一份 `TICKER/YYYY-MM-DD/TICKER_YYYY-MM-DD_SEC_expected.json.gz`。含完整 SEC 運算元，不含第三方原始參考值。壓縮與解壓 bytes 雜湊均保存。**只能作回歸答案，不得作 runtime parser 的輸入或將讀檔偽稱重新解析。**

另有 `source-snapshots/UPS_2026-09-30_SEC_web_text.txt.gz`，是真正先前取得的 SEC 工具文字快照，解壓後 bytes 與舊來源收據相同，不是原始 HTML。

主要可重播 SEC 證據已在 repo：

- `research/sec-30-baseline-2026-11-04/*.json.gz`：既有 SEC 申報 facts。來源擷取後的結構資料，不能說成原始 HTML。
- `research/progressive-sec-html-20261104/`：五份真正 SEC HTML gzip，manifest 含壓縮及解壓雜湊。
- `research/sec-dom-sources-20261104/`：CAT、Comcast 與舊 PGR 的正常 SEC 瀏覽器表格快照，各自 manifest。
- `research/xom-sec-dom-20261104/` 與 `research/xom-sec-verified-20261104/`：舊 CIK 表格、工具文字、解析 facts 與來源。
- `research/shared-raw-semantics/sources/`：四家共用語意實驗的原始 SEC HTML、XSD 與 linkbase gzip。
- `research/remaining-sec-coverage-20261104/coverage.json`：六家指定欄位與全部運算元，可用作檢查，不可當 runtime parser 答案來源。

已下載原始檔可重組或建立可追溯索引，保留原 manifest 與 bytes 雜湊。欠原始 bytes 的期別明標 `facts_cache`、`dom_snapshot` 或 `web_text`，不得製造 `.html` 外觀假裝原始檔。新的正常 SEC 下載要保留實際取得資訊，遇 403 等拒絕停止，不以改身分或瀏覽器 session 繞過。下載 User-Agent 的聯絡設定若未提供，離線重播仍應可運作，不猜帳密或聯絡地址。

第三方原始參考及完整比對 row 在本機 `data/vendor/local/`，不傳雲端、不推 repo。交接 manifest 只有來源選擇及明細 hash，可據此產生 reference registry 和缺檔狀態。需要實際供應商原值的測試可明標需本機參考，**不可因此阻止雲端完成 SEC parser 與 viewer**。

## 建議結構與實作順序

先寫短 architecture 文件及主要 class 介面，接著直接實作。可依查核結果調整命名，不需再次詢問同一架構授權。

`libs/sec_revenue/` 建議包含資料模型、證據儲存、SEC 下載、XBRL 抽取、季度計算、規則選值、參考 registry、風險分析及 viewer service。`libs/sec_revenue/parsers/base.py` 定義 base class，`parsers/aapl.py` 等各家獨立 class。共用引擎不可含 `if ticker == ...` 公司規則；各 parser 持有自己的 selector、期間別名、修訂規則及有日期範圍的 special rule ID。

`scripts` 保留薄 CLI 入口，業務邏輯在 class。歷史實驗可封存在 `research` 或明標 legacy，既有凍結程式及來源雜湊不得悄悄改寫。不可只把舊全域函式包進 class，繼續以大量 ticker switch 當正式路徑。

原型資料 convention 可採 `data/sec/TICKER/PERIOD_END/ACCESSION/...`，`data/outputs/TICKER/PERIOD_END/TICKER_PERIOD_END_BASIS_revenue.json`，參考檔使用 `TICKER_PERIOD_END_PROVIDER_BASIS_reference.json`。日期以實際 SEC 期間為主，另存 fiscal year 與 fiscal quarter；FY、YTD9、Q 不混為同一期。要能保留原申報與重編版本，寫入需 atomic，重跑不可覆蓋不同 bytes。快取能雜湊驗證，capture 格式固定記於 manifest。

先做共用引擎和一至兩個 ticker 的完整 vertical slice，包含取得或 cache、解析、Q4、輸出、風險、viewer。接著移植全部三十家公司，逐家用獨立測試與既有期望值比較，修差異原因，最後跑整批。不要停在只有 Apple 的範例；若新路徑有真實缺口，逐公司回報，不能把舊 fixture 直接當新結果。

風險是「parser 維護風險」，不是投資風險或準確率。以相鄰歷史與近期的 concept、完整維度形狀、欄位增刪、實際使用 special rule ID、缺來源或解析拒絕等訊號分析，門檻與計算方式可讀可測。近期新架構、未見必要 tag、未知或缺期間不可因為沒有資料就給低風險。輸出分數、等級、各項原因、比較的日期與 schema hash。

viewer 可用輕量 Python 服務或可重跑產生的靜態資料，支援 ticker 輸入、期別及 basis 切換、數字表、圖、證據詳情和風險說明。公司總額及成分不得重複加總；負數抵銷不可硬畫正數圓餅。先有可在雲端實測的版本，不能要求 Mac 開著才能驗證。

## 驗收

1. 新環境安裝後，單一可讀 CLI 能離線重播 ticker，批次重播三十家，重新產生固定路徑結果。
2. 正式 parsing code 不讀 `*_expected`、舊完成輸出或 vendor 值來產生主要數字。既有 SEC facts cache 與原始 bytes 路徑須明確區分。
3. 各 ticker 獨立 class 與規則，新增 ticker 只新增自己的檔案和 registry。修改某家不改其他 parser 的 regression 結果，實測隔離。
4. 三十家新輸出逐期逐分類與 240 份 SEC baseline 比較，數字、期間、scope 與運算元均可追溯。差異具體列出，舊 29 / 30 不自動改名為新架構已通過。
5. 同一輸入及規則重跑兩次，業務輸出一致。執行時間記錄與 deterministic payload 分開。
6. 原始來源按 ticker、期別、accession 可查，格式與 hash 正確。原先未存 raw bytes 的來源不偽裝成已補齊。
7. reference registry、固定輸出及參考檔名、CVX 雙 basis、特殊規則及風險理由有文件與真實樣本。
8. viewer 真正啟動並測試 ticker、期間、basis、缺資料、非法輸入。瀏覽器能用時以正常 UI 檢查。不要只交一張 mockup 或聲稱啟動等於功能通過。
9. 新類別與模組有適量繁中 docstring、必要型別與財報語意註解。README 說明新 ticker 怎麼加、下載、重播、核對、看 viewer。
10. 執行適當單元與整合測試，既有 176 項離線測試為歷史保護網。新路徑須有行為測試，不能只斷言 class 存在。測試後按既有授權 PR/merge，最後清楚回報新架構實測幾家、未移植與資料缺口。
