import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const html=fs.readFileSync(new URL('../outputs/NeoviBOM/NeoviBOM.html',import.meta.url),'utf8');
const scripts=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const nodes=new Map();
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',value:'',hidden:false,querySelectorAll(){return []},addEventListener(type,handler){this[type]=handler},showModal(){this.open=true},close(){this.open=false}});return nodes.get(id)}
node('snapshot').textContent=scripts[0];
const context=vm.createContext({document:{getElementById:node,querySelectorAll:()=>[]},console});
vm.runInContext(scripts[1],context);
const run=code=>vm.runInContext(code,context);


assert.match(html, /<title>Site Bill of Material<\/title>/);
assert.doesNotMatch(node('navigation').innerHTML,/Franklin|Santa Rita|Projects|neovi/i);
assert.equal((node('viewModes').innerHTML.match(/data-presentation=/g)||[]).length,2);
assert.doesNotMatch(node('viewModes').innerHTML,/Detailed catalog/);
for(const phase of ['Foundation','Panels','Finishing']){
 node('phases').click({target:{closest:()=>({dataset:{phase}})}});
 assert.equal((node('content').innerHTML.match(/class="material-entry"/g)||[]).length,run(`data.items.filter(i=>i.phase===${JSON.stringify(phase)}).length`));
 assert.match(node('content').innerHTML,/Materials <small>/);
 assert.match(node('content').innerHTML,/Tools <small>/);
 assert.doesNotMatch(node('content').innerHTML,/<details[^>]* open/);
}
run("state.phase='Panels';render()");
assert.deepEqual([...node('content').innerHTML.matchAll(/<h2 class="group-title">Panels \/ (.*?) <span/g)].map(m=>m[1]),['Floors','Walls','Trusses','Roof Panels']);
run("state.phase='Foundation';render()");
assert.match(node('content').innerHTML,/Total station surveying/);
assert.match(node('content').innerHTML,/Surveying tool for site layout/);
assert.equal(run('usedFor({})'),'N/A');
assert.equal(run('new Set(data.items.filter(i=>i.monroeEstimate).map(i=>i.originalLineId||i.lineId)).size'),275);
assert.equal(run("data.items.some(i=>i.lineId==='FND-021')"),false); // Deliberately represented by the total-station sheet row.
assert.equal(run("data.items.find(i=>i.lineId==='PAN-016').monroeEstimate.quantity"),400);
assert.match(run("monroeDetails(data.items.find(i=>i.lineId==='PAN-016'))"),/50 trusses × 8 EA per truss = 400 EA/);
assert.match(run("monroeDetails(data.items.find(i=>i.lineId==='PAN-016'))"),/Monroe-Item-Formulas\.md/);
assert.match(run("inlineDetails([data.items.find(i=>i.lineId==='FND-014')])"),/How calculated/);
assert.match(run("inlineDetails([data.items.find(i=>i.lineId==='FND-014')])"),/Specification and catalog details/);
assert.match(run("readableFormula(data.items.find(i=>i.lineId==='FND-014').monroeEstimate.formula)"),/50 pile positions × 2 EA per pile position = 100 EA/);
assert.equal(run("data.items.find(i=>i.lineId==='FND-037').unit"),'EA');
assert.equal(run("shownQuantity([data.items.find(i=>i.lineId==='FND-037')]).text"),'1');
assert.match(run("data.items.find(i=>i.lineId==='FND-037').description"),/100 ft assumed/);
run("state.query='no-such-material-zz';render()");
assert.match(node('content').innerHTML,/No matching materials/);
node('viewModes').click({target:{closest:()=>({dataset:{presentation:'ordering'}})}});
assert.equal(run('state.phase'),'');
assert.match(node('content').innerHTML,/All phases combined/);
assert.match(node('content').innerHTML,/Screws/);
assert.equal(run('purchaseGroups(data.items).flat().length'),run('data.items.length'));
// Same screw with different use IDs combines; different size or unit does not.
assert.equal(run(`purchaseGroups([
 {itemId:'FLOOR-1',description:'Floor screw',inventoryPrefix:'FAST',specification:'#10 x 2 inch hex head',unit:'EA'},
 {itemId:'TRUSS-1',description:'Truss screw',inventoryPrefix:'FAST',specification:'#10 x 2 inch hex head',unit:'EA'},
 {itemId:'ROOF-1',description:'Roof screw',inventoryPrefix:'FAST',specification:'#10 x 3 inch hex head',unit:'EA'}]).length`),2);
assert.equal(run(`purchaseGroups([
 {description:'Floor screws',specification:'TBD - approve exact specification',unit:'EA'},
 {description:'Truss screws',specification:'TBD - approve exact specification',unit:'EA'}]).length`),2);
assert.equal(run(`purchaseGroups([
 {description:'Floor fastener',vendor:'Vendor A',partNumber:'ABC',unit:'EA'},
 {description:'Roof fastener',vendor:'Vendor A',partNumber:'ABC',unit:'EA'}]).length`),1);
let prints=0,printedReport='';context.window={print(){prints++;printedReport=node('printReport').innerHTML}};
for(const phase of ['Foundation','Panels','Finishing']){
 run(`state.presentation='phase';state.phase=${JSON.stringify(phase)};state.path=['Tools'];state.query='zz-no-match';render();printPhase()`);
 assert.equal((printedReport.match(/class="material-entry"/g)||[]).length,run(`data.items.filter(i=>i.phase===${JSON.stringify(phase)}).length`));
 assert.equal(run('state.query'),'zz-no-match');
}
assert.equal(prints,3);
run('openCodeIndex()');
for(const code of ['EQUIP','SUP','TOOL','MAT','FIX','FAST','RIG'])assert.ok(node('detailContent').innerHTML.includes('<strong>'+code+'</strong>'));
run("state.view='documents';render()");assert.match(node('docList').innerHTML,/data-doc-folder/);
console.log('PASS: two views, every phase item, stage ordering, Total station, expandable details, cross-category purchasing matches, unknown specification separation, print reports and code index.');

assert.equal(run("data.items.filter(i=>i.checklistSource).length"),34);
assert.equal(run("data.items.find(i=>i.description==='Helical piles (6-inch)').listedQuantity"),50);
assert.equal(run("data.items.find(i=>i.description==='Helical piles (4-inch)').listedQuantity"),25);
assert.equal(run("data.items.find(i=>i.description==='Pile caps').listedQuantity"),75);
assert.equal(run("data.items.find(i=>i.description==='8x6 beam, L=8 ft').listedQuantity"),6);
assert.equal(run("listedQty(purchaseGroups(data.items).find(rows=>rows[0].purchaseType==='sheet-cutter-9-16'))"),'24');
assert.equal(run("listedQty(purchaseGroups(data.items).find(rows=>rows[0].purchaseType==='sheet-impact'))"),'2 + N/A');
assert.equal(run("shownQuantity([data.items.find(i=>i.lineId==='PAN-029')]).text"),'130');
assert.equal(run("shownQuantity([data.items.find(i=>i.lineId==='PAN-025')]).text"),'2');
assert.equal(run("shownQuantity([data.items.find(i=>i.lineId==='SHEET-008')]).text"),'4');
assert.equal(run("data.items.find(i=>i.lineId==='SHEET-008').stage"),'Shared Foundation Support');
assert.equal(run("data.items.find(i=>i.lineId==='SHEET-008').checklistGroup"),'Supplemental');
assert.equal(run("shownQuantity([data.items.find(i=>i.lineId==='SHEET-009')]).text"),'14');
assert.equal(run("data.items.find(i=>i.lineId==='SHEET-009').stage"),'Helical Piles');
assert.equal(run("shownQuantity([data.items.find(i=>i.lineId==='SHEET-020')]).text"),'200');
assert.equal(run("shownQuantity([data.items.find(i=>i.lineId==='SHEET-010')]).text"),'1');
assert.equal(run("data.items.find(i=>i.lineId==='SHEET-010').originalLineId"),'FND-060');
assert.equal(run("shownQuantity([data.items.find(i=>i.lineId==='SHEET-013')]).text"),'10');
assert.equal(run("data.items.find(i=>i.lineId==='SHEET-013').description"),'Orange-handle magnets');
assert.equal(run("data.items.find(i=>i.lineId==='SHEET-013').originalLineId"),'FND-061');
assert.equal(run("data.items.some(i=>i.lineId==='SHEET-014'||/Nylon chokers/i.test(i.description))"),false);
assert.equal(run("shownQuantity(data.items.filter(i=>i.originalLineId==='FND-048')).text"),'4');
assert.equal(run("data.items.find(i=>i.originalLineId==='FND-048').unit"),'EA');
assert.equal(run("shownQuantity(data.items.filter(i=>i.originalLineId==='FND-029')).text"),'2 + N/A');
assert.equal(run("orderingList(data.items).includes('Monroe estimate')"),true);
const unknownOrderingGroups=run("purchaseGroups(data.items.filter(i=>!i.description.startsWith('Define '))).filter(rows=>shownQuantity(rows).text.includes('N/A')).length");
assert.ok(unknownOrderingGroups<20,`${unknownOrderingGroups} ordering groups still lack a complete quantity`);
console.log(`Quantity display: ${unknownOrderingGroups} ordering groups retain N/A for an unresolved use.`);
assert.equal(run("purchaseGroups(data.items).filter(rows=>rows.some(i=>i.description.startsWith('Helical piles ('))).length"),2);
assert.equal(run("data.items.filter(i=>/total station/i.test(i.description)).length"),1);
run("state.view='catalog';state.presentation='phase';state.phase='Site Setup';state.query='';state.path=[];render()");
assert.match(node('content').innerHTML,/Temporary power/);
assert.doesNotMatch(node('content').innerHTML,/Mud mats \(winter\)/);
console.log('PASS: user-provided quantities, separate pile sizes, combined cutters, Site Setup and no duplicate total station.');

assert.equal(node('printReport').innerHTML,'');
assert.equal(run('new Set(data.items.map(i=>i.catalogId)).size'),run('data.items.length'));
assert.equal(run("checklistGroup({inventoryPrefix:'TOOL',description:'Annular cutter'})"),'Consumables');
assert.equal(run("specified('8x6 beam; remaining specification not supplied')"),false);
assert.equal(run("purchaseGroups([{lineId:'A',partNumber:'123',description:'A',unit:'EA'},{lineId:'B',partNumber:'123',description:'B',unit:'EA'}]).length"),2);
run("state.presentation='ordering';state.phase='';state.path=[];state.query='';render()");
assert.match(node('content').innerHTML,/Items still to define/);
console.log('PASS: audit regressions for IDs, print cleanup, unknown vendor identity, incomplete specifications and consumables.');

run("state.view='catalog';state.presentation='phase';state.phase='Foundation';state.path=[];state.query='';render()");
assert.doesNotMatch(node('content').innerHTML,/Additional catalog items|Other existing catalog items|class="extra-catalog"/);
assert.equal(run('data.items.some(i=>i.supplementalCatalog)'),false);
for(const [id,stage] of [['FND-020','Helical Piles'],['FND-007','Helical Piles'],['FND-055','Helical Piles'],['FND-056','Helical Piles'],['FND-057','Helical Piles'],['FND-037','Helical Piles'],['FND-016','Bedframe']]){
 assert.equal(run(`data.items.find(i=>i.lineId===${JSON.stringify(id)}).stage`),stage);
 assert.ok(node('content').innerHTML.includes(run(`data.items.find(i=>i.lineId===${JSON.stringify(id)}).description`)));
}
assert.equal(run("data.items.some(i=>i.lineId==='FND-003'||i.lineId==='FND-005')"),false);
assert.match(run("table(data.items.filter(i=>i.phase==='Foundation'&&i.stage==='Shared Foundation Support'),true)"),/Materials <small>0<\/small>/);
console.log('PASS: full Foundation inventory integrated into work packages, without an additional-items disclosure.');
