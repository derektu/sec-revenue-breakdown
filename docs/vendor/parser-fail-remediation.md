> 最新完成狀態為 **21 / 30 OK**，見 [目前逐公司 OK／Fail](historical-rule-study.md) 與 [本輪續查](remaining-company-resolution.md)。下列內容保留當時的研究紀錄，舊計數不是目前總數。

> 後續：第二批五家已修復，現為 **14 / 30 OK**，見 [第二批結果](priority-parser-repairs.md)。下文保留第一批完成時的問題與修法盤點；不代表這五家仍 Fail。

# Fail 修復與剩餘處理方式

2026-11-04 第一批已修復 DIS、JNJ、META，完整八季重跑後由 **6 / 30 提升至 9 / 30 OK**。原六家仍全部通過。其餘 21 家尚未通過，不把預期可修復當已完成。

## 已完成的三家

| 公司 | 真正問題 | 程式修法 | 八季重跑 |
|---|---|---|---|
| DIS | 網站用曆季標籤，公司用週六財季；舊分類空欄被一概視為缺資料 | 限定已覆核八季，以星期、同月季末與七天界限確認標籤；依分部改組證據將舊 Media and Entertainment 空欄標 N/A，現行三分類須全部有值且相同 | 24 / 24 相同，OK |
| JNJ | 網站用曆季標籤，公司用週日財季；已分拆 Consumer Health 空欄被一概視為缺資料 | 同上但要求週日；Consumer Health 僅在現行兩分類完整且符合已覆核範圍時標 N/A | 16 / 16 相同，OK |
| META | 全年減九個月的 Q4 廣告與其他收入有四捨五入差額 | 真正下載並解析公司 Q4 發行稿的單季分部表。驗證單位、季度／年度欄、年份、唯一表格及組成加總；優先直接披露的單季值，保留原推算作對照 | 24 / 24 相同，OK |

依據：[Disney 10-K 的 Reporting Period、三分部及 2023 重組說明](https://www.sec.gov/Archives/edgar/data/1744489/000174448925000155/dis-20250927.htm)、[JNJ 10-K 的財年規則及 Note 17 分拆後兩分部](https://www.sec.gov/Archives/edgar/data/200406/000020040626000016/jnj-20251228.htm)、[Meta 官方 Q4 發行稿的 Segment Information](https://investor.atmeta.com/investor-news/press-release-details/2026/Meta-Reports-Fourth-Quarter-and-Full-Year-2025-Results/)。

新規則沒有參考金額常數，沒有把缺資料改成零；若日期不符、舊欄重新出現數字或現行分類缺值，仍維持 Fail。META 不是人工抄兩個正確值，而是實際 HTML 表格 parser；遇到其他年或表頭變更會拒絕，未宣稱支援未來未知版面。

原 6 / 30 評分將空欄全當缺漏，沒有分清已停用分類與真正缺資料；本輪以公司改組及現行分類證據修正這個判定問題。只要有證據的修復完成並重跑八季，就更新狀態。

## 剩餘 21 家：修什麼、如何才算完成

下列為具體下一步，尚未實作或尚未驗證成功。所有修法都必須保留一個固定參考來源、同一組八季，完成後重跑整家公司；不能按欄位挑對自己有利的來源。

| 公司 | 可行處理方式 | 轉 OK 前需解決 |
|---|---|---|
| ORCL | 按實際二／五／八／十一月財季建立網站三／六／九／十二月標籤規則；釐清 Cloud／Software 與舊 License／Support 分類的生效期間，以現行四分類與總額確認完整性 | 八季日期及分類更替都有依據，不能只因 32 個數值相同就略過 |
| GOOGL | 抽取避險專用概念，擴大收入關鍵字過濾，檢查年度與九個月概念連續性；必要時用直接季度表取代推算 | 兩個避險缺漏及一個精度差異逐一解決，舊欄空值有分類依據 |
| MSFT | 先查 2026 Q1 More Personal Computing 是當期原報或後來重分類；依固定來源版本重播八季，明列分部改組與空欄生效期間 | 一筆差異有可重現規則或公司證據解釋，分類空欄不再一概棄權 |
| PG | 比較網站縮寫精度、SEC 直接季度及原始單位；對那一筆超出界限的差異查公司分部表，不再擴大容差 | 唯一差異解釋完成，其餘精度相容也須明列計算原因 |
| JPM | 查 2024 年度／九個月 CIB 重組前後 member，加入有日期限制的名稱對照；保留 managed／FTE 口徑 | Q4 CIB 能由同口徑運算產生，舊分部空欄有依據 |
| BAC | 對 2025 Q4 三個差異優先找直接季度分部表／發行稿，核對 FTE 對帳與重編版本 | 三個差異不能混用 GAAP／FTE 數值解決 |
| UNH | 查 Optum 總額、子部門及跨部門抵銷的範圍，以及比較期間重編；必要時擷取表格的總 Optum 列 | 三筆差異有確定原因，不能重複加父子分類 |
| WMT | 擴大抽取 corporate 的 Membership and other income，或解析分部 HTML 表格；殘差只作驗算 | 七季人工補表轉成程式輸出；最新原檔仍遭 403 時不繞過，保留缺口或用可正常取得的公司披露 |
| CMCSA | 解析 MD&A 的兩個淨業務群表，或為原始分部、HQ、群內抵銷建立完整計算；保留分拆前後版本 | 八季都由程式產生；四筆 SA 日期錯置已有證據，可作明列例外，但不能用人工數字算完成 |
| HD | 對年度／九個月逐項查完整維度，補有依據的產品線 member／scope 接合；確認零售財季標籤 | 八個缺漏與八季日期全部解決，不任意移除合併軸 |
| KO | 將 external revenue、gross segment revenue、intersegment revenue 分成不同規則，按公司分部表選定固定參考的口徑 | 消除 28 個多值歧義，補齊 19 缺漏及日期；不依金額挑 concept |
| LLY | 查年度與九個月治療領域表，補 Other 及分類名稱接合；完成目前未重播的最新季 | Q4 十筆及 Other 三筆缺漏解決，完整八季重跑；無須把最新季當盲測 |
| COST | 依 12／16 週季度及年末建期間表，按財報的實際起訖而非最接近日期匹配；檢查直接季收入 | 兩個未對應季度與四個不同值解決 |
| UPS | 把本土／國際地區軸與分部軸版本分期；更新最新 SEC 基準，查 Q4 的直接 Supply Chain 表 | 最新季補齊、三個分類缺漏及一個差異解決 |
| CAT | 補入參考最新季度的 SEC 資料；釐清 Power & Energy 改名及金融產品／抵銷口徑 | 最新季補齊，兩個歷史缺漏及舊分類空值有依據 |
| MCD | 使用正常可用參考頁補第八季；查 Q4 美國分部年報／九個月 scope 的差異 | 缺一季參考及一筆 Q4 結果 |
| CVX | 先從正常參考頁補足三季，再查 2024 Q4 原始年報與九個月是否同為 gross sales／抵銷口徑 | 缺三季參考，現有一季 Q4 四分類也須完成 |
| BRK-B | 從富途正常可用歷史頁補缺兩季；若改來源，要整組八季重比 | 目前六季已相同，缺兩季參考仍不能放行 |
| PGR | 抽取範圍由 revenue／sales 擴大到 investment income、holding／realized gains；用表格階層分清總損益與其中的 security sales | 補第八季、補完整收益規則及 Q4；不能把重疊損益都當平行收入 |
| XOM | 建立舊 CIK 與 successor 的公司身分橋接，保留原申報版本；依 segment table 區分 gross sales、其他收入和抵銷 | 先有完整八季 SEC 基準，再處理現有一季四個分部差異 |
| PLD | 補原三家任一家正常可用的八季；若研究允許公司 IR 作固定參考，現有 IR 八季結果另列已完成 | 嚴格以原三家為參考時仍缺資料，不把 IR 成果藏掉或算成原三家已通過 |

優先順序：先 ORCL、GOOGL、MSFT、PG、JPM 等少數差異／分類接合；再處理 WMT、CMCSA、HD、KO 的表格與口徑；缺季或身分橋接的公司獨立追蹤。這是依目前缺口安排，沒有將未測工時當承諾。

## 重現與驗證

入口：[resolve_parser_failures.py](../../scripts/resolve_parser_failures.py)。先以原 runner 全量重播三十家公司，再套用三家修復；舊 receipts、原始列與舊結果均不改寫。

最新版：[逐公司 OK／Fail](historical-rule-study.md)、[判定及雜湊](../../research/parser-fail-resolution-20261104/eight-quarter-status.json)、[驗證](../../research/parser-fail-resolution-20261104/verification.json)。同目錄 `summary.json` 為原 runner 的未裁決計數，完成判定以 `eight-quarter-status.json` 為準。

本機原公司發行稿：`data/vendor/local/parser-fixes-20261104/meta-q4-2025-release.html`；新逐筆結果：`data/vendor/local/cohort-adjudication-20261104/parser-fail-resolution-20261104/{TICKER}-resolved.json`。公司直接季度的公開數字另存 `meta-direct-quarter.json`；第三方原始參考列仍僅本機。
