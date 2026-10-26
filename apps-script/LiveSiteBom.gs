/** @OnlyCurrentDoc */
/*
 * Bound to the native "Monroe Site BOM Live" Google Sheet.
 * Deploy as a Web app: execute as owner, access anyone. Public reads are JSONP;
 * writes require a PIN whose salted hash stays in Script Properties.
 */
const META_SHEET = 'Meta';
const STATE_PREFIX = 'State_v';
const MAX_FAILURES = 5;
const LOCK_MINUTES = 15;

function doGet(e) {
  const mode = String((e.parameter || {}).mode || 'read');
  if (mode !== 'read' && mode !== 'history') return output_({error:'Unknown mode'}, e);
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const state = mode === 'read' ? readState_() : readHistory_();
    return output_(state, e);
  } finally { lock.releaseLock(); }
}

function doPost(e) {
  const p = e.parameter || {};
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    if (!validPin_(String(p.pin || ''))) return ContentService.createTextOutput('PIN rejected or temporarily locked');
    if (p.action === 'save') return save_(p);
    if (p.action === 'restore') return restore_(p);
    if (p.action === 'source') return source_(p);
    return ContentService.createTextOutput('Unknown action');
  } finally { lock.releaseLock(); }
}

function output_(value, e) {
  const json = JSON.stringify(value).replace(/</g, '\\u003c');
  const callback = String((e.parameter || {}).callback || '');
  if (!/^siteBomCallback_[A-Za-z0-9]{8,64}$/.test(callback))
    return ContentService.createTextOutput(json).setMimeType(ContentService.MimeType.JSON);
  return ContentService.createTextOutput(callback + '(' + json + ');').setMimeType(ContentService.MimeType.JAVASCRIPT);
}

function spreadsheet_() { return SpreadsheetApp.getActiveSpreadsheet(); }
function meta_() {
  const sheet = spreadsheet_().getSheetByName(META_SHEET);
  if (!sheet) throw new Error('Missing Meta sheet');
  const values = sheet.getRange(2, 1, 1, 7).getValues()[0];
  if (!/^State_v\d+$/.test(String(values[0]))) throw new Error('Invalid active state');
  return {sheet:String(values[0]), revision:Number(values[1]), nonce:String(values[2] || ''), updatedAt:String(values[3] || ''), actor:String(values[4] || ''), sourceSheet:String(values[5] || 'Source_v1'), sourceHash:String(values[6] || '')};
}

function readStateSheet_(name) {
  const sheet = spreadsheet_().getSheetByName(name);
  if (!sheet) throw new Error('Missing ' + name);
  const rows = sheet.getLastRow() > 1 ? sheet.getRange(2, 1, sheet.getLastRow()-1, 3).getValues() : [];
  const items = [], categories = [];
  for (const row of rows) {
    if (!row[0]) continue;
    const entry = JSON.parse(String(row[2]));
    if (row[0] === 'item') items.push(entry);
    else if (row[0] === 'category') categories.push(entry);
    else throw new Error('Unknown state row ' + row[0]);
  }
  return {items, categories};
}

function readState_() {
  const m = meta_();
  return Object.assign({schema:'neovi.site-bom.live.v1'}, m, readStateSheet_(m.sheet));
}

function readHistory_() {
  return {revisions:spreadsheet_().getSheets().map(s=>s.getName()).filter(n=>/^State_v\d+$/.test(n)).map(n=>Number(n.slice(7))).sort((a,b)=>b-a)};
}

function validateState_(value) {
  if (!value || !Array.isArray(value.items) || !Array.isArray(value.categories) || value.items.length > 5000 || value.categories.length > 1000)
    throw new Error('Invalid state structure');
  const ids = new Set(), paths = new Set();
  for (const item of value.items) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) throw new Error('Invalid item');
    const id = String(item.lineId || '');
    if (!/^[A-Za-z0-9_-]{1,80}$/.test(id) || ids.has(id)) throw new Error('Missing or duplicate item ID');
    ids.add(id);
    if (!String(item.description || '').trim() || String(item.description).length > 500) throw new Error('Invalid item name');
    if (!String(item.phase || '').trim() || String(item.phase).length > 150 || !String(item.stage || '').trim() || String(item.stage).length > 150) throw new Error('Invalid phase or work area');
    if (item.categoryPath != null && (!Array.isArray(item.categoryPath) || item.categoryPath.length > 8 || item.categoryPath.some(p=>typeof p !== 'string' || !p.trim() || p.length > 150))) throw new Error('Invalid item category path');
    if (item.unit != null && (typeof item.unit !== 'string' || item.unit.length > 40)) throw new Error('Invalid unit');
    if (item.manualOrder != null && (!Number.isFinite(item.manualOrder) || Math.abs(item.manualOrder)>1000000)) throw new Error('Invalid item order');
    if (item.siteChecked != null && typeof item.siteChecked !== 'boolean') throw new Error('Invalid checkoff');
    if (item.siteQuantity != null && (!Number.isFinite(item.siteQuantity) || item.siteQuantity < 0)) throw new Error('Invalid site quantity');
    if (item.listedQuantity != null && (!Number.isFinite(item.listedQuantity) || item.listedQuantity < 0)) throw new Error('Invalid listed quantity');
    if (JSON.stringify(item).length > 45000) throw new Error('Item too large for Google Sheets');
  }
  for (const category of value.categories) {
    if (!category || !Array.isArray(category.path) || !category.path.length || category.path.length > 8 || category.path.some(p=>typeof p !== 'string' || !p.trim() || p.length > 150)) throw new Error('Invalid category');
    const key = JSON.stringify(category.path);
    if (paths.has(key)) throw new Error('Duplicate category');
    paths.add(key);
  }
}

function writeState_(value, revision, nonce, actor, sourceSheet, sourceHash) {
  validateState_(value);
  const name = STATE_PREFIX + revision;
  if (spreadsheet_().getSheetByName(name)) throw new Error('Revision already exists');
  const sheet = spreadsheet_().insertSheet(name);
  sheet.getRange(1,1,1,3).setValues([['Type','ID or path','JSON']]);
  const rows = value.items.map(item=>['item',item.lineId,JSON.stringify(item)]).concat(value.categories.map(category=>['category',category.path.join(' / '),JSON.stringify(category)]));
  if (rows.length) sheet.getRange(2,1,rows.length,3).setValues(rows);
  sheet.hideSheet();
  const previous=meta_();
  spreadsheet_().getSheetByName(META_SHEET).getRange(2,1,1,7).setValues([[name,revision,nonce,new Date().toISOString(),actor,sourceSheet||previous.sourceSheet,sourceHash||previous.sourceHash]]);
  SpreadsheetApp.flush();
}

function save_(p) {
  const m = meta_();
  if (Number(p.revision) !== m.revision) return ContentService.createTextOutput('Revision conflict');
  const nonce = String(p.nonce || '');
  if (!/^[A-Za-z0-9_-]{12,80}$/.test(nonce)) throw new Error('Invalid nonce');
  const actor = String(p.actor || 'PIN editor').trim().slice(0,100);
  const value = JSON.parse(String(p.payload || ''));
  writeState_(value,m.revision+1,nonce,actor);
  return ContentService.createTextOutput('Saved revision ' + (m.revision+1));
}

function restore_(p) {
  const m = meta_(), target = Number(p.targetRevision);
  if (Number(p.revision) !== m.revision) return ContentService.createTextOutput('Revision conflict');
  if (!Number.isSafeInteger(target) || target < 1 || target >= m.revision) throw new Error('Invalid restore revision');
  const value = readStateSheet_(STATE_PREFIX+target);
  writeState_(value,m.revision+1,String(p.nonce || ''),String(p.actor || 'PIN editor')+' restored '+target);
  return ContentService.createTextOutput('Restored revision ' + target);
}

function source_(p) {
  const m=meta_(), hash=String(p.sourceHash || '');
  if (!/^[a-f0-9]{64}$/.test(hash)) throw new Error('Invalid source hash');
  if (hash===m.sourceHash) return ContentService.createTextOutput('Source already current');
  if (Number(p.revision)!==m.revision) return ContentService.createTextOutput('Revision conflict');
  const incoming=JSON.parse(String(p.payload || ''));
  if (!Array.isArray(incoming.items)) throw new Error('Missing source items');
  const before=readStateSheet_(m.sourceSheet).items;
  const edited=readState_();
  const merged=mergeSource_(before,edited.items,incoming.items);
  const sourceName='Source_v'+(m.revision+1);
  const sourceTab=spreadsheet_().insertSheet(sourceName);
  sourceTab.getRange(1,1,1,3).setValues([['Type','ID or path','JSON']]);
  if(incoming.items.length)sourceTab.getRange(2,1,incoming.items.length,3).setValues(incoming.items.map(i=>['item',i.lineId,JSON.stringify(i)]));
  sourceTab.hideSheet();
  writeState_({items:merged,categories:edited.categories},m.revision+1,String(p.nonce || ''),'NeoviOne export',sourceName,hash);
  return ContentService.createTextOutput('Imported source revision '+(m.revision+1));
}

function mergeSource_(before,edited,incoming) {
  const oldById=new Map(before.map(i=>[i.lineId,i]));
  const editedById=new Map(edited.map(i=>[i.lineId,i]));
  const nextIds=new Set();
  const merged=incoming.map(fresh=>{
    const id=String(fresh.lineId || '');
    if (!id || nextIds.has(id)) throw new Error('Duplicate source ID');
    nextIds.add(id);
    const old=oldById.get(id),current=editedById.get(id);
    if (!current) return old ? null : fresh; // A site deletion remains deleted.
    if (!old) return current;
    const next={...fresh};
    for(const field of new Set([...Object.keys(old),...Object.keys(current)])){
      if(JSON.stringify(current[field])!==JSON.stringify(old[field])){
        if(Object.hasOwn(current,field))next[field]=current[field];else delete next[field];
      }
    }
    return next;
  }).filter(Boolean);
  for(const current of edited){
    if(nextIds.has(current.lineId))continue;
    merged.push({...current,sourceMissing:true}); // Never silently erase an old source item.
  }
  return merged;
}

function digest_(salt,pin) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,salt+':'+pin)
    .map(b=>('0'+(b&255).toString(16)).slice(-2)).join('');
}

function validPin_(pin) {
  const props=PropertiesService.getScriptProperties();
  const until=Number(props.getProperty('LOCK_UNTIL') || 0);
  if (Date.now() < until) return false;
  const salt=props.getProperty('PIN_SALT'), hash=props.getProperty('PIN_HASH');
  if (!salt || !hash) throw new Error('Configure PIN before deploying');
  const candidate=/^\d{6}$/.test(pin) ? digest_(salt,pin) : digest_(salt,'000000');
  let difference=0; for (let i=0;i<hash.length;i++) difference |= hash.charCodeAt(i)^candidate.charCodeAt(i);
  if (difference===0 && /^\d{6}$/.test(pin)) { props.deleteProperty('PIN_FAILURES'); return true; }
  const failures=Number(props.getProperty('PIN_FAILURES') || 0)+1;
  if (failures >= MAX_FAILURES) { props.setProperty('LOCK_UNTIL',String(Date.now()+LOCK_MINUTES*60*1000)); props.deleteProperty('PIN_FAILURES'); }
  else props.setProperty('PIN_FAILURES',String(failures));
  return false;
}

// In Script Properties, enter SITE_BOM_SETUP_PIN once, run this function in
// the Apps Script editor, then deploy. The clear-text property is deleted.
function configureEditorPin() {
  const props=PropertiesService.getScriptProperties();
  const pin=String(props.getProperty('SITE_BOM_SETUP_PIN') || '');
  if (!/^\d{6}$/.test(pin)) throw new Error('Set a six-digit SITE_BOM_SETUP_PIN Script Property first');
  const salt=Utilities.getUuid()+Utilities.getUuid();
  props.setProperty('PIN_SALT',salt);
  props.setProperty('PIN_HASH',digest_(salt,pin));
  props.deleteProperty('SITE_BOM_SETUP_PIN');
  props.deleteProperty('PIN_FAILURES');
  props.deleteProperty('LOCK_UNTIL');
}

function testReadState() {
  const state=readState_();
  if (state.revision!==1 || state.items.length<300 || state.categories.length<100)
    throw new Error('Live Sheet does not contain the expected initial catalog');
  Logger.log('Revision '+state.revision+': '+state.items.length+' items, '+state.categories.length+' categories');
}
