(function () {
  'use strict';
  const endpoint = window.SITE_BOM_LIVE_URL;
  if (!endpoint) return;
  const banner = document.createElement('div');
  banner.setAttribute('role', 'status');
  banner.style.cssText = 'position:sticky;top:0;z-index:10;padding:8px 16px;background:#fff3cd;color:#463b15;text-align:center;font:13px Segoe UI,Arial,sans-serif';
  banner.textContent = 'Loading shared Site BOM…';
  document.body.prepend(banner);
  const editLink = document.createElement('a');
  editLink.href = 'editor.html';
  editLink.textContent = 'Edit shared BOM';
  editLink.style.cssText = 'display:block;margin:12px 0;color:#fff;font-weight:600';
  document.querySelector('aside nav')?.after(editLink);
  function jsonp() {
    return new Promise((resolve,reject) => {
      const name = 'siteBomCallback_' + Array.from(crypto.getRandomValues(new Uint8Array(12)),x=>x.toString(16).padStart(2,'0')).join('');
      const script = document.createElement('script');
      const timer = setTimeout(() => finish(new Error('Shared BOM timed out')),20000);
      function finish(value) { clearTimeout(timer); delete window[name]; script.remove(); value instanceof Error ? reject(value) : resolve(value); }
      window[name] = finish;
      script.onerror = () => finish(new Error('Shared BOM unavailable'));
      const url = new URL(endpoint);
      url.searchParams.set('mode','read'); url.searchParams.set('callback',name); url.searchParams.set('_',Date.now());
      script.src = url.href; document.head.append(script);
    });
  }
  const originalTable = table;
  table = function (items,showEmptyMaterials) {
    const known = new Set(['Site services','Equipment','Supplemental','Materials','Tools','Consumables']);
    const extra = [...new Set(items.map(checklistGroup).filter(group=>!known.has(group)))];
    return originalTable(items.filter(i=>known.has(checklistGroup(i))),showEmptyMaterials) + extra.map(group =>
      '<section class="work-area"><h2 class="group-title">'+esc(group)+'</h2>'+compactList(items.filter(i=>checklistGroup(i)===group))+'</section>').join('');
  };
  const originalSourceOrder = sourceOrder;
  sourceOrder = (a,b) => Number.isFinite(a.manualOrder) && Number.isFinite(b.manualOrder) && a.manualOrder!==b.manualOrder
    ? a.manualOrder-b.manualOrder : originalSourceOrder(a,b);
  openProgress = id => { location.href='editor.html#'+encodeURIComponent(id); };
  jsonp().then(live => {
    if (!Array.isArray(live.items) || !Number.isSafeInteger(live.revision)) throw new Error('Invalid shared BOM');
    data.items = live.items;
    topFolders.splice(0,topFolders.length,...[...new Set(live.items.map(i=>itemPath(i)[0]))].sort());
    sheetReferenceCounts.clear();
    for (const i of live.items) if(i.checklistSource&&i.originalLineId)
      sheetReferenceCounts.set(i.originalLineId,(sheetReferenceCounts.get(i.originalLineId)||0)+1);
    progress = Object.fromEntries(live.items.map(i=>[i.lineId,{quantity:i.siteQuantity??null,done:!!i.siteChecked}]));
    banner.style.background='#e9f6ed'; banner.style.color='#19522e';
    banner.textContent='Shared Site BOM · revision '+live.revision+' · saved '+new Date(live.updatedAt).toLocaleString();
    render();
  }).catch(error => {
    banner.textContent='Shared BOM unavailable. Showing the last published snapshot; editing is paused. '+error.message;
  });
})();
