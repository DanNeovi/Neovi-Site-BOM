// Null means unavailable, never zero. A model measurement is not a verified
// item takeoff until its scope and material mapping have been established.
import { roundUpTo } from './calculations.mjs';
export function projectQuantityRows(lines, verifiedInputs = new Map(), purchasingInputs = new Map()) {
  const up = roundUpTo;
  const known = value => Number.isFinite(value) && value >= 0;
  const rows = lines.map(line => {
    const evidence = verifiedInputs.get(line.lineId);
    const validEvidence = evidence?.verified === true && evidence.references?.length > 0
      && Number.isFinite(evidence.value) && evidence.value >= 0;
    const required = validEvidence ? evidence.value : null;
    const input = purchasingInputs.get(line.itemId) ?? {};
    const spare = required === null ? null : up(required * line.sparePercent, line.quantityIncrement);
    // This subtotal is useful even when project extras and inventory are unknown.
    // It is explicitly separate from final kit demand and purchase quantities.
    const baseKit = required === null ? null : up(Math.max(required + spare, line.minimumKitQty), line.quantityIncrement);
    const kit = required === null || !known(input.manualExtra) ? null
      : up(Math.max(required + spare + input.manualExtra, line.minimumKitQty), line.quantityIncrement);
    const base = line.takeoffFormula || (line.sourceMode === "FIXED" ? `${line.fixedQty} ${line.unit} (catalog allowance; project applicability N/A)`
      : line.sourceMode === "MANUAL" ? `verified takeoff of ${line.description} (${line.unit})`
        : `SUM(${line.inputKey}) x ${line.multiplier}`);
    const reason = line.lineId === "PAN-020"
      ? "Roof areas exist; roof-to-slope-material mapping and overlapping layers are unresolved."
      : line.sourceMode === "FIXED"
        ? "Fixed catalog allowance exists; model does not establish the site requirement."
        : line.sourceMode === "MANUAL"
          ? "No verified model-to-item takeoff mapping; manual measurement or count is needed."
          : `No verified model source mapped to ${line.inputKey}.`;
    return {
      lineId: line.lineId, itemId: line.itemId, phase: line.phase, deliveryStage: line.deliveryStage,
      catalogId: line.catalogId, categoryPath: line.categoryPath.join(' > '), takeoffFormula: line.takeoffFormula,
      categorySection: line.categorySection, workArea: line.stage, category: line.category, system: line.system,
      item: line.description, unit: line.unit, sourceMode: line.sourceMode,
      sourceReferences: validEvidence ? evidence.references.join("; ") : null,
      required, spare, baseKit, kit, totalItemDemand: null, onHand: null, committed: null,
      targetStock: null, net: null, packSize: null, minimumOrder: null, order: null, unitCost: null, cost: null,
      requiredFormula: `R = ${base}`,
      spareFormula: `S = up(R x ${line.sparePercent * 100}%, ${line.quantityIncrement})`,
      kitFormula: `K = up(MAX(R + S + E, ${line.minimumKitQty}), ${line.quantityIncrement})`,
      baseKitFormula: `Base kit = up(MAX(R + S, ${line.minimumKitQty}), ${line.quantityIncrement}); excludes unentered extras`,
      totalFormula: "D = SUM(K for this Item ID across all phases)",
      netFormula: "N = MAX(0, D + stock target - on hand - committed)",
      orderFormula: "O = IF(N = 0, 0, up(MAX(N, minimum order), pack size))",
      costFormula: "Cost = O x unit cost",
      assumptions: `Catalog only: spare ${line.sparePercent * 100}%; increment ${line.quantityIncrement}; minimum kit ${line.minimumKitQty}; pack ${line.packSize}; minimum order ${line.minimumOrderQty}. Project confirmation N/A.`,
      reason: validEvidence ? "Required takeoff verified; project extras, purchasing inputs and rule approval still need confirmation." : reason,
    };
  });
  for (const row of rows) {
    const input = purchasingInputs.get(row.itemId) ?? {};
    const matching = rows.filter(other => other.itemId === row.itemId);
    row.totalItemDemand = matching.every(other => other.kit !== null) ? matching.reduce((sum, other) => sum + other.kit, 0) : null;
    for (const field of ['onHand','committed','targetStock','minimumOrder','unitCost']) row[field] = known(input[field]) ? input[field] : null;
    row.packSize = known(input.packSize) && input.packSize > 0 ? input.packSize : null;
    if ([row.totalItemDemand,row.onHand,row.committed,row.targetStock].every(value => value !== null)) {
      row.net = Math.max(0, row.totalItemDemand + row.targetStock - row.onHand - row.committed);
      if (row.net === 0) row.order = 0;
      else if (row.packSize !== null && row.minimumOrder !== null) row.order = up(Math.max(row.net,row.minimumOrder),row.packSize);
    }
    row.cost = row.order === 0 ? 0 : row.order !== null && row.unitCost !== null ? row.order * row.unitCost : null;
  }
  return rows;
}
