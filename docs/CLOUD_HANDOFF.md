# 雲端接續工作 — 2026-11-04 UTC

## 已完成的 SEC 接續工作

後續重新發布的環境已正確允許 `data.sec.gov` 與 `www.sec.gov`；兩者均回傳 HTTP 200。完整固定的 30 家公司群組，已以 2026-11-04 為截止日，在基於 `3eaba53` 的 `research/sec-30-baseline` 上執行。結果與重現方式見 [SEC_30_BASELINE.md](SEC_30_BASELINE.md)。已處理 234 季，因繼受發行公司歷史不足缺少六季，下載錯誤為零；每個已處理季度均成功離線重算。原始封存檔仍是獨立且未解決的工作。PR #3 的本機供應商研究亦已保留：見 [Apple 比對](vendor/apple-comparison.md)及[即時瀏覽器檢查](vendor/live-browser-check.md)。該本機 Apple 單一公司樣本回報 Stock Analysis 40 個、Futu 25 個數值符合已存 SEC 候選證據；原始擷取資料仍在 Mac 上，未用於此次雲端基準。

以下歷史章節描述先前環境與阻礙，不代表目前已驗證的 SEC 網路政策。

## 復原原始碼整合後的狀態

已整合經審查的 `local/vendor-reference` 分支 `4113daa`，保留其 Git 歷史、原始來源位元組及本機復原證據。唯一合併衝突為 `.gitignore`；兩組排除規則均已保留。雲端檢查驗證了清單中 10 個檔案的雜湊、30 家公司名單，以及全部 18 項合成／安全測試。目前接續路徑見 `docs/RECOVERED_INTEGRATION.md` 與可執行的 `scripts/verify_recovered.py`。

封存原始 README 保持不變，提供另存的繁體中文譯文：[先導實驗譯文](../research/recovered-sec/README.zh-TW.md)、[八季候選稽核譯文](../research/recovered-sec/eight_quarter_eval/README.zh-TW.md)。它們翻譯的是歷史內容；目前入口請見[復原交接文件](../research/recovered-sec/HANDOFF.md)。

以下較早紀錄描述初始環境檢查與 Library 傳輸失敗。來源取得現已透過明確的 Git 交接解決；當時此處仍無法取得原始封存檔、來源快照及已存的 234 季資料集。僅復原原始碼，不代表雲端資料重現或供應商一致性已成立。未變更網路設定。

## 儲存庫與環境

- 遠端：`https://github.com/derektu/sec-revenue-breakdown.git`。
- GitHub 連接器確認 `visibility: private`、預設分支 `main`，以及目前帳號的拉取／推送權限。未變更可見性。
- 已擷取遠端 HEAD `2be07eaceee665ad04c0b2486fbdc19f00c0b9b6`。當時只有 `README.md`。環境最初是尚無提交的 `work` 分支，未簽出任何提交，fetch refspec 也僅涵蓋 HEAD。
- 已由擷取的遠端 HEAD 建立 `research/cloud-baseline`，保留既有 main 與使用者工作。此 checkout 及工作區指令目錄中沒有適用的 `.agents/skills` 或 `AGENTS.md`。
- 雲端獨立於 Mac 執行。未從 Mac 傳入瀏覽器工作階段、憑證或供應商資料集。

## 封存檔取得阻礙

Library 已找到全部三個檔案，名稱、識別碼與位元組大小記錄於 `research/sources.json`。這只驗證中繼資料可取得，**不代表本機可讀取檔案或已驗證封存內容**。未下載或解壓任何封存檔。

當前 Library skill 的三個 Python 輔助工具已取得至儲存庫外的新私有暫存目錄。已將完整未改動的結構化搜尋結果、明確選項 `000001002` 與相對目的地傳給指定下載工具；結束時顯示：

```
library download request failed: hosted apps tools/list request failed: network
```

這是執行環境的傳輸失敗；工具未揭露精確主機／根因，也不是核准遭拒。未嘗試原始簽章 URL 傳輸、替代下載實作或憑證繞道。應修復受支援的 hosted-app 傳輸連線，再接續 Library skill 下載流程。本次工作的工具輸入與腳本暫存於 `/workspace/scratch/sec-library-*`；新工作須重新取得當前工具。這些暫存路徑不是可攜交付物。

### 有限度的後續重試

2026-11-04 移除舊副本後，已重新從當前 Library skill 取得全部三個輔助工具至新私有目錄。沿用完整原始結構化搜尋結果與明確選項，以最多 45 秒執行受支援下載命令一次。命令立即以結束碼 1 退出，錯誤相同：

```
library download request failed: hosted apps tools/list request failed: network
```

已確認指定目的地有零個 ZIP 檔。因此無法驗證內容、封存檔雜湊、原始測試或基準結果。未嘗試其他傳輸路徑。沒有核准遭拒，也沒有結果不確定的寫入。錯誤未指出遭封鎖的目的地；不可將新增 SEC 網域說成此獨立 Library 傳輸失敗的修復方式。

最小的受支援升級處理方式，是透過 [Help Center 聊天按鈕](https://help.openai.com/en/articles/6614161-how-can-i-contact-support)聯絡 OpenAI Support，提供雲端工作 ID `01a1a415-f259-76fd-b5e3-3d4c196f70f4`、日期、此完整錯誤，以及搜尋可找到三個封存檔、下載卻在 hosted-app 工具探索階段失敗的事實。初次回報不需密碼、權杖、瀏覽器狀態或未遮蔽的網路紀錄。仍待使用者採取行動；本工作未聯絡支援。現有證據無法指出範圍更小、可自行處理的 Library 網路修復方式。

## 網路限制

當時強制執行的雲端政策允許套件管理器預設清單與 GitHub Git 操作。允許清單中沒有 `www.sec.gov`、`data.sec.gov` 與 `api.github.com`。`gh repo view` 因 `Forbidden` 失敗；儲存庫可見性改由可用且已授權的 GitHub 連接器確認。不要由 API 網域受限推論 Git 缺少驗證。不要編輯網路政策快照或繞過代理伺服器。

### 經使用者審閱的 SEC 存取設定

已於 2026-11-04 對照當前官方[雲端環境文件](https://developers.openai.com/codex/environments/cloud-environments)確認：

1. 開啟 **Settings > Codex Cloud > Environments**，在 **sec-revenue-breakdown** 選擇 **… > Edit**。
2. 在 **Public internet access** 保持完整網際網路存取關閉。於 **Additional allowed domains** 分別新增 `www.sec.gov` 與 `data.sec.gov`，保留既有套件管理器設定。
3. 儲存、在設定流程測試服務，審閱設定後選擇 **Republish**。以更新的環境與 `research/cloud-baseline` 分支啟動**新工作**。既有工作會保留原狀態。

若工作區政策不允許變更，請工作區管理員審閱。本工作未變更網路設定。發布後須檢查當前強制執行的政策，並使用可識別操作者的 User-Agent 測試 SEC 存取；網域列入允許清單不等於成功存取 SEC。Library 傳輸連線須另行修復與驗證。

## 已就緒的部分

儲存庫現已記錄研究範圍、來源追溯需求、來源封存檔識別資訊、已知基準限制與具體接續步驟。使用標準函式庫的封存工具會稽核雜湊與大小，拒絕危險路徑、連結、快取／憑證項目及已知憑證特徵，驗證 ZIP CRC，並僅暫存至由 Git 忽略的 `data/staging/`，不覆寫先前工作。它無法證明任意文字都不含憑證或可再散布；納入追蹤前仍需人工審查檔案與內容。

隨附測試涵蓋匯入安全，並非 SEC 擷取正確性。當時在封存檔取得成功前，原始實驗程式碼、資料集、原始測試、精確群組、期間與來源申報 URL 仍不可取得。先前的 234/240 與 138 季數字尚未重現。當時沒有聲稱已進行 Stock Analysis/Futu 比對或供應商驗證。

## 驗證

從儲存庫根目錄執行：

```sh
python3 -m unittest discover -s tests -v
python3 -m json.tool research/sources.json > /dev/null
git diff --check
```

已於 2026-11-04 在此雲端環境執行：六項測試全部通過（0.007s）、來源登錄表解析成功，`git diff --check` 通過。這些檢查僅涵蓋新增的暫存基礎。接續細節見 `docs/RESEARCH_PLAN.md`；這些步驟不需一台持續開機的本機電腦。

2026-11-04 後續驗證：六項測試再次全部通過（0.009s），來源 JSON 與 `git diff --check` 均通過。這些檢查在下載重試失敗後重跑，以確認未受影響的工作仍可使用。
