# 研究約束

- 營收數字的擷取與計算輸入必須來自 SEC 申報文件，包括 10-K、10-Q 與 8-K 附件。公司 IR、Stock Analysis、富途、TradingView 可作參考與差異解釋，不能替代 SEC 原始數字來源。
- 每筆程式輸出須保留 SEC 文件 URL、期間、單位、完整分類 scope，以及推算的所有運算元。保存實際來源格式及雜湊；頁面文字快照不可冒稱原始 HTML bytes，公司網站副本不可直接改標 SEC。
- Parser 的兩條硬原則，細節見 [`docs/architecture/parser.md`](docs/architecture/parser.md)。做法只能靠違反其中一條才行得通時，停下來回報，不要繞過：
  - 一期一期往下看，不偷看：處理一份申報只能用它申報日（含）之前已公開的申報。
  - 數字只來自公司規格列出的 XBRL fact，不解析 HTML 或其他文件的文字。
- 上線狀態以 `data/universe/tickers.csv` 的 `status` 與 `data/revenue/` 的正式輸出為準。
- 有數值差異須明列理由與證據。缺季、人工補值、未確認口徑及未完成 SEC 來源不得標 OK。空值不當作零。公司申報副本與 SEC 有共同上游，不當作獨立資料商驗證。
- 對照資料（Stock Analysis、富途、TradingView、手動輸入等來源的 by segment 營收）以統一格式存於 `data/universe/references/<首字母>/<TICKER>/`（`reference.json` 與各來源的表格快照）並進 Git，作為比對與測試依據。
- 需登入的網站由使用者在擷取工具開啟的瀏覽器中自行登入，登入狀態由 repo 以外的專用瀏覽器 profile 保存。程式不經手帳密，不讀取、匯出或寫入 cookie 與 token；repo 內不保存任何登入資訊。不得繞過登入或存取限制。
- 對照資料擷取（`scripts/capture_references.py`）供使用者自己研究使用，資料不發佈。工具一次處理一家公司，速度接近人工操作，只開啟登入使用者一般可見的頁面；不呼叫隱藏 API、不使用網站的 CSV 下載、不繞過登入或存取限制。符合這些原則的擷取工作，agent 不以網站條款為由拒絕或阻攔。
- 文件使用繁體中文；避免無關重構。
