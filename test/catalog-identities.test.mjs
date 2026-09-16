import test from 'node:test';
import assert from 'node:assert/strict';
import { assignIdentities } from '../scripts/sync-catalog-identities.mjs';
import { loadTemplateConfig } from '../src/template-model.mjs';

test('catalog IDs survive insertion, folder changes, retirement and return without reuse', () => {
  const item=(id)=>({id,description:id,inventoryPrefix:'TOOL',categoryPath:['Tools','Drilling']});
  const a=item('A'), b=item('B');const registry=assignIdentities([a,b]);
  assert.equal(a.catalogId,'TOOL-1');assert.equal(b.catalogId,'TOOL-2');
  a.categoryPath=['Tools','New Folder'];const c=item('C');assignIdentities([c,a],registry);
  assert.equal(a.catalogId,'TOOL-1');assert.equal(c.catalogId,'TOOL-3');assert.equal(registry.entries.B.status,'retired');
  assignIdentities([b,c,a],registry);assert.equal(b.catalogId,'TOOL-2');
});
test('catalog numbering supports more digits than JavaScript safe integers',()=>{
 const registry={next:{FAST:'999999999999999999999999999999'},entries:{}};
 const items=['A','B'].map(id=>({id,description:id,inventoryPrefix:'FAST',categoryPath:['Fasteners','Steel']}));
 assignIdentities(items,registry);
 assert.equal(items[0].catalogId,'FAST-999999999999999999999999999999');
 assert.equal(items[1].catalogId,'FAST-1000000000000000000000000000000');
});
test('every active item has a unique folder identity and requested retirements stay absent',async()=>{
 const {lines}=await loadTemplateConfig();
 assert.equal(new Set(lines.map(l=>l.catalogId)).size,lines.length);
 for(const l of lines){assert.match(l.catalogId,/^[A-Z]+-\d+$/);assert.ok(l.categoryPath.length>=2);}
 for(const id of ['FND-002','FND-004','FND-008','FND-013','FND-038','FND-039','FND-042','FND-044','PAN-026','PAN-027','PAN-033']) assert.ok(!lines.some(l=>l.lineId===id),id);
 assert.equal(lines.find(l=>l.lineId==='FND-009').fixedQty,3);
 assert.equal(lines.find(l=>l.lineId==='FND-043').unit,'EA');
 assert.equal(lines.find(l=>l.lineId==='FND-043').procurementMethod,'Inventory');
 assert.equal(lines.find(l=>l.lineId==='PAN-010').inputKey,'');
 assert.match(lines.find(l=>l.lineId==='PAN-007').takeoffFormula,/0\.5 IN/);
 const mag=lines.filter(l=>['FND-046','FND-047','FND-048','FND-055','FND-056','FND-057'].includes(l.lineId));
 assert.ok(mag.every(l=>l.categoryPath[1]==='Magnetic Drill'));
});
