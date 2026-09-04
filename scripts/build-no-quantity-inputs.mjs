import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadTemplateConfig } from "../src/template-model.mjs";

const moduleDir = path.dirname(fileURLToPath(import.meta.url));
const { config, lines, contract } = await loadTemplateConfig();
const outputDir = path.resolve(moduleDir, `../outputs/site-bom-v${config.settings.templateVersion}`);
const projectInputSchema = contract.schemas.projectInputs;
const catalogSchema = contract.schemas.catalog;
const siteStages = Object.freeze([...contract.siteStages]);
const siteStageOrder = new Map(siteStages.map((stage, index) => [stage, index]));
const projectInputHeaders = [
  "Schema Version",
  "Project",
  "Revision",
  "Record Type",
  "Input Key",
  "Value",
  "Unit",
  "Source",
  "Source Reference",
  "Location",
  "Notes",
  "Schema ID",
];
const siteShippingHeaders = [
  "Project",
  "Revision",
  "Stage",
  "Site Team",
  "Phase",
  "Work Area",
  "Category",
  "System",
  "Item",
  "Quantity",
  "Unit",
  "Team Scope",
  "Quantity Basis",
  "Source Reference",
  "Schema ID",
  "Schema Version",
  "Catalog Version",
  "Category Code",
  "Line ID",
  "Item ID",
  "Notes",
];

function csvCell(value) {
  const raw = value === null || value === undefined ? "" : String(value);
  const safe = /^[=+@\-\t\r]/.test(raw) ? `'${raw}` : raw;
  return `"${safe.replaceAll('"', '""')}"`;
}

function toProjectInputCsv(rows) {
  const matrix = [projectInputHeaders, ...rows.map((entry) => [
    projectInputSchema.version,
    entry.project ?? "",
    entry.revision ?? "",
    entry.recordType,
    entry.inputKey,
    "",
    entry.unit,
    entry.source,
    entry.sourceReference,
    entry.location,
    entry.notes,
    projectInputSchema.id,
  ])];
  return matrix.map((cells) => cells.map(csvCell).join(",")).join("\r\n") + "\r\n";
}

function toSiteShippingCsv(rows) {
  const matrix = [siteShippingHeaders, ...rows.map((entry) => [
    "",
    "",
    entry.siteStage,
    entry.siteTeam,
    entry.phase,
    entry.workArea,
    entry.category,
    entry.system,
    entry.item,
    "",
    entry.unit,
    entry.teamScope,
    entry.quantityBasis,
    entry.sourceReference,
    catalogSchema.id,
    catalogSchema.version,
    contract.catalogVersion,
    entry.categoryCode,
    entry.lineId,
    entry.itemId,
    entry.notes,
  ])];
  return matrix.map((cells) => cells.map(csvCell).join(",")).join("\r\n") + "\r\n";
}

function humanizeInputKey(inputKey) {
  return inputKey.replaceAll("_", " ");
}

function quantityBasis(line) {
  const parts = [];
  if (line.sourceMode === "DIRECT") parts.push(`Use ${humanizeInputKey(line.inputKey)}`);
  else if (line.sourceMode === "CALCULATED") parts.push(`Calculate from ${humanizeInputKey(line.inputKey)}`);
  else if (line.sourceMode === "FIXED") parts.push("Standard site item; confirm before shipment");
  else parts.push("Confirm quantity to ship");
  if (line.multiplier !== 1) parts.push(`${line.multiplier} per source quantity`);
  if (line.sparePercent > 0) parts.push(`include ${line.sparePercent * 100}% spare`);
  if (line.minimumKitQty > 0) parts.push(`minimum ${line.minimumKitQty}`);
  return parts.join("; ");
}

function cleanNotes(line) {
  return [line.ruleNotes, line.itemNotes, line.lineNotes].filter(Boolean).join("; ");
}

function validateDraftRows(rows, settings, label) {
  const seenKeys = new Set();
  const allowedUnits = new Set(settings.units);
  const allowedSources = new Set(settings.sourceTypes);
  const allowedRecordTypes = new Set(settings.recordTypes);
  const errors = [];
  for (const [index, entry] of rows.entries()) {
    const rowNumber = index + 2;
    if (!/^[a-z][a-z0-9_]*$/.test(entry.inputKey)) errors.push(`${label} row ${rowNumber} has invalid Input Key ${entry.inputKey}`);
    if (seenKeys.has(entry.inputKey)) errors.push(`${label} row ${rowNumber} duplicates Input Key ${entry.inputKey}`);
    seenKeys.add(entry.inputKey);
    if (!allowedRecordTypes.has(entry.recordType)) errors.push(`${label} row ${rowNumber} has invalid Record Type ${entry.recordType}`);
    if (!allowedUnits.has(entry.unit)) errors.push(`${label} row ${rowNumber} has invalid Unit ${entry.unit}`);
    if (!allowedSources.has(entry.source)) errors.push(`${label} row ${rowNumber} has invalid Source ${entry.source}`);
    if (!siteStageOrder.has(entry.siteStage)) errors.push(`${label} row ${rowNumber} has invalid Site Stage ${entry.siteStage}`);
    if (!entry.location.startsWith(`${entry.siteStage} / `)) errors.push(`${label} row ${rowNumber} Location does not begin with ${entry.siteStage}`);
    for (const field of ["sourceReference", "location", "notes"]) {
      if (!String(entry[field] ?? "").trim()) errors.push(`${label} row ${rowNumber} is missing ${field}`);
    }
  }
  if (errors.length) throw new Error(errors.join("\n"));
}

function validateSiteRows(rows, settings) {
  const allowedUnits = new Set(settings.units);
  const allowedCategories = new Set(settings.categories);
  const seenLineIds = new Set();
  const errors = [];
  for (const [index, entry] of rows.entries()) {
    const rowNumber = index + 2;
    if (!siteStageOrder.has(entry.siteStage)) errors.push(`Site-items row ${rowNumber} has invalid Stage ${entry.siteStage}`);
    if (!allowedUnits.has(entry.unit)) errors.push(`Site-items row ${rowNumber} has invalid Unit ${entry.unit}`);
    if (!allowedCategories.has(entry.category)) errors.push(`Site-items row ${rowNumber} has invalid Category ${entry.category}`);
    if (seenLineIds.has(entry.lineId)) errors.push(`Site-items row ${rowNumber} duplicates Line ID ${entry.lineId}`);
    seenLineIds.add(entry.lineId);
    if (config.settings.categoryCodes[entry.category] !== entry.categoryCode) errors.push(`Site-items row ${rowNumber} has invalid Category Code ${entry.categoryCode}`);
    if (config.settings.categoryTeams[entry.category] !== entry.siteTeam) errors.push(`Site-items row ${rowNumber} has invalid Site Team ${entry.siteTeam}`);
    if (config.settings.categoryTeamScopes[entry.category] !== entry.teamScope) errors.push(`Site-items row ${rowNumber} has invalid Team Scope`);
    for (const field of ["siteTeam", "teamScope", "phase", "workArea", "category", "categoryCode", "system", "item", "quantityBasis", "lineId", "itemId", "sourceReference"]) {
      if (!String(entry[field] ?? "").trim()) errors.push(`Site-items row ${rowNumber} is missing ${field}`);
    }
    const visibleText = `${entry.item} ${entry.quantityBasis} ${entry.notes}`;
    if (/DIRECT_ITEM|Rule:|Current input key:|\bMANUAL\b|\bCALCULATED\b/.test(visibleText)) {
      errors.push(`Site-items row ${rowNumber} exposes internal rule terminology`);
    }
    if (/factory/i.test(`${entry.siteStage} ${entry.phase} ${entry.workArea} ${entry.category}`)) {
      errors.push(`Site-items row ${rowNumber} contains factory scope`);
    }
  }
  for (const stage of siteStages) {
    if (!rows.some((entry) => entry.siteStage === stage)) errors.push(`Site-items catalog is missing ${stage}`);
  }
  if (errors.length) throw new Error(errors.join("\n"));
}

await fs.mkdir(outputDir, { recursive: true });

const operationalRows = contract.projectInputs.map((entry) => ({
  siteStage: entry.deliveryStage,
  recordType: entry.recordType,
  inputKey: entry.inputKey,
  unit: entry.unit,
  source: entry.source,
  sourceReference: entry.sourceReference,
  location: `${entry.deliveryStage} / ${entry.location}`,
  notes: entry.notes,
}));

const catalogRows = lines
  .map((line) => ({
    siteStage: line.deliveryStage,
    siteTeam: line.siteTeam,
    teamScope: line.teamScope,
    sourceOrdinal: line.sourceOrdinal,
    phase: line.phase,
    workArea: line.stage,
    category: line.category,
    categoryCode: line.categoryCode,
    system: line.system,
    item: line.description,
    unit: line.unit,
    quantityBasis: quantityBasis(line),
    lineId: line.lineId,
    itemId: line.itemId,
    sourceReference: `site-bom.template.json#${line.lineId}`,
    notes: cleanNotes(line),
  }))
  .sort((left, right) => siteStageOrder.get(left.siteStage) - siteStageOrder.get(right.siteStage)
    || left.sourceOrdinal.join(".").localeCompare(right.sourceOrdinal.join("."), undefined, { numeric: true }));

const operationalPath = path.join(outputDir, "Neovi-Site-BOM-Project-Inputs-No-Quantities.csv");
const catalogPath = path.join(outputDir, "Neovi-Site-BOM-All-Discussed-Items-No-Quantities.csv");
validateDraftRows(operationalRows, config.settings, "Operational inputs");
validateSiteRows(catalogRows, config.settings);
if (operationalRows.length !== Object.keys(config.settings.inputUnits).length) {
  throw new Error(`Operational template has ${operationalRows.length} rows but the template contract defines ${Object.keys(config.settings.inputUnits).length} Input Keys.`);
}
await fs.writeFile(operationalPath, toProjectInputCsv(operationalRows), "utf8");
await fs.writeFile(catalogPath, toSiteShippingCsv(catalogRows), "utf8");

console.log(`Wrote ${operationalRows.length} operational Project Input rows to ${operationalPath}`);
console.log(`Wrote ${catalogRows.length} site-only item rows to ${catalogPath}`);
for (const stage of siteStages) console.log(`  ${stage}: ${catalogRows.filter((row) => row.siteStage === stage).length}`);
