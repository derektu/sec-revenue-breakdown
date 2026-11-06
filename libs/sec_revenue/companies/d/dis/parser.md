# DIS parser

## 觀點

業務分部（`view="business_segment"`），採用 Stock Analysis 的分部營收總額觀點，含分部間交易。分類名稱取自 SEC 分部表，順序照 Stock Analysis：Entertainment、Experiences、Sports；Eliminations 列為調節項。總營收 Revenues 取不帶維度的合併 fact。

| 對照來源 | 分類與口徑 | 與採用觀點的對應 |
|---|---|---|
| Stock Analysis | Entertainment、Parks and Experiences、Sports | Parks and Experiences 對應 SEC 的 Experiences；Entertainment、Sports 含分部間交易 |
| 富途 | 娛樂、體驗、體育、抵銷 | 同一分部總額口徑，另列 Eliminations |
| TradingView | Entertainment、Experiences、Sports | Entertainment、Sports 採 Third parties，沒有分部間交易；不是本 parser 的總額口徑 |

只有富途列出抵銷，另兩個來源沒有，因此 Eliminations 依多數規則列為調節項。三類分部營收加 Eliminations 等於合併營收，不另加 Corporate 或 Other。

`us-gaap:StatementBusinessSegmentsAxis` 的成員是娛樂、體驗與體育等業務別，不是地區。申報另有 `srt:StatementGeographicalAxis` 的地區拆分，以及廣告、訂閱、授權、入園等產品或服務別拆分，均不採用。

FY2023 Q2、Q3 原申報仍採兩分部，依各期原文名稱輸出 Disney Media and Entertainment Distribution、Disney Parks, Experiences and Products，沒有調節項。Stock Analysis 對應名稱為 Media and Entertainment、Parks and Experiences。不以之後重編的 Entertainment、Sports 拆回這些季度。

## 分類與 tag

所有分類、調節項與總營收的 concept 都是 `us-gaap:Revenues`。下表完整列出 dimensions；除表列維度外不帶其他維度。

| 分類 | 完整 dimensions |
|---|---|
| Entertainment | `us-gaap:StatementBusinessSegmentsAxis=dis:EntertainmentSegmentMember` |
| Experiences | `us-gaap:StatementBusinessSegmentsAxis=dis:ExperiencesSegmentMember` |
| Sports | `us-gaap:StatementBusinessSegmentsAxis=dis:SportsSegmentMember` |
| Eliminations（調節項） | `us-gaap:StatementBusinessSegmentsAxis=dis:SegmentEliminationsMember` |
| Disney Media and Entertainment Distribution（舊結構） | `us-gaap:StatementBusinessSegmentsAxis=dis:DisneyMediaAndEntertainmentDistributionMember` |
| Disney Parks, Experiences and Products（舊結構） | `us-gaap:StatementBusinessSegmentsAxis=dis:DisneyParksExperiencesAndProductsMember` |
| Revenues（合併總營收） | 無維度 |

`compose` 以 `find(filing, request, REVENUE, {SEGMENT: OLD_SEGMENTS[0][1]})` 查找指定期間的舊分部營收。`find` 將 concept 與完整 dimensions 依該份申報的 namespace URI 比對；回傳不是 `Missing` 時組兩分部，否則組三分部及 Eliminations。數字只由該份申報中符合期間、concept 與完整 dimensions 的 XBRL fact 組成，不讀其他申報或原文數字。

`categories` 在 2023-07-02 起回答三分部加 Eliminations。首份新結構主申報是 FY2023 10-K（0001744489-23-000216，期末 2023-09-30，申報日 2023-11-21），切換日取其 Q4 起日。最後一份舊結構主申報是 FY2023 Q3 10-Q（0001744489-23-000171，期末 2023-07-01）。FY2023 10-K 本身的分部表同時列出新三分部與重列的前兩年度，不把其比較欄當作早期原申報的分類。

`categories` 只涵蓋 Disney Media and Entertainment Distribution／Disney Parks, Experiences and Products 結構以後的分類；更早的 Media Networks 等分部結構不在涵蓋範圍。

預設範圍從實際期末日 2024-03-30 起，各期皆為三分部及 Eliminations，不再切換。前一年度 FY2023 10-K 也能組出三分部，供 FY2024 Q4 的口徑一致檢核使用。

名稱取自 10-Q、10-K 分部表的 Entertainment、Experiences、Sports、Eliminations 列標籤；舊兩分部取自 FY2023 Q2、Q3 分部表。總營收名稱為損益表的 Revenues，採無維度 fact，不採以下帶維度的分部合計：

- 舊 10-Q 的 `us-gaap:StatementBusinessSegmentsAxis=dis:TotalSegmentsMember`。
- 新 10-Q 的 `srt:ProductOrServiceAxis=dis:TotalSegmentsMember`。
- 10-K 的 `srt:ProductOrServiceAxis=dis:TotalSegmentMember`（單數）。
- `srt:ConsolidationItemsAxis=us-gaap:OperatingSegmentsMember`。

TradingView 的第三方營收另帶 `srt:ProductOrServiceAxis=dis:EntertainmentThirdPartyMember` 或 `dis:SportsThirdPartyMember`，以及對應的業務分部維度。本 parser 不採這些 fact，也不把 `dis:EliminationsAndOtherMember` 與 `dis:SegmentEliminationsMember` 重複加總。

## 期別與推算

財年在最接近 9 月底的星期六結束，為 52／53 週制。期別保留申報實際期末日，不改成 Stock Analysis 顯示的曆季底。

- Q1–Q3 取 10-Q 單季 fact。
- FY 取當期最早原始 10-K 的年度 fact。
- Q4 由當期 10-K 全年減同財年 Q3 10-Q 九個月累計。分類一致與口徑一致均由框架檢核，不從後來重編的比較欄補數字。
- 預設起始日為 2024-01-01，第一期是 FY2024 Q2（2024-03-30）。FY2024 Q1（2023-12-30）不在輸出範圍，不參與 Q4 依據的結構檢核；Q4 推算條件以 `categories` 判斷財年起日至 Q3 期末的分類集合是否與年度相同。
- FY2024 Q4（2024-09-28）使用 0001744489-24-000276 的年度與 0001744489-24-000232 的九個月累計；FY2025 Q4（2025-09-27）使用 0001744489-25-000155 與 0001744489-25-000136。
- FY2026 為 53 週財年，年度期末為 2026-10-03，Q4 為 14 週（98 天），在框架單季 84–98 天的範圍內。
- 較早範圍若包含 FY2023 Q4，三分部年度與原申報兩分部季度結構不同，交由框架判定不推算，不以重編後季度補值。

2024-01-24 的 0001744489-24-000064 是 FY2023 的 Part III 10-K/A，主文件沒有營收 fact。主申報是 2023-11-21 的原申報；修正申報只參與差異標記，不作數值來源。

## 數字在原文的位置

分類與 Eliminations 的 fact 同時標在附註 Segment Information 的分部表與「依分部與產品別的營收」拆分表；合併總營收也出現在損益表。10-Q 的分類、調節項及總營收證據取自拆分表；10-K 的分類與調節項證據取自分部表，總營收證據取自拆分表。

| 申報 | 分部表編號 | 證據表格 |
|---|---:|---|
| FY2023 Q2、Q3 10-Q | 12 | 不在正式輸出範圍，無證據檔 |
| FY2023 10-K（0001744489-23-000216） | 108 | 僅作上一財年口徑檢核，無該期輸出證據檔 |
| FY2024 Q1 10-Q | 11 | 不在正式輸出範圍，無證據檔 |
| FY2024 Q2 10-Q | 12 | 單季：拆分表 t16 |
| FY2024 Q3 10-Q | 12 | 單季：拆分表 t16；Q4 九個月運算元：拆分表 t18 |
| FY2024 10-K | 76 | FY 與 Q4 年度運算元：分類及 Eliminations 為分部表 t76；總營收為拆分表 t88 |
| FY2025 Q1 10-Q | 12 | 單季：拆分表 t17 |
| FY2025 Q2 10-Q | 13 | 單季：拆分表 t18 |
| FY2025 Q3 10-Q | 13 | 單季：拆分表 t18；Q4 九個月運算元：拆分表 t20 |
| FY2025 10-K | 73 | FY 與 Q4 年度運算元：分類及 Eliminations 為分部表 t73；總營收為拆分表 t84 |
| FY2026 Q1 10-Q | 12 | 單季：拆分表 t17 |
| FY2026 Q2、Q3 10-Q | 13 | 單季：拆分表 t18 |

表格編號為框架從 SEC 原始 HTML 建立的索引；證據表格對應 `data/revenue/D/DIS/` 各期 `evidence/` 檔名的 `-t<編號>`。分類使用 Entertainment、Sports 的分部總額列，不取其下的 Third parties 列。

## 已知的重複 fact

無維度合併營收與分部總額在損益表、分部附註及 MD&A 等位置重複標記。相同 concept、完整 dimensions、期間的重複 fact 交由框架檢查一致並選取證據，不以 fact id 指定特定一筆。

## 驗證

正式 `status.json` 中，FY2024 Q2 至 FY2026 Q3 的 10 個季度及 FY2024、FY2025 的 2 個年度全部為 `published`，沒有 `failed` 或 `not_derived`。各期 `revenue.json` 的結構、單位與精度、加總及證據完整檢核均通過；FY2024、FY2025 Q4 均由年度減九個月累計推算。

以正式季度輸出的三個分類逐筆比對 Stock Analysis，共 30 筆，全部在顯示精度內。Experiences 對應來源的 Parks and Experiences。來源期末日對齊到曆季底，實際輸出仍保留申報期末日。

下表各分類欄為「正式輸出（百萬美元） / Stock Analysis 顯示值」。來源的 `B` 為十億美元，顯示至 0.01B；一致的容許差額為 5 百萬美元，加上各運算元 decimals 的半單位誤差，Q4 同時計入年度及九個月運算元。

| 財年季別 | 實際期末日 | Stock Analysis 期末日 | Entertainment | Experiences | Sports |
|---|---|---|---:|---:|---:|
| FY2024 Q2 | 2024-03-30 | 2024-03-31 | 9,796 / 9.80B | 8,393 / 8.39B | 4,312 / 4.31B |
| FY2024 Q3 | 2024-06-29 | 2024-06-30 | 10,580 / 10.58B | 8,386 / 8.39B | 4,558 / 4.56B |
| FY2024 Q4 | 2024-09-28 | 2024-09-30 | 10,829 / 10.83B | 8,240 / 8.24B | 3,914 / 3.91B |
| FY2025 Q1 | 2024-12-28 | 2024-12-31 | 10,872 / 10.87B | 9,415 / 9.42B | 4,850 / 4.85B |
| FY2025 Q2 | 2025-03-29 | 2025-03-31 | 10,682 / 10.68B | 8,889 / 8.89B | 4,534 / 4.53B |
| FY2025 Q3 | 2025-06-28 | 2025-06-30 | 10,704 / 10.70B | 9,086 / 9.09B | 4,308 / 4.31B |
| FY2025 Q4 | 2025-09-27 | 2025-09-30 | 10,208 / 10.21B | 8,766 / 8.77B | 3,980 / 3.98B |
| FY2026 Q1 | 2025-12-27 | 2025-12-31 | 11,609 / 11.61B | 10,006 / 10.01B | 4,909 / 4.91B |
| FY2026 Q2 | 2026-03-28 | 2026-03-31 | 11,715 / 11.72B | 9,487 / 9.49B | 4,609 / 4.61B |
| FY2026 Q3 | 2026-06-27 | 2026-06-30 | 11,345 / 11.35B | 9,968 / 9.97B | 4,500 / 4.50B |

沒有同來源對照值或不在預設輸出範圍的項目如下：

- FY2024（2024-09-28）、FY2025（2025-09-27）：Stock Analysis 對照資料只有季度，沒有年度值，FY 序列不作同來源比對。
- Eliminations 與合併總營收：Stock Analysis 擷取的分部表沒有對應值，不作同來源比對。正式輸出各期的三分類加 Eliminations 均等於合併總營收。
- FY2024 Q1（2023-12-30）及更早期別：不在預設輸出範圍，不列入比對。

## 比較欄

`status.json` 的 10 個季度與 2 個年度均沒有 `differences`，也沒有 `comparison_errors`，沒有比較欄差異標記。
