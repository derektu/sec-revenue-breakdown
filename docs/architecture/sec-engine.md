# SEC 重播資料契約

`EvidenceStore` 驗證來源 bytes，按 ticker／申報期／accession 保存。`XbrlEngine` 只接受 raw_filings 的 SEC facts 或真正 inline XBRL；不讀 quarter_results。`QuarterEngine` 以完整 concept、dimensions、unit 配對 FY 與 YTD9，保留兩側運算元，衝突拒絕。`IssuerParser` 以公司檔案自己的 selectors、日期限制與正規化規則產生具名 basis。`ReplayService` 協調固定路徑輸出；`RiskAnalyzer` 比較近期 schema 及實際特殊規則。基準期望值僅由獨立 regression CLI 讀取。

每筆觀察包含 ticker、period_end、basis、category、status、value_usd、SEC_operands。缺值為 null 並附原因；不補零。來源索引區分 facts_cache、original_html、dom_snapshot、web_text；原始 HTML 缺漏不因 facts cache 存在而視為已補齊。新輸出不覆寫研究資料。檔案寫入以 atomic replace，證據以 hash 命名避免覆寫不同版本。

選值使用精確完整 scope，替代 selector 如得出不同值拒絕。Q4 必須同一起日及相鄰期間，不跨未知 scope。已知公司 scope bridge 需在公司 parser 內具名且限制期間。此輪全為已見期間回溯；研究 29/30 與固定供應商 24/30 不變。
