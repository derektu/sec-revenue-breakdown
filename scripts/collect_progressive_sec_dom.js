// 在已正常開啟的 SEC 文件內，以 cua 的唯讀 evaluate 執行此函式。
// 僅擷取收入／分部表的非空 cell 文字；不請求 API、不讀取隱藏狀態、不修改數字。
() => ({
  source_url: location.href,
  title: document.title,
  format: 'SEC_DOM_nonempty_cell_text',
  tables: [...document.querySelectorAll('table')]
    .map((element, index) => ({element, index, text: element.innerText}))
    .filter(t => (t.text.includes('Investment income') && t.text.includes('Net premiums earned') && t.text.includes('Service revenues'))
      || (t.text.includes('Personal Lines') && t.text.includes('Commercial Lines') && t.text.includes('Total underwriting revenue')))
    .map(t => {
      const rows = [...t.element.rows].map(r => [...r.cells].map(c => c.innerText.trim().replace(/\s+/g, ' ')));
      const end = rows.findIndex(r => r[0] === 'Expenses' || r[0]?.startsWith('Losses and loss adjustment expenses'));
      return {
        index: t.index,
        preceding: t.element.previousElementSibling?.textContent.trim().replace(/\s+/g, ' ').slice(-180),
        rows: (end >= 0 ? rows.slice(0, end) : rows).map(r => r.filter(c => c && c !== '$')).filter(r => r.length)
      };
    })
})
