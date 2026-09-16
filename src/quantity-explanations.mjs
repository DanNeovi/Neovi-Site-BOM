// Human-readable rules share the catalog's assumptions; no new takeoff ratios.
export function quantityBasis(line) {
  const base = line.takeoffFormula ? `Required = ${line.takeoffFormula}` : line.sourceMode === "FIXED"
    ? `Required = ${line.fixedQty} ${line.unit} (fixed; confirm for project)`
    : line.sourceMode === "MANUAL"
      ? `Required = measured/counted ${line.description} in ${line.unit}; enter Manual Base Qty (takeoff needed)`
      : `Required = SUM(${line.inputKey.replaceAll("_", " ")} in ${line.inputUnit || line.unit}) x ${line.multiplier} = quantity in ${line.unit}`;
  return [
    base,
    `Spare = round up(Required x ${line.sparePercent * 100}%, increment ${line.quantityIncrement})`,
    `Kit = round up(MAX(Required + Spare + Manual Extra, ${line.minimumKitQty}), increment ${line.quantityIncrement}) ${line.unit}`,
    `Net = MAX(0, SUM(all kits for item ${line.itemId}) + target stock - on hand - already committed)`,
    `Order = 0 if Net = 0; otherwise round up(MAX(Net, minimum order ${line.minimumOrderQty}), pack ${line.packSize}) ${line.unit}`,
    "Order once per Item ID across all phases; resolve Needs Review before buying",
  ].join("; ");
}
