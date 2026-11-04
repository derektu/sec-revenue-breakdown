# Taxonomy 版本橋接：64 組受限回溯實驗

本輪接續[原始 SEC 共用解析實驗](SHARED_RAW_SEMANTICS.md)，只處理其中因 extension namespace 換版而拒絕相減的 **64 組 FY／九個月 scope**。從 TSLA、CMCSA、UNH、NEE 已固定的八份歷史原始 filing、40 份 schema／linkbase 重新取證，沒有下載新資料或接觸 vendor 原始資料。

結果為 **23 組通過本輪橋接證據契約、41 組仍需覆核**。通過只代表此兩份來源可在這組條件下作版本對應與算術；尚未認證業務口徑延續、重編、互斥分類或完整營收組成。全部是已接觸的歷史回溯，未見測試為零。

## 程式與可重現證據

- [taxonomy_bridge.py](../scripts/taxonomy_bridge.py)：原始 schema、標籤、定義、階層、scope 與來源檢查，通過後才做相減。
- [逐組證據](../research/taxonomy-bridge/results/cases.json.gz)：每組 annual／YTD fact IDs、兩側 schema 屬性、各 label role 和語言、documentation、definition 路徑、直接父子鄰接、presentation 鄰接及 preferredLabel、鄰接自訂節點的 schema／定義、原表列名、來源 URL／SHA-256、拒絕原因與算術結果。
- [摘要](../research/taxonomy-bridge/results/summary.json)、[七個代表案例](../research/taxonomy-bridge/review-cases.json)、[時間紀錄](../research/taxonomy-bridge/effort.json)。代表案例由 agent 檢視原始證據後建立，沒有獨立人類標記者。
- [離線驗證收據](../research/taxonomy-bridge/verification.json)：禁止網路，重讀原始 SEC 檔後比對完整語意輸出，排除處理時間；全部 **81 項測試通過**，包括新增 15 項橋接測試及既有 66 項測試。

使用 Python 3.12、`lxml==6.1.1`，從 repo 根目錄執行；目的地必須不存在：

```sh
python3 scripts/taxonomy_bridge.py --out /tmp/新的版本橋接結果
python3 scripts/verify_taxonomy_bridge.py --report /tmp/新的版本橋接驗證.json
```

固定輸入沿用 `research/shared-raw-semantics/manifest.json`、原始壓縮檔及先前 `q4-evidence.json`，全部雜湊驗證。沒有改寫上一輪收據或自動放寬原 parser 的 namespace 規則；這是獨立的附加驗證實驗。

## 橋接契約

先根據上一輪已保存的 64 組候選取出完整 fact，**不依數字挑配對**，檢查所有重複揭露的 annual × YTD 配對；任一配對不符就保留整組待查。僅支援原本 lexical QName 相同的候選，不自動改大小寫、改名或移除維度。

1. 原始來源須為 SEC HTTPS，兩側 context 的 CIK identifier／scheme 須相同且對應來源 URL 的公司；保留 LegalEntityAxis，不能用法人數字取代營運分部。
2. 幣別、完整 concept、完整 dimensions、財年起日及 FY／YTD9 期間相容，兩側都必須通過上一輪收入 fact 擷取條件。期間末相差須在單季範圍。
3. 版本不同的自訂 member 須由各自 filing 的本地 schema 宣告，namespace 的擁有者一致、日期對應該來源申報期；比對 type、substitutionGroup、periodType、balance、abstract、nillable。
4. 保留同一 XLink label 對應的**全部**資源，檢查標準英文 label、documentation 與各 label role／語言集合。缺定義或新增／不同 label-role 都不自動通過。定義有時只是名稱重述，並非獨立業務定義證明。
5. 對指定軸檢查 definition 的 axis→domain→member 路徑及 member 的直接父子鄰接；角色 URI 集合與角色內結構都要求一致。同時比對 presentation 鄰接與 preferredLabel。涉及 prohibited、非零 priority、跨 targetRole 或過於複雜的圖則拒絕；不聲稱已實作完整 effective DTS。
6. 對路徑及鄰接自訂節點也比對 schema／labels／documentation。小計自身定義不變，但子項定義改變時仍會拒絕；標準鄰接節點的 namespace 必須維持一致。
7. 原始表格在第一個數值 fact 之前的列名須非空且相同；未標記表格、敘述內數字或沒有列名的重複項不猜測配對。這個簡單守門也可能拒絕格式不同但語意合理的揭露。

最後才檢查重複值是否矛盾，再做 annual 減 YTD。橋接決定不讀取 fact 金額，也不讀取舊基準數值。後續數值比較只作回歸檢查，不回頭影響是否橋接。

## 實測結果與覆核負擔

| 公司 | 2025 主要期：有條件支持 | 2025 主要期：需覆核 | 2024 比較欄：有條件支持／需覆核 |
|---|---:|---:|---:|
| TSLA | 11 | 1 | 11／1 |
| CMCSA | 0 | 25 | 0／25 |
| UNH | 12 | 10 | 12／10 |
| NEE | 0 | 5 | 0／5 |
| 合計 | 23 | 41 | 23／41 |

64 組的變動都涉及自訂維度 member；原始候選合計涉及 36 個不同自訂 member。沒有真實的自訂 revenue concept 或自訂 axis 橋接正例，因此不能推論這兩類也已驗證。23 組支持只涉及 13 個不同 member 對應，UNH 的 ExternalCustomers／Intersegment 在不同完整 scope 重複出現；不是 23 個獨立業務定義，其中七組推算結果是零。

2024 部分使用的是 **2025 Q3／FY 原始文件中的 2024 比較欄**，仍由這兩份來源各自的 taxonomy 描述。它不是額外取得的原始 2024 taxonomy，也不是獨立測試樣本或新公司的泛化證據。兩個年度各 23 組算術結果與既有 SEC 基準同 scope 候選相同；基準也來自相關原始資料，故這只是數值回歸一致，不能當作獨立語意正確率。其餘 41 組不產出橋接算術答案。

拒絕原因可能重疊：41 組 definition／presentation 證據未完全相同，六組有某個重複揭露缺表格列名，五組 label-role 集合不同，五組有鄰接節點 metadata 差異。將**階層差異**分開後，36 組只有角色集合／名稱不一致，五組另有共用角色內的鄰接變化；這個「只有」僅描述階層比較，不能理解為其他所有 metadata 都相同。

- **TSLA 汽車銷售**：兩側自訂 schema、標準 label／documentation、ProductOrServiceAxis 路徑、父子鄰接及列名一致，可建立此版本對應。FY 65,821 百萬減九個月 49,071 百萬，得到 16,750 百萬；數字是在通過證據條件後才計算。
- **TSLA 能源銷售明細**：FY 新增 AdditionalInformation 揭露角色，原本共用角色沒有偵測到鄰接變動。嚴格契約仍拒絕；不能把拒絕說成收入意義已改變。
- **UNH 外部客戶／產品**：完整產品與客戶 scope 保留，相關自訂 member 的 metadata／鄰接一致，可作受限橋接。
- **UNH Total Optum**：標籤／documentation 完全相同，但共用 SegmentFinancialInformationDetails 角色的子 member 在 Q／FY 有大小寫變化。五組相關 scope 留待覆核，不自行推斷改名等價。
- **CMCSA**：季度的 SegmentInformationScheduleofSegmentInformationDetails 與年度的 SegmentInformationReportableSegmentDetails 等角色不同，年度又新增其他揭露角色。可能只是格式／命名差異，仍需具體角色對照證據；25 組全部保留。
- **NEE**：FPL 基本定義仍是全資子公司，但 label-role、角色名稱與集合不同；NEER 的基本定義也相同，年度角色卻不同。五組保留，沒有以 FPL 法人與分部金額相同橋接。

本輪沒有新增逐公司橋接 alias 或角色改名表；這不表示消除了既有公司的 selector／aggregation 維護。恰好相反，36 組僅因角色集合差異而拒絕，呈現「共用、保守守門」如何把工作轉成覆核成本。下一輪若加入角色別名，應記錄每份對照證據與規則數，並凍結後另選尚未用於調整的資料。

## 負向測試、時間與侷限

新增測試在原始真實案例上進行受控變異，明確區分真實差異與合成負例：

- 把 64 組的兩側數字都改成相同值，所有橋接決定保持不變；改數字只影響通過後的算術。
- 標準 label、documentation、schema type、definition 父子、presentation preferredLabel 改變，或缺定義、prohibited 關係，均會拒絕。
- 即使小計自己的 label／定義沒變，直接子項定義改變仍拒絕。
- 同額的成本／收入、實體不同、兩側同用錯誤 CIK、完整 dimensions 缺漏、財年起日不同、非 SEC 來源或 namespace owner 不同，仍拒絕。
- 重複 facts 的數字相互矛盾時，保留語意證據判定，但不計算 Q4。

整個資料處理執行的實測秒數在 summary，禁止網路重播與回歸測試時間在 verification。[effort.json](../research/taxonomy-bridge/effort.json)記錄建立此分支到時間收據的 agent wall clock，包含程式、原始證據檢視、試跑、測試及文件，不等於人類工時或每組審查時間。獨立人類參與觀測為零，**41 組真正需要的人類覆核工時仍未量測**；不以 agent 時間換算人類成本。

尚未處理原先 29 組缺同 scope YTD、改名 member 的完整映射、自訂 axis／concept 的真實橋接、跨來源重編或業務定義變更、外部完整 DTS、文字附註與未標記表格，也沒有重新裁決 TradingView／富途／Stock Analysis 的粒度。23／64 是這份已接觸資料在特定保守契約下的通過數，不能稱盲測準確率、一般可橋接率或 1,500 家成本估計。
