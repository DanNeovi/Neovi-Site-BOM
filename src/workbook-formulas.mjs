// Stable display sections. Keep existing numbers when adding work categories.
export const CATEGORY_SECTIONS = Object.freeze([
  ["1.1", "Foundation", "Site Setup and Support", "Sitework"],
  ["1.2", "Foundation", "Helical Piles", "Structural"],
  ["1.3", "Foundation", "Steel Bedframe", "Structural"],
  ["1.4", "Panels", "Floors", "Structural"],
  ["1.5", "Panels", "Walls", "Structural"],
  ["2.1", "Panels", "Floors", "Structural"],
  ["2.2", "Panels", "Walls", "Structural"],
  ["2.3", "Panels", "Trusses", "Structural"],
  ["2.4", "Panels", "Roof Panels", "Building Envelope"],
  ["2.5", "Finishing", "Rough MEP", "Electrical"],
  ["2.6", "Finishing", "Rough MEP", "Fire Protection"],
  ["2.7", "Finishing", "Rough MEP", "Plumbing"],
  ["2.8", "Finishing", "Rough MEP", "Mechanical"],
  ["2.9", "Finishing", "Low Voltage", "Electrical"],
  ["3.1", "Finishing", "Finish MEP", "Electrical"],
  ["3.2", "Finishing", "Finish MEP", "Fire Protection"],
  ["3.3", "Finishing", "Finish MEP", "Plumbing"],
  ["3.4", "Finishing", "Windows and Doors", "Doors & Windows"],
  ["3.5", "Finishing", "Cabinets", "Interior Finishes"],
  ["3.6", "Finishing", "Low Voltage", "Electrical"],
  ["3.7", "Finishing", "General", "Interior Finishes"],
  ["3.8", "Finishing", "General", "Doors & Windows"],
  ["3.9", "Finishing", "Flooring", "Interior Finishes"],
  ["3.10", "Finishing", "Truss Area Finish", "Interior Finishes"],
  ["3.11", "Finishing", "Gutter / Fascia", "Building Envelope"],
  ["3.12", "Finishing", "Ceiling", "Interior Finishes"],
  ["3.14", "Finishing", "Solid Surface", "Interior Finishes"],
  ["3.15", "Finishing", "Finish MEP", "Mechanical"],
]);

export function categorySectionNumber(deliveryStage, phase, workArea, category) {
  const section = CATEGORY_SECTIONS.find(([number, p, w, c]) =>
    number.split(".")[0] === String(deliveryStage) && p === phase && w === workArea && c === category);
  return section ? section[0] : "Unnumbered";
}

export const PHASE_HEADERS = Object.freeze([
  "Work Area", "Category", "Kit ID", "Line ID", "Item ID", "Scope", "Item", "Specification", "Unit", "Owner",
  "Source Mode", "Input Key", "Source Value", "Multiplier", "Fixed Qty", "Manual Base Qty", "Calculation",
  "Required Qty", "Rule Spare %", "Rule Spare Qty", "Qty Increment", "Minimum Kit Qty", "Manual Extra", "Kit Demand",
  "Total Item Demand", "On Hand", "Already Committed", "Net Need", "Pack Size", "Minimum Order", "Order Qty (All Phases)",
  "Procurement Method", "Vendor", "Part Number", "Unit Cost", "Order Cost (All Phases)", "Needed By", "Status",
  "Accounted For", "Template Notes", "Adjustment Reason / Notes", "Needs Review",
  "System", "Delivery Stage", "Site Team", "Team Scope",
]);

export const PROJECT_INPUT_HEADERS = Object.freeze([
  "Schema Version", "Project", "Revision", "Record Type", "Input Key", "Value", "Unit", "Source",
  "Source Reference", "Location", "Notes", "Schema ID",
]);

export const ITEM_HEADERS = Object.freeze([
  "Item ID", "Item", "Specification", "Specification Approved", "Unit", "Owner", "Procurement Method", "Vendor",
  "Part Number", "Unit Cost", "Pack Size", "Minimum Order Qty", "Target Stock Qty", "Item Notes",
]);

export const BOM_LINE_HEADERS = Object.freeze([
  "Line ID", "Item ID", "Phase", "Work Area", "Category", "Kit ID", "Scope", "Line Notes", "System", "Delivery Stage",
  "Site Team", "Team Scope",
  "Catalog ID", "Category Path",
]);

export const RULE_HEADERS = Object.freeze([
  "Line ID", "Source Mode", "Input Key", "Expected Input Unit", "Multiplier", "Fixed Qty", "Spare %",
  "Qty Increment", "Minimum Kit Qty", "Rule Status", "Rule Notes",
]);

export const PROCUREMENT_HEADERS = Object.freeze([
  "Item ID", "Item", "Specification", "Specification Approved", "Unit", "Owner", "Procurement Method", "Vendor",
  "Part Number", "Unit Cost", "Pack Size", "Minimum Order Qty", "Target Stock Qty", "Total Kit Demand", "On Hand",
  "Already Committed", "Net Need", "Order Qty", "Extended Cost", "Needed By", "Status", "Accounted For", "Notes", "Needs Review",
]);

export const IMPORT_AUDIT_HEADERS = Object.freeze(["Source Row", "Input Key", "Source Reference", "Issue"]);

export const PHASE_COLUMN = Object.freeze({
  stage: "A", category: "B", kitId: "C", lineId: "D", itemId: "E", scope: "F", item: "G", specification: "H",
  unit: "I", owner: "J", sourceMode: "K", inputKey: "L", sourceValue: "M", multiplier: "N", fixedQty: "O",
  manualBaseQty: "P", calculation: "Q", requiredQty: "R", sparePercent: "S", spareQty: "T", increment: "U",
  minimumKitQty: "V", manualExtra: "W", kitDemand: "X", totalItemDemand: "Y", onHand: "Z",
  alreadyCommitted: "AA", netNeed: "AB", packSize: "AC", minimumOrderQty: "AD", orderQty: "AE",
  procurementMethod: "AF", vendor: "AG", partNumber: "AH", unitCost: "AI", extendedCost: "AJ",
  neededBy: "AK", status: "AL", accountedFor: "AM", templateNotes: "AN", notes: "AO", review: "AP",
  system: "AQ", deliveryStage: "AR", siteTeam: "AS", teamScope: "AT",
});

export const PROCUREMENT_COLUMN = Object.freeze({
  itemId: "A", item: "B", specification: "C", specificationApproved: "D", unit: "E", owner: "F",
  procurementMethod: "G", vendor: "H", partNumber: "I", unitCost: "J", packSize: "K", minimumOrderQty: "L",
  targetStockQty: "M", totalKitDemand: "N", onHand: "O", alreadyCommitted: "P", netNeed: "Q", orderQty: "R",
  extendedCost: "S", neededBy: "T", status: "U", accountedFor: "V", notes: "W", review: "X",
});

export function phaseRowFormulas(row, inputStartRow = 2, inputEndRow = 1001, phaseName = "") {
  const c = PHASE_COLUMN;
  const schemaRange = `'Project Inputs'!$A$${inputStartRow}:$A$${inputEndRow}`;
  const schemaIdRange = `'Project Inputs'!$L$${inputStartRow}:$L$${inputEndRow}`;
  const projectRange = `'Project Inputs'!$B$${inputStartRow}:$B$${inputEndRow}`;
  const revisionRange = `'Project Inputs'!$C$${inputStartRow}:$C$${inputEndRow}`;
  const inputKeys = `'Project Inputs'!$E$${inputStartRow}:$E$${inputEndRow}`;
  const inputValues = `'Project Inputs'!$F$${inputStartRow}:$F$${inputEndRow}`;
  const inputUnits = `'Project Inputs'!$G$${inputStartRow}:$G$${inputEndRow}`;
  const expectedSchema = `'Template Settings'!$B$5`;
  const expectedSchemaId = `'Template Settings'!$B$10`;
  const activeProject = `'Template Settings'!$B$6`;
  const activeRevision = `'Template Settings'!$B$7`;
  const modeRef = `$${c.sourceMode}${row}`;
  const sourceRef = `$${c.sourceValue}${row}`;
  const unitRef = `$${c.unit}${row}`;
  const lineLookup = (column) => `IFERROR(INDEX('BOM Lines'!$${column}$4:$${column}$1000,MATCH($${c.lineId}${row},'BOM Lines'!$A$4:$A$1000,0)),"")`;
  const itemLookup = (column) => `IFERROR(INDEX('Items'!$${column}$4:$${column}$1000,MATCH($${c.itemId}${row},'Items'!$A$4:$A$1000,0)),"")`;
  const ruleLookup = (column) => `IFERROR(INDEX('Rules'!$${column}$4:$${column}$1000,MATCH($${c.lineId}${row},'Rules'!$A$4:$A$1000,0)),"")`;
  const procurementLookup = (column) => `IFERROR(INDEX('Procurement Summary'!$${column}$4:$${column}$1000,MATCH($${c.itemId}${row},'Procurement Summary'!$A$4:$A$1000,0)),"")`;
  const expectedInputUnit = ruleLookup("D");
  const matchingInputCount = `COUNTIFS(${inputKeys},$${c.inputKey}${row},${inputUnits},${expectedInputUnit},${schemaIdRange},${expectedSchemaId},${schemaRange},${expectedSchema},${projectRange},${activeProject},${revisionRange},${activeRevision})`;
  const linePhase = lineLookup("C");
  const specificationApproved = itemLookup("D");
  const ruleStatus = ruleLookup("J");
  const n = (key) => `TEXT($${c[key]}${row},"0.########")`;
  const calculationSteps = [
    `IF(${modeRef}="FIXED","Fixed "&${n("fixedQty")},IF(${modeRef}="MANUAL","Manual "&${n("manualBaseQty")},SUBSTITUTE($${c.inputKey}${row},"_"," ")&": "&${n("sourceValue")}&" x "&${n("multiplier")}))&" = "&${n("requiredQty")}&" "&${unitRef}&" required"`,
    `"Spare = round up("&${n("requiredQty")}&" x "&TEXT($${c.sparePercent}${row},"0.####%")&", increment "&${n("increment")}&") = "&${n("spareQty")}`,
    `"Kit = round up(MAX("&${n("requiredQty")}&" + "&${n("spareQty")}&" spare + "&${n("manualExtra")}&" extra, minimum "&${n("minimumKitQty")}&"), increment "&${n("increment")}&") = "&${n("kitDemand")}&" "&${unitRef}`,
    `"Net = MAX(0, "&${n("totalItemDemand")}&" all kits + "&TEXT(${procurementLookup("M")},"0.########")&" stock - "&${n("onHand")}&" on hand - "&${n("alreadyCommitted")}&" committed) = "&${n("netNeed")}`,
    `IF(OR(NOT(ISNUMBER($${c.packSize}${row})),$${c.packSize}${row}<=0),"Order unavailable: enter a positive pack size",IF($${c.netNeed}${row}=0,"Order = 0 (no net need)","Order = round up(MAX("&${n("netNeed")}&", minimum "&${n("minimumOrderQty")}&"), pack "&${n("packSize")}&") = "&${n("orderQty")}&" "&${unitRef}))`,
    `"Order once per Item ID across all phases"`,
    `IF(OR(NOT(ISNUMBER($${c.unitCost}${row})),$${c.unitCost}${row}<0),"Cost unavailable: enter a non-negative unit cost", "Cost = "&${n("orderQty")}&" x "&${n("unitCost")}&" = "&TEXT($${c.extendedCost}${row},"0.00"))`,
    `IF(OR($${c.review}${row}<>"",${procurementLookup("X")}<>"",COUNTIF('Import Audit'!$D$5:$D$1004,"<>")>0),"PREVIEW ONLY: resolve Needs Review / Import Audit before buying","")`,
  ];
  const reviewBody = `TEXTJOIN("; ",TRUE,IF(OR($${c.lineId}${row}="",$${c.itemId}${row}="",$${c.item}${row}="",$${c.unit}${row}="",$${c.owner}${row}=""),"Missing line or item information",""),IF(OR(${specificationApproved}<>TRUE,LEFT($${c.specification}${row},3)="TBD"),"Specification needs approval",""),IF($${c.owner}${row}="Unassigned","Owner needs assignment",""),IF($${c.status}${row}="","Status required",""),IF(AND(OR(${modeRef}="DIRECT",${modeRef}="CALCULATED"),$${c.inputKey}${row}=""),"Missing input key",""),IF(AND(OR(${modeRef}="DIRECT",${modeRef}="CALCULATED"),${matchingInputCount}=0),"Input not supplied with expected unit for active project/revision",""),IF(OR(AND(${modeRef}="MANUAL",OR(NOT(ISNUMBER($${c.manualBaseQty}${row})),$${c.manualBaseQty}${row}<0)),NOT(ISNUMBER($${c.manualExtra}${row})),$${c.manualExtra}${row}<0),"Manual quantities must be non-negative numbers",""),IF(AND(${modeRef}="MANUAL",$${c.manualBaseQty}${row}=0,$${c.status}${row}<>"Not Required"),"Manual quantity required or mark Not Required",""),IF(AND($${c.manualExtra}${row}>0,$${c.notes}${row}=""),"Manual extra needs a reason",""),IF(OR($${c.multiplier}${row}<0,$${c.fixedQty}${row}<0,$${c.sparePercent}${row}<0,$${c.increment}${row}<=0,$${c.minimumKitQty}${row}<0),"Calculation assumptions are invalid",""),IF($${c.scope}${row}="FACTORY","Factory-only item",""),IF(${ruleStatus}<>"APPROVED","Calculation rule needs approval",""),IF(${linePhase}<>"${escapeFormulaText(phaseName)}","Line belongs on different phase tab",""))`;

  return {
    stage: `=IFERROR(VLOOKUP(${lineLookup("J")}&"|"&${lineLookup("C")}&"|"&${lineLookup("D")}&"|"&${lineLookup("E")},'Template Settings'!$M$4:$N$100,2,FALSE),"Unnumbered")&" "&${lineLookup("D")}`,
    category: `=${lineLookup("E")}`,
    kitId: `=${lineLookup("F")}`,
    itemId: `=${lineLookup("B")}`,
    scope: `=${lineLookup("G")}`,
    item: `=${itemLookup("B")}`,
    specification: `=${itemLookup("C")}`,
    unit: `=${itemLookup("E")}`,
    owner: `=${itemLookup("F")}`,
    sourceMode: `=${ruleLookup("B")}`,
    inputKey: `=${ruleLookup("C")}`,
    sourceValue: `=IF(OR(${modeRef}="DIRECT",${modeRef}="CALCULATED"),IFERROR(SUMIFS(${inputValues},${inputKeys},$${c.inputKey}${row},${inputUnits},${expectedInputUnit},${schemaIdRange},${expectedSchemaId},${schemaRange},${expectedSchema},${projectRange},${activeProject},${revisionRange},${activeRevision}),0),0)`,
    multiplier: `=${ruleLookup("E")}`,
    fixedQty: `=${ruleLookup("F")}`,
    requiredQty: `=MAX(0,IF(${modeRef}="FIXED",$${c.fixedQty}${row},IF(${modeRef}="MANUAL",$${c.manualBaseQty}${row},${sourceRef}*$${c.multiplier}${row})))`,
    sparePercent: `=${ruleLookup("G")}`,
    spareQty: `=IF(OR($${c.requiredQty}${row}="",$${c.increment}${row}<=0),0,CEILING(MAX(0,$${c.requiredQty}${row}*$${c.sparePercent}${row}),$${c.increment}${row}))`,
    increment: `=${ruleLookup("H")}`,
    minimumKitQty: `=${ruleLookup("I")}`,
    kitDemand: `=IF(OR($${c.requiredQty}${row}="",$${c.increment}${row}<=0),0,CEILING(MAX(MAX(0,$${c.requiredQty}${row})+MAX(0,$${c.spareQty}${row})+MAX(0,$${c.manualExtra}${row}),MAX(0,$${c.minimumKitQty}${row})),$${c.increment}${row}))`,
    totalItemDemand: `=${procurementLookup("N")}`,
    onHand: `=${procurementLookup("O")}`,
    alreadyCommitted: `=${procurementLookup("P")}`,
    netNeed: `=${procurementLookup("Q")}`,
    packSize: `=${procurementLookup("K")}`,
    minimumOrderQty: `=${procurementLookup("L")}`,
    orderQty: `=${procurementLookup("R")}`,
    procurementMethod: `=${procurementLookup("G")}`,
    vendor: `=${procurementLookup("H")}`,
    partNumber: `=${procurementLookup("I")}`,
    unitCost: `=${procurementLookup("J")}`,
    extendedCost: `=${procurementLookup("S")}`,
    templateNotes: `=TEXTJOIN(" | ",TRUE,${lineLookup("H")},${itemLookup("N")},${ruleLookup("K")})`,
    review: `=IF($${c.lineId}${row}="","",${reviewBody})`,
    system: `=${lineLookup("I")}`,
    deliveryStage: `=${lineLookup("J")}`,
    siteTeam: `=${lineLookup("K")}`,
    teamScope: `=${lineLookup("L")}`,
    // Keep the explanation beside Required Qty, using the same calculated cells.
    calculation: `=TEXTJOIN(CHAR(10),TRUE,${calculationSteps.join(",")})`,
  };
}

export function procurementRowFormulas(row, phaseNames) {
  const c = PROCUREMENT_COLUMN;
  const itemLookup = (column) => `IFERROR(INDEX('Items'!$${column}$4:$${column}$1000,MATCH($${c.itemId}${row},'Items'!$A$4:$A$1000,0)),"")`;
  const demandTerms = phaseNames.map((phase) => (
    `SUMIF('${escapeSheetName(phase)}'!$E$8:$E$1000,$${c.itemId}${row},'${escapeSheetName(phase)}'!$X$8:$X$1000)`
  ));
  const reviewBody = `TEXTJOIN("; ",TRUE,IF(AND($${c.totalKitDemand}${row}>0,OR($${c.specificationApproved}${row}<>TRUE,LEFT($${c.specification}${row},3)="TBD")),"Specification needs approval",""),IF(AND($${c.orderQty}${row}>0,OR($${c.procurementMethod}${row}="",$${c.procurementMethod}${row}="TBD")),"Procurement method required",""),IF(AND($${c.orderQty}${row}>0,$${c.procurementMethod}${row}="Order",$${c.vendor}${row}=""),"Vendor required",""),IF(AND($${c.orderQty}${row}>0,$${c.procurementMethod}${row}="Order",$${c.partNumber}${row}=""),"Part number required",""),IF(AND($${c.orderQty}${row}>0,$${c.unitCost}${row}=""),"Unit cost required",""),IF(OR(NOT(ISNUMBER($${c.onHand}${row})),$${c.onHand}${row}<0,NOT(ISNUMBER($${c.alreadyCommitted}${row})),$${c.alreadyCommitted}${row}<0),"Inventory quantities must be non-negative numbers",""),IF(OR(NOT(ISNUMBER($${c.targetStockQty}${row})),$${c.targetStockQty}${row}<0),"Target stock must be non-negative",""),IF(OR(NOT(ISNUMBER($${c.packSize}${row})),$${c.packSize}${row}<=0),"Pack size must be positive",""),IF(OR(NOT(ISNUMBER($${c.minimumOrderQty}${row})),$${c.minimumOrderQty}${row}<0),"Minimum order must be non-negative",""),IF(AND($${c.unitCost}${row}<>"",OR(NOT(ISNUMBER($${c.unitCost}${row})),$${c.unitCost}${row}<0)),"Unit cost must be non-negative",""))`;

  return {
    item: `=${itemLookup("B")}`,
    specification: `=${itemLookup("C")}`,
    specificationApproved: `=${itemLookup("D")}`,
    unit: `=${itemLookup("E")}`,
    owner: `=${itemLookup("F")}`,
    procurementMethod: `=${itemLookup("G")}`,
    vendor: `=${itemLookup("H")}`,
    partNumber: `=${itemLookup("I")}`,
    unitCost: `=${itemLookup("J")}`,
    packSize: `=${itemLookup("K")}`,
    minimumOrderQty: `=${itemLookup("L")}`,
    targetStockQty: `=${itemLookup("M")}`,
    totalKitDemand: `=${demandTerms.join("+") || "0"}`,
    netNeed: `=MAX(0,MAX(0,$${c.totalKitDemand}${row})+MAX(0,$${c.targetStockQty}${row})-MAX(0,$${c.onHand}${row})-MAX(0,$${c.alreadyCommitted}${row}))`,
    orderQty: `=IF(OR($${c.netNeed}${row}=0,$${c.packSize}${row}<=0),0,CEILING(MAX($${c.netNeed}${row},MAX(0,$${c.minimumOrderQty}${row})),$${c.packSize}${row}))`,
    extendedCost: `=IF(OR($${c.orderQty}${row}=0,$${c.unitCost}${row}="",$${c.unitCost}${row}<0),IF($${c.orderQty}${row}=0,0,""),$${c.orderQty}${row}*$${c.unitCost}${row})`,
    review: `=IF($${c.itemId}${row}="","",${reviewBody})`,
  };
}

export function importAuditRowFormulas(auditRow, inputRow, inputStartRow = 2, inputEndRow = 1001) {
  const keys = `'Project Inputs'!$E$${inputStartRow}:$E$${inputEndRow}`;
  const refs = `'Project Inputs'!$I$${inputStartRow}:$I$${inputEndRow}`;
  const sources = `'Project Inputs'!$H$${inputStartRow}:$H$${inputEndRow}`;
  const schema = `'Project Inputs'!A${inputRow}`;
  const project = `'Project Inputs'!B${inputRow}`;
  const revision = `'Project Inputs'!C${inputRow}`;
  const recordType = `'Project Inputs'!D${inputRow}`;
  const key = `'Project Inputs'!E${inputRow}`;
  const value = `'Project Inputs'!F${inputRow}`;
  const unit = `'Project Inputs'!G${inputRow}`;
  const source = `'Project Inputs'!H${inputRow}`;
  const reference = `'Project Inputs'!I${inputRow}`;
  const location = `'Project Inputs'!J${inputRow}`;
  const schemaId = `'Project Inputs'!L${inputRow}`;
  const rowRange = `'Project Inputs'!A${inputRow}:L${inputRow}`;
  const populated = `COUNTA(${rowRange})>0`;
  const knownKeyCount = `COUNTIF('Rules'!$C$4:$C$1000,${key})`;
  const expectedUnit = `IFERROR(INDEX('Rules'!$D$4:$D$1000,MATCH(${key},'Rules'!$C$4:$C$1000,0)),"")`;
  return {
    sourceRow: `=IF(${populated},${inputRow},"")`,
    inputKey: `=IF(${populated},${key},"")`,
    sourceReference: `=IF(${populated},${reference},"")`,
    issue: `=IF(NOT(${populated}),"",TEXTJOIN("; ",TRUE,IF(${schemaId}<>'Template Settings'!$B$10,"Schema ID mismatch",""),IF(${schema}<>'Template Settings'!$B$5,"Schema mismatch",""),IF(${project}<>'Template Settings'!$B$6,"Project mismatch",""),IF(${revision}<>'Template Settings'!$B$7,"Revision mismatch",""),IF(AND(${recordType}<>"FACT",${recordType}<>"DIRECT_ITEM"),"Invalid record type",""),IF(${key}="","Missing input key",""),IF(AND(${key}<>"",${knownKeyCount}=0),"Unknown input key",""),IF(OR(NOT(ISNUMBER(${value})),${value}<0),"Value must be a non-negative number",""),IF(${unit}="","Missing unit",""),IF(AND(${unit}<>"",COUNTIF('Template Settings'!$G$4:$G$100,${unit})=0),"Invalid unit",""),IF(AND(${key}<>"",${knownKeyCount}>0,${unit}<>${expectedUnit}),"Unit does not match input key",""),IF(${source}="","Missing source",""),IF(AND(${source}<>"",COUNTIF('Template Settings'!$I$4:$I$100,${source})=0),"Invalid source",""),IF(${reference}="","Missing source reference",""),IF(AND(${key}<>"",${source}<>"",${reference}<>"",COUNTIFS(${keys},${key},${sources},${source},${refs},${reference})>1),"Duplicate source row","")))`,
  };
}

export function phaseSummaryFormulas(firstDataRow, lastDataRow) {
  const c = PHASE_COLUMN;
  return {
    totalLines: `=COUNTA($${c.lineId}$${firstDataRow}:$${c.lineId}$${lastDataRow})`,
    accountedFor: `=COUNTIF($${c.accountedFor}$${firstDataRow}:$${c.accountedFor}$${lastDataRow},TRUE)`,
    needsReview: `=COUNTIF($${c.review}$${firstDataRow}:$${c.review}$${lastDataRow},"<>")+COUNTIFS($${c.review}$${firstDataRow}:$${c.review}$${lastDataRow},"",$${c.status}$${firstDataRow}:$${c.status}$${lastDataRow},"Needs Review",$${c.lineId}$${firstDataRow}:$${c.lineId}$${lastDataRow},"<>")`,
    kitDemand: `=SUM($${c.kitDemand}$${firstDataRow}:$${c.kitDemand}$${lastDataRow})`,
    importIssues: `=COUNTIF('Import Audit'!$D$5:$D$1004,"<>")`,
    readyPercent: `=IF(COUNTIF('Import Audit'!$D$5:$D$1004,"<>")>0,0,IFERROR(COUNTIFS($${c.accountedFor}$${firstDataRow}:$${c.accountedFor}$${lastDataRow},TRUE,$${c.review}$${firstDataRow}:$${c.review}$${lastDataRow},"",$${c.status}$${firstDataRow}:$${c.status}$${lastDataRow},"<>",$${c.status}$${firstDataRow}:$${c.status}$${lastDataRow},"<>Needs Review")/COUNTA($${c.lineId}$${firstDataRow}:$${c.lineId}$${lastDataRow}),0))`,
  };
}

function escapeFormulaText(value) {
  return String(value).replaceAll('"', '""');
}

function escapeSheetName(value) {
  return String(value).replaceAll("'", "''");
}
