# SEC 營收組成研究

研究 S&P 500、400、600 公司的 SEC 營收組成，從三十家公司、八季實驗開始。
程式、公開 SEC 結果及查核文件保存在 repo；第三方原始參考資料留在本機忽略目錄。

2026-11-04 雲端已執行三十家公司候選基準，兩個 SEC 主機均可存取，234 個可得季度零下載錯誤，
來源快照雜湊及離線重播已驗證。XOM successor CIK 只有兩個截止日，因此缺六個要求季度。
這是候選基準，不是完整組成資料或跨公司準確率。

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
