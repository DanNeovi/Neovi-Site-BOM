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
  async function readOnce() {
    const url = new URL(endpoint);
    url.searchParams.set('mode','read');
    url.searchParams.set('_',Date.now());
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(),20000);
    try {
      const response = await fetch(url,{credentials:'omit',cache:'no-store',signal:controller.signal});
      if (!response.ok) throw new Error('Shared BOM returned HTTP '+response.status);
      return await response.json();
    } finally { clearTimeout(timer); }
  }
  async function readShared() {
    let error;
    for (let attempt = 0; attempt < 2; attempt++) {
      try { return await readOnce(); } catch (e) { error = e; }
    }
    throw error;
  }
  const originalTable = table;
  const originalInlineDetails = inlineDetails;
  inlineDetails = function (items) {
    return originalInlineDetails(items) + '<details class="all-fields"><summary>All item fields</summary>' + items.map(i => fields(i)).join('') + '</details>';
  };
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
  let loading=false, loaded=false, retryTimer=null, retryDelay=30000;
  const retryButton=document.createElement('button');
  retryButton.type='button';
  retryButton.textContent='Retry live connection';
  retryButton.style.cssText='margin-left:10px;padding:3px 9px;border:1px solid currentColor;border-radius:4px;background:transparent;color:inherit;cursor:pointer';
  retryButton.onclick=()=>{clearTimeout(retryTimer);retryTimer=null;loadShared();};
  function scheduleRetry(){
    if(retryTimer)return;
    retryTimer=setTimeout(()=>{retryTimer=null;if(document.hidden)scheduleRetry();else loadShared();},retryDelay);
    retryDelay=Math.min(retryDelay*2,300000);
  }
  async function loadShared(){
    if(loading)return;
    loading=true;
    banner.textContent='Loading shared Site BOM…';
    try{
      const live=await readShared();
      if(!Array.isArray(live.items)||!Number.isSafeInteger(live.revision))throw new Error('Invalid shared BOM');
      data.items=live.items;
      topFolders.splice(0,topFolders.length,...[...new Set(live.items.map(i=>itemPath(i)[0]))].sort());
      sheetReferenceCounts.clear();
      for(const i of live.items)if(i.checklistSource&&i.originalLineId)
        sheetReferenceCounts.set(i.originalLineId,(sheetReferenceCounts.get(i.originalLineId)||0)+1);
      progress=Object.fromEntries(live.items.map(i=>[i.lineId,{quantity:i.siteQuantity??null,done:!!i.siteChecked}]));
      banner.style.background='#e9f6ed';banner.style.color='#19522e';
      banner.textContent='Shared Site BOM · revision '+live.revision+' · saved '+new Date(live.updatedAt).toLocaleString();
      render();
      const tag=document.querySelector('.topline .tag');
      if(tag)tag.textContent='Monroe · shared live BOM';
      loaded=true;retryDelay=30000;clearTimeout(retryTimer);retryTimer=null;
    }catch(error){
      loaded=false;
      banner.style.background='#fff3cd';banner.style.color='#463b15';
      banner.textContent='Shared BOM unavailable. Showing the last published snapshot; editing is paused. '+error.message+' ';
      banner.append(retryButton);
      scheduleRetry();
    }finally{loading=false;}
  }
  window.addEventListener('online',()=>{if(!loaded)loadShared();});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!loaded)loadShared();});
  loadShared();
})();
