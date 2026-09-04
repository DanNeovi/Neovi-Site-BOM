import test from "node:test";
import assert from "node:assert/strict";
import {
  buildProjectInputExpectations,
  buildProjectInputMap,
  flattenBomLines,
  loadTemplateConfig,
  loadSiteBomContract,
  summarizeCatalog,
  validateProjectInputs,
  validateTemplateConfig,
} from "../src/template-model.mjs";

test("starter model contains all three phases and the supplied line set", async () => {
  const { lines, items } = await loadTemplateConfig();
  const summary = summarizeCatalog(lines, items);
  assert.deepEqual(Object.keys(summary.byPhase), ["Foundation", "Panels", "Finishing"]);
  assert.equal(summary.byPhase.Foundation, 19);
  assert.equal(summary.byPhase.Panels, 24);
  assert.equal(summary.byPhase.Finishing, 125);
  assert.equal(summary.totalLines, 168);
  assert.equal(summary.totalItems, 168);
});

test("every flattened BOM line has explicit hierarchy, system, delivery stage, and stable identities", async () => {
  const { config } = await loadTemplateConfig();
  const lines = flattenBomLines(config);
  const lineIds = new Set();
  for (const line of lines) {
    assert.ok(line.phase);
    assert.ok(line.stage);
    assert.ok(line.category);
    assert.ok(line.categoryCode);
    assert.ok(line.system);
    assert.ok(line.siteTeam);
    assert.ok(line.teamScope);
    assert.ok(config.settings.siteStages.includes(line.deliveryStage));
    assert.ok(line.kitId);
    assert.ok(line.lineId);
    assert.ok(line.itemId);
    assert.ok(!lineIds.has(line.lineId), `Duplicate ${line.lineId}`);
    lineIds.add(line.lineId);
  }
});

test("canonical contract owns schemas, category codes, stages, and all input definitions", async () => {
  const contract = await loadSiteBomContract();
  const { config, lines } = await loadTemplateConfig();
  assert.equal(contract.schemas.projectInputs.id, "neovi.site-bom.project-inputs");
  assert.equal(contract.schemas.projectInputs.version, "2.0");
  assert.equal(contract.schemas.catalog.id, "neovi.site-bom.catalog");
  assert.equal(contract.schemas.catalog.version, "2.0");
  assert.equal(contract.catalogVersion, config.settings.templateVersion);
  assert.equal(contract.projectInputs.length, 22);
  assert.deepEqual([...new Set(lines.map((line) => line.deliveryStage))].sort(), contract.siteStages);
  assert.deepEqual([...new Set(lines.map((line) => line.categoryCode))].sort(), contract.categories.map(({ code }) => code).sort());
  assert.deepEqual([...new Set(lines.map((line) => line.siteTeam))].sort(), contract.categories.map(({ siteTeam }) => siteTeam).sort());
});

test("starter model uses only the broad standardized category vocabulary", async () => {
  const { config, lines } = await loadTemplateConfig();
  assert.deepEqual(config.settings.categories, [
    "Sitework",
    "Structural",
    "Building Envelope",
    "Doors & Windows",
    "Interior Finishes",
    "Plumbing",
    "Fire Protection",
    "Mechanical",
    "Electrical",
  ]);
  assert.deepEqual([...new Set(lines.map((line) => line.category))].sort(), [...config.settings.categories].sort());
});

test("configuration rejects categories outside the standardized vocabulary", async () => {
  const config = structuredClone((await loadTemplateConfig()).config);
  config.phases[0].stages[0].categories[0].name = "One-off Category";
  const result = validateTemplateConfig(config);
  assert.ok(result.errors.some((error) => error.includes("is not listed in settings.categories")));
});

test("configuration allows one Item ID in multiple BOM Lines with occurrence-specific notes", async () => {
  const config = structuredClone((await loadTemplateConfig()).config);
  const firstCategory = config.phases[0].stages[0].categories[0];
  firstCategory.items.push({
    ...firstCategory.items[0],
    id: "FND-999",
    lineId: "FND-999",
    itemId: "FND-001",
    lineNotes: "Second installation occurrence",
  });
  const result = validateTemplateConfig(config);
  assert.deepEqual(result.errors, []);
});

test("configuration rejects duplicate Line IDs", async () => {
  const config = structuredClone((await loadTemplateConfig()).config);
  const firstCategory = config.phases[0].stages[0].categories[0];
  firstCategory.items.push({ ...firstCategory.items[0] });
  const result = validateTemplateConfig(config);
  assert.ok(result.errors.some((error) => error.includes("Duplicate line ID: FND-001")));
});

test("configuration rejects conflicting data for a shared Item ID", async () => {
  const config = structuredClone((await loadTemplateConfig()).config);
  const firstCategory = config.phases[0].stages[0].categories[0];
  firstCategory.items.push({
    ...firstCategory.items[0],
    id: "FND-999",
    lineId: "FND-999",
    itemId: "FND-001",
    description: "Conflicting product",
  });
  const result = validateTemplateConfig(config);
  assert.ok(result.errors.some((error) => error.includes("Shared item ID FND-001 has conflicting purchasing data")));
});

test("configuration rejects calculated rules without an input key", async () => {
  const config = structuredClone((await loadTemplateConfig()).config);
  config.phases[0].stages[0].categories[0].items[0].rule = { sourceMode: "CALCULATED" };
  const result = validateTemplateConfig(config);
  assert.ok(result.errors.some((error) => error.includes("requires an inputKey")));
});

test("configuration rejects negative business assumptions", async () => {
  const config = structuredClone((await loadTemplateConfig()).config);
  config.phases[0].stages[0].categories[0].items[0].minimumOrderQty = -1;
  const result = validateTemplateConfig(config);
  assert.ok(result.errors.some((error) => error.includes("minimumOrderQty cannot be negative")));
});

test("configuration rejects string booleans and non-approved status vocabulary", async () => {
  const config = structuredClone((await loadTemplateConfig()).config);
  const item = config.phases[0].stages[0].categories[0].items[0];
  item.specificationApproved = "false";
  item.rule = { sourceMode: "MANUAL", status: "DONE" };
  const result = validateTemplateConfig(config);
  assert.ok(result.errors.some((error) => error.includes("specificationApproved must be a boolean")));
  assert.ok(result.errors.some((error) => error.includes("Invalid rule status DONE")));
  assert.equal(flattenBomLines(config)[0].specificationApproved, false);
});

test("configuration rejects case-duplicate and non-uppercase contract lists", async () => {
  const config = structuredClone((await loadTemplateConfig()).config);
  config.settings.units.push("ea");
  config.settings.sourceTypes[0] = "revit";
  const result = validateTemplateConfig(config);
  assert.ok(result.errors.some((error) => error.includes("settings.units cannot contain duplicates")));
  assert.ok(result.errors.some((error) => error.includes("settings.units values must be uppercase")));
  assert.ok(result.errors.some((error) => error.includes("settings.sourceTypes values must be uppercase")));
});

test("configuration preserves sentinel values used by workbook formulas", async () => {
  const config = structuredClone((await loadTemplateConfig()).config);
  config.settings.statuses = ["Ready"];
  config.settings.procurementMethods = ["Inventory"];
  config.settings.ruleStatuses = ["READY_FOR_TEST"];
  const result = validateTemplateConfig(config);
  assert.ok(result.errors.some((error) => error.includes("settings.statuses must include Needs Review")));
  assert.ok(result.errors.some((error) => error.includes("settings.procurementMethods must include TBD")));
  assert.ok(result.errors.some((error) => error.includes("settings.ruleStatuses must include APPROVED")));
});

test("project inputs reject exact duplicate source rows", () => {
  const inputs = {
    schemaId: "neovi.site-bom.project-inputs",
    schemaVersion: "2.0",
    project: "House A",
    revision: "R01",
    rows: [
      { recordType: "FACT", inputKey: "connections", value: 2, unit: "EA", source: "REVIT", sourceReference: "A", location: "L1" },
      { recordType: "FACT", inputKey: "connections", value: 2, unit: "EA", source: "REVIT", sourceReference: "A", location: "L1" },
    ],
  };
  const result = validateProjectInputs(inputs);
  assert.ok(result.errors.some((error) => error.includes("duplicates an existing source row")));
});

test("project inputs sum distinct source rows but reject mixed revisions", () => {
  const inputs = {
    schemaId: "neovi.site-bom.project-inputs",
    schemaVersion: "2.0",
    project: "House A",
    revision: "R01",
    rows: [
      { recordType: "FACT", inputKey: "connections", value: 2, unit: "EA", source: "REVIT", sourceReference: "A", location: "L1" },
      { recordType: "FACT", inputKey: "connections", value: 3, unit: "EA", source: "REVIT", sourceReference: "B", location: "L1" },
    ],
  };
  assert.equal(buildProjectInputMap(inputs).get("connections"), 5);
  inputs.rows[1].revision = "R02";
  const result = validateProjectInputs(inputs);
  assert.ok(result.errors.some((error) => error.includes("multiple Revision values")));
});

test("project inputs reject mixed units and unknown keys against the template contract", async () => {
  const { config, lines } = await loadTemplateConfig();
  const expectations = buildProjectInputExpectations(config, lines);
  const inputs = {
    schemaId: "neovi.site-bom.project-inputs",
    schemaVersion: "2.0",
    project: "House A",
    revision: "R01",
    rows: [
      { recordType: "FACT", inputKey: "floor_connection_count", value: 2, unit: "EA", source: "REVIT", sourceReference: "A" },
      { recordType: "FACT", inputKey: "floor_connection_count", value: 10, unit: "FT", source: "REVIT", sourceReference: "B" },
      { recordType: "FACT", inputKey: "typo_key", value: 1, unit: "EA", source: "REVIT", sourceReference: "C" },
    ],
  };
  const result = validateProjectInputs(inputs, expectations);
  assert.ok(result.errors.some((error) => error.includes("mixed units for floor_connection_count")));
  assert.ok(result.errors.some((error) => error.includes("does not match expected EA")));
  assert.ok(result.errors.some((error) => error.includes("unknown Input Key: typo_key")));
});
