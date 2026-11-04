# SEC 營收組成可行性實驗（繁體中文譯文）

> 本文件為相鄰 [README.md](README.md) 的繁體中文譯文。原文是受 recovery-manifest SHA-256 驗證保護的歷史封存資料，原檔與雜湊保持不變。以下命令與敘述保留當時情境；`download.py` 未匯入目前套件，目前操作入口請見 [HANDOFF.md](HANDOFF.md)。

實驗執行於 2026-11-03，使用 Python 3.12.14。這是實際下載原始申報文件並執行程式碼的實驗，不是文獻回顧。它是**經人工篩選的確定性擷取基準**，並非已完成的自動化 LLM 基準測試。刻意選用歷史 2024 年申報，作為小型、可重現的先導實驗，並非最新財務資訊。

## 觀察結果

- 已直接使用 Python urllib 成功下載三份原始 SEC HTML 申報文件。精確 URL、位元組長度與 SHA-256 雜湊見 `data/manifest.json`。
- Apple FY2024 10-K：1,503,892 位元組。Amazon FY2024 10-K：1,922,467 位元組。Amazon Q3 2024 10-Q：1,385,053 位元組。
- 廣泛的 revenue/sales 概念擷取分別回傳 91、91 與 94 個候選資料項，這些候選均無數值解析錯誤。這不是精確率指標：廣泛正規表示式刻意也會擷取備供出售證券等誤收項目。
- 選取精確合併營收概念、精確 contexts 與人工篩選的維度成員後，保留 124 個組成項目期間觀察值。
- 全部 26 個產品／服務、營運部門與地理分組期間加總，均精確符合其對應合併營收。每份 10-K 包含三個比較年度；10-Q 包含本期／前期季度，以及本期／前期 YTD 期間。此次 10-Q 擷取未填入地理資料。缺少的分組不計為成功。
- 三項單元測試通過，涵蓋 scale／正負號／context 保留、相同重複資料合併與衝突重複資料拒絕。負向對照確認：重複組成項目及混合季度與 YTD，不會與季度營收核對相符。

## 資料中的具體發現

以下數值單位為百萬美元，非投資指引。

1. Apple FY2024 產品／服務：iPhone 201,183；Mac 29,984；iPad 26,694；Wearables/Home/Accessories 37,005；Services 96,169。合計 391,035。獨立的 Products 小計 294,866 **不可**再加到上述五個組成項目。
2. Amazon FY2024 產品／服務：Online stores 247,029；Physical stores 21,215；Third-party seller services 156,146；Advertising services 56,214；Subscription services 44,374；AWS 107,556；Other 5,425。合計 637,959。
3. Amazon FY2024 營運部門：North America 387,497；International 142,906；AWS 107,556。合計 637,959。這是同一總額的另一種拆分。AWS 在兩種呈現中都出現，不可重複計算。
4. Amazon Q3 2024 季度營收合計 158,877，九個月 YTD 合計為 450,167。兩者期末相同，因此只依期末日期選取會出錯。
5. Amazon 廣告在 Q3 申報使用 `amzn:AdvertisingServicesMember`，年度申報卻使用 `us-gaap:AdvertisingMember`。即使是同一公司與財政年度，只依名稱或固定公司專屬成員的對應方式仍可能漏掉連續性。
6. Apple 營運部門以地理命名，但獨立地理揭露使用不同的國家分組。分類必須保留揭露的軸與定義，不可只由標籤猜測。
7. Amazon Q3 也包含非合併權益法被投資公司的 `us-gaap:Revenues` 資料項。看似營收的標籤，不足以確認申報實體與範圍。

## 重現方式

從本目錄出發，必要時在合適的 Python 環境安裝 `requirements.txt` 中的相依套件，然後執行：

```
python download.py
python extract.py
python validate.py
python -m unittest -v test_extract.py
```

既有本機下載會重用；只刪除確定要重新取得的檔案。部署 download.py 前，將其 User-Agent 佔位聯絡資訊換成操作者真實且獲授權的聯絡方式，並實作符合 SEC 規範的速率限制／退避等待。不使用帳號憑證。此次先導實驗僅依序發送少量請求，不需安裝作業。

## 產物與來源追溯

- `data/*.html`：完整、不可變的 SEC 來源快照。
- `data/manifest.json`：URL、位元組長度與 SHA-256。
- `outputs/*_facts.json`：候選資料項，含原始概念、維度、單位、原始文字、scale、decimals、context ID、inline fact ID、來源行號、表格索引與來源列文字。
- `outputs/normalized.json`：選取的正規化資料列與營收占比。資料列明確記錄選取使用了人工篩選排除規則。
- `outputs/validation.json`：完整核對結果。
- `outputs/extraction.log`、`validation.log`、`test.log`：實際執行結果。

manifest 透過檔名／申報身分串聯輸出。SEC HTML 經壓縮，`source_line` 可能較粗略；context ID、fact ID、表格索引、列文字與原始快照可提供更好的位置證據。

## 已證明與尚未證明的事項

已證明：此雲端執行環境能取得真實 SEC 申報文件、撰寫／執行 Python、保留維度 contexts 與來源追溯資訊、區分年度／季度／YTD 期間，以及核對選取的分組。

尚未證明：跨公司正式應用的召回率／精確率、自動語意分組、跨時間對應準確性、模型 API 吞吐量／成本／延遲、OCR，或任何代理框架的優越性。未呼叫外部 LLM API，也未要求 API 憑證。分析者是在檢視這些申報後，於 validate.py 選定排除規則；這些規則並非通用解法。

解析器是小型 lxml 基準，**不是完整符合標準的 iXBRL 處理器**。它未解析 calculation/presentation/definition linkbases、分類標準標籤、延續鏈、所有轉換格式、nil 語意、實體範圍變體或精度區間。不支援的數值字串會回報，而非自行解讀。它保留 decimals，但使用精確算術，並非考量四捨五入容許誤差的驗證。核對成功不代表所有揭露均已擷取，也不代表選取的分組在概念上正確。

## 建議的下一個實驗

選擇代理框架前，先評估混合流程：

1. 固定多樣化語料，例如軟體、零售、工業、金融與醫療等 20-30 家公司，每家至少兩年及一份 10-Q。納入重組、重編與收購。
2. 為明確營收類別、範圍、定義、總額、期間與來源位置建立標註真值。部分公司／年度應保留為不參與規則制定的測試資料。
3. 比較符合標準的 XBRL 基準、以模型擷取 HTML 表格／文字的基準，以及混合方法：確定性數值／context 加上模型選表、分類與成員對應。要求引用證據並明確允許放棄判定。
4. 將 `product_service`、`operating_segment`、`geography` 與 `other` 分開。納入父子關係、會計基礎、生效日期、重編旗標與來源。不可合成未揭露的部門乘產品矩陣。
5. 在保留測試集衡量欄位準確性、揭露召回率、證據有效性、放棄判定／人工審查比例、總額核對、去重、期間選取、模型成本與延遲。逐一回報錯誤，不只提供整體加總檢查。
6. 使用敘述性附註區分已報導營收、訂單額 bookings、GMV、ARR、部門間銷售與被投資公司營收。淨額／總額認列對平台交易尤其重要；只靠加總無法驗證。

使用雲端程式代理執行此工作是可行的。關鍵研究問題是在多樣化保留語料上的擷取覆蓋與語意正確性，而非代理是否能執行 Python 或取得這三個檔案。
