import {
  applySiteBomContract,
  flattenBomLines,
  loadSiteBomContract,
  readJson,
  validateTemplateConfig,
} from "./template-model.mjs";

export const MASTER_SNAPSHOT_FORMAT = "neovi-site-bom-master-snapshot";
export const MASTER_SNAPSHOT_VERSION = 2;
const LEGACY_MASTER_SNAPSHOT_VERSION = 1;
const canonicalContract = await loadSiteBomContract();

export async function loadMasterSnapshot(filePath) {
  const snapshot = await readJson(filePath);
  const config = masterSnapshotToConfig(snapshot);
  const validation = validateTemplateConfig(config);
  if (validation.errors.length) {
    throw new Error(["Invalid Site BOM master snapshot:", ...validation.errors.map((error) => `- ${error}`)].join("\n"));
  }
  const linesById = new Map(flattenBomLines(config).map((line) => [line.lineId, line]));
  const lines = snapshot.bomLines.map((line) => linesById.get(clean(line.lineId)));
  const items = snapshot.items.map(snapshotItemToCatalogItem);
  return { config, lines, items, warnings: validation.warnings };
}

export function masterSnapshotToConfig(snapshot) {
  if (!snapshot || typeof snapshot !== "object" || Array.isArray(snapshot)) {
    throw new Error("Master snapshot must be an object.");
  }
  if (snapshot.format !== MASTER_SNAPSHOT_FORMAT
    || ![LEGACY_MASTER_SNAPSHOT_VERSION, MASTER_SNAPSHOT_VERSION].includes(snapshot.formatVersion)) {
    throw new Error(`Master snapshot must use ${MASTER_SNAPSHOT_FORMAT} version ${LEGACY_MASTER_SNAPSHOT_VERSION} or ${MASTER_SNAPSHOT_VERSION}.`);
  }
  for (const field of ["items", "bomLines", "rules"]) {
    if (!Array.isArray(snapshot[field]) || snapshot[field].length === 0) throw new Error(`Master snapshot ${field} must be a non-empty array.`);
  }

  const items = uniqueMap(snapshot.items, "itemId", "Item ID");
  const rules = uniqueMap(snapshot.rules, "lineId", "Rule Line ID");
  for (const item of items.values()) validateSnapshotItem(item, snapshot.settings);
  const lineIds = new Set();
  const phaseMap = new Map();
  for (const bomLine of snapshot.bomLines) {
    const lineId = clean(bomLine.lineId);
    const itemId = clean(bomLine.itemId);
    if (!lineId) throw new Error("Master snapshot contains a BOM Line without a Line ID.");
    if (lineIds.has(lineId)) throw new Error(`Duplicate Line ID in master snapshot: ${lineId}`);
    lineIds.add(lineId);
    const item = items.get(itemId);
    const rule = rules.get(lineId);
    if (!item) throw new Error(`BOM Line ${lineId} references missing Item ID ${itemId || "<blank>"}.`);
    if (!rule) throw new Error(`BOM Line ${lineId} has no Rules row.`);
    const phaseName = clean(bomLine.phase);
    const stageName = clean(bomLine.stage);
    const categoryName = clean(bomLine.category);
    if (snapshot.formatVersion === MASTER_SNAPSHOT_VERSION
      && (!clean(bomLine.system) || !clean(bomLine.deliveryStage))) {
      throw new Error(`BOM Line ${lineId || "<blank>"} in snapshot version ${MASTER_SNAPSHOT_VERSION} requires System and Delivery Stage.`);
    }
    const system = clean(bomLine.system) || "Legacy / Unclassified";
    const deliveryStage = clean(bomLine.deliveryStage)
      || legacyDeliveryStage(phaseName, stageName, lineId);
    if (!phaseName || !stageName || !categoryName) throw new Error(`BOM Line ${lineId} is missing phase, stage, or category.`);
    if (!phaseMap.has(phaseName)) phaseMap.set(phaseName, new Map());
    const stageMap = phaseMap.get(phaseName);
    if (!stageMap.has(stageName)) stageMap.set(stageName, new Map());
    const categoryMap = stageMap.get(stageName);
    const categoryKey = JSON.stringify([categoryName, system, deliveryStage]);
    if (!categoryMap.has(categoryKey)) categoryMap.set(categoryKey, {
      name: categoryName,
      system,
      deliveryStage,
      items: [],
    });
    categoryMap.get(categoryKey).items.push({
      id: lineId,
      lineId,
      itemId,
      kitId: clean(bomLine.kitId),
      scope: clean(bomLine.scope),
      lineNotes: clean(bomLine.lineNotes),
      description: clean(item.description),
      specification: clean(item.specification),
      specificationApproved: item.specificationApproved,
      unit: clean(item.unit),
      owner: clean(item.owner),
      procurementMethod: clean(item.procurementMethod),
      vendor: clean(item.vendor),
      partNumber: clean(item.partNumber),
      unitCost: item.unitCost === "" ? null : item.unitCost,
      packSize: item.packSize,
      minimumOrderQty: item.minimumOrderQty,
      targetStockQty: item.targetStockQty,
      itemNotes: clean(item.notes),
      rule: {
        sourceMode: clean(rule.sourceMode),
        inputKey: clean(rule.inputKey),
        inputUnit: clean(rule.inputUnit),
        multiplier: rule.multiplier,
        fixedQty: rule.fixedQty,
        sparePercent: rule.sparePercent,
        quantityIncrement: rule.quantityIncrement,
        minimumKitQty: rule.minimumKitQty,
        status: clean(rule.ruleStatus),
        notes: clean(rule.ruleNotes),
      },
    });
  }
  for (const id of rules.keys()) {
    if (!lineIds.has(id)) throw new Error(`Rules row ${id} has no BOM Line.`);
  }

  const phaseColors = snapshot.settings?.phaseColors ?? {};
  const defaultColors = { Foundation: "#1F4E78", Panels: "#548235", Finishing: "#BF8F00" };
  const phases = [...phaseMap].map(([phaseName, stageMap], phaseIndex) => ({
    name: phaseName,
    code: clean(snapshot.settings?.phaseCodes?.[phaseName]) || phaseName.slice(0, 3).toUpperCase(),
    color: clean(phaseColors[phaseName]) || defaultColors[phaseName] || ["#1F4E78", "#548235", "#BF8F00"][phaseIndex % 3],
    stages: [...stageMap].map(([stageName, categoryMap]) => ({
      name: stageName,
      categories: [...categoryMap.values()],
    })),
  }));

  return applySiteBomContract({
    settings: snapshot.settings,
    defaults: {
      scope: "SITE",
      specification: "TBD - approve exact specification",
      specificationApproved: false,
      unit: "EA",
      owner: "Unassigned",
      procurementMethod: "TBD",
      packSize: 1,
      minimumOrderQty: 0,
      targetStockQty: 0,
      unitCost: null,
      rule: { sourceMode: "MANUAL", multiplier: 1, fixedQty: 0, sparePercent: 0, quantityIncrement: 1, minimumKitQty: 0, status: "NEEDS_REVIEW" },
    },
    phases,
  }, canonicalContract);
}

function legacyDeliveryStage(phase, workArea, lineId) {
  if (phase === "Foundation" || ["PAN-001", "PAN-008"].includes(lineId)) return "1";
  if (phase === "Panels" || workArea === "Rough MEP" || ["FIN-095", "FIN-096", "FIN-097"].includes(lineId)) return "2";
  return "3";
}

function uniqueMap(rows, key, label) {
  const result = new Map();
  for (const row of rows) {
    const id = clean(row?.[key]);
    if (!id) throw new Error(`Master snapshot contains a blank ${label}.`);
    if (result.has(id)) throw new Error(`Duplicate ${label} in master snapshot: ${id}`);
    result.set(id, row);
  }
  return result;
}

function validateSnapshotItem(item, settings = {}) {
  const itemId = clean(item.itemId);
  if (!/^[A-Za-z0-9][A-Za-z0-9_.:-]*$/.test(itemId)) throw new Error(`Master snapshot Item ID is invalid: ${itemId}`);
  for (const field of ["description", "specification", "unit", "owner", "procurementMethod"]) {
    if (!clean(item[field])) throw new Error(`Master snapshot Item ${itemId} is missing ${field}.`);
  }
  if (typeof item.specificationApproved !== "boolean") {
    throw new Error(`Master snapshot Item ${itemId} specificationApproved must be boolean.`);
  }
  for (const [field, settingName] of [["unit", "units"], ["owner", "owners"], ["procurementMethod", "procurementMethods"]]) {
    if (Array.isArray(settings[settingName]) && !settings[settingName].includes(clean(item[field]))) {
      throw new Error(`Master snapshot Item ${itemId} has invalid ${field}: ${clean(item[field])}`);
    }
  }
  validateSnapshotNumber(item, "packSize", itemId, { positive: true });
  validateSnapshotNumber(item, "minimumOrderQty", itemId);
  validateSnapshotNumber(item, "targetStockQty", itemId);
  if (item.unitCost !== null && item.unitCost !== "" && item.unitCost !== undefined) {
    validateSnapshotNumber(item, "unitCost", itemId);
  }
}

function validateSnapshotNumber(item, field, itemId, options = {}) {
  const numeric = Number(item[field]);
  if (!Number.isFinite(numeric) || numeric < 0 || (options.positive && numeric <= 0)) {
    throw new Error(`Master snapshot Item ${itemId} has invalid ${field}: ${item[field]}`);
  }
}

function snapshotItemToCatalogItem(item) {
  return {
    itemId: clean(item.itemId),
    description: clean(item.description),
    specification: clean(item.specification),
    specificationApproved: item.specificationApproved,
    unit: clean(item.unit),
    owner: clean(item.owner),
    procurementMethod: clean(item.procurementMethod),
    vendor: clean(item.vendor),
    partNumber: clean(item.partNumber),
    unitCost: item.unitCost === null || item.unitCost === "" || item.unitCost === undefined ? null : Number(item.unitCost),
    packSize: Number(item.packSize),
    minimumOrderQty: Number(item.minimumOrderQty),
    targetStockQty: Number(item.targetStockQty),
    notes: clean(item.notes),
  };
}

function clean(value) {
  return String(value ?? "").trim();
}
