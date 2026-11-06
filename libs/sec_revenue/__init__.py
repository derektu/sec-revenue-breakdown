"""SEC 營收組成 pipeline：download 下載 SEC 申報包，parse 依公司 parser（`companies/`）以框架（`revenue/`）產生 `data/revenue/` 的正式輸出，viewer 唯讀顯示；capture 擷取對照資料，universe 管理 ticker 清單與對照資料格式。"""
