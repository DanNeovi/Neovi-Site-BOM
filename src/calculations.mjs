import { SOURCE_MODES } from "./template-model.mjs";

const EPSILON = 1e-9;

export function roundUpTo(value, increment = 1) {
  const numericValue = Number(value);
  const numericIncrement = Number(increment);
  if (!Number.isFinite(numericValue)) throw new TypeError(`Value must be numeric: ${value}`);
  if (!Number.isFinite(numericIncrement) || numericIncrement <= 0) {
    throw new RangeError(`Increment must be a positive number: ${increment}`);
  }
  if (numericValue <= 0) return 0;
  return Math.ceil((numericValue - EPSILON) / numericIncrement) * numericIncrement;
}

export function calculateBomLine(line, projectInputMap, projectFields = {}) {
  if (!SOURCE_MODES.includes(line.sourceMode)) {
    throw new Error(`Unsupported source mode ${line.sourceMode} for ${line.lineId}`);
  }

  const rawSourceValue = ["DIRECT", "CALCULATED"].includes(line.sourceMode)
    ? Number(projectInputMap.get(line.inputKey) ?? 0)
    : 0;
  const sourceValue = nonNegative(rawSourceValue);
  const rawManualBaseQty = numericOrNaN(projectFields.manualBaseQty ?? 0);
  const rawManualExtra = numericOrNaN(projectFields.manualExtra ?? 0);
  const manualBaseQty = nonNegative(rawManualBaseQty);
  const manualExtra = nonNegative(rawManualExtra);
  const multiplier = nonNegative(line.multiplier ?? 1);

  let requiredQty;
  switch (line.sourceMode) {
    case "DIRECT":
    case "CALCULATED":
      requiredQty = sourceValue * multiplier;
      break;
    case "FIXED":
      requiredQty = nonNegative(line.fixedQty);
      break;
    case "MANUAL":
      requiredQty = manualBaseQty;
      break;
    default:
      requiredQty = 0;
  }

  const ruleSpareQty = roundUpTo(
    requiredQty * nonNegative(line.sparePercent),
    line.quantityIncrement ?? 1,
  );
  const kitDemandQty = roundUpTo(
    Math.max(
      requiredQty + ruleSpareQty + manualExtra,
      nonNegative(line.minimumKitQty),
    ),
    line.quantityIncrement ?? 1,
  );
  const issues = reviewBomLine(line, projectInputMap, {
    ...projectFields,
    rawSourceValue,
    rawManualBaseQty,
    rawManualExtra,
    requiredQty,
  });

  return {
    lineId: line.lineId,
    itemId: line.itemId,
    sourceValue,
    requiredQty,
    ruleSpareQty,
    manualExtra,
    kitDemandQty,
    calculation: formatCalculation(line, { sourceValue, manualBaseQty, requiredQty, ruleSpareQty, kitDemandQty }),
    issues,
  };
}

export function calculateProcurementItem(item, lineResults, projectFields = {}) {
  const totalKitDemand = lineResults
    .filter((entry) => (entry.itemId ?? entry.result?.itemId) === item.itemId)
    .reduce((sum, entry) => sum + nonNegative(entry.kitDemandQty ?? entry.result?.kitDemandQty), 0);
  const rawOnHand = Number(projectFields.onHand ?? 0);
  const rawAlreadyCommitted = Number(projectFields.alreadyCommitted ?? 0);
  const rawTargetStock = Number(projectFields.targetStock ?? item.targetStockQty ?? 0);
  const rawMinimumOrderQty = Number(projectFields.minimumOrderQty ?? item.minimumOrderQty ?? 0);
  const rawPackSize = Number(projectFields.packSize ?? item.packSize ?? 1);
  const rawUnitCost = projectFields.unitCost ?? item.unitCost;
  const onHand = nonNegative(projectFields.onHand);
  const alreadyCommitted = nonNegative(projectFields.alreadyCommitted);
  const targetStock = nonNegative(projectFields.targetStock ?? item.targetStockQty);
  const netNeed = Math.max(0, totalKitDemand + targetStock - onHand - alreadyCommitted);
  const minimumOrderQty = nonNegative(projectFields.minimumOrderQty ?? item.minimumOrderQty);
  const packSize = positive(projectFields.packSize ?? item.packSize, 1);
  const orderQty = netNeed === 0 ? 0 : roundUpTo(Math.max(netNeed, minimumOrderQty), packSize);
  const unitCost = nullableNonNegative(projectFields.unitCost ?? item.unitCost);
  const issues = reviewProcurementItem(item, {
    ...projectFields,
    rawOnHand,
    rawAlreadyCommitted,
    rawTargetStock,
    rawMinimumOrderQty,
    rawPackSize,
    rawUnitCost,
    totalKitDemand,
    onHand,
    alreadyCommitted,
    targetStock,
    netNeed,
    orderQty,
    packSize,
    minimumOrderQty,
    unitCost,
  });

  return {
    itemId: item.itemId,
    totalKitDemand,
    onHand,
    alreadyCommitted,
    targetStock,
    netNeed,
    packSize,
    minimumOrderQty,
    orderQty,
    unitCost,
    extendedCost: unitCost === null ? null : orderQty * unitCost,
    issues,
  };
}

export function calculateSiteBom(lines, items, projectInputMap, lineFields = new Map(), procurementFields = new Map()) {
  const lineResults = lines.map((line) => calculateBomLine(line, projectInputMap, lineFields.get(line.lineId) ?? {}));
  const procurementResults = items.map((item) => (
    calculateProcurementItem(item, lineResults, procurementFields.get(item.itemId) ?? {})
  ));
  return { lineResults, procurementResults };
}

function reviewBomLine(line, projectInputMap, fields = {}) {
  const issues = [];
  if (!line.lineId || !line.itemId || !line.description || !line.specification || !line.unit || !line.owner) {
    issues.push("Missing line or item information");
  }
  if (!line.specificationApproved || String(line.specification ?? "").startsWith("TBD")) {
    issues.push("Specification needs approval");
  }
  if (line.owner === "Unassigned") issues.push("Owner needs assignment");
  if (["DIRECT", "CALCULATED"].includes(line.sourceMode)) {
    if (!line.inputKey) issues.push("Missing input key");
    else if (!projectInputMap.has(line.inputKey)) issues.push("Input not supplied");
  }
  if (line.scope === "FACTORY") issues.push("Factory-only item is not part of the Site BOM");
  const rawManualBaseQty = numericOrNaN(fields.rawManualBaseQty ?? fields.manualBaseQty ?? 0);
  const rawManualExtra = numericOrNaN(fields.rawManualExtra ?? fields.manualExtra ?? 0);
  if (nonNegative(rawManualExtra) > 0 && !String(fields.adjustmentReason ?? "").trim()) {
    issues.push("Manual extra needs a reason");
  }
  if (!Number.isFinite(rawManualBaseQty) || !Number.isFinite(rawManualExtra)) {
    issues.push("Manual quantity must be numeric");
  }
  if (rawManualBaseQty < 0 || rawManualExtra < 0) {
    issues.push("Negative manual quantity");
  }
  if (line.sourceMode === "MANUAL"
    && rawManualBaseQty === 0
    && String(fields.status ?? "") !== "Not Required") {
    issues.push("Manual quantity required or mark Not Required");
  }
  if (Number(fields.rawSourceValue ?? 0) < 0) issues.push("Negative source quantity");
  if (Number(fields.requiredQty ?? 0) < 0) issues.push("Negative required quantity");
  if (line.ruleStatus !== "APPROVED") issues.push("Calculation rule needs approval");
  return [...new Set(issues)];
}

function reviewProcurementItem(item, fields = {}) {
  const issues = [];
  if (fields.totalKitDemand > 0 && (!item.specificationApproved || String(item.specification ?? "").startsWith("TBD"))) {
    issues.push("Specification needs approval");
  }
  if (fields.orderQty > 0 && (!item.procurementMethod || item.procurementMethod === "TBD")) {
    issues.push("Procurement method required");
  }
  if (fields.orderQty > 0 && item.procurementMethod === "Order") {
    if (!item.vendor) issues.push("Vendor required");
    if (!item.partNumber) issues.push("Part number required");
  }
  if (fields.orderQty > 0 && fields.unitCost === null) issues.push("Unit cost required");
  if (Number(fields.rawOnHand ?? fields.onHand ?? 0) < 0
    || Number(fields.rawAlreadyCommitted ?? fields.alreadyCommitted ?? 0) < 0) {
    issues.push("Inventory quantities cannot be negative");
  }
  if (!Number.isFinite(Number(fields.rawTargetStock)) || Number(fields.rawTargetStock) < 0) issues.push("Target stock cannot be negative");
  if (!Number.isFinite(Number(fields.rawPackSize)) || Number(fields.rawPackSize) <= 0) issues.push("Pack size must be positive");
  if (!Number.isFinite(Number(fields.rawMinimumOrderQty)) || Number(fields.rawMinimumOrderQty) < 0) issues.push("Minimum order cannot be negative");
  if (fields.rawUnitCost !== undefined && fields.rawUnitCost !== null && fields.rawUnitCost !== ""
    && (!Number.isFinite(Number(fields.rawUnitCost)) || Number(fields.rawUnitCost) < 0)) {
    issues.push("Unit cost cannot be negative");
  }
  return [...new Set(issues)];
}

function formatCalculation(line, values) {
  const unit = line.unit ?? "";
  if (line.sourceMode === "FIXED") return `Fixed ${formatNumber(line.fixedQty)} ${unit}`.trim();
  if (line.sourceMode === "MANUAL") return `Manual ${formatNumber(values.manualBaseQty)} ${unit}`.trim();

  const parts = [
    `${formatNumber(values.sourceValue)} ${humanizeKey(line.inputKey)}`,
    `× ${formatNumber(line.multiplier)}`,
  ];
  if (Number(line.sparePercent) > 0) parts.push(`+ ${formatPercent(line.sparePercent)} spare`);
  if (Number(line.minimumKitQty) > 0) parts.push(`min kit ${formatNumber(line.minimumKitQty)}`);
  parts.push(`= ${formatNumber(values.kitDemandQty)} ${unit}`);
  return parts.join(" ").trim();
}

function nonNegative(value) {
  const numeric = Number(value ?? 0);
  if (!Number.isFinite(numeric)) return 0;
  return Math.max(0, numeric);
}

function numericOrNaN(value) {
  if (value === undefined || value === null || String(value).trim() === "") return Number.NaN;
  return Number(value);
}

function nullableNonNegative(value) {
  if (value === undefined || value === null || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? Math.max(0, numeric) : null;
}

function positive(value, fallback) {
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : fallback;
}

function humanizeKey(key) {
  return String(key ?? "input").replaceAll("_", " ");
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 3 }).format(Number(value ?? 0));
}

function formatPercent(value) {
  return new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 }).format(Number(value ?? 0));
}
