> 數字擷取與計算來源必須是 SEC；本文使用公司 IR 作原始數字的舊實驗已被 [SEC 來源檢查](sec-primary-source-policy.md) 取代，僅保留研究歷程。

> 本文為前批 20 / 30 紀錄；最新為 **21 / 30 OK**，見 [剩餘公司原表續查](remaining-company-resolution.md)。HD 已裁決完成，PGR 的原表／Q4 亦已修復，仍缺最新季參考。

# 八季 parser：20 / 30 OK，10 / 30 Fail

截至 2026-11-04，本批新增 **COST、KO、WMT、BAC、UNH、UPS** 六家。完整三十家公司結論在 [historical-rule-study.md](historical-rule-study.md)；機器可讀結論在 [extended-completion-status.json](../../research/completed-parser-repairs-20261104/extended-completion-status.json)。同目錄的 `summary.json`、`eight-quarter-status.json`、`completion-status.json` 是依序重跑的前階段收據，不能當作最新總數。

OK 的條件是固定一家原參考網站、完整八個目標季度、各分類由程式擷取與計算，逐項相同，或有原表支持的具體差異解釋。缺季、人工補表或未解釋差異仍算 Fail。所有結果都是已接觸資料的回溯驗證；BAC／UPS 部分歷史計算還使用後來申報的重編比較欄，沒有宣稱未見季度準確率。

## 本批六家為何改成 OK

| 公司 | 結果 | 實際修法與依據 |
|---|---|---|
| COST | 八季 16 項相同 | 按零售財年把二／五／八或九／十一月的週日季末對應網站三／六／九／十二月標籤；不用最近日期猜。 |
| KO | 八季 57 項相同；七個舊分類空欄為 N/A | 參考收入包含分部間收入，因此固定選 `us-gaap:Revenues` 的 gross 列，加獨立抵銷；不拿第三方外部收入的另一 concept 混比。舊 member 的接合限定完整 scope 與期間；Friday 季末另有日期規則。 |
| WMT | 八季 32 項相同 | corporate 是公司層級會員及其他收入，程式以合併 Revenues 減三營運分部 Revenues。七個歷史直接／Q4 公司列支持同一定義；最新季亦由相同公式產生，不再查人工八季補值表。淨銷售不可代替 Revenues。 |
| BAC | 八季 40 項相同 | FY2025 的稅務權益投資會計方法追溯變更；2025 Q4 改用新方法下的 FY 減同年 YTD9，比較欄按最早可用後期申報選取，沒有按參考金額挑版本。 |
| UNH | 八季 21 項相同；三項可解釋差異 | 直接解析公司 Q2／Q3 PDF 的同季 GAAP／adjusted 收入表與抵銷註腳。Q2、Q3 的參考 Optum 採 adjusted；Q2 參考抵銷可重現為 GAAP 總額減 UHC 與 adjusted Optum。輸出固定完整 GAAP，保留差額，未聲稱知道供應商內部實作。 |
| UPS | 八季 24 項相同 | 歷史 scope 接合限定完整維度；非報導分部 SCS 只在直接總列缺席時合計其三產品。2024 Q4 的美國空運業務從 SCS 移至 Domestic，使用已重編 YTD 比較欄。最新 2026 Q3 從公司 PDF 解析三個收入列，明確更新目標八季，不冒稱舊基準已有最新資料。 |

公司原始依據與完整 URL 固定在程式 `EVIDENCE`、各結果的運算元與來源欄：

- [Walmart 公司季報](https://www.sec.gov/Archives/edgar/data/104169/000010416926000102/wmt-20260430.htm)。
- [BAC FY2025 Note 1](https://www.sec.gov/Archives/edgar/data/70858/000007085826000157/bac-20251231.htm)。
- [UPS FY2025 Note 14](https://www.sec.gov/Archives/edgar/data/1090727/000162828026008432/ups-20251231.htm) 與 [Q3 2026 公司發行稿](https://investors.ups.com/_assets/_82dd7397931c18431557facb5a665332/ups/news/2026-10-27_UPS_Releases_3Q_2026_2172.pdf)。
- [UNH Q2 2026](https://www.unitedhealthgroup.com/content/dam/UHG/PDF/investors/2026/unh-reports-second-quarter-2026-results.pdf) 與 [Q3 2026](https://www.unitedhealthgroup.com/content/dam/UHG/PDF/investors/2026/unh-reports-third-quarter-2026-results.pdf) 的 REVENUES BY BUSINESS 表。

## 其餘十家：已嘗試什麼、還差什麼

| 公司 | 本輪實際進展 | 仍為 Fail 的原因與可行下一步 |
|---|---|---|
| CMCSA | 新增完整 HTML 業務群表 parser，按表頭跨度區分季度／九個月／全年，排除固定匯率表；兩份已保存申報可擷取或推算三個目標季度。 | 仍缺五季原表；不能用舊人工數值宣稱程式完成八季。公司 IR 正常單次 GET 回 403，已停止該請求；需取得其餘正常可存取的原表再跑相同規則。 |
| HD | 八季四分類均已產出，日期與 scope 已接合；30 項相同。另嘗試 FY2025 重編全年與後期同年九個月比較欄。 | 2024 Q4 Hardlines／Other 各差 4.60 億美元、方向相反；重編版本仍無法讓四分類都一致。新鮮 SA 畫面與保存參考一致，尚無證據可直接判 SA 錯誤；需進一步釐清當季產品分類轉移。 |
| MCD | 修正只限 2024 Q3 的美國 member 名稱，Q4 已恢復；七季 21 項全部相同。 | 保存富途資料只到 2026 Q2，最新 Q3 缺。正常頁面重新查看仍未取得該季；需補同一家參考或取得另一家完整八季，不能跨來源拼八季。 |
| LLY | 年度美國＋非美國五產品合計，只在直接全球列不存在時使用；39 項相同、一項可計算的申報精度差異。 | SA 保存的八季是 2024 Q3～2026 Q2；目標八季是 2024 Q4～2026 Q3，缺最新一季。SA 正常頁面仍只見 Q2，富途本次頁面暫無內容；不能把舊八季算最新八季。SEC 最新 facts 已接觸，沒有盲測聲明。 |
| BRK-B | 六季 48 項相同，正常富途季度選單已重新查看。 | 選單缺 2024 Q3、2025 Q3；需同一家完整八季參考，不是計算有 48 項相同就算八季通過。 |
| PGR | 保留已取得七季，23 項相同；檢查年度與季度 concept 差異。 | 年度保費收入不等於季度含手續費的收入；現有基準的原始擷取又漏掉部分投資／證券收益 concept。仍有 16 項定義未實作、10 項缺 scope。需原始完整損益表擴充收入與投資規則，另補缺季；本次富途正常頁面暫無內容，不宣稱永久無資料。 |
| XOM | 修正外部收入與 gross 分部收入的差異；唯一對齊的 2026 Q2 五項全部相同。 | 舊 CIK 34088 的歷史申報仍缺；現有 successor CIK 2115436 只有兩季。正常 SEC submissions 單次 GET 回 403，未重試或繞過。需可正常取得的舊申報後才能跑滿八季。 |
| CVX | 已保存五季 20 項全部相同。舊表的 OilAndGas 產品軸只在已覆核的四個地區／分部 gross 收入列做完整 scope 接合；Other 另接合，總抵銷只加最底部 US／non-US 列，沒有再加分部內抵銷。 | 2024 Q4 四項已修好，仍因富途缺三季而 Fail。修復入口與收據見下方；需補同一家缺季參考才可改成 OK。 |
| CAT | 已修復歷史分部改名與公司對帳 member，七季 42 項全部相同。公司正常新聞頁可見最新 Q3 PDF 連結。 | 最新 2026 Q3 原表未保存；兩次一般 PDF 請求逾時，斷線前瀏覽器下載未返回結果，復線後常見下載與工具暫存位置未找到檔案。保留「下載結果未定」，不重複該動作；另以正常單次 GET 嘗試 SEC 發行稿，回 403 後停止。取得可正常存取的原表後可加最新單季表 parser。 |
| PLD | 對公司 IR 八季 32 項全部相同。重新查看 SA 的該頁為 404，富途該頁未呈現業務表。 | 尚無原三家任一家的完整八季參考，因此保守排除在主計數。這是參考覆蓋缺口，不能說公司 parser 沒有八季結果，也不能推論三個平台全面無資料。 |

這十家都有具體剩餘條件；本輪沒有把來源缺季、讀不到原表或無法裁決的差額轉成零，也沒有把每家挑幾項命中當成準確率。

## 重跑與檢查

入口為 [extend_issuer_repairs.py](../../scripts/extend_issuer_repairs.py)，公司規則在 [remaining_issuer_rules.py](../../scripts/remaining_issuer_rules.py) 與 [company_revision_rules.py](../../scripts/company_revision_rules.py)。Comcast 的實際原表 parser 是 [parse_comcast_business_groups.py](../../scripts/parse_comcast_business_groups.py)，[收據](../../research/issuer-repair-evidence/comcast-raw-table-parser.json) 明確標記不是完整八季。

```sh
data/vendor/local/.venv/bin/python scripts/extend_issuer_repairs.py \
  --out /tmp/新的八季重播目錄
```

須先有本機原始資料與 `pdftotext`，輸出目錄及同名本機詳細目錄必須不存在。此入口只重播已下載來源，不新增網路請求。完整原始參考金額、運算元、差額與前階段結果在忽略目錄 `data/vendor/local/cohort-adjudication-20261104/completed-parser-repairs-20261104/{TICKER}-extended.json`，不推送第三方原始資料。

[本機驗證收據](../../research/completed-parser-repairs-20261104/local-verification.json) 記錄 111 項離線測試全部通過，另逐一驗證三十份原基準／凍結收據、程式與證據雜湊、三十份完整結果雜湊，以及原始參考值／日期未更動。原始 SEC HTML 並未全部重新下載或重剖；主要沿用保存的完整 facts，補上少數公司原始 PDF／HTML parser。

## CVX 後續修復

[repair_chevron_q4.py](../../scripts/repair_chevron_q4.py) 已將 2024 Q4 四個缺運算元修好；[CVX-status.json](../../research/chevron-q4-repair-20261104/CVX-status.json) 更新此公司為「五季二十項相同，仍缺三季」。主總數維持 20 / 30。此後續收據取代上一輪 CVX 的逐筆狀態，不改寫舊收據。年度與九個月兩份來源 URL、程式及本機詳細結果雜湊均固定在收據內。
