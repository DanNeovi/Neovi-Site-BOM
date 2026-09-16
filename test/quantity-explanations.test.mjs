import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { quantityBasis } from "../src/quantity-explanations.mjs";
import { loadTemplateConfig } from "../src/template-model.mjs";
import { calculateBomLine, calculateProcurementItem } from "../src/calculations.mjs";
import { phaseRowFormulas, CATEGORY_SECTIONS, categorySectionNumber } from "../src/workbook-formulas.mjs";

const { lines, items } = await loadTemplateConfig();

test("all catalog items have stable stage-prefixed category numbers", () => {
  assert.equal(new Set(CATEGORY_SECTIONS.map(section => section[0])).size, CATEGORY_SECTIONS.length);
  for (const line of lines) {
    assert.match(line.categorySection, /^\d+\.\d+$/);
    assert.equal(line.categorySection.split(".")[0], line.deliveryStage);
  }
  assert.equal(categorySectionNumber("3", "Finishing", "Truss Area Finish", "Interior Finishes"), "3.10");
  assert.equal(categorySectionNumber("3", "Finishing", "Gutter / Fascia", "Building Envelope"), "3.11");
  assert.equal(categorySectionNumber("3", "Finishing", "Finish MEP", "Electrical"), "3.1");
});

test("category numbers distinguish delivery stages and do not depend on item order", () => {
  assert.equal(categorySectionNumber("1", "Panels", "Floors", "Structural"), "1.4");
  assert.equal(categorySectionNumber("2", "Panels", "Floors", "Structural"), "2.1");
  assert.equal(categorySectionNumber("2", "Panels", "New category", "Structural"), "Unnumbered");
  for (const line of [...lines].reverse()) {
    assert.equal(categorySectionNumber(line.deliveryStage, line.phase, line.stage, line.category), line.categorySection);
  }
});

test("explanations preserve distinct measured and purchased units", () => {
  const text = quantityBasis({ ...lines[0], sourceMode: "CALCULATED", inputKey: "measured_area", inputUnit: "SQFT", unit: "EA", multiplier: 0.03125 });
  assert.match(text, /in SQFT\) x 0.03125 = quantity in EA/);
});

test("all catalog lines explain source, rounding, inventory and ordering", () => {
  assert.ok(lines.length > 0);
  for (const line of lines) {
    const explanation = quantityBasis(line);
    assert.doesNotMatch(explanation, /undefined|NaN/);
    for (const step of ["Required =", "Spare =", "Kit =", "Net =", "Order =", "Order once"]) {
      assert.ok(explanation.includes(step), `${line.lineId}: missing ${step}`);
    }
    if (line.sourceMode === "MANUAL" && !line.takeoffFormula) assert.match(explanation, /takeoff needed/);
  }
});

test("fixed and manual explanations include extras, spares and minimums", () => {
  for (const sourceMode of ["FIXED", "MANUAL"]) {
    const result = calculateBomLine({ ...lines[0], sourceMode, fixedQty: 3, sparePercent: 0.25,
      quantityIncrement: 2, minimumKitQty: 10 }, new Map(), { manualBaseQty: 3, manualExtra: 1 });
    assert.equal(result.requiredQty, 3);
    assert.equal(result.ruleSpareQty, 2);
    assert.equal(result.kitDemandQty, 10);
    assert.match(result.calculation, /3 \+ 2 spare \+ 1 extra, minimum 10/);
    assert.match(result.calculation, /increment 2\) = 10/);
  }
});

test("live explanation references final quantities and all-phase stock without a circular dependency", () => {
  const formula = phaseRowFormulas(8).calculation;
  for (const reference of ["$R8", "$T8", "$W8", "$V8", "$U8", "$X8", "$Y8", "$Z8", "$AA8", "$AB8", "$AC8", "$AD8", "$AE8"]) {
    assert.ok(formula.includes(reference), `Missing ${reference}`);
  }
  assert.match(formula, /'Procurement Summary'!\$M\$4/);
  assert.match(formula, /PREVIEW ONLY/);
  assert.match(formula, /Order once per Item ID/);
  assert.doesNotMatch(formula, /\$Q8/);
});

test("measured areas from the large Monroe Everything export exercise fractional quantities and packs", async () => {
  const fixture = JSON.parse(await fs.readFile(new URL("fixtures/everything-roof-samples.json", import.meta.url)));
  assert.equal(fixture.exportElementCount, 200802);
  assert.equal(new Set(fixture.rows.map(row => row.sourceReference)).size, 3);
  const sourceArea = fixture.rows.reduce((sum, row) => sum + row.value, 0);
  const line = lines.find(row => row.inputKey === "roof_slope_material_area");
  const result = calculateBomLine(line, new Map([[line.inputKey, sourceArea]]));
  assert.ok(Math.abs(result.requiredQty - 2694.1875158282427) < 1e-9);
  assert.equal(result.ruleSpareQty, 270);
  assert.equal(result.kitDemandQty, 2965);
  const item = items.find(row => row.itemId === line.itemId);
  // Inventory and 32 SQFT packs are explicit test assumptions, not vendor specifications.
  const purchase = calculateProcurementItem({ ...item, packSize: 32, minimumOrderQty: 0 }, [result], { onHand: 100 });
  assert.equal(purchase.netNeed, 2865);
  assert.equal(purchase.orderQty, 2880);
  assert.match(result.calculation, /270 spare/);
  assert.match(result.calculation, /= 2,965 SQFT/);
});

test("Franklin Everything roof samples retain small fractional areas in the quantity calculation", async () => {
  const fixture = JSON.parse(await fs.readFile(new URL("fixtures/everything-franklin-roof-samples.json", import.meta.url)));
  assert.equal(fixture.exportElementCount, 128660);
  const line = lines.find(row => row.inputKey === "roof_slope_material_area");
  const sourceArea = fixture.rows.reduce((sum, row) => sum + row.value, 0);
  const result = calculateBomLine(line, new Map([[line.inputKey, sourceArea]]));
  assert.ok(Math.abs(result.requiredQty - 3204.858952651164) < 1e-9);
  assert.equal(result.ruleSpareQty, 321);
  assert.equal(result.kitDemandQty, 3526);
  assert.match(result.calculation, /321 spare/);
  assert.match(result.calculation, /= 3,526 SQFT/);
});

test("complete qualifying Santa Rita and Franklin roof candidate sets reproduce independently verified totals", async () => {
  const projects = JSON.parse(await fs.readFile(new URL("fixtures/everything-project-roof-candidates.json", import.meta.url)));
  const expected = [[204135, 11, 593, 6518], [128660, 6, 327, 3588]];
  const line = lines.find(row => row.inputKey === "roof_slope_material_area");
  for (const [index, project] of projects.entries()) {
    const [elements, candidates, spare, kit] = expected[index];
    assert.equal(project.elementCount, elements);
    assert.equal(project.rows.length, candidates);
    assert.equal(new Set(project.rows.map(row => row.key)).size, candidates);
    for (const row of project.rows) {
      assert.equal(row.sourceKey, "host");
      assert.equal(row.unit, "SQFT");
      assert.equal(row.phaseCreated, "New Construction");
      assert.ok(!row.phaseDemolished && !row.designOption && !row.viewSpecific);
      assert.ok(row.value > 0);
    }
    const value = project.rows.reduce((sum, row) => sum + row.value, 0);
    const result = calculateBomLine(line, new Map([[line.inputKey, value]]));
    assert.equal(result.ruleSpareQty, spare);
    assert.equal(result.kitDemandQty, kit);
  }
});
