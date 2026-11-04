# 原始 SEC 共用語意解析：受限回溯實驗

本輪的可交付成果是可離線執行的程式、固定原始證據及失敗時保留歧義的判定，不只是報告。研究對象為 TSLA、CMCSA、UNH、NEE 的 2025 Q3 與 FY2025，共八份真實 filing。這些公司及歷史期間已參與研究，**未見測試為零**。尚未建立能自動選擇完整營收組成的 parser，也沒有 1,500 家準確率或人力成本估計。

## 證據與執行

- 程式：[shared_raw_semantics.py](../scripts/shared_raw_semantics.py)、[既有規則比較](../scripts/compare_shared_semantics.py)、[離線驗證入口](../scripts/verify_shared_semantics.py)。不讀取本機 vendor 原始資料。
- [來源清單](../research/shared-raw-semantics/manifest.json)：八份 HTML 的來源 URL、申報日期與 SHA-256，全部符合先前 30 家基準。另固定各 filing 的 extension schema 和 calculation、definition、label、presentation linkbase，共 48 個 SEC 原始檔；原始位元組以 gzip 保存在 `research/shared-raw-semantics/sources/`。不下載外部 taxonomy imports。
- [實際結果](../research/shared-raw-semantics/results/summary.json)：每份壓縮 JSON 含所有數值 facts、原始列文字、可解回 HTML 的 XPath、fact ID、期間、實體 identifier、完整 dimensions、namespace、單位及關係的來源雜湊。不是只有已挑選的正例。
- [逐列查核契約](../research/shared-raw-semantics/review-cases.json)：40 個 fact 案例、五個 taxonomy 父子案例、一組同額但不同 scope 的案例。這是 agent 依原始列、concept 與 context 進行的定向查核，沒有獨立人類標記者，也不是隨機準確率樣本。
- [驗證收據](../research/shared-raw-semantics/verification.json)：禁止網路重跑八份原始檔，對比保存輸出的全部語意內容（只排除處理時間），並執行 66 項測試，全部通過。54 項 repo 測試包含新增的 10 項實驗測試，另 12 項為既有 recovered parser／季度測試。

從 repo 根目錄，以 Python 3.12、`lxml==6.1.1` 執行，不需 SEC 連線或供應商資料：

```sh
python3 scripts/shared_raw_semantics.py --out /tmp/新的共用解析結果
python3 scripts/verify_shared_semantics.py --report /tmp/新的離線驗證收據.json
```

兩個目的地都必須尚未存在。固定原始來源已隨 repo 保存，不依賴雲端 cache。首次取得支援檔時 SEC 回傳一次 HTTP 503；中止後保留已得檔案，只補抓缺檔，來源清單已記錄此例外。

## 共用判定的實際邊界

收入性質使用八個明確標準 revenue concepts，成本使用四個標準 cost concepts，且檢查 namespace。公司自訂 concept、其他收入相關 concept 不因名字含 revenue 就通過；例如遞延收入轉列只表示一部分收入的來源，不是可與全額收入並列加總的獨立組成。營業利益保留為 abstain。這個有限白名單仍須持續維護，沒有涵蓋銀行、保險與所有其他產業的收入定義。

數字同時檢查支援的 transformation、scale、sign、幣別及 duration context；未知 transformation、缺 context、typed dimension、非維度 segment/scenario 等直接保留拒絕原因。Q、九個月 YTD、FY 各自保留，沒有把九個月當單季。週制財年僅以寬 duration 分桶，尚未建立 12／16 週日期映射；不能拿這些桶直接替代供應商的季度日期裁決。

definition 的 domain-member 路徑只用來提出小計／明細重疊警告。presentation 及 calculation 原始關係均保留；presentation 順序不當成互斥分類，也沒有把 credit balance 當作收入證明。這不是完整 DTS、effective relationship、default dimension 或 hypercube 驗證器；跨 targetRole 的階層未完整解析，沒有警告也不代表沒有重疊。

calculation 只嘗試同完整 context、同 unit 的收入等式，且避開優先權或 prohibited arc 的複雜集合。本樣本沒有取得可通過這個受限條件的完整收入等式。UNH 的收入 calculation 需要的 customer revenue 在原始 facts 中依產品維度拆列，不能靠忽略維度把等式補齊。即使未來等式成立，輸出也只會標成算術證據，不認定供應商分類語意正確。

**全樣本自動認證的完整分類組合為零。**「admissible revenue」只表示符合目前收入 fact 擷取契約，可能包含總額、小計、明細、外部收入、內部收入等，彼此不可直接混加。

## 原始重跑與既有規則比較

13,305 個數值 fact occurrences 中，843 個通過受限收入契約、64 個通過受限成本契約；含歷史比較欄及重複揭露，不是獨立季度或正確分類數。其中收入有 503 個多軸 occurrences、22 個含 LegalEntityAxis，產生 23 個跨角色父子重疊警告。

舊 extractor 在同八份原始檔共產出 1,339 個 revenue/sales 名稱候選：843 個屬目前收入集合、57 個成本、439 個目前 abstain。這 439 個不能全部稱為錯誤，它們包含有限白名單尚未覆蓋的語意。所有兩者可解析的數值相同；改善是語意分流，並非改數字湊參考值。

| 公司／申報 | 舊名稱候選 | 本輪收入 | 本輪成本 | 父子警告 | 既有 catalog term：找到／缺完整 scope | 解析秒數 |
|---|---:|---:|---:|---:|---:|---:|
| TSLA 10-Q | 231 | 84 | 32 | 7 | 5／0 | 0.179 |
| TSLA 10-K | 185 | 64 | 25 | 7 | 5／0 | 0.209 |
| CMCSA 10-Q | 182 | 176 | 0 | 3 | 12／0 | 0.109 |
| CMCSA 10-K | 156 | 144 | 0 | 0 | 12／0 | 0.207 |
| UNH 10-Q | 255 | 172 | 4 | 3 | 4／0 | 0.142 |
| UNH 10-K | 219 | 132 | 3 | 3 | 4／0 | 0.290 |
| NEE 10-Q | 48 | 36 | 0 | 0 | 3／1 | 0.268 |
| NEE 10-K | 63 | 35 | 0 | 0 | 3／1 | 0.445 |

此處 term 是現有 catalog 每個來源、label、alternative 的單一葉項出現次數，八份合計 50 次，48 次有完整 scope 候選、NEE 兩次缺少一個替代 scope；缺替代不代表整個 label 一定失敗。它不是原先四家公司實驗的「48 個 Q/FY selectors、8 條聚合」相同統計口徑，也不表示把那些規則減成零。本輪新 parser 沒有 ticker 分支，但仍借用既有 catalog 做比較，沒有刪除或取代逐公司規則。

- **Tesla**：Q／FY 原始檔分別有 32／25 個 CostOfRevenue 被舊名稱過濾收進收入候選；同一個「Automotive sales」列名可出現在收入區和成本區，應以完整 concept 判斷。taxonomy 可找出 AutomotiveRevenuesMember 下的 sales、credits、leasing，避免把小計與明細平加。產品口徑和汽車營運分部仍是不同選擇；本輪不替使用者選 vendor。
- **UNH**：definition 可找出 TotalOptumMember 下三子部門。Q 與 FY 的子部門 QName 有大小寫變動（例如 OptumHealthMember／OptumhealthMember），保留原字，不以自動改大小寫視為語意等價。既有 catalog 的總 Optum scope 仍能找到，不能因此推論所有明細 selector 都不需維護。
- **NextEra**：Q3 的 FPL 法人與營運分部各有 5,285 百萬收入，完整 context 不同；測試明確要求保留兩筆 scope，不能因同額就橋接。YTD 與 FY 另外存在實體及分部維度變動，原先人工 scope bridge 的必要性沒有被消除。
- **Comcast**：同時保留外部客戶、部門間收入與完整分部維度，Q3 找到 ResidentialConnectivity 的明細重疊。FY 沒有對應警告，不代表無重疊。兩個淨業務群與毛分部仍需要 HQ／抵銷及附註裁決；本輪沒有自動解出先前人工業務群表。

供應商只作參考：[既有來源裁決](vendor/cohort-rule-adjudication.md)中 Comcast 的 HQ／抵銷漏項及 Stock Analysis 季度標籤互換仍適用。本輪比較的是已允許的公開 catalog scopes 與原始 SEC facts，**沒有重新讀取、抓取或逐值驗證 TradingView、富途、Stock Analysis 原始資料**；沒有把既有匿名結果改稱這次新驗證。

## Q4 與 taxonomy 換版

[Q4 證據](../research/shared-raw-semantics/results/q4-evidence.json)將 FY 減九個月的結果另存。要求 entity identifier、幣別、concept expanded QName、完整 expanded dimensions、財年起日相同，並拒絕相互矛盾的重複值。名稱相同但 extension namespace 換版時，標成 `abstain_taxonomy_version_bridge_required`；沒有同 scope 九個月數字則不補零。

| 公司 | 同 scope 算術候選 | taxonomy 版本需裁決 | 缺同 scope YTD9 |
|---|---:|---:|---:|
| TSLA | 4 | 12 | 1 |
| CMCSA | 4 | 25 | 9 |
| UNH | 5 | 22 | 16 |
| NEE | 3 | 5 | 3 |

共 109 組去重的 FY 收入 scope，只有 16 組能在本輪嚴格條件下做同 scope 相減；這 16 組仍未認證財報重編或業務定義連續性。64 組只找到 lexical QName 相同而 expanded namespace 不同的候選，29 組沒有同 scope YTD9。這些拒絕是刻意保守，不能拿 16／109 當季度營收準確率或真實可解析率。也沒有把這 109 組當作互斥分類。

## 時間、維護成本與 1,500 家

機器每份原始檔的解析／關係檢查約 0.1–0.5 秒，不含既有 catalog 比較、首次下載、人工研究、測試或 GitHub 整合。首次下載的可觀測秒數在 manifest；支援檔部分由中斷後 cache 復原，原下載時間未完整記錄，不捏造網路總耗時。[時間紀錄](../research/shared-raw-semantics/effort.json)以本分支開始到記錄時的實際 wall clock 表示 agent 工作時間，不當作人類工時。

本輪沒有獨立人類操作或人工標記者參與，因此已觀測獨立人類工時為 0，**所需人類審查工時尚未量測**。40 個 fact 契約、五個階層契約、一個 scope 對照組由 agent 定向檢視後建立；這些也有維護成本，不把它們隱藏在「共用規則數為零」之下。此輪不能回答每增加一家公司要多少人分鐘。

可共用的部分已具體證明：原始 fact 取證、收入／成本有限集合分流、期間保留、實體與維度不丟失、taxonomy 父子警告、嚴格 Q4 橋接守門及可重現拒絕原因。這些不需要在 parser 加入四家公司專用分支。

擴到 1,500 家仍困難的部分是：自訂 concept 的經濟意義、taxonomy 換版的語意延續、scope 變更與法人橋接、抵銷與重編、供應商選擇的粒度、文字表及未標記細項、週制財年、銀行／保險等不同收入構成。本輪沒有減少既有公司 catalog 的維護責任；證明的是可共用的證據與守門機制，尚未證明可共用的完整分類裁決。

下一個能改變規模判斷的實驗，應固定這版共用程式，對不同公司的 extension 版本橋接與文字表做分開計時，逐項記錄「可自動解決／需一次公司設定／需每季裁決」及錯誤拒絕，而不是再增加同公司同格式正例。若要測未見季度，須另取得尚未用於規則調整的新季度並事前凍結；本輪不主張已完成。
