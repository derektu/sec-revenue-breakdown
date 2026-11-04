# SEC 營收組成研究

這是研究 S&P 500、400 與 600 成分公司 SEC 營收組成的雲端工作區，以先前的 30 家公司、八季實驗為起點。

**目前狀態：**完整的 30 家公司 SEC 候選資料基準已於 2026-11-04 在雲端執行。兩個 SEC 主機皆可連線。全部 234 個可取得季度均已處理，下載錯誤為零；ExxonMobil 的繼受公司 CIK 僅有兩個申報期末，因此缺少六個要求的季度。18 項測試全部通過，來源快照雜湊已驗證，全部 234 季均已完成離線重算。公開 SEC 衍生結果與來源追溯資料已提交；大型原始 HTML 快取仍由 Git 忽略。

另外，本機 Apple DOM 比對回報：Stock Analysis 八季共 40 個數值、Futu 五季共 25 個數值，均與儲存的 SEC 證據相符。這些供應商擷取資料仍保留在 Mac 上由 Git 忽略的路徑；原生 CSV 匯出及更廣泛的供應商資料準確性尚未驗證。通用雲端基準未使用供應商資料作為輸入。

- [已執行的 30 家公司雲端基準與重現方式](docs/SEC_30_BASELINE.md)
- [逐家公司結果](research/sec-30-baseline-2026-11-04/company_summary.csv)
- [全部 240 個要求的季度欄位](research/sec-30-baseline-2026-11-04/quarter_summary.csv)
- [雲端狀態、驗證與阻礙](docs/CLOUD_HANDOFF.md)
- [研究需求、已知問題與後續步驟](docs/RESEARCH_PLAN.md)
- [封存檔識別資訊與來源登錄表](research/sources.json)
- [已復原 SEC 原始碼入口](research/recovered-sec/HANDOFF.md)
- [雲端整合審查](docs/RECOVERED_INTEGRATION.md)
- [雲端驗證證據](research/cloud-verification.json)
- [本機 Apple 參考資料比對與限制](docs/vendor/apple-comparison.md)
- [30 家公司供應商覆蓋情況與候選資料診斷](docs/vendor/cohort-research.md)

## 解析器與執行入口

實際的 inline-XBRL 解析位於 [`research/recovered-sec/extract.py`](research/recovered-sec/extract.py) 的 `parse(path)`，讀取本機申報 HTML 並產生候選資料項。它是基本候選擷取器，並非完整符合標準的 XBRL 處理器或語意解析器；階層、實體範圍、轉換與跨申報語意仍有限制。

- 單份申報入口 [`scripts/sec_single_filing.py`](scripts/sec_single_filing.py) 匯入 `parse`，下載指定 URL 的 HTML 後呼叫 `parse(raw)`。
- 30 家公司八季入口 [`research/recovered-sec/eight_quarter_eval/run.py`](research/recovered-sec/eight_quarter_eval/run.py) 同樣匯入 `parse`，在 `run_company(company, cutoff)` 逐份取得 HTML 後呼叫 `parse(path)`，再進行季度推導與候選分組稽核。

234 季離線重播是從已保存的解析結果重算季度資料項、Q4 運算元與分組，**不是重新解析全部原始 HTML**。方法與限制見[八季實驗繁體中文譯文](research/recovered-sec/eight_quarter_eval/README.zh-TW.md)；封存原文保留不變，目前操作方式見[交接文件](research/recovered-sec/HANDOFF.md)。

所有雲端來源完整性檢查與合成測試，請使用 Python 3.12 及復原環境所用的 `lxml==6.1.1` 相依套件：

```sh
python3 scripts/verify_recovered.py
```

若僅執行暫存工具及其測試，Python 3.11+ 即可，不需額外套件或網路：

```sh
python3 -m unittest discover -s tests -v
python3 scripts/stage_archive.py /path/to/eight_quarter_reproducible_results.zip
python3 scripts/stage_archive.py /path/to/eight_quarter_reproducible_results.zip --extract
```

第一個封存檔命令只做稽核。`--extract` 會在由 Git 忽略的 `data/staging/` 下建立新目錄；不會執行匯入的程式碼，也不會更新 Git。將公開 SEC 證據及經審查的程式碼納入追蹤中的研究目錄之前，應先檢查暫存檔案。受限制的供應商資料、瀏覽器狀態、憑證、大型快取與原始封存檔暫存內容均排除於 Git 之外。
