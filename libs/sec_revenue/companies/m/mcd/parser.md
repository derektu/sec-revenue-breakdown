# MCD parser

## 觀點

營收類型（`view="product"`），共 3 類：Franchised restaurants、Company-owned and operated restaurants、Other revenues。

| 對照來源 | 拆分 |
|---|---|
| TradingView | Franchised Restaurants、Company-owned and Operated Restaurants、Other（2020 年起） |
| 富途 | 營運分部：U.S.、International Operated Markets、International Developmental Licensed Markets & Corporate |

對照資料沒有 Stock Analysis 的 MCD 分類。MCD 的三個營運分部以地區劃分。地區拆分不是觀點，所以不採用，改用損益表的營收類型，與 TradingView 相同。

## 分類與 tag

三類與總營收都是損益表上不帶維度的 fact：

| 分類 | concept |
|---|---|
| Franchised restaurants | `mcd:Revenuesfromfranchisedrestaurants` |
| Company-owned and operated restaurants | `mcd:SalesbyCompanyoperatedrestaurants` 或 `mcd:SalesByCompanyOwnedAndOperatedRestaurants`（兩種寫法都找） |
| Other revenues | `mcd:OtherRevenues` |
| 總營收（Total revenues） | `us-gaap:Revenues` |

- 直營餐廳營收在申報之間來回使用兩個自訂 concept：10-K 與 Q1 10-Q 用 `mcd:SalesbyCompanyoperatedrestaurants`，Q2、Q3 10-Q 用 `mcd:SalesByCompanyOwnedAndOperatedRestaurants`。兩者是損益表同一列，所以兩種寫法都找；同一份申報兩種寫法都有時，數值必須在精度內一致。
- 三類加總等於總營收，沒有調節項。各期差距在 1 百萬美元以內（各列分別四捨五入）。
- 分類名稱取自損益表的列標籤，`Revenues from franchised restaurants` 與 `Sales by Company-owned and operated restaurants` 去掉前綴；總營收取自 `Total revenues`。

## 期別與推算

- 財年即曆年，季末日是 3、6、9、12 月的最後一天。
- Q1–Q3：10-Q 中三個月期間的 fact。
- Q4：10-K 年度減去同年 Q3 10-Q 的九個月累計。年度與 Q1–Q3 的分類相同，範圍內每個 Q4 都推算。
- FY：10-K 的年度 fact。

## 數字在原文的位置

損益表的 `REVENUES` 段，三類與 `Total revenues` 同表。Franchised restaurants 在 10-K 另見於加盟營收附註（Rents、Royalties、Initial fees 的合計）。Q1–Q3 與 FY 每期一張表；Q4 為 10-K 與 Q3 10-Q 各一張。

## 驗證

10 季（2024-03-31 至 2026-06-30）與 2 個年度。2026 年 Q3 10-Q 尚未申報。

| 來源 | 結果 |
|---|---|
| TradingView（只有年度） | FY2024、FY2025 三類都在顯示精度內 |
| 富途 | 只有營運分部，沒有可比的分類 |

Q 序列沒有對照資料，以下列方式檢查合理性：
- 每季三類加總與總營收的差距都在 1 百萬美元以內。
- FY2024、FY2025 都等於同財年四季加總（各類差距 1 百萬美元以內，各列分別四捨五入）。
- Franchised restaurants 占總營收的比例各季穩定，沒有跳動。
- 沒有差異標記：各申報的比較欄與已上線輸出都在精度內相同。
