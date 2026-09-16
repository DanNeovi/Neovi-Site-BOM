import test from "node:test";
import assert from "node:assert/strict";
import { loadTemplateConfig } from "../src/template-model.mjs";
import { projectQuantityRows } from "../src/project-quantity-report.mjs";
const { lines } = await loadTemplateConfig();

test('model length floating-point noise does not add an extra foot', () => {
  const row=projectQuantityRows(lines,new Map([['FIN-087',{verified:true,value:264.00000000000006,references:['windows']}]]))
    .find(row=>row.lineId==='FIN-087');
  assert.equal(row.baseKit,264);
});

test('confirmed rigging quantities count complete sets and lifts', async () => {
  const fs = await import('node:fs/promises');
  const standards = JSON.parse(await fs.readFile(new URL('../config/confirmed-site-standards.json', import.meta.url), 'utf8'));
  for (const [id, expected] of [['PAN-001',1],['PAN-008',2]]) {
    const line=lines.find(row=>row.lineId===id);
    assert.equal(line.fixedQty,expected);
    assert.ok(standards[id]);
    const row=projectQuantityRows(lines,new Map([[id,{verified:true,value:line.fixedQty,references:['config/site-bom.template.json#'+id]}]])).find(row=>row.lineId===id);
    assert.equal(row.required,expected);
    assert.equal(row.spare,0);
    assert.equal(row.baseKit,expected);
    assert.equal(row.order,null);
  }
});

test("all project items retain missing quantities as unavailable", () => {
  const rows = projectQuantityRows(lines);
  assert.equal(rows.length, lines.length);
  assert.equal(new Set(rows.map(row => row.lineId)).size, lines.length);
  for (const row of rows) {
    for (const field of ["required", "spare", "kit", "net", "order", "cost", "onHand", "packSize", "unitCost"]) {
      assert.equal(row[field], null, `${row.lineId}: ${field} must not default to zero or a catalog allowance`);
    }
    for (const field of ["requiredFormula", "spareFormula", "kitFormula", "totalFormula", "netFormula", "orderFormula", "costFormula", "reason"]) assert.ok(row[field]);
  }
  assert.match(rows.find(row => row.lineId === "PAN-020").reason, /mapping.*unresolved/);
});

test("unverified model evidence cannot become a project quantity", () => {
  const row = projectQuantityRows(lines, new Map([["PAN-020", { value: 5924.745848, references: ["roof:test"] }]]))
    .find(row => row.lineId === "PAN-020");
  assert.equal(row.required, null);
  assert.equal(row.order, null);
});

test("verified zero takeoff is distinct from missing data and still needs purchasing inputs", () => {
  const row = projectQuantityRows(lines, new Map([["PAN-020", { verified: true, value: 0, references: ["roof:test"] }]]))
    .find(row => row.lineId === "PAN-020");
  assert.equal(row.required, 0);
  assert.equal(row.sourceReferences, "roof:test");
  assert.equal(row.order, null);
});

test("known takeoffs calculate spare and base kit without inventing inventory", () => {
  const row = projectQuantityRows(lines, new Map([["PAN-013", {verified:true,value:34,references:['link:holdowns']}]]))
    .find(row => row.lineId === 'PAN-013');
  assert.equal(row.spare,4);
  assert.equal(row.baseKit,38);
  assert.equal(row.kit,null);
  assert.equal(row.order,null);
});

test("provided purchasing inputs unlock dependent calculations", () => {
  const evidence = new Map([["PAN-013", {verified:true,value:34,references:['link:holdowns']}]]);
  const inputs = new Map([["PAN-013",{manualExtra:2,onHand:5,committed:3,targetStock:0,packSize:25,minimumOrder:0,unitCost:2}]]);
  const row = projectQuantityRows(lines,evidence,inputs).find(row => row.lineId === 'PAN-013');
  assert.equal(row.kit,40);
  assert.equal(row.net,32);
  assert.equal(row.order,50);
  assert.equal(row.cost,100);
});
