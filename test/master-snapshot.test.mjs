import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { MASTER_SNAPSHOT_VERSION, loadMasterSnapshot, masterSnapshotToConfig } from "../src/master-snapshot.mjs";
import { flattenBomLines, loadTemplateConfig, validateTemplateConfig } from "../src/template-model.mjs";

test("downloaded flat master snapshots rebuild the same line model", async () => {
  const { config, lines, items } = await loadTemplateConfig();
  const snapshot = {
    format: "neovi-site-bom-master-snapshot",
    formatVersion: MASTER_SNAPSHOT_VERSION,
    settings: {
      ...config.settings,
      phaseCodes: Object.fromEntries(config.phases.map((phase) => [phase.name, phase.code])),
      phaseColors: Object.fromEntries(config.phases.map((phase) => [phase.name, phase.color])),
    },
    items: items.map((item) => ({ ...item, description: item.description, notes: item.notes })),
    bomLines: lines.map((line) => ({
      lineId: line.lineId, itemId: line.itemId, phase: line.phase, stage: line.stage,
      category: line.category, kitId: line.kitId, scope: line.scope, lineNotes: line.lineNotes,
      system: line.system, deliveryStage: line.deliveryStage,
    })),
    rules: lines.map((line) => ({
      lineId: line.lineId, sourceMode: line.sourceMode, inputKey: line.inputKey, inputUnit: line.inputUnit,
      multiplier: line.multiplier, fixedQty: line.fixedQty, sparePercent: line.sparePercent,
      quantityIncrement: line.quantityIncrement, minimumKitQty: line.minimumKitQty,
      ruleStatus: line.ruleStatus, ruleNotes: line.ruleNotes,
    })),
  };
  const rebuilt = masterSnapshotToConfig(snapshot);
  assert.deepEqual(validateTemplateConfig(rebuilt).errors, []);
  assert.equal(flattenBomLines(rebuilt).length, lines.length);
  assert.equal(flattenBomLines(rebuilt).find((line) => line.lineId === "PAN-003").inputUnit, "EA");
  assert.equal(flattenBomLines(rebuilt).find((line) => line.lineId === "PAN-003").system, "Floor Connections");

  snapshot.items.reverse();
  snapshot.items.push({
    ...snapshot.items[0],
    itemId: "UNUSED-ITEM",
    description: "Unused but valid inventory item",
  });
  snapshot.bomLines = [snapshot.bomLines[100], snapshot.bomLines[0], ...snapshot.bomLines.slice(1, 100), ...snapshot.bomLines.slice(101)];
  const temporaryDirectory = await fs.mkdtemp(path.join(os.tmpdir(), "neovi-site-bom-snapshot-"));
  const snapshotPath = path.join(temporaryDirectory, "master.json");
  try {
    await fs.writeFile(snapshotPath, JSON.stringify(snapshot), "utf8");
    const loaded = await loadMasterSnapshot(snapshotPath);
    assert.equal(loaded.items[0].itemId, snapshot.items[0].itemId);
    assert.equal(loaded.items.at(-1).itemId, "UNUSED-ITEM");
    assert.deepEqual(loaded.lines.map((line) => line.lineId), snapshot.bomLines.map((line) => line.lineId));
  } finally {
    await fs.rm(temporaryDirectory, { recursive: true, force: true });
  }
});

test("master snapshots reject duplicate identities", () => {
  const snapshot = {
    format: "neovi-site-bom-master-snapshot",
    formatVersion: 1,
    settings: {},
    items: [{ itemId: "I" }, { itemId: "I" }],
    bomLines: [{ lineId: "L", itemId: "I", phase: "Foundation", stage: "S", category: "C" }],
    rules: [{ lineId: "L" }],
  };
  assert.throws(() => masterSnapshotToConfig(snapshot), /Duplicate Item ID/);
});
