# 本機參考資料與雲端交接

本機研究負責 `docs/vendor/`、忽略追蹤的 `data/vendor/local/`，以及
`research/recovered-sec/` 的還原程式。雲端 SEC 基準位於
`research/sec-30-baseline-2026-11-04/`。程式與研究摘要透過獨立分支、PR 與測試整合至
[共同 repo](https://github.com/derektu/sec-revenue-breakdown)，不直接修改另一工作的分支。
使用者已授權本研究 repo 的程式 PR／merge。

## 目前入口

- [第二輪逐公司查核、來源選擇與擴展評估](evidence-review.md)
- [逐公司日期與分類稽核](company-audit.md)
- [第一輪涵蓋與數字候選診斷](cohort-research.md)
- [Apple 小樣本](apple-comparison.md)
- [瀏覽器、下載與條款的實際狀態](live-browser-check.md)
- [還原 SEC 程式與驗證](../../research/recovered-sec/HANDOFF.md)

## 檔案界線

| 路徑 | 內容 | Git 處理 |
| --- | --- | --- |
| `docs/vendor/` | 方法、摘要、來源限制、查核計數 | 可檢閱並整合 |
| `research/recovered-sec/` | SEC 研究程式、合成測試、名單 | 保留來源雜湊 |
| `data/vendor/local/` | 第三方原始觀察、完整數值、詳細比對、研究 ZIP、虛擬環境 | 全部忽略追蹤 |
| `research/recovered-sec/data/`、`outputs/` | 可重建的本機驗證產物 | 忽略追蹤 |

本機已有 DOM 參考資料；原生 CSV 尚未確認成功。私人 repo 不代表取得第三方資料再散布權。
瀏覽器登入、cookie、密碼、token 與原始第三方資料不進入 Git，也不交給雲端。
完整研究值保留本機；可分享摘要僅含計數、狀態及公開 SEC／公司來源定位。

## 重現與協作

原始資料保留不變，衍生結果另存新檔。記錄來源 URL、UTC 時間、期間基礎、幣別、倍率、
分類、負值、缺值與來源版本；Q、YTD、FY、TTM 必須分開。不要以缺資料代替零，
不要將父分類與子分類重複加總，也不要以名稱或數字相同直接認定語意一致。

還原套件的 ZIP 與原始檔雜湊在 `recovery-manifest.json`；歷史 README 描述的是原實驗，
目前使用方式以 `research/recovered-sec/HANDOFF.md` 為準。整合時檢查重複程式與現有基準，
避免兩個下載程序共用可寫快取。對話不視為自動共享的工作紀錄，交接依據是 repo 文件與 PR。

最新進展：[多家公司歷史規則與回溯驗證](historical-rule-study.md)。
