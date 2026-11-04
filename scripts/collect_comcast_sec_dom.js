// 在正常開啟的 Comcast SEC 季報，以 cua 唯讀 evaluate 執行。
// 保留 cell 的原邏輯 column 與 colspan，不把百分比／匯率調整欄當收入。
() => ({
  source_url: location.href,
  title: document.title,
  format: 'SEC_DOM_sparse_cell_spans',
  tables: [...document.querySelectorAll('table')].map((element, index) => ({element, index}))
    .filter(t => [...t.element.rows].some(r => /Total (Connectivity & Platforms|Content & Experiences) revenue/i.test(r.cells[0]?.innerText || '')))
    .map(t => ({
      index: t.index,
      rows: [...t.element.rows].map((row, index) => {
        let column = 0;
        return [index, [...row.cells].map(cell => {
          const value = [column, cell.colSpan, cell.innerText.trim().replace(/\s+/g, ' ')];
          column += cell.colSpan;
          return value;
        }).filter(c => c[2] && c[2] !== '$')];
      }).filter(([index, cells]) => index < 3 || cells.some(c => /^Total (Connectivity & Platforms|Content & Experiences) revenue$/i.test(c[2])))
    }))
})
