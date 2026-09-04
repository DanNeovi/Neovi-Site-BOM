import test from "node:test";
import assert from "node:assert/strict";
import { calculateBomLine, calculateProcurementItem, roundUpTo } from "../src/calculations.mjs";
import { loadProjectInputCsv } from "../src/project-input-csv.mjs";
import { buildProjectInputMap, loadTemplateConfig } from "../src/template-model.mjs";

const { lines, items } = await loadTemplateConfig();
const { projectInputs } = await loadProjectInputCsv();
const inputMap = buildProjectInputMap(projectInputs);

function line(lineId) {
  const result = lines.find((candidate) => candidate.lineId === lineId);
  assert.ok(result, `Missing test line ${lineId}`);
  return result;
}

function item(itemId) {
  const result = items.find((candidate) => candidate.itemId === itemId);
  assert.ok(result, `Missing test item ${itemId}`);
  return result;
}

test("floor connecting rods preserve the 25 percent rule", () => {
  const result = calculateBomLine(line("PAN-003"), inputMap);
  assert.equal(result.sourceValue, 80);
  assert.equal(result.requiredQty, 80);
  assert.equal(result.ruleSpareQty, 20);
  assert.equal(result.kitDemandQty, 100);
});

test("floor plates apply the configurable minimum kit quantity", () => {
  const result = calculateBomLine(line("PAN-002"), inputMap);
  assert.equal(result.sourceValue, 186);
  assert.equal(result.requiredQty, 186);
  assert.equal(result.kitDemandQty, 250);
});

test("vendor pack does not inflate installation demand", () => {
  const result = calculateBomLine(line("PAN-009"), inputMap);
  assert.equal(result.requiredQty, 1240);
  assert.equal(result.ruleSpareQty, 124);
  assert.equal(result.kitDemandQty, 1364);
});

test("manual extra remains auditable and part of kit demand", () => {
  const withoutReason = calculateBomLine(line("PAN-003"), inputMap, { manualExtra: 10 });
  assert.equal(withoutReason.kitDemandQty, 110);
  assert.ok(withoutReason.issues.includes("Manual extra needs a reason"));

  const withReason = calculateBomLine(line("PAN-003"), inputMap, {
    manualExtra: 10,
    adjustmentReason: "Prototype field buffer",
  });
  assert.equal(withReason.kitDemandQty, 110);
  assert.ok(!withReason.issues.includes("Manual extra needs a reason"));
});

test("inventory is subtracted before vendor pack rounding", () => {
  const lineResult = calculateBomLine(line("PAN-009"), inputMap);
  const result = calculateProcurementItem(item("PAN-009"), [lineResult], { onHand: 64 });
  assert.equal(lineResult.kitDemandQty, 1364);
  assert.equal(result.netNeed, 1300);
  assert.equal(result.orderQty, 1300);
});

test("purchasing aggregates multiple BOM lines by shared Item ID", () => {
  const sharedItem = { ...item("PAN-009"), itemId: "SHARED", packSize: 25, minimumOrderQty: 0 };
  const result = calculateProcurementItem(sharedItem, [
    { itemId: "SHARED", kitDemandQty: 60 },
    { itemId: "SHARED", kitDemandQty: 40 },
  ], { onHand: 10 });
  assert.equal(result.totalKitDemand, 100);
  assert.equal(result.netNeed, 90);
  assert.equal(result.orderQty, 100);
});

test("zero net need does not trigger a minimum order", () => {
  const result = calculateProcurementItem(
    { ...item("PAN-009"), minimumOrderQty: 500 },
    [{ itemId: "PAN-009", kitDemandQty: 100 }],
    { onHand: 100 },
  );
  assert.equal(result.netNeed, 0);
  assert.equal(result.orderQty, 0);
});

test("negative inventory is normalized safely and still flagged", () => {
  const result = calculateProcurementItem(
    item("PAN-009"),
    [{ itemId: "PAN-009", kitDemandQty: 100 }],
    { onHand: -5, alreadyCommitted: -2 },
  );
  assert.equal(result.onHand, 0);
  assert.equal(result.alreadyCommitted, 0);
  assert.ok(result.issues.includes("Inventory quantities cannot be negative"));
});

test("negative manual quantities cannot reduce demand and remain visible for review", () => {
  const result = calculateBomLine(line("PAN-003"), inputMap, { manualBaseQty: -5, manualExtra: -10 });
  assert.equal(result.manualExtra, 0);
  assert.equal(result.requiredQty, 80);
  assert.equal(result.kitDemandQty, 100);
  assert.ok(result.issues.includes("Negative manual quantity"));
});

test("zero manual demand requires an explicit Not Required status", () => {
  const manualLine = {
    ...lines.find((candidate) => candidate.sourceMode === "MANUAL"),
    specification: "Approved specification",
    specificationApproved: true,
    owner: "Procurement",
    ruleStatus: "APPROVED",
  };
  const pending = calculateBomLine(manualLine, inputMap, { manualBaseQty: 0, status: "Ready" });
  assert.ok(pending.issues.includes("Manual quantity required or mark Not Required"));

  const notRequired = calculateBomLine(manualLine, inputMap, { manualBaseQty: 0, status: "Not Required" });
  assert.ok(!notRequired.issues.includes("Manual quantity required or mark Not Required"));
});

test("invalid procurement assumptions are normalized and flagged", () => {
  const result = calculateProcurementItem(
    item("PAN-009"),
    [{ itemId: "PAN-009", kitDemandQty: 100 }],
    { targetStock: -5, packSize: 0, minimumOrderQty: -2, unitCost: -10 },
  );
  assert.equal(result.targetStock, 0);
  assert.equal(result.packSize, 1);
  assert.equal(result.unitCost, 0);
  assert.ok(result.issues.includes("Target stock cannot be negative"));
  assert.ok(result.issues.includes("Pack size must be positive"));
  assert.ok(result.issues.includes("Minimum order cannot be negative"));
  assert.ok(result.issues.includes("Unit cost cannot be negative"));
});

test("roundUpTo supports decimal units without floating point overshoot", () => {
  assert.equal(roundUpTo(10, 0.5), 10);
  assert.equal(roundUpTo(10.01, 0.5), 10.5);
  assert.equal(roundUpTo(0, 0.25), 0);
});
