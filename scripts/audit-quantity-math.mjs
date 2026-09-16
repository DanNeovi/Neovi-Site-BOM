import fs from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";
import { loadTemplateConfig, buildProjectInputMap } from "../src/template-model.mjs";
import { calculateBomLine, calculateProcurementItem } from "../src/calculations.mjs";
import { projectInputsToCsv, projectInputsFromCsv } from "../src/project-input-csv.mjs";

const { lines, items, config } = await loadTemplateConfig();
const output = path.resolve("outputs/NeoviBOM/_Internal/Model-Data");
await fs.mkdir(output, { recursive: true });
const scenarios = [];
for (const line of lines) {
  for (const [name, input, manualExtra, onHand, committed, target, minimum, pack] of [
    ["zero demand", 0, 0, 0, 0, 0, 0, 1],
    ["fractional takeoff and extras", 10.25, 2, 0, 0, 0, 0, 1],
    ["inventory covers demand", 10.25, 0, 1e6, 0, 0, 100, 25],
    ["stock, commitments and packs", 10.25, 2, 3, 2, 5, 20, 8],
    ["shared item across two kits", 10.25, 2, 3, 2, 5, 20, 8],
  ]) {
    const fields = { manualBaseQty: input, manualExtra, adjustmentReason: "Arithmetic audit", status: "Ready" };
    const result = calculateBomLine(line, new Map([[line.inputKey, input]]), fields);
    const item = { ...items.find(item => item.itemId === line.itemId), targetStockQty: target, minimumOrderQty: minimum, packSize: pack, unitCost: 2.5 };
    const occurrences = name === "shared item across two kits" ? 2 : 1;
    const purchase = calculateProcurementItem(item, Array(occurrences).fill(result), { onHand, alreadyCommitted: committed });
    scenarios.push({ name, line, input, fields, item, occurrences, result, purchase });
  }
}

const projects = [];
for (const file of process.argv.slice(2)) {
  const evidence = JSON.parse(await fs.readFile(file, "utf8"));
  const candidates = evidence.roofAreaTestCandidates;
  assert.ok(candidates?.length, `${file}: no qualifying area records`);
  assert.equal(new Set(candidates.map(row => row.key)).size, candidates.length);
  const project = evidence.metadata["project.title"];
  const inputKey = "roof_slope_material_area";
  const line = lines.find(line => line.inputKey === inputKey);
  const rows = candidates.map(row => ({
    schemaId: config.settings.schemaId, schemaVersion: config.settings.schemaVersion,
    project, revision: "AUDIT-ONLY", recordType: "DIRECT_ITEM", inputKey,
    value: row.value, unit: row.unit, source: "REVIT", sourceReference: row.key,
    location: `${line.categorySection} ${line.stage} / Phase: ${line.phase} / ${row.level || "Level not supplied"}`,
    notes: `Stage ${line.deliveryStage}; ${line.category}; arithmetic test candidate only; material scope is unapproved`,
  }));
  const csv = projectInputsToCsv({ schemaId: config.settings.schemaId, schemaVersion: config.settings.schemaVersion, project, revision: "AUDIT-ONLY", rows });
  const imported = projectInputsFromCsv(csv, { inputUnits: config.settings.inputUnits });
  const map = buildProjectInputMap(imported.projectInputs);
  const result = calculateBomLine(line, map);
  const item = items.find(item => item.itemId === line.itemId);
  const purchase = calculateProcurementItem(item, [result]);
  const packScenario = calculateProcurementItem({ ...item, packSize: 32, minimumOrderQty: 0, unitCost: 2.5 }, [result], { onHand: 100 });
  const slug = path.basename(file).replace("-evidence.json", "");
  await fs.writeFile(path.join(output, `${slug}-roof-arithmetic-inputs-TEST-ONLY.csv`), csv);
  projects.push({ project, source: evidence.source, bytes: evidence.bytes, exportedAt: evidence.metadata.exportedAtUtc,
    elementCount: evidence.elementCount, duplicateElementKeys: evidence.duplicateElementKeys,
    bomTaggedElements: evidence.bomTaggedElements.length, candidateCount: candidates.length,
    roofExclusions: evidence.roofExclusions, scope: evidence.testScope, candidates, line, result, purchase, packScenario });
}
const report = { catalogLines: lines.length, manualLines: lines.filter(line => line.sourceMode === "MANUAL").length,
  auditScope: "Synthetic arithmetic for every catalog line plus all qualifying roof-area records from each export. Not a whole-project takeoff or approved buy list.",
  scenarios, projects };
await fs.writeFile(path.join(output, "quantity-audit.json"), JSON.stringify(report, null, 2));
console.log(`Prepared ${scenarios.length} catalog scenarios and ${projects.length} export tests for independent decimal verification.`);
