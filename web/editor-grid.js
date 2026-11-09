(function () {
  'use strict';
  const columns = [
    { key: 'lineId', label: 'Code', css: 'code-col', readonly: true },
    { key: 'description', label: 'Item', css: 'item-col', required: true },
    { key: 'phase', label: 'Phase', css: 'w-phase', required: true },
    { key: 'stage', label: 'Work area', css: 'w-stage', required: true },
    { key: 'checklistGroup', label: 'Group', css: 'w-group' },
    { key: 'categoryPath', label: 'Category', css: 'w-category' },
    { key: 'monroeEstimate', label: 'Plan qty', css: 'w-qty grid-number', readonly: true },
    { key: 'estimateBasis', label: 'Plan basis', css: 'w-stage', readonly: true },
    { key: 'listedQuantity', label: 'Listed qty', css: 'w-qty grid-number', numeric: true },
    { key: 'siteQuantity', label: 'Site qty', css: 'w-qty grid-number', numeric: true },
    { key: 'unit', label: 'Unit', css: 'w-unit', required: true },
    { key: 'siteChecked', label: 'Checked', css: 'w-check grid-check', boolean: true },
    { key: 'specification', label: 'Specification', css: 'w-spec' },
    { key: 'vendor', label: 'Vendor', css: 'w-vendor' },
    { key: 'partNumber', label: 'Part number', css: 'w-part' },
    { key: 'itemNotes', label: 'Notes', css: 'w-notes' },
  ];
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  const csvCell = value => '"' + String(value ?? '').replaceAll('"', '""') + '"';
  const sortRows = (a, b) => (a.phaseOrder ?? 999) - (b.phaseOrder ?? 999) || (a.stageOrder ?? 999) - (b.stageOrder ?? 999) || (a.manualOrder ?? 999999) - (b.manualOrder ?? 999999) || String(a.description).localeCompare(String(b.description));
  const planQuantity = item => item.monroeEstimate && item.monroeEstimate.basis !== 'PLANNING_PLACEHOLDER' ? item.monroeEstimate.quantity : null;
  function display(item, column) {
    if (column.key === 'categoryPath') return (item.categoryPath || []).join(' > ');
    if (column.key === 'monroeEstimate') return planQuantity(item) ?? '';
    if (column.key === 'estimateBasis') return item.monroeEstimate?.basis || '';
    if (column.boolean) return item[column.key] ? '✓' : '';
    return item[column.key] ?? '';
  }
  function parseValue(raw, column) {
    const value = String(raw).trim();
    if (column.readonly) throw new Error(column.label + ' is read only.');
    if (column.required && !value) throw new Error(column.label + ' cannot be blank.');
    if (column.numeric) {
      if (!value) return null;
      const number = Number(value.replaceAll(',', ''));
      if (!Number.isFinite(number) || number < 0) throw new Error(column.label + ' must be a nonnegative number.');
      return number;
    }
    if (column.boolean) {
      if (['1', 'yes', 'true', 'checked', '✓', 'x'].includes(value.toLowerCase())) return true;
      if (['', '0', 'no', 'false', 'unchecked'].includes(value.toLowerCase())) return false;
      throw new Error('Checked must be Yes or No.');
    }
    if (column.key === 'categoryPath') {
      const path = value.split('>').map(part => part.trim()).filter(Boolean);
      if (!path.length) throw new Error('Category cannot be blank.');
      return path;
    }
    return value;
  }
  window.createSiteBomGrid = function ({ getLive, commitDraft, mark, renderAll, status }) {
    const byId = id => document.getElementById(id);
    const viewport = byId('gridViewport');
    const table = byId('gridTable');
    let rows = [], anchor = null, focus = null, dragging = false, editor = null;
    const changed = new Set();
    const cellKey = (row, column) => `${row.lineId}:${column.key}`;
    const inBounds = point => point && point.row >= 0 && point.row < rows.length && point.col >= 0 && point.col < columns.length;
    function rectangle() {
      if (!inBounds(anchor) || !inBounds(focus)) return null;
      return { top: Math.min(anchor.row, focus.row), bottom: Math.max(anchor.row, focus.row), left: Math.min(anchor.col, focus.col), right: Math.max(anchor.col, focus.col) };
    }
    function updateSelection() {
      const rect = rectangle();
      table.querySelectorAll('td[data-row]').forEach(cell => {
        const row = Number(cell.dataset.row), col = Number(cell.dataset.col);
        cell.classList.toggle('grid-selected', !!rect && row >= rect.top && row <= rect.bottom && col >= rect.left && col <= rect.right);
        cell.classList.toggle('grid-active', !!focus && row === focus.row && col === focus.col);
      });
      byId('gridSelectionStatus').textContent = rect ? `${rect.bottom - rect.top + 1} row(s) × ${rect.right - rect.left + 1} column(s) selected · ${columns[focus.col].label} · ${rows[focus.row].lineId}` : 'Select a cell to inspect or edit it.';
    }
    function select(row, col, extend = false, scroll = false) {
      const point = { row: Math.max(0, Math.min(rows.length - 1, row)), col: Math.max(0, Math.min(columns.length - 1, col)) };
      if (!inBounds(point)) return;
      if (!extend || !anchor) anchor = point;
      focus = point;
      updateSelection();
      const cell = table.querySelector(`td[data-row="${point.row}"][data-col="${point.col}"]`);
      if (scroll) cell?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      viewport.focus({ preventScroll: true });
    }
    function visibleRows() {
      const live = getLive();
      if (!live) return [];
      const q = byId('gridSearch').value.trim().toLowerCase();
      const phase = byId('gridPhase').value, group = byId('gridGroup').value;
      return live.items.filter(item => (!phase || item.phase === phase) && (!group || (item.checklistGroup || 'Materials') === group) && (!q || [item.lineId, item.description, item.phase, item.stage, item.checklistGroup, (item.categoryPath || []).join(' '), item.specification, item.vendor, item.partNumber, item.itemNotes].join(' ').toLowerCase().includes(q))).sort(sortRows);
    }
    function setOptions(select, values, allLabel) {
      const previous = select.value;
      select.innerHTML = `<option value="">${allLabel}</option>` + values.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
      if (values.includes(previous)) select.value = previous;
    }
    function render() {
      if (!getLive()) return;
      const live = getLive();
      setOptions(byId('gridPhase'), [...new Set(live.items.map(item => item.phase).filter(Boolean))].sort(), 'All phases');
      setOptions(byId('gridGroup'), [...new Set(live.items.map(item => item.checklistGroup || 'Materials'))].sort(), 'All groups');
      const activeId = focus && rows[focus.row]?.lineId, activeKey = focus && columns[focus.col]?.key;
      rows = visibleRows();
      table.innerHTML = `<thead><tr><th class="row-index">#</th>${columns.map(column => `<th class="${column.css || ''}" title="${escapeHtml(column.label)}">${escapeHtml(column.label)}</th>`).join('')}</tr></thead><tbody>${rows.map((item, index) => `<tr><th class="row-index" scope="row">${index + 1}</th>${columns.map((column, col) => { const value = display(item, column); const classes = [column.css || '', column.readonly ? 'readonly' : '', value === '' ? 'grid-empty' : '', changed.has(cellKey(item, column)) ? 'grid-dirty' : ''].join(' '); return `<td data-row="${index}" data-col="${col}" class="${classes}" title="${escapeHtml(value)}">${escapeHtml(value === '' ? '—' : value)}</td>`; }).join('')}</tr>`).join('')}</tbody>`;
      byId('gridCount').textContent = `${rows.length} visible / ${live.items.length} total items`;
      if (activeId) {
        const next = rows.findIndex(item => item.lineId === activeId);
        if (next >= 0) { anchor = { row: next, col: focus.col }; focus = anchor; }
        else anchor = focus = null;
      }
      if (!activeKey || !inBounds(focus)) anchor = focus = null;
      updateSelection();
    }
    function applyChanges(entries) {
      if (!entries.length) return;
      if (commitDraft() === false) return;
      const next = entries.map(({ row, col, raw }) => {
        const item = rows[row], column = columns[col];
        if (!item || !column) throw new Error('Paste extends beyond the visible table.');
        return { item, column, value: parseValue(raw, column) };
      });
      for (const { item, column, value } of next) {
        if (column.key === 'phase' || column.key === 'stage') {
          const peer = getLive().items.find(other => other !== item && other.phase === (column.key === 'phase' ? value : item.phase) && other.stage === (column.key === 'stage' ? value : item.stage));
          if (peer) { item.phaseOrder = peer.phaseOrder; item.stageOrder = peer.stageOrder; }
        }
        item[column.key] = value;
        changed.add(cellKey(item, column));
      }
      mark();
      renderAll();
    }
    function selectedText() {
      const rect = rectangle();
      if (!rect) return '';
      return Array.from({ length: rect.bottom - rect.top + 1 }, (_, offset) => columns.slice(rect.left, rect.right + 1).map(column => String(display(rows[rect.top + offset], column)).replaceAll('\t', ' ').replaceAll('\r', ' ').replaceAll('\n', ' ')).join('\t')).join('\r\n');
    }
    function pasteText(text) {
      if (!inBounds(focus)) return;
      const matrix = text.replace(/\r\n?/g, '\n').replace(/\n$/, '').split('\n').map(line => line.split('\t'));
      const rect = rectangle(), repeat = matrix.length === 1 && matrix[0].length === 1 && rect && (rect.bottom > rect.top || rect.right > rect.left);
      const top = repeat ? rect.top : focus.row, left = repeat ? rect.left : focus.col;
      const height = repeat ? rect.bottom - rect.top + 1 : matrix.length;
      const width = repeat ? rect.right - rect.left + 1 : Math.max(...matrix.map(line => line.length));
      if (top + height > rows.length || left + width > columns.length) throw new Error('Paste extends beyond the visible table.');
      const entries = [];
      for (let r = 0; r < height; r++) for (let c = 0; c < width; c++) {
        const col = left + c;
        if (columns[col].readonly) continue;
        entries.push({ row: top + r, col, raw: repeat ? matrix[0][0] : (matrix[r][c] ?? '') });
      }
      if (!entries.length) throw new Error('The selected cells are read only.');
      applyChanges(entries);
      select(top + height - 1, left + width - 1);
      status(`${entries.length} cell(s) updated in your draft. Save shared changes to publish.`);
    }
    function closeEditor(save) {
      if (!editor) return;
      const { input, row, col } = editor;
      editor = null;
      const raw = input.value;
      input.remove();
      if (!save) return;
      try { applyChanges([{ row, col, raw }]); select(row, col); }
      catch (error) { status(error.message, 'error'); select(row, col); }
    }
    function edit(initial) {
      if (!inBounds(focus)) return;
      const { row, col } = focus, column = columns[col];
      if (column.readonly) { status(column.label + ' is read only.', 'error'); return; }
      const cell = table.querySelector(`td[data-row="${row}"][data-col="${col}"]`);
      if (!cell) return;
      const box = cell.getBoundingClientRect(), parent = viewport.getBoundingClientRect();
      const input = document.createElement(column.key === 'itemNotes' || column.key === 'specification' ? 'textarea' : 'input');
      input.className = 'grid-cell-editor';
      input.value = initial ?? String(display(rows[row], column));
      input.style.left = `${box.left - parent.left + viewport.scrollLeft}px`;
      input.style.top = `${box.top - parent.top + viewport.scrollTop}px`;
      input.style.width = `${Math.max(box.width, 210)}px`;
      input.style.height = `${Math.max(box.height, input.tagName === 'TEXTAREA' ? 92 : 35)}px`;
      viewport.append(input);
      editor = { input, row, col };
      input.focus();
      if (initial === undefined) input.select();
      input.addEventListener('keydown', event => {
        if (event.key === 'Escape') { event.preventDefault(); closeEditor(false); }
        else if (event.key === 'Enter' && (input.tagName !== 'TEXTAREA' || event.ctrlKey)) { event.preventDefault(); closeEditor(true); select(Math.min(row + 1, rows.length - 1), col, false, true); }
        else if (event.key === 'Tab') { event.preventDefault(); closeEditor(true); select(row, Math.min(col + (event.shiftKey ? -1 : 1), columns.length - 1), false, true); }
      });
      input.addEventListener('blur', () => { if (editor?.input === input) closeEditor(true); });
    }
    table.addEventListener('mousedown', event => {
      const cell = event.target.closest('td[data-row]');
      if (!cell || event.button !== 0) return;
      event.preventDefault();
      dragging = true;
      select(Number(cell.dataset.row), Number(cell.dataset.col), event.shiftKey);
    });
    table.addEventListener('mouseover', event => {
      if (!dragging) return;
      const cell = event.target.closest('td[data-row]');
      if (cell) select(Number(cell.dataset.row), Number(cell.dataset.col), true);
    });
    document.addEventListener('mouseup', () => { dragging = false; });
    table.addEventListener('dblclick', event => {
      const cell = event.target.closest('td[data-row]');
      if (cell) { select(Number(cell.dataset.row), Number(cell.dataset.col)); edit(); }
    });
    viewport.addEventListener('keydown', event => {
      if (editor || !inBounds(focus)) return;
      const moves = { ArrowDown: [1, 0], ArrowUp: [-1, 0], ArrowRight: [0, 1], ArrowLeft: [0, -1] };
      if (moves[event.key]) { event.preventDefault(); select(focus.row + moves[event.key][0], focus.col + moves[event.key][1], event.shiftKey, true); }
      else if (event.key === 'Enter' || event.key === 'F2') { event.preventDefault(); edit(); }
      else if (event.key === 'Delete' || event.key === 'Backspace') {
        event.preventDefault();
        try { const rect = rectangle(), entries = []; for (let row = rect.top; row <= rect.bottom; row++) for (let col = rect.left; col <= rect.right; col++) if (!columns[col].readonly && !columns[col].required) entries.push({ row, col, raw: '' }); applyChanges(entries); }
        catch (error) { status(error.message, 'error'); }
      } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) { event.preventDefault(); edit(event.key); }
    });
    viewport.addEventListener('copy', event => { if (!inBounds(focus)) return; event.preventDefault(); event.clipboardData.setData('text/plain', selectedText()); });
    viewport.addEventListener('paste', event => { if (!inBounds(focus)) return; event.preventDefault(); try { pasteText(event.clipboardData.getData('text/plain')); } catch (error) { status(error.message, 'error'); } });
    byId('gridSearch').addEventListener('input', render);
    byId('gridPhase').addEventListener('change', render);
    byId('gridGroup').addEventListener('change', render);
    document.querySelector('.grid-mobile-nav')?.addEventListener('click', event => {
      const button = event.target.closest('button[data-grid-column]');
      if (!button) return;
      const col = columns.findIndex(column => column.key === button.dataset.gridColumn);
      if (col < 0) return;
      if (col === 1) { viewport.scrollTo({ left: 0, behavior: 'smooth' }); return; }
      const heading = table.querySelectorAll('thead th')[col + 1];
      if (!heading) return;
      const stickyWidth = window.matchMedia('(max-width: 570px)').matches ? 138 : 0;
      const left = viewport.scrollLeft + heading.getBoundingClientRect().left - viewport.getBoundingClientRect().left - stickyWidth - 8;
      viewport.scrollTo({ left: Math.max(0, left), behavior: 'smooth' });
    });
    byId('gridCopy').addEventListener('click', async () => { try { if (!selectedText()) throw new Error('Select cells to copy.'); await navigator.clipboard.writeText(selectedText()); status('Selection copied.'); } catch (error) { status(error.message, 'error'); } });
    byId('gridExport').addEventListener('click', () => {
      const csv = [columns.map(column => column.label), ...rows.map(item => columns.map(column => display(item, column)))].map(line => line.map(csvCell).join(',')).join('\r\n') + '\r\n';
      const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
      const link = document.createElement('a'); link.href = url; link.download = 'Monroe-Site-BOM-visible.csv'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    byId('gridAddItem').addEventListener('click', () => {
      try {
        if (commitDraft() === false) return;
        const live = getLive(), base = rows[focus?.row] || rows.at(-1) || live.items.at(-1);
        const id = 'SITE-' + crypto.randomUUID().split('-')[0].toUpperCase();
        live.items.push({ lineId: id, itemId: id, catalogId: id, description: 'New item', phase: base?.phase || 'Foundation', stage: base?.stage || 'New work area', phaseOrder: base?.phaseOrder ?? 99, stageOrder: base?.stageOrder ?? 99, checklistGroup: base?.checklistGroup || 'Materials', categoryPath: [...(base?.categoryPath || ['Materials'])], unit: 'EA', siteQuantity: null, listedQuantity: null, siteChecked: false, itemNotes: '', manualOrder: live.items.length, createdBySite: true });
        mark(); renderAll();
        const index = rows.findIndex(item => item.lineId === id);
        if (index >= 0) { select(index, 1, false, true); edit(); }
        else status('Row added outside the current filter. Clear filters to edit it.');
      } catch (error) { status(error.message, 'error'); }
    });
    return { render, reset: () => { changed.clear(); anchor = focus = null; render(); } };
  };
})();
