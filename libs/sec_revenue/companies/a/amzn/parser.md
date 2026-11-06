# AMZN parser

## 觀點

產品與服務別（`view="product"`），共 7 類：Online stores、Physical stores、Third-party seller services、Advertising services、Subscription services、AWS、Other。

| 對照來源 | 拆分 |
|---|---|
| Stock Analysis | 同樣的 7 類 |
| TradingView | 同樣的 7 類 |
| 富途 | 營運分部：North America、International、AWS |

兩個來源用產品與服務別，所以採用這組拆分。營運分部中 North America 與 International 以地區劃分，不採用。

AMZN 另有兩種營收拆分，都不採用：

| 拆分 | XBRL 維度 | 不採用的原因 |
|---|---|---|
| 商品／服務（`us-gaap:ProductMember`、`us-gaap:ServiceMember`） | `srt:ProductOrServiceAxis` | 對照來源不用；與 7 類同一個軸，但是另一層拆分 |
| 國家（US、DE、GB、JP、Non-US） | `srt:StatementGeographicalAxis` | 地區拆分，且只在 10-K 揭露 |

## 分類與 tag

concept 是 `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`，帶 `srt:ProductOrServiceAxis`：

| 分類 | 成員 |
|---|---|
| Online stores | `amzn:OnlineStoresMember` |
| Physical stores | `amzn:PhysicalStoresMember` |
| Third-party seller services | `amzn:ThirdPartySellerServicesMember` |
| Advertising services | `amzn:AdvertisingServicesMember`（10-Q）或 `us-gaap:AdvertisingMember`（10-K） |
| Subscription services | `amzn:SubscriptionServicesMember` |
| AWS | `amzn:AmazonWebServicesMember` |
| Other | `amzn:OtherServicesMember` |
| 總營收（Consolidated） | 不帶維度 |

- Advertising services 在 10-K 與 10-Q 用不同的成員，數字是同一列，所以 parser 在每份申報都找這兩種寫法。Q4 的年度運算元來自 10-K 的 `us-gaap:AdvertisingMember`，九個月運算元來自 Q3 10-Q 的 `amzn:AdvertisingServicesMember`。
- `categories` 每一天都是這 7 類。
- 7 類加總等於總營收，沒有調節項。
- 分類名稱取自營收附註表的列標籤（去掉註腳編號）；總營收取自同表的 `Consolidated`。

## 期別與推算

- 財年即曆年，季末日是 3、6、9、12 月的最後一天。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同年 Q3 10-Q 的九個月累計。年度與 Q1–Q3 的分類相同，範圍內每個 Q4 都推算。
- FY：10-K 的年度 fact。

## 數字在原文的位置

附註的產品與服務別營收表（`Net Sales:` 段），7 類與 `Consolidated` 同表。Q1–Q3 與 FY 每期一張表；Q4 為 10-K 與 Q3 10-Q 各一張。

## 驗證

11 季（2024-03-31 至 2026-09-30）與 2 個年度，與對照資料逐期比對：

| 來源 | 結果 |
|---|---|
| Stock Analysis | 11 季 7 類全部在顯示精度內 |
| TradingView（只有年度） | FY2024、FY2025 7 類都在顯示精度內 |
| 富途 | 只有營運分部，沒有可比的分類 |

- FY 序列：FY2024、FY2025 都等於同財年四季加總。
- 沒有差異標記：各申報的比較欄與已上線輸出都在精度內相同。
