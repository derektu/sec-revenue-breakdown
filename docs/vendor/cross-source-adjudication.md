# 八季跨來源裁決：29 / 30 OK

依使用者接續指示，參考可來自不同地方，不能因固定供應商缺季而忽略其他合法證據。**目前跨來源逐期裁決為 29 / 30 OK，CVX 尚未完成。** [最新收據](../../research/cross-source-final-20261104/completion-status.json) 與 [逐公司表](historical-rule-study.md) 分開保留原固定供應商測試的 **24 / 30**，未回寫舊成績。

原始數字及所有主要運算輸入仍只來自 SEC。本批沒有把公司 PDF 改標 SEC，也沒有從參考值補造主要輸出。公司申報副本與 SEC 有共同上游，支持的是另一格式的期間、分類及計算核對，不能稱獨立資料商準確率或盲測。

## 原先剩餘六家的結論

| 公司 | 本次結論 | 逐期參考與裁決 |
|---|---|---|
| LLY | **OK** | 歷史七個目標季採已保存 Stock Analysis，新季採公司網站 2026 Q3 10-Q PDF；五分類八季 39 項相同、一項原有申報精度解釋。比較的是全球 therapeutic areas，含產品及 collaboration／other 收入，不是五個 operating segments。 |
| BRK-B | **OK** | 富途六季加公司網站 2024／2025 Q3 申報 PDF 副本的兩季，共八季 64 項相同。兩季副本的解析、保險子項與合併對帳由雲端 PR #25 完成；本機重核對其 SEC 選值與八季重播結果，沒有假稱已重新取得未同步的原摘錄。 |
| PGR | **OK** | 改採已保存公司 PDF 的一致十二列，八季 96 項皆與 SEC 相同；本批實際重新解析五份既有 PDF，沒有重下載。富途另保留七季與 Q4 六項計算差異紀錄，不抹掉不一致。 |
| XOM | **OK** | 歷史七個目標季沿用已裁決富途，新季採公司網站 2026 Q3 申報 PDF 副本。合計 44 項相同、16 項歷史 Q4 有具體參考計算差異解釋；新季兩個定義各自核對，不因金額接近選口徑。 |
| PLD | **OK** | 重用已取得的公司 IR 八季參考，32 項全部相同；主要輸出重新與 SEC coverage 選值比較。三個合併收入列加總額，總額不可再與三項重複加總。沒有重新下載八季發布稿。 |
| CVX | **Fail** | 現有六季 24 項相同；2025 Q3、2025 Q4 的完整四分類收入參考仍未取得。可讀新聞稿提供分部 earnings，不能當作收入。 |

跨來源 OK 仍要求八個目標季度、每季預先列出的完整分類、已確認日期／單位／口徑，以及有 SEC 出處的數字或明列的差異理由。僅八個金額命中、缺一分類、語意未覆核或輸出來自 IR，都不能通過。不是單純更換來源名稱就將 Fail 改成 OK。

## 新參考實際驗證

LLY 的[公司網站 10-Q PDF](https://investor.lilly.com/static-files/4413f2f3-6625-42b5-851e-ae9201e3bb95) 第 9 頁總註明以百萬美元列示，第 10 頁產品收入表有單季／年份／美國、海外、全球欄。parser 使用五個類別的全球總計，並與同表收入對帳；`Other` 不誤取成 `Other oncology`。地區加總的百萬申報捨入差異保留，未用地區合計覆蓋較精確的直接全球欄。成功讀取的兩個文字摘錄留本機；其後重新查詢該文件遇 403，已停止，不影響先前取得的實際摘錄。

PGR 採公司網站連出的五份 CDN PDF：[2025 年報](https://s202.q4cdn.com/605347829/files/doc_financials/2025/q4/PGR-Q4-2025-10K.pdf)、[2025 Q3](https://s202.q4cdn.com/605347829/files/doc_financials/2025/q3/Progressive-2025-Third-Quarter.pdf)、[2026 Q1](https://s202.q4cdn.com/605347829/files/doc_financials/2026/q1/interactive/pdfs/Progressive-2026-First-Quarter.pdf)、[2026 Q2](https://s202.q4cdn.com/605347829/files/doc_financials/2026/q2/interactive/pdfs/Progressive-2026-Second-Quarter.pdf)、[2026 Q3](https://s202.q4cdn.com/605347829/files/content_files/Progressive-2026-Third-Quarter.pdf)。先核對各檔與下載收據的 SHA-256，再分開解析合併與承保表。Personal Lines 含 Property 與 fees，Q4 參考亦用相同版本 FY 減九個月。證券總額及組成、承保總額與合併收入列屬重疊資訊，十二列不能全部相加。

XOM 的[公司網站 2026 Q3 PDF](https://investor.exxonmobil.com/sec-filings/all-sec-filings/content/0002115436-26-000020/0002115436-26-000020.pdf) 第 3 頁合併表與第 9 頁分部表，提供單季、US／non-US 與收入對帳。最新主要系列選 all-income 分部加 corporate／抵銷、再扣合併投資與其他收益，因其完整對回 sales；gross sales＋intersegment 五欄另行比較也相同，但仍有 700 萬美元覆蓋差額，不補成零或「其他」。歷史富途 Q2 的 gross 與其餘季 all-income 差異持續明標，沒有聲稱整條參考序列是一個不變口徑。

BRK-B 缺季的來源與分類裁決見 [雲端補充研究](missing-ir-reference-study.md)；PLD 已有四個季度發布稿及其比較欄覆蓋八季，來源與合併收入定義見 [原研究紀錄](evidence-review.md)。PLD 的 IR 參考目前是已保存的結構化觀察，沒有宣稱本批持有新抓原始 HTML bytes。

## CVX 的實際阻礙與下一步

- 公司[2025 Q3 發布稿入口](https://www.chevron.com/newsroom/2025/q4/chevron-reports-3q-2025-results) 正常讀取回 403，沒有重試或繞過。
- 發行人公開發布的 [Business Wire 2025 Q3 新聞稿](https://www.businesswire.com/news/home/20251031139973/en/Chevron-Reports-Third-Quarter-2025-Results) 可讀，但所核實的 Upstream／Downstream 數字是 earnings，合併 sales 也不能代替四分類收入。
- [Business Wire 2025 Q4](https://www.businesswire.com/news/home/20260130488543/en/Chevron-Reports-Fourth-Quarter-2025-Results) 正常讀取逾時，未取得可用參考。
- [AnnualReports 公司目錄](https://www.annualreports.com/Company/chevron-corporation) 可讀，但本批未從中取得缺少兩季的完整四分類收入參考。

後續已用正常 Edge 實際讀取公司 Q3 頁面及其十頁 PDF（[附件](https://www.chevron.com/-/media/chevron/stories/documents/3Q-2025-earnings-press-release.pdf)），確認瀏覽器可讀，故不能將工具的 403 泛化成登入或瀏覽器限制。附件分部表是 earnings、capex 與產量，仍不是所需四分類收入。未變更登入，讀取後已關閉本次分頁。

下一步是從正常可讀的公司季度報告／財務補充或其他合法來源取得這兩季同口徑收入表，；需要上游明確授權時才請使用者處理。SEC 輸出已具備，不需再次下載 SEC 來填參考缺口。

## 複雜度與投入紀錄

| 公司 | 本批實際處理 | 擴展時的主要人工覆核 |
|---|---|---|
| LLY | 一份新 PDF 的兩段文字；新增五分類全球欄 parser | 單季／累計、全球欄與 `Other` 列名稱；單一 operating segment 與產品分類不可混稱。 |
| BRK-B | 重用雲端兩季 16 項裁決，加本機既有六季 | 2025 格式改成多張表；保險投資收入、公司／抵銷與合併加總。原摘錄仍在雲端本機工作目錄，非本 Mac。 |
| PGR | 重剖五份現有 PDF、八季十二列；保留供應商衝突 | Property 重編、fees、證券總額重複計算風險及 FY／YTD 接合。 |
| XOM | 一份新 PDF 的兩段文字，兩口徑各自對帳 | 新舊 CIK、gross／all-income 與負數扣回；不能用一個金額吻合取代範圍選擇。 |
| PLD | 重跑八季已保存 IR 原值與 SEC 選取 | 三個合併收入列與總額的層級，並非完整營運分部分類。 |
| CVX | 查核四個公開入口，另以正常 Edge 讀完 Q3 十頁附件，未填補缺參考 | 先取得真正的收入表，排除 earnings、產量、全年或合併總額替代。 |

本批沒有要求使用者登入或手動操作；沒有獨立第二人的人工覆核，也沒有量測人工分鐘，因此不報虛構工時或每千家公司成本。實際可重用的是表頭／期間／scope 的 parser、拒絕判定和逐期證據；跨公司格式、重編及來源取得仍需逐案覆核。

## 重播與保存

[裁決入口](../../scripts/adjudicate_cross_source_references.py) 僅從 SEC coverage 或先前 SEC-only 選取載入主要數字，參考 parser 只回傳比較值。兩份新 PDF 保存的是帶行號的工具文字摘錄，未取得 PDF bytes；PGR 五份是先前已保存的真正 PDF bytes，兩者分開登錄。原始第三方內容及完整差額明細均留 `data/vendor/local/`，repo 只公開主要 SEC 輸出、摘要與雜湊。

```sh
data/vendor/local/.venv/bin/python scripts/adjudicate_cross_source_references.py \
  --references data/vendor/local/cross-source-20261104 --out /tmp/新的跨來源裁決
```

須已有本機 PGR PDF、前輪明細及新摘錄；輸出目錄與同名本機詳細目錄必須不存在。BRK-B 的兩季採雲端已驗證收據繼承，沒有假稱本機可重剖未同步的摘錄。

[驗證收據](../../research/cross-source-final-20261104/verification.json) 記錄離線測試、完整分類 gate、來源與明細雜湊核對；數字吻合但分類缺漏、未覆核語意或主要輸出來自 IR 都被拒絕。所有季度均已接觸，沒有盲測或新季度泛化成績。
