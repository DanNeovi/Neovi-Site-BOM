/**
 * Native Google Sheets builder. This file is combined with the template data,
 * shared formula module, and google-sheet-setup.gs by the build script.
 */
const SITE_BOM_PHASE_SHEETS = Object.freeze([...SITE_BOM_BUILD_DATA.settings.visiblePhases]);
const SITE_BOM_ADMIN_SHEETS = Object.freeze([
  "Template Settings",
  "Items",
  "BOM Lines",
  "Rules",
  "Project Inputs",
  "Import Audit",
  "Procurement Summary",
]);
const SITE_BOM_ALL_SHEETS = [...SITE_BOM_PHASE_SHEETS, ...SITE_BOM_ADMIN_SHEETS];

const SITE_BOM_COLORS = {
  navy: "#17365D",
  white: "#FFFFFF",
  text: "#1F2937",
  border: "#D1D5DB",
  formula: "#F3F4F6",
  projectInput: "#FFF2CC",
  templateInput: "#DDEBF7",
  warning: "#FCE8E6",
  warningText: "#9C0006",
  success: "#E2F0D9",
  successText: "#006100",
  muted: "#6B7280",
};

function buildSiteBomTemplate() {
  const ui = SpreadsheetApp.getUi();
  const confirmation = ui.alert(
    "Build Neovi Site BOM",
    "This will replace every sheet in this spreadsheet with the Site BOM template. Continue?",
    ui.ButtonSet.YES_NO,
  );
  if (confirmation !== ui.Button.YES) return;

  const spreadsheet = SpreadsheetApp.getActive();
  const sheets = new Map();
  for (const name of SITE_BOM_ALL_SHEETS) {
    const sheet = spreadsheet.getSheetByName(name) || spreadsheet.insertSheet(name);
    resetBuildSheet_(sheet, name === "Import Audit" ? 1004 : 250, SITE_BOM_PHASE_SHEETS.includes(name) ? PHASE_HEADERS.length : 24);
    sheets.set(name, sheet);
  }
  for (const sheet of spreadsheet.getSheets()) {
    if (!SITE_BOM_ALL_SHEETS.includes(sheet.getName())) spreadsheet.deleteSheet(sheet);
  }
  SITE_BOM_ALL_SHEETS.forEach((name, index) => {
    spreadsheet.setActiveSheet(sheets.get(name));
    spreadsheet.moveActiveSheet(index + 1);
  });

  buildNativeSettings_(sheets.get("Template Settings"));
  buildNativeItems_(sheets.get("Items"));
  buildNativeBomLines_(sheets.get("BOM Lines"));
  buildNativeRules_(sheets.get("Rules"));
  buildNativeProjectInputs_(sheets.get("Project Inputs"));
  buildNativeImportAudit_(sheets.get("Import Audit"));
  buildNativeProcurement_(sheets.get("Procurement Summary"));
  for (const phase of SITE_BOM_PHASE_SHEETS) buildNativePhase_(sheets.get(phase), phase);

  SpreadsheetApp.flush();
  setupSiteBomTemplate_({ allowEmptyInputs: true });
}

function resetBuildSheet_(sheet, minimumRows, minimumColumns) {
  if (sheet.getMaxRows() < minimumRows) sheet.insertRowsAfter(sheet.getMaxRows(), minimumRows - sheet.getMaxRows());
  if (sheet.getMaxColumns() < minimumColumns) sheet.insertColumnsAfter(sheet.getMaxColumns(), minimumColumns - sheet.getMaxColumns());
  if (sheet.getFilter()) sheet.getFilter().remove();
  sheet.getRange(1, 1, sheet.getMaxRows(), sheet.getMaxColumns()).breakApart();
  sheet.clear();
  sheet.clearConditionalFormatRules();
  sheet.setFrozenRows(0);
  sheet.setFrozenColumns(0);
  sheet.setHiddenGridlines(true);
  sheet.showSheet();
}

function buildNativeSettings_(sheet) {
  const settings = SITE_BOM_BUILD_DATA.settings;
  sheet.getRange("A1:K1").merge().setValue("Template Settings — master controls and active project selection");
  styleTitle_(sheet.getRange("A1:K1"), SITE_BOM_COLORS.navy);
  sheet.getRange("A3:C3").setValues([["Setting", "Value", "Purpose"]]);
  styleHeader_(sheet.getRange("A3:C3"));
  const firstInput = SITE_BOM_BUILD_DATA.projectInputs[0] || {};
  sheet.getRange("A4:C10").setValues([
    ["Template Version", settings.templateVersion, "Version of the master template"],
    ["Input Schema Version", settings.schemaVersion, "Every imported CSV row must match"],
    ["Active Project", firstInput.project || "", "Must match the imported CSV"],
    ["Active Revision", firstInput.revision || "", "Must match the imported CSV"],
    ["Operational Source", "Native Google Sheet", "Editable project Site BOM"],
    ["Visible Phase Tabs", settings.visiblePhases.join(", "), "Only these tabs remain visible after setup"],
    ["Input Schema ID", settings.schemaId, "Identifies the Project Inputs contract"],
  ]);
  sheet.getRange("B4:B10").setBackground(SITE_BOM_COLORS.templateInput);
  sheet.getRange("A11:C13").setValues([
    ["Native build", "Run buildSiteBomTemplate() from Apps Script", "Creates the complete workbook without an XLSX"],
    ["Project refresh", "Import the Revit CSV into Project Inputs using Replace current sheet", "Never import over a phase tab"],
    ["Warnings in seed", SITE_BOM_BUILD_DATA.warnings.length, "Specifications or rules requiring approval"],
  ]);
  const lists = [
    ["Statuses", settings.statuses],
    ["Owners", settings.owners],
    ["Units", settings.units],
    ["Procurement Methods", settings.procurementMethods],
    ["Sources", settings.sourceTypes],
    ["Rule Statuses", settings.ruleStatuses],
    ["Categories", settings.categories],
  ];
  lists.forEach(([name, values], index) => {
    const column = 5 + index;
    sheet.getRange(3, column).setValue(name);
    styleHeader_(sheet.getRange(3, column));
    if (values.length) sheet.getRange(4, column, values.length, 1).setValues(values.map((value) => [value]));
    sheet.setColumnWidth(column, 155);
  });
  sheet.setFrozenRows(3);
  sheet.setColumnWidth(1, 170);
  sheet.setColumnWidth(2, 245);
  sheet.setColumnWidth(3, 340);
}

function buildNativeItems_(sheet) {
  const rows = SITE_BOM_BUILD_DATA.items.map((item) => [
    item.itemId, item.description, item.specification, item.specificationApproved, item.unit, item.owner,
    item.procurementMethod, item.vendor, item.partNumber, item.unitCost, item.packSize, item.minimumOrderQty,
    item.targetStockQty, item.notes,
  ]);
  sheet.getRange("A1:N1").merge().setValue("Items — one row per purchasable SKU or controlled item");
  styleTitle_(sheet.getRange("A1:N1"), SITE_BOM_COLORS.navy);
  sheet.getRange("A3:N3").setValues([ITEM_HEADERS]);
  styleHeader_(sheet.getRange("A3:N3"));
  sheet.getRange(4, 1, rows.length, 14).setValues(rows).setBackground(SITE_BOM_COLORS.templateInput);
  sheet.getRange(4, 3, rows.length, 1).setWrap(true);
  sheet.getRange(4, 10, rows.length, 1).setNumberFormat('"$"#,##0.00');
  sheet.getRange(4, 11, rows.length, 3).setNumberFormat("#,##0.##");
  const approvedRange = sheet.getRange(4, 4, rows.length, 1);
  approvedRange.insertCheckboxes();
  approvedRange.setValues(rows.map((row) => [Boolean(row[3])]));
  sheet.getRange(4, 5, rows.length, 1).setDataValidation(rangeValidation_("Template Settings", "G4:G100"));
  sheet.getRange(4, 6, rows.length, 1).setDataValidation(rangeValidation_("Template Settings", "F4:F100"));
  sheet.getRange(4, 7, rows.length, 1).setDataValidation(rangeValidation_("Template Settings", "H4:H100"));
  sheet.getRange(4, 10, rows.length, 1).setDataValidation(nonNegativeNumberValidation_());
  sheet.getRange(4, 11, rows.length, 1).setDataValidation(positiveNumberValidation_());
  sheet.getRange(4, 12, rows.length, 2).setDataValidation(nonNegativeNumberValidation_());
  sheet.getRange(3, 1, rows.length + 1, 14).createFilter();
  sheet.setFrozenRows(3);
  setColumnWidths_(sheet, [110, 220, 300, 130, 70, 110, 135, 125, 125, 90, 85, 110, 110, 260]);
}

function buildNativeBomLines_(sheet) {
  const rows = SITE_BOM_BUILD_DATA.lines.map((line) => [
    line.lineId, line.itemId, line.phase, line.stage, line.category, line.kitId, line.scope, line.lineNotes,
    line.system, line.deliveryStage, line.siteTeam, line.teamScope,
  ]);
  sheet.getRange("A1:L1").merge().setValue("BOM Lines — fixed work area, trade, site team, delivery stage, and kit placement");
  styleTitle_(sheet.getRange("A1:L1"), SITE_BOM_COLORS.navy);
  sheet.getRange("A3:L3").setValues([BOM_LINE_HEADERS]);
  styleHeader_(sheet.getRange("A3:L3"));
  sheet.getRange(4, 1, rows.length, 12).setValues(rows).setBackground(SITE_BOM_COLORS.templateInput);
  sheet.getRange(4, 5, rows.length, 1).setDataValidation(rangeValidation_("Template Settings", "K4:K100"));
  sheet.getRange(4, 10, rows.length, 1).setDataValidation(listValidation_(SITE_BOM_BUILD_DATA.settings.siteStages));
  sheet.getRange(3, 1, rows.length + 1, 12).createFilter();
  sheet.setFrozenRows(3);
  setColumnWidths_(sheet, [105, 105, 100, 165, 180, 125, 80, 300, 170, 105, 185, 320]);
}

function buildNativeRules_(sheet) {
  const rows = SITE_BOM_BUILD_DATA.lines.map((line) => [
    line.lineId, line.sourceMode, line.inputKey, line.inputUnit, line.multiplier, line.fixedQty,
    line.sparePercent, line.quantityIncrement, line.minimumKitQty, line.ruleStatus, line.ruleNotes,
  ]);
  sheet.getRange("A1:K1").merge().setValue("Rules — line-level demand calculations; vendor packs belong in Items");
  styleTitle_(sheet.getRange("A1:K1"), SITE_BOM_COLORS.navy);
  sheet.getRange("A3:K3").setValues([RULE_HEADERS]);
  styleHeader_(sheet.getRange("A3:K3"));
  sheet.getRange(4, 1, rows.length, 11).setValues(rows).setBackground(SITE_BOM_COLORS.templateInput);
  sheet.getRange(4, 7, rows.length, 1).setNumberFormat("0.0%");
  sheet.getRange(4, 5, rows.length, 5).setNumberFormat("#,##0.##");
  sheet.getRange(4, 2, rows.length, 1).setDataValidation(listValidation_(["DIRECT", "CALCULATED", "FIXED", "MANUAL"]));
  sheet.getRange(4, 4, rows.length, 1).setDataValidation(rangeValidation_("Template Settings", "G4:G100"));
  sheet.getRange(4, 5, rows.length, 3).setDataValidation(nonNegativeNumberValidation_());
  sheet.getRange(4, 8, rows.length, 1).setDataValidation(positiveNumberValidation_());
  sheet.getRange(4, 9, rows.length, 1).setDataValidation(nonNegativeNumberValidation_());
  sheet.getRange(4, 10, rows.length, 1).setDataValidation(rangeValidation_("Template Settings", "J4:J100"));
  sheet.getRange(3, 1, rows.length + 1, 11).createFilter();
  sheet.setFrozenRows(3);
  setColumnWidths_(sheet, [105, 110, 225, 105, 85, 85, 80, 95, 110, 125, 300]);
}

function buildNativeProjectInputs_(sheet) {
  const rows = SITE_BOM_BUILD_DATA.projectInputs.map((row) => [
    row.schemaVersion, row.project, row.revision, row.recordType, row.inputKey, row.value, row.unit, row.source,
    row.sourceReference, row.location, row.notes, row.schemaId,
  ]);
  sheet.getRange("A1:L1").setValues([PROJECT_INPUT_HEADERS]);
  styleHeader_(sheet.getRange("A1:L1"));
  if (rows.length) {
    sheet.getRange(2, 1, rows.length, 12).setValues(rows).setBackground(SITE_BOM_COLORS.projectInput);
    sheet.getRange(2, 4, rows.length, 1).setDataValidation(listValidation_(SITE_BOM_BUILD_DATA.settings.recordTypes));
    sheet.getRange(2, 6, rows.length, 1).setDataValidation(nonNegativeNumberValidation_());
    sheet.getRange(2, 7, rows.length, 1).setDataValidation(rangeValidation_("Template Settings", "G4:G100"));
    sheet.getRange(2, 8, rows.length, 1).setDataValidation(rangeValidation_("Template Settings", "I4:I100"));
  }
  sheet.getRange(1, 1, Math.max(2, rows.length + 1), 12).createFilter();
  sheet.setFrozenRows(1);
  setColumnWidths_(sheet, [105, 165, 90, 110, 235, 90, 70, 100, 210, 150, 280, 220]);
}

function buildNativeImportAudit_(sheet) {
  const firstRow = 5;
  const lastRow = 1004;
  sheet.getRange("A1:D1").merge().setValue("Import Audit — every imported row must be clean before approval");
  styleTitle_(sheet.getRange("A1:D1"), SITE_BOM_COLORS.navy);
  sheet.getRange("A3:B3").setValues([["Issue Count", null]]);
  sheet.getRange("B3").setFormula(`=COUNTIF($D$${firstRow}:$D$${lastRow},"<>")`);
  sheet.getRange("A4:D4").setValues([["Source Row", "Input Key", "Source Reference", "Issue"]]);
  styleHeader_(sheet.getRange("A4:D4"));
  const formulas = [];
  for (let inputRow = 2; inputRow <= 1001; inputRow += 1) {
    const rowFormulas = importAuditRowFormulas(inputRow + 3, inputRow);
    formulas.push([rowFormulas.sourceRow, rowFormulas.inputKey, rowFormulas.sourceReference, rowFormulas.issue]);
  }
  sheet.getRange(firstRow, 1, formulas.length, 4).setFormulas(formulas);
  sheet.getRange(firstRow, 4, formulas.length, 1).setWrap(true);
  addNotBlankRule_(sheet, sheet.getRange(firstRow, 4, formulas.length, 1), SITE_BOM_COLORS.warning, SITE_BOM_COLORS.warningText);
  sheet.setFrozenRows(4);
  setColumnWidths_(sheet, [90, 235, 215, 400]);
}

function buildNativeProcurement_(sheet) {
  const items = SITE_BOM_BUILD_DATA.items;
  const lastRow = 3 + items.length;
  sheet.getRange("A1:X1").merge().setValue("Procurement Summary — inventory is subtracted once, then minimum order and vendor pack are applied");
  styleTitle_(sheet.getRange("A1:X1"), SITE_BOM_COLORS.navy);
  sheet.getRange("A2:F2").setValues([["Total Order Cost", null, "Needs Review", null, "Items to Order", null]]);
  sheet.getRange("B2").setFormula(`=SUM($S$4:$S$${lastRow})`).setNumberFormat('"$"#,##0.00');
  sheet.getRange("D2").setFormula(`=COUNTIF($X$4:$X$${lastRow},"<>")`);
  sheet.getRange("F2").setFormula(`=COUNTIF($R$4:$R$${lastRow},">0")`);
  sheet.getRange("A3:X3").setValues([PROCUREMENT_HEADERS]);
  styleHeader_(sheet.getRange("A3:X3"));
  const rows = items.map((item) => [
    item.itemId, item.description, item.specification, item.specificationApproved, item.unit, item.owner,
    item.procurementMethod, item.vendor, item.partNumber, item.unitCost, item.packSize, item.minimumOrderQty,
    item.targetStockQty, null, 0, 0, null, null, null, null, "Needs Review", false, "", null,
  ]);
  sheet.getRange(4, 1, rows.length, 24).setValues(rows);
  const formulaColumns = new Map([
    [2, "item"], [3, "specification"], [4, "specificationApproved"], [5, "unit"], [6, "owner"],
    [7, "procurementMethod"], [8, "vendor"], [9, "partNumber"], [10, "unitCost"], [11, "packSize"],
    [12, "minimumOrderQty"], [13, "targetStockQty"], [14, "totalKitDemand"], [17, "netNeed"],
    [18, "orderQty"], [19, "extendedCost"], [24, "review"],
  ]);
  const formulas = items.map((_, index) => procurementRowFormulas(4 + index, SITE_BOM_PHASE_SHEETS));
  setFormulaColumns_(sheet, 4, formulas, formulaColumns);
  sheet.getRange(4, 15, rows.length, 2).setBackground(SITE_BOM_COLORS.projectInput);
  sheet.getRange(4, 20, rows.length, 4).setBackground(SITE_BOM_COLORS.projectInput);
  sheet.getRange(4, 1, rows.length, 14).setBackground(SITE_BOM_COLORS.formula);
  sheet.getRange(4, 17, rows.length, 3).setBackground(SITE_BOM_COLORS.formula);
  sheet.getRange(4, 24, rows.length, 1).setBackground(SITE_BOM_COLORS.formula).setWrap(true);
  sheet.getRange(4, 14, rows.length, 5).setNumberFormat("#,##0.##");
  sheet.getRange(4, 10, rows.length, 1).setNumberFormat('"$"#,##0.00');
  sheet.getRange(4, 19, rows.length, 1).setNumberFormat('"$"#,##0.00');
  sheet.getRange(4, 20, rows.length, 1).setNumberFormat("yyyy-mm-dd");
  sheet.getRange(4, 21, rows.length, 1).setDataValidation(rangeValidation_("Template Settings", "E4:E100"));
  sheet.getRange(4, 22, rows.length, 1).insertCheckboxes();
  sheet.getRange(4, 15, rows.length, 2).setDataValidation(nonNegativeNumberValidation_());
  addNotBlankRule_(sheet, sheet.getRange(4, 24, rows.length, 1), SITE_BOM_COLORS.warning, SITE_BOM_COLORS.warningText);
  sheet.getRange(3, 1, rows.length + 1, 24).createFilter();
  sheet.setFrozenRows(3);
  sheet.setFrozenColumns(1);
  setColumnWidths_(sheet, [105, 210, 285, 125, 65, 100, 130, 125, 125, 85, 75, 100, 100, 100, 75, 105, 80, 85, 100, 90, 100, 95, 245, 300]);
}

function buildNativePhase_(sheet, phase) {
  const lines = SITE_BOM_BUILD_DATA.lines.filter((line) => line.phase === phase && line.scope !== "FACTORY");
  const lastRow = 7 + lines.length;
  const phaseColor = lines[0]?.phaseColor || SITE_BOM_COLORS.navy;
  sheet.getRange("A1:AT1").merge().setValue(`${phase} Site BOM`);
  styleTitle_(sheet.getRange("A1:AT1"), phaseColor);
  sheet.getRange("A2:AT2").merge().setValue(
    "Yellow cells are project inputs. Blue cells are master-template inputs. Gray cells are calculations. Order quantities are item totals across all three phases.",
  ).setBackground("#EAF2F8").setFontColor(SITE_BOM_COLORS.text).setWrap(true);
  const summary = phaseSummaryFormulas(8, lastRow);
  const cards = [
    [1, "Lines", summary.totalLines],
    [4, "Accounted For", summary.accountedFor],
    [7, "Needs Review", summary.needsReview],
    [10, "Kit Demand", summary.kitDemand],
    [13, "Import Issues", summary.importIssues],
    [16, "Ready %", summary.readyPercent],
  ];
  cards.forEach(([column, label, formula]) => {
    sheet.getRange(4, column, 2, 2).setBackground("#F8FAFC").setBorder(true, true, true, true, false, false, SITE_BOM_COLORS.border, SpreadsheetApp.BorderStyle.SOLID);
    sheet.getRange(4, column).setValue(label).setFontWeight("bold").setFontColor(SITE_BOM_COLORS.muted);
    sheet.getRange(5, column).setFormula(formula).setFontWeight("bold");
  });
  sheet.getRange("P5").setNumberFormat("0%");
  sheet.getRange("A7:AT7").setValues([PHASE_HEADERS]);
  styleHeader_(sheet.getRange("A7:AT7"));

  const rows = lines.map((line) => [
    line.stage, line.category, line.kitId, line.lineId, line.itemId, line.scope, line.description, line.specification,
    line.unit, line.owner, line.sourceMode, line.inputKey, null, line.multiplier, line.fixedQty, 0, null, null,
    line.sparePercent, null, line.quantityIncrement, line.minimumKitQty, 0, null, null, null, null, null, null, null,
    null, line.procurementMethod, line.vendor, line.partNumber, line.unitCost, null, null, "Needs Review", false,
    [line.lineNotes, line.ruleNotes].filter(Boolean).join(" | "), "", null, null, null, null, null,
  ]);
  sheet.getRange(8, 1, rows.length, 46).setValues(rows);
  const formulaColumns = new Map([
    [1, "stage"], [2, "category"], [3, "kitId"], [5, "itemId"], [6, "scope"], [7, "item"], [8, "specification"],
    [9, "unit"], [10, "owner"], [11, "sourceMode"], [12, "inputKey"], [13, "sourceValue"], [14, "multiplier"],
    [15, "fixedQty"], [17, "calculation"], [18, "requiredQty"], [19, "sparePercent"], [20, "spareQty"],
    [21, "increment"], [22, "minimumKitQty"], [24, "kitDemand"], [25, "totalItemDemand"], [26, "onHand"],
    [27, "alreadyCommitted"], [28, "netNeed"], [29, "packSize"], [30, "minimumOrderQty"], [31, "orderQty"],
    [32, "procurementMethod"], [33, "vendor"], [34, "partNumber"], [35, "unitCost"], [36, "extendedCost"],
    [40, "templateNotes"], [42, "review"], [43, "system"], [44, "deliveryStage"],
    [45, "siteTeam"], [46, "teamScope"],
  ]);
  const formulas = lines.map((_, index) => phaseRowFormulas(8 + index, 2, 1001, phase));
  setFormulaColumns_(sheet, 8, formulas, formulaColumns);

  sheet.getRange(8, 16, rows.length, 1).setBackground(SITE_BOM_COLORS.projectInput);
  sheet.getRange(8, 23, rows.length, 1).setBackground(SITE_BOM_COLORS.formula);
  sheet.getRange(8, 37, rows.length, 3).setBackground(SITE_BOM_COLORS.projectInput);
  sheet.getRange(8, 41, rows.length, 1).setBackground(SITE_BOM_COLORS.projectInput);
  sheet.getRange(8, 1, rows.length, 15).setBackground(SITE_BOM_COLORS.formula);
  sheet.getRange(8, 17, rows.length, 6).setBackground(SITE_BOM_COLORS.formula);
  sheet.getRange(8, 24, rows.length, 13).setBackground(SITE_BOM_COLORS.formula);
  sheet.getRange(8, 40, rows.length, 1).setBackground(SITE_BOM_COLORS.formula);
  sheet.getRange(8, 42, rows.length, 1).setBackground(SITE_BOM_COLORS.formula);
  sheet.getRange(8, 43, rows.length, 4).setBackground(SITE_BOM_COLORS.formula);
  sheet.getRange(8, 4, rows.length, 1).setBackground(SITE_BOM_COLORS.templateInput);
  sheet.getRange(8, 7, rows.length, 2).setWrap(true);
  sheet.getRange(8, 17, rows.length, 1).setWrap(true);
  sheet.getRange(8, 40, rows.length, 3).setWrap(true);
  sheet.getRange(8, 46, rows.length, 1).setWrap(true);
  sheet.getRange(8, 13, rows.length, 4).setNumberFormat("#,##0.##");
  sheet.getRange(8, 18, rows.length, 14).setNumberFormat("#,##0.##");
  sheet.getRange(8, 19, rows.length, 1).setNumberFormat("0.0%");
  sheet.getRange(8, 35, rows.length, 2).setNumberFormat('"$"#,##0.00');
  sheet.getRange(8, 37, rows.length, 1).setNumberFormat("yyyy-mm-dd");
  sheet.getRange(8, 38, rows.length, 1).setDataValidation(rangeValidation_("Template Settings", "E4:E100"));
  sheet.getRange(8, 39, rows.length, 1).insertCheckboxes();
  sheet.getRange(8, 16, rows.length, 1).setDataValidation(nonNegativeNumberValidation_());
  sheet.getRange(8, 23, rows.length, 1).setDataValidation(nonNegativeNumberValidation_());
  addNotBlankRule_(sheet, sheet.getRange(8, 42, rows.length, 1), SITE_BOM_COLORS.warning, SITE_BOM_COLORS.warningText);
  addTextEqualRule_(sheet, sheet.getRange(8, 38, rows.length, 1), "Ready", SITE_BOM_COLORS.success, SITE_BOM_COLORS.successText);
  sheet.getRange(7, 1, rows.length + 1, 46).createFilter();
  sheet.setFrozenRows(7);
  sheet.setFrozenColumns(5);
  setColumnWidths_(sheet, [145, 160, 115, 95, 95, 65, 210, 260, 65, 100, 95, 205, 80, 65, 75, 85, 225, 80, 70, 80, 75, 85, 80, 80, 95, 75, 100, 75, 75, 85, 105, 120, 125, 125, 80, 105, 90, 100, 95, 245, 245, 290, 170, 105, 185, 320]);
}


function setFormulaColumns_(sheet, startRow, formulaRows, mapping) {
  for (const [column, property] of mapping.entries()) {
    sheet.getRange(startRow, column, formulaRows.length, 1).setFormulas(formulaRows.map((row) => [row[property]]));
  }
}

function styleTitle_(range, color) {
  range.setBackground(color).setFontColor(SITE_BOM_COLORS.white).setFontWeight("bold").setVerticalAlignment("middle");
}

function styleHeader_(range) {
  range.setBackground(SITE_BOM_COLORS.navy).setFontColor(SITE_BOM_COLORS.white).setFontWeight("bold").setWrap(true).setVerticalAlignment("middle");
}

function setColumnWidths_(sheet, widths) {
  widths.forEach((width, index) => sheet.setColumnWidth(index + 1, width));
}

function listValidation_(values) {
  return SpreadsheetApp.newDataValidation().requireValueInList(values, true).setAllowInvalid(false).build();
}

function rangeValidation_(sheetName, a1) {
  const range = SpreadsheetApp.getActive().getSheetByName(sheetName).getRange(a1);
  return SpreadsheetApp.newDataValidation().requireValueInRange(range, true).setAllowInvalid(false).build();
}

function nonNegativeNumberValidation_() {
  return SpreadsheetApp.newDataValidation().requireNumberGreaterThanOrEqualTo(0).setAllowInvalid(false).build();
}

function positiveNumberValidation_() {
  return SpreadsheetApp.newDataValidation().requireNumberGreaterThan(0).setAllowInvalid(false).build();
}

function addNotBlankRule_(sheet, range, fill, fontColor) {
  const rules = sheet.getConditionalFormatRules();
  rules.push(SpreadsheetApp.newConditionalFormatRule().whenCellNotEmpty().setBackground(fill).setFontColor(fontColor).setRanges([range]).build());
  sheet.setConditionalFormatRules(rules);
}

function addTextEqualRule_(sheet, range, text, fill, fontColor) {
  const rules = sheet.getConditionalFormatRules();
  rules.push(SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo(text).setBackground(fill).setFontColor(fontColor).setRanges([range]).build());
  sheet.setConditionalFormatRules(rules);
}
