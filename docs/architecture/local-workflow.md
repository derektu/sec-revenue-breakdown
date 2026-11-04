# 本機分階段操作

這條正式路徑將下載與萃取分開。`download` 不產生營收輸出；`extract` 不連網，只讀已下載的 SEC 原文；`viewer` 只讀萃取輸出。沒有前端編譯步驟，Python 3.11+ 與 lxml 即可執行。

## 拉取與安裝

在本機 repo 先檢查 `git status`，保留既有未提交工作，再安全切至 main 並同步：

```bash
git fetch origin
git switch main
git pull --ff-only origin main
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

以下命令都從 repo 根目錄執行；省略 `--data` 時使用 `data`。macOS 可直接用 `.venv/bin/python`，不需啟動 Node／npm。

## 支援的 ticker 清單

`libs/sec_revenue/registry.json` 是支援清單，包含獨立 parser、CIK 與 reference metadata。可用自己的子集合檔案，不需改程式：

```bash
.venv/bin/python scripts/sec_pipeline.py tickers
.venv/bin/python scripts/sec_pipeline.py tickers > tickers.local.txt
```

編輯 `tickers.local.txt`，一行一個 ticker，可加 `#` 註解；也接受逗號分隔，或 `.json` 的字串清單。`tickers.local.*` 已忽略，不會推上 Git。

所有 download／extract 都接受 `--tickers AAPL MSFT CVX`、`--tickers AAPL,MSFT` 或 `--ticker-file tickers.local.txt`。兩者同時提供時取去重後聯集；省略或 `--tickers ALL` 表示全部支援公司。不支援的 ticker 在發出請求前就拒絕。

## 下載 SEC 申報

首次連網請先在該終端設定 **SEC_USER_AGENT** 環境變數，內容為真實姓名／組織與聯絡 email。程式不提供假身分、不保存帳密，也不把身分寫入快取。純快取／`--offline` 與萃取不需要此設定；線上 `--latest` 刷新仍需要。

```bash
# 選定 ticker、實際申報期範圍；已有且 hash 正確的原文直接沿用
.venv/bin/python scripts/sec_pipeline.py download --ticker-file tickers.local.txt --start 2025-01-01 --end 2026-11-04

# 刷新 SEC submissions，下載每家公司最近一期；既有原文仍可 cache hit
.venv/bin/python scripts/sec_pipeline.py download --ticker-file tickers.local.txt --latest

# 從指定起日更新到最新：抓取該範圍內所有期別，不只最後一期
.venv/bin/python scripts/sec_pipeline.py download --tickers AAPL MSFT --start 2025-01-01 --latest

# 強制刷新索引並重抓指定原文；不同 bytes 留存為不同 hash 版本
.venv/bin/python scripts/sec_pipeline.py download --tickers AAPL --start 2025-01-01 --end 2026-11-04 --force

# 完全不連網，只驗證並沿用既有索引與原文；缺任何必要檔案即失敗
.venv/bin/python scripts/sec_pipeline.py download --tickers AAPL --latest --offline
```

`--start`、`--end` 為包含邊界的 `YYYY-MM-DD`，依 SEC **實際 reportDate** 選擇，不能把零售 52／53 週季末硬改成曆季末。沒有日期範圍時只選最新一期。`--latest` 在線上會刷新 SEC 索引；離線時只表示「本機已知最新」，輸出的 `catalog_source` 明列來源。一般未加 `--latest`／`--force` 時可沿用本機 catalog；若指定範圍超出 recent 覆蓋，會補 SEC 歷史 submissions 分頁。

「最新」一般以已申報的 10-K／10-Q（含修訂）為準。CAT、UPS 已審閱的 2026Q3 8-K earnings exhibit 另有公司規則，把事件日與實際收入季度分開。並非所有新 8-K 都可自動視為新季度財報；未建立規則的披露不能冒稱已支援。新 tags 或表格架構不符時會拒絕萃取。

年度 Q4 自動納入同一實體的上一季 YTD9。BAC 2025 與 UPS 2024 的已審閱比較欄依賴由各自 parser 額外宣告。PGR 年報會從 filing index 找到唯一合併 Exhibit 13，不能拿 parent-only 10-K 代替。輔助申報會標 `dependency: true`，不會因下載了依賴檔就把它變成使用者要求的目標期別。

單次正常 GET、至多每秒五次；403／其他拒絕立即停止，不重試或換身分。已成功的 bytes 保留。附件下載中斷的文件組會明標未完成，萃取拒絕混用新舊附件；之後重跑可續用已完成的同組檔案。

## 萃取營收

```bash
# 只萃取下載快取中指定 ticker／實際期別範圍
.venv/bin/python scripts/sec_pipeline.py extract --ticker-file tickers.local.txt --start 2025-01-01 --end 2026-11-04

# 只萃取每家公司已下載的最新目標期；這一步不查 SEC
.venv/bin/python scripts/sec_pipeline.py extract --ticker-file tickers.local.txt --latest

# 強制重新讀原文、解析與計算，不重抓原文
.venv/bin/python scripts/sec_pipeline.py extract --tickers AAPL --start 2025-01-01 --end 2026-11-04 --force
```

來源集合、filing metadata 與規則 fingerprint 相同且上次成功時，顯示 `cache_hit` 並跳過萃取。原文／accession／規則變動會失效，缺輸出會重建；hash 不符則拒絕。公司自己的規則指紋不包含其他公司的模組，改 AAPL 不會使 MSFT 的 cache 失效。共用引擎或該公司可用比較欄變動時可使該公司的既有萃取失效，避免沿用過時 Q4／重編口徑。

一家公司有多個 basis 時逐一產生。CVX 預設 net，gross 與抵銷另存。新原文流程的 XOM 固定使用可完整對帳的 all-income 分部及扣回欄，另存 `basis_description`；舊研究為參考網站 Q2 使用的 gross 欄位例外只留在歷史重播，不暗中套用於新的資料。

CVX net 與 XOM all-income 另有明確成分對帳：差額只在所有 SEC 申報運算元的精度界限內接受，保留差額與允許精度，不修改原始數字。

缺值、歧義、未知表頭／scope、缺 Q4 運算元或原文解析失敗時，輸出保留 null、錯誤與風險，不以舊研究答案或零補齊。CLI 回傳碼：`0` 成功或 cache hit；`1` 下載／輸入／快取驗證失敗；`2` 萃取已有可供檢查的部分結果，但仍有缺值或失敗。失敗結果不視為成功 cache，下一次仍會嘗試萃取。

## Viewer

```bash
.venv/bin/python scripts/sec_pipeline.py viewer --host 127.0.0.1 --port 8765
```

從同一台本機瀏覽器開啟 <http://127.0.0.1:8765>。ticker、期間與 basis 選單來自現有輸出，不限制固定八期。未下載／未萃取的公司回報無資料；已有成功歷史期不因本次只萃取某一季而從索引消失。頁面可看完整 SEC 運算元、申報精度、風險及來源格式。

可選 Playwright UI 測試（先安裝 `playwright`，並使用本機 Chromium 或執行 `python -m playwright install chromium`）：

```bash
.venv/bin/python scripts/check_sec_viewer_ui.py --tickers AAPL MSFT CVX
```

## Cache 與版本

| 路徑 | 內容 |
|---|---|
| `data/sec/TICKER/PERIOD/ACCESSION/HASH.html` | 真正下載的原始 HTML bytes 與 hash 收據 |
| `data/sec/TICKER/_metadata/CIK/HASH.json` | SEC submissions 原始 JSON |
| `data/sec/TICKER/PERIOD/ACCESSION/HASH.json` | SEC filing index 等原始 JSON，格式明列 `sec_json` |
| `data/pipeline/TICKER/catalog.json` | 可驗證的申報清單與 metadata 來源收據 |
| `data/pipeline/TICKER/downloads.json` | 目標期別、依賴檔及目前選用的原文版本 |
| `data/pipeline/TICKER/extractions.json` | 各期 fingerprint、成功／失敗與輸出 hash |
| `data/outputs/TICKER/PERIOD/TICKER_PERIOD_BASIS_revenue.json` | 固定命名的目前輸出 |
| `data/outputs/TICKER/PERIOD/versions/FINGERPRINT/...` | 不同來源／規則的歷史萃取版本 |

以上產物皆不推 Git。一般 SEC 下載不依賴 `data/vendor/local`；不會拿第三方內容替代 SEC。舊 `replay_sec.py` 與 30 家／240 期凍結回歸繼續保留，與新原文流程分開測試；歷史重播請指定 `--out data/engine-check`，不要用相同 `data/outputs` 覆蓋新的原文萃取結果。先前「250 份缺 HTML」指雲端 checkout 沒有保存原文，不代表 SEC 沒有該申報；這個新 download 流程就是用來取得並持久保存原文。
