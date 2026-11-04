# SEC 營收組成研究

研究 S&P 500、400、600 公司的 SEC 營收組成，從三十家公司、八季實驗開始。
程式、公開 SEC 結果及查核文件保存在 repo；第三方原始參考資料留在本機忽略目錄。

**本機日常操作請看 [分階段下載、萃取與 viewer](docs/architecture/local-workflow.md)。** `sec_pipeline.py` 支援 ticker 清單、日期範圍、更新最新、cache 與 force；`replay_sec.py` 保留供既有研究離線回歸。

**擷取與計算的數字來源只用 SEC 申報（含 8-K 附件）；公司 IR 與 vendor 只作參考。**
目前跨來源逐期裁決為 **29 / 30 OK**，原固定供應商基準 **24 / 30** 另行保留，見 [逐公司結論](docs/vendor/historical-rule-study.md) 與 [SEC 來源規則](docs/vendor/sec-primary-source-policy.md)。

[三十家公司可行性總結](docs/vendor/feasibility-conclusion.md) 說明 CVX net 與 gross 選擇、240 季 SEC 指定欄位、公司規則數、來源缺口及擴展至 1,500 家的限制。[逐公司盤點](docs/vendor/feasibility-inventory.md) 列出八季日期與參考覆蓋。

最初雲端候選基準取得 234 個季度，當時 XOM successor CIK 缺六季。後續以舊 CIK、SEC 附件及個別規則補足，現在三十家公司各八季的指定欄位均有 SEC 輸出。原候選基準保留，不當作目前缺口或完整披露準確率。

本機已取得 29 家的第三方 DOM 參考值；PLD 另以公司 IR 八季資料查核。
Apple 有八季 40 筆 Stock Analysis、五季 25 筆富途觀察與指定 SEC 證據相同。
第二輪更正四家載入空白誤判，新增 WMT、BRK-B、NEE、XOM 查核。
原生 CSV 與 TradingView 八季明細未確認取得，全部三十家完整八季語意驗證尚未完成。
最新季度已接觸，現有結果屬回溯驗證，不能宣稱盲測泛化。

- [三十家公司雲端基準與重現](docs/SEC_30_BASELINE.md)
- [逐公司 SEC 結果](research/sec-30-baseline-2026-11-04/company_summary.csv)
- [240 個要求季度欄位](research/sec-30-baseline-2026-11-04/quarter_summary.csv)
- [雲端狀態與限制](docs/CLOUD_HANDOFF.md)
- [研究需求與後續工作](docs/RESEARCH_PLAN.md)
- [封存來源登錄](research/sources.json)
- [還原程式入口](research/recovered-sec/HANDOFF.md)
- [雲端整合審查](docs/RECOVERED_INTEGRATION.md)
- [雲端驗證證據](research/cloud-verification.json)
- [歷史訓練、凍結與保留季度評估](docs/TEMPORAL_EVALUATION.md)
- [本機參考來源入口](docs/vendor/README.md)
- [第二輪來源裁決、測試切分與擴展評估](docs/vendor/evidence-review.md)
- [三十家公司日期與分類稽核](docs/vendor/company-audit.md)

使用 Python 3.12 與 `lxml==6.1.1` 執行來源完整性與合成測試：

```sh
python3 scripts/verify_recovered.py
```

封存 staging 與本機測試使用 Python 3.11+，不需網路：

```sh
python3 -m unittest discover -s tests -v
python3 scripts/stage_archive.py /path/to/eight_quarter_reproducible_results.zip
python3 scripts/stage_archive.py /path/to/eight_quarter_reproducible_results.zip --extract
```

第一個封存命令只稽核；`--extract` 在忽略的 `data/staging/` 建新目錄，不執行匯入程式或修改 Git。
升級為追蹤檔案前先檢查內容。受限參考資料、登入狀態、憑證、大型快取及原始封存均排除於 Git。

最新進展：[多家公司歷史規則與回溯驗證](docs/vendor/historical-rule-study.md)。

接續研究：[WMT 與 NEE 範圍缺口查核](docs/vendor/scope-gap-review.md)。

原始財報共用解析實驗：[四家 Q／FY、原始證據、拒絕判定與規模限制](docs/SHARED_RAW_SEMANTICS.md)。

版本橋接接續：[64 組 Q／FY taxonomy 證據契約與覆核負擔](docs/TAXONOMY_BRIDGE.md)。

## 歷史 SEC 回歸重播引擎

正式入口為 `libs/sec_revenue`，歷史 `scripts` 實驗及 research 不改寫。Python 3.11+：

```bash
python -m pip install -r requirements.txt
python scripts/replay_sec.py AAPL --out data/engine-check
python scripts/replay_sec.py ALL --out data/engine-check
python scripts/check_engine_regression.py
python -m unittest discover -s tests -v
python scripts/serve_sec_viewer.py --data data/engine-check --port 8765
```

Viewer：[雲端埠 8765](http://127.0.0.1:8765)。這個位址屬於執行服務的雲端機器；從外部瀏覽需使用環境的埠預覽／轉送功能，並非 Mac 上已啟動服務。可選的正常 UI 驗證：

```bash
python -m pip install playwright
# 環境若沒有 Chromium，先執行 python -m playwright install chromium
python scripts/check_sec_viewer_ui.py --url http://127.0.0.1:8765
```

重播完全離線，不需本機 vendor 資料或瀏覽器登入。`data/sec/TICKER/實際申報期/ACCESSION/HASH.FORMAT` 保存來源及收據；`.json` facts cache 是原擷取結構資料，`.txt` 是文字快照，只有真正原始 HTML 才用 `.html`。`data/sec/TICKER/index.json` 明列原始 HTML 是否實際存在。原始研究 gzip 與凍結 hash 均保留。

固定輸出為 `data/outputs/TICKER/PERIOD/TICKER_PERIOD_BASIS_revenue.json`，每家公司 `index.json` 列出當次正式輸出，viewer 不混讀過時檔案。包含實際期間、會計年度／季度、USD、完整 scope、運算元、替代算式、申報精度及風險。後續尚無年報的季度以最後已知結帳日推估年度標籤，明標 `projected_from_last_annual_calendar`；實際數值期間不推估。CVX 預設 `net`，`gross` 與抵銷另存；其他 basis 為 `reported` 或 `segments`，表示不同財報分類，不是資料商名稱。

參考來源設定在 `libs/sec_revenue/registry.json`，重播時輸出至 `data/references/TICKER/registry.json`。每期列來源與雲端缺原值狀態，檔名契約為 `TICKER_PERIOD_END_PROVIDER_BASIS_reference.json`。雲端沒有原始參考金額時不製造參考檔，也不阻止 SEC 重播。

新增 ticker：新增 `libs/sec_revenue/parsers/newissuer.py` 的 `IssuerParser` 子類別，在 registry 登記 module、class、實際目標期別、主要 basis 和 reference metadata。公司規則在自己的 class：`rules` 精確 concept／完整 dimensions／unit；`aliases` 具日期限制；必要時覆寫 `normalize`、`pool`、`categories` 或 `parse`，保留規則 ID 與所有 SEC 運算元。加入 hash 可驗證的 SEC facts cache／原始來源與獨立回歸測試；新來源可在該 ticker 的 registry 設定 `facts_cache_path`、`facts_cache_sha256`，不修改既有凍結研究，不修改共用引擎或其他公司 parser。單檔除錯可用 `python scripts/download_sec_source.py --ticker AAPL --period YYYY-MM-DD --accession ACCESSION --url SEC_URL` 或 `SecDownloadEngine(EvidenceStore(...), SEC_USER_AGENT)`；這個單檔除錯入口不建立批次索引，日常請用 `sec_pipeline.py download`。需真實聯絡資訊，單次 GET 拒絕即停止。主要離線路徑不需要此設定。

新架構實測與限制見 [驗證紀錄](docs/architecture/cloud-engine-verification.md)，資料契約見 [引擎契約](docs/architecture/sec-engine.md)。風險是 parser 維護風險；依最近兩次 schema 變化、實際特殊規則、缺值與缺原始 bytes 計分。已見期間回溯，不是盲測，也不代表完整披露召回率；原跨來源 29/30 與固定供應商 24/30 成績不變。
