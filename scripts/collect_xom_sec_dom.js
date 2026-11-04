// 正常 SEC 文件上的唯讀財務表擷取；輸出為 DOM cell 文字，不是 HTML bytes。
// 第一份 2026 Q1 快照另保留分部 Sales、投資收入等列；parser 依列名讀取，不依行數猜值。
() => ({
  format: 'SEC_DOM_cell_textContent', source_url: location.href, title: document.title,
  tables: [...document.querySelectorAll('table')].map((t, index) => ({
    index, rows: [...t.rows].map(r => [...r.cells].map(c => c.textContent.trim().replace(/\s+/g, ' ')).filter(s => s && s !== '$'))
  })).filter(t => t.rows.some(r => ['Total revenues and other income', 'Segment revenues and other income'].includes(r[0])))
    .map(t => ({...t, rows: t.rows.filter((r, i) => i < 6 || [
      'Segment revenues and other income', 'Other revenues (2)', 'Elimination of intersegment revenues',
      'Total consolidated revenues and other income', 'Reconciliation of consolidated revenues'
    ].includes(r[0]) || (!t.rows.some(x => x[0] === 'Segment revenues and other income') && [
      'Sales and other operating revenue', 'Income from equity affiliates', 'Other income', 'Total revenues and other income'
    ].includes(r[0])))}))
})
