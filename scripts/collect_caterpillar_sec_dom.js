// 在已正常開啟的 SEC 8-K 附件中，以 cua 唯讀 evaluate 擷取。
// 本次只覆核 2026 Q3，保留實際非空 cell 文字，不把破折號改零。
() => ({
  source_url: location.href,
  title: document.title,
  format: 'SEC_DOM_nonempty_cell_text',
  tables: [...document.querySelectorAll('table')]
    .map((element, index) => ({element, index, text: element.innerText}))
    .filter(t => t.text.includes('Sales and Revenues by Segment') || t.text.includes('Sales and Revenues by Geographic Region'))
    .map(t => {
      const rows = [...t.element.rows].map(r => [...r.cells]
        .map(c => c.innerText.trim().replace(/\s+/g, ' ')).filter(c => c && c !== '$')).filter(r => r.length);
      const end = rows.findIndex(r => r[0] === 'Third Quarter 2025');
      return {index: t.index, rows: end >= 0 ? rows.slice(0, end) : rows};
    })
})
