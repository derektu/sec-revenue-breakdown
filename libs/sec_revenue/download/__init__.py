"""SEC 下載：CIK 查詢（`catalog`）、申報清單（`catalog`）、要下載的申報（`plan`）與完整申報包（`packages`）。

任何 ticker 都能下載；每份文件保存 sha256、filing index、文件原址與 inline XBRL viewer URL，記錄在
`pipeline/<TICKER>/packages.json`。parser 只讀申報包，不需要另外的下載清單。
"""
