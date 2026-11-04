# CAT、Comcast、PGR 的 SEC 原表修復：23 / 30 OK

本批完成 **CAT OK、Comcast（CMCSA）OK**，總數由 21 增為 **23 / 30**。PGR 的 SEC 擷取與計算已補好，但參考仍少最新一季，因此仍為 Fail。最新 [三十家公司結論](../../research/comcast-sec-repair-20261104/completion-status.json) 保留固定參考來源、目標日期、逐項結果計數及本機完整比較檔雜湊。

這是已看過期間的八季回溯驗證，不是盲測或下季準確率。23 家共 744 個數字輸出都有 SEC 運算元；停用分類的 N/A 不算數字，也沒有補零。第三方原始參考資料不發布。

## 本批結論

| 公司 | 結論 | 本批實作與證據 |
|---|---|---|
| CAT | **OK** | 最新季新增六項 SEC 8-K 附件擷取，連同既有七季共 48 項與固定 Stock Analysis 參考相同。八個停用舊分類欄保留 N/A。 |
| CMCSA | **OK** | 七份 SEC 文件產生八季兩個淨業務群共 16 項：十項相同、兩項 Q4 申報精度解釋、四項參考期別差異。輸出保留 SEC 當季金額，未改成參考金額。 |
| PGR | **Fail：缺一季參考** | 五份 SEC 文件產生七季 49 項對照：43 相同、六項 Q4 證券收益有參考計算錯誤證據。最新 2026 Q3 的 SEC 數字亦已擷取，但尚無同一家富途參考，不能計八季完成。 |

### CAT 的口徑

SEC [2026 Q3 Exhibit 99.1](https://www.sec.gov/Archives/edgar/data/18230/000001823026000052/ex991toformcat3q2026earnin.htm) 的分部表使用 gross 分部收入。Financial Products 採分部 1,177 百萬美元；不是另表法人數字，也不是扣抵銷後的 1,028 百萬。抵銷為 Machinery, Power & Energy 的 -1,800 加 Financial Products 的 -149，合計 -1,949 百萬。六分類加總等於合併收入 20,682 百萬，另用地區表的外部／分部間收入獨立交叉核對。

目標八季為 2024-12-31 至 2026-09-30，已明確加入最新季，沒有沿用過時的八季集合。先前結果未定的公司 PDF 下載未重複；本次原始輸入直接取 SEC 附件。

### Comcast 的季度與重編

固定比較的是 `Total Connectivity & Platforms revenue` 與 `Total Content & Experiences revenue`，不是未扣內部交易的分類加總、營業利益或固定匯率金額。程式以跨欄表頭定位年份及單季／累計欄，排除固定匯率對帳表。一般單季使用原期 SEC 申報，不能以後期重編比較欄覆蓋當期數字。Q4 則用相同分類、單位及年度起點的 FY 減九個月，保留全部運算元；2024 Q4 使用已保存 2025 文件的比較欄，明標 `comparative_used`。

兩個 Q4 欄位與參考相差百萬美元，差額落在兩個以百萬申報運算元的合計精度內，逐筆保留差額。另四項差異如下，單位為百萬美元：

| 季度 | 業務群 | SEC 本季 | 已保存參考 |
|---|---|---:|---:|
| 2026 Q1 | Connectivity & Platforms | 19,962 | 19,795 |
| 2026 Q1 | Content & Experiences | 11,940 | 10,728 |
| 2026 Q2 | Connectivity & Platforms | 19,795 | 19,962 |
| 2026 Q2 | Content & Experiences | 10,728 | 11,940 |

SEC [Q1](https://www.sec.gov/Archives/edgar/data/1166691/000162828026026805/cmcsa-20260331.htm) 與 [Q2](https://www.sec.gov/Archives/edgar/data/1166691/000162828026049360/cmcsa-20260630.htm) 日期表頭明確，兩個業務群在參考中同時呈相反季度對應；先前正常畫面重看與保存參考一致。程式同時檢查兩分類成對對應及重看證據，才接受此例外，不因單一數字碰巧相同就裁決。無法據此知道供應商內部原因，輸出仍採 SEC 正確日期。

### PGR 的收入定義

SEC [2025 年報 Exhibit 13](https://www.sec.gov/Archives/edgar/data/80661/000008066126000086/pgr-20251231_d2.htm) 才包含所需財務原表，不能只解析 10-K 母文件的附表。新 parser 分開處理保費、費用、服務、投資收入及證券收益，並以分部與合併收入交叉核對。全年與九個月的分類及期間一致才推算 Q4；破折號不當零。

參考兩個 Q4 的證券收益三欄，各自加總等於 SEC 單季總額，但其「合計」填成全年值，分項則呈負累計值。程式保留 SEC 的 FY 減九個月結果，檢查整組三欄與合計證據後明列六項參考計算差異；沒有因參考值而修改 SEC 輸出。最新 SEC 季度已取得，缺的是富途最新季度參考。

## 來源保存與重播

正常 Edge 開啟 SEC 公開申報頁面後，唯讀擷取可見財務表格。11 份新快照是 **DOM 表格 cell 文字／跨欄位置，不是原始 HTML bytes**；Comcast 另沿用兩份已保存且經解壓雜湊驗證的 SEC 原始 HTML。CLI 曾回 403 不代表正常瀏覽器頁面不可讀；本次沒有改登入、繞過驗證或重試未知的下載。

[來源目錄](../../research/sec-dom-sources-20261104/) 的三份 manifest 保存 SEC URL、SHA-256 及瀏覽器擷取物件的 canonical FNV32。轉存後逐份驗證 checksum 一致；每個輸出保留實際來源格式、日期、單位、分類、表格位置與來源雜湊。`collect_*_sec_dom.js` 是唯讀擷取函式，`parse_*` 與 evaluator 從實際 cell 資料產生數值，沒有人工填值表。

依序重播下列入口。須已有前輪本機參考與結果；每次 `--out` 目錄及對應本機明細目錄必須不存在。後續入口的 `BASE` 指向前一步已保存的正式收據，另建實驗時須明確確認依賴，不能把新路徑當作自動串接。

```sh
data/vendor/local/.venv/bin/python scripts/evaluate_progressive_sec.py \
  --manifest research/sec-dom-sources-20261104/PGR-manifest.json --out /tmp/新的PGR實驗
data/vendor/local/.venv/bin/python scripts/evaluate_caterpillar_sec.py \
  --manifest research/sec-dom-sources-20261104/CAT-manifest.json --out /tmp/新的CAT實驗
data/vendor/local/.venv/bin/python scripts/evaluate_comcast_sec.py \
  --manifest research/sec-dom-sources-20261104/CMCSA-manifest.json --out /tmp/新的Comcast實驗
```

[本機驗證收據](../../research/comcast-sec-repair-20261104/local-verification.json)：140 項離線測試通過，含來源範圍、單季／累計、年份欄序、固定匯率排除、Q4 同口徑、缺值與重複表拒絕，以及 CAT 獨立對帳；30 份明細、來源／程式雜湊及原始參考值與日期保存通過。沒有宣稱本批重剖全部 30 家原始 HTML。

## 剩餘七家如何解決

| 公司 | 尚缺什麼 | 下一個具體處理方式 |
|---|---|---|
| MCD | 凍結窗口為 2024 Q3 至 2026 Q2，富途缺 2024 Q3；七季 21 項相同 | 補同一家 2024 Q3 歷史參考，或選另一家完整八季參考；不能混兩家補季。 |
| LLY | 保存的是較舊八季，缺目標 2026 Q3 | 補同一家 Stock Analysis 最新季並確認新八季集合。 |
| BRK-B | 富途缺 2024 Q3、2025 Q3；六季 48 項相同 | 查季度切換與正常歷史頁面，或更換完整八季參考後整組重跑。 |
| PGR | 最新季富途參考缺；SEC 擷取已解決 | 補最新同源參考，完成第八季實際比對。 |
| XOM | 舊 CIK 歷史 SEC 與參考期別未完成 | 先核對 legacy／successor CIK 及期間，正常 SEC 文件可讀才擷取；不能把未對齊的 53 項當缺零。 |
| CVX | 富途缺 2024 Q3、2025 Q3、2025 Q4；已取得五季 20 項相同 | 補同一家三季參考，或完整更換固定參考來源。 |
| PLD | 公司 IR 八季已有 32 項相同，原三家八季參考不完整 | 找到其中一家完整參考後重跑；IR 不替代約定的固定參考。 |

這些是具體待完成項目，並非已證明無法解析；尤其正常瀏覽器可讀 SEC 的結果已解決 CAT／Comcast 原先的原表缺口。
