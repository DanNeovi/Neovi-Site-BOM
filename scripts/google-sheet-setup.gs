/**
 * One-time native Google Sheets setup for the Neovi Site BOM master.
 * Included in the generated native Google Sheets builder. No XLSX is used.
 */
const SITE_BOM_PROTECTION_PREFIX = "Neovi Site BOM managed range";
const SITE_BOM_MAX_MASTER_ROWS = 997;
const SITE_BOM_MAX_PHASE_ROWS = 993;
const SITE_BOM_MAX_INPUT_ROWS = 1000;

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("Site BOM")
    .addItem("Apply template setup", "setupSiteBomTemplate")
    .addItem("Sync template changes", "syncSiteBomMasterData")
    .addItem("Prepare Project Inputs import", "prepareProjectInputImport")
    .addItem("Validate before approval", "validateSiteBomBeforeApproval")
    .addItem("Download master snapshot", "downloadSiteBomMasterSnapshot")
    .addItem("Show admin sheets", "showSiteBomAdminSheets")
    .addToUi();
}

function setupSiteBomTemplate() {
  setupSiteBomTemplate_({ allowEmptyInputs: false });
}

function setupSiteBomTemplate_(options) {
  const spreadsheet = SpreadsheetApp.getActive();
  syncSiteBomMasterData_(spreadsheet);
  validateImportedProjectInputs_(spreadsheet, { allowEmpty: options.allowEmptyInputs === true });
  validateProjectAdjustments_(spreadsheet);
  removeManagedProtections_(spreadsheet);

  for (const name of SITE_BOM_PHASE_SHEETS) {
    const sheet = requiredSheet_(spreadsheet, name);
    sheet.showSheet();
    const lastRow = Math.max(8, lastDataRow_(sheet, 4));
    ensureCheckboxesPreserveValues_(sheet.getRange(`AM8:AM${lastRow}`));
    for (const a1 of [
      "A1:AT7",
      `A8:O${lastRow}`,
      `Q8:AJ${lastRow}`,
      `AN8:AN${lastRow}`,
      `AP8:AT${lastRow}`,
    ]) protectStrict_(sheet.getRange(a1), `${SITE_BOM_PROTECTION_PREFIX}: ${name} ${a1}`);
  }

  const procurement = requiredSheet_(spreadsheet, "Procurement Summary");
  const procurementLastRow = Math.max(4, lastDataRow_(procurement, 1));
  ensureCheckboxesPreserveValues_(procurement.getRange(`V4:V${procurementLastRow}`));
  for (const a1 of [
    "A1:X3",
    `A4:N${procurementLastRow}`,
    `Q4:S${procurementLastRow}`,
    `X4:X${procurementLastRow}`,
  ]) protectStrict_(procurement.getRange(a1), `${SITE_BOM_PROTECTION_PREFIX}: Procurement ${a1}`);

  for (const [sheetName, a1] of [
    ["Items", "A1:N3"],
    ["BOM Lines", "A1:L3"],
    ["Rules", "A1:K3"],
    ["Import Audit", "A1:D1004"],
  ]) {
    const sheet = requiredSheet_(spreadsheet, sheetName);
    protectStrict_(sheet.getRange(a1), `${SITE_BOM_PROTECTION_PREFIX}: ${sheetName} ${a1}`);
  }

  for (const [sheetName, columnCount] of [["Items", 14], ["BOM Lines", 12], ["Rules", 11]]) {
    const sheet = requiredSheet_(spreadsheet, sheetName);
    const lastRow = Math.max(4, lastDataRow_(sheet, 1));
    const a1 = sheet.getRange(4, 1, lastRow - 3, columnCount).getA1Notation();
    protectStrict_(sheet.getRange(a1), `${SITE_BOM_PROTECTION_PREFIX}: fixed master ${sheetName} ${a1}`);
  }

  for (const name of SITE_BOM_ADMIN_SHEETS) requiredSheet_(spreadsheet, name).hideSheet();
  requiredSheet_(spreadsheet, SITE_BOM_PHASE_SHEETS[0]).activate();
  SpreadsheetApp.getUi().alert(`Site BOM setup complete. Visible phase tabs: ${SITE_BOM_PHASE_SHEETS.join(", ")}.`);
}

/**
 * Rebuilds the visible phase line lists and the procurement Item ID list from
 * the editable master tables. Project values are preserved by stable Line ID
 * or Item ID, so rows can be added, removed, reordered, or moved safely.
 */
function syncSiteBomMasterData() {
  setupSiteBomTemplate_({ allowEmptyInputs: true });
}

function prepareProjectInputImport() {
  const sheet = requiredSheet_(SpreadsheetApp.getActive(), "Project Inputs");
  sheet.showSheet();
  sheet.activate();
  SpreadsheetApp.getUi().alert(
    "Project Inputs is ready. Use File > Import > Upload and choose Replace current sheet. " +
    "After import, review Import Audit and run Apply template setup to hide admin sheets again.",
  );
}

function showSiteBomAdminSheets() {
  const spreadsheet = SpreadsheetApp.getActive();
  for (const name of SITE_BOM_ADMIN_SHEETS) requiredSheet_(spreadsheet, name).showSheet();
}

function downloadSiteBomMasterSnapshot() {
  const spreadsheet = SpreadsheetApp.getActive();
  syncSiteBomMasterData_(spreadsheet);
  const settingsSheet = requiredSheet_(spreadsheet, "Template Settings");
  const items = masterRows_(requiredSheet_(spreadsheet, "Items"), 4, 14).map((row) => ({
    itemId: text_(row[0]), description: text_(row[1]), specification: text_(row[2]),
    specificationApproved: row[3] === true, unit: text_(row[4]), owner: text_(row[5]),
    procurementMethod: text_(row[6]), vendor: text_(row[7]), partNumber: text_(row[8]),
    unitCost: row[9] === "" ? null : row[9], packSize: row[10], minimumOrderQty: row[11],
    targetStockQty: row[12], notes: text_(row[13]),
  }));
  const bomLines = masterRows_(requiredSheet_(spreadsheet, "BOM Lines"), 4, 12).map((row) => ({
    lineId: text_(row[0]), itemId: text_(row[1]), phase: text_(row[2]), stage: text_(row[3]),
    category: text_(row[4]), kitId: text_(row[5]), scope: text_(row[6]), lineNotes: text_(row[7]),
    system: text_(row[8]), deliveryStage: text_(row[9]), siteTeam: text_(row[10]), teamScope: text_(row[11]),
  }));
  const rules = masterRows_(requiredSheet_(spreadsheet, "Rules"), 4, 11).map((row) => ({
    lineId: text_(row[0]), sourceMode: text_(row[1]), inputKey: text_(row[2]), inputUnit: text_(row[3]),
    multiplier: row[4], fixedQty: row[5], sparePercent: row[6], quantityIncrement: row[7],
    minimumKitQty: row[8], ruleStatus: text_(row[9]), ruleNotes: text_(row[10]),
  }));
  const inputUnits = {};
  rules.filter((rule) => rule.inputKey).forEach((rule) => { inputUnits[rule.inputKey] = rule.inputUnit; });
  const phaseCodes = {};
  const phaseColors = {};
  SITE_BOM_BUILD_DATA.lines.forEach((line) => {
    phaseCodes[line.phase] = line.phaseCode;
    phaseColors[line.phase] = line.phaseColor;
  });
  const snapshot = {
    format: "neovi-site-bom-master-snapshot",
    formatVersion: 2,
    exportedAt: new Date().toISOString(),
    settings: {
      templateName: SITE_BOM_BUILD_DATA.settings.templateName,
      templateVersion: text_(settingsSheet.getRange("B4").getDisplayValue()),
      schemaId: text_(settingsSheet.getRange("B10").getDisplayValue()),
      schemaVersion: text_(settingsSheet.getRange("B5").getDisplayValue()),
      catalogVersion: SITE_BOM_BUILD_DATA.settings.catalogVersion,
      catalogSchemaId: SITE_BOM_BUILD_DATA.settings.catalogSchemaId,
      catalogSchemaVersion: SITE_BOM_BUILD_DATA.settings.catalogSchemaVersion,
      siteStages: [...SITE_BOM_BUILD_DATA.settings.siteStages],
      categoryCodes: { ...SITE_BOM_BUILD_DATA.settings.categoryCodes },
      visiblePhases: [...SITE_BOM_PHASE_SHEETS],
      statuses: listValues_(settingsSheet, 5),
      owners: listValues_(settingsSheet, 6),
      units: listValues_(settingsSheet, 7),
      procurementMethods: listValues_(settingsSheet, 8),
      sourceTypes: listValues_(settingsSheet, 9),
      recordTypes: [...SITE_BOM_BUILD_DATA.settings.recordTypes],
      ruleStatuses: listValues_(settingsSheet, 10),
      categories: listValues_(settingsSheet, 11),
      inputUnits,
      phaseCodes,
      phaseColors,
    },
    items,
    bomLines,
    rules,
  };
  const json = JSON.stringify(snapshot, null, 2);
  const encoded = Utilities.base64Encode(json);
  const version = snapshot.settings.templateVersion.replace(/[^A-Za-z0-9_.-]+/g, "-") || "snapshot";
  const fileName = `neovi-site-bom-master-${version}.json`;
  const html = HtmlService.createHtmlOutput(
    `<div style="font:14px Arial,sans-serif;padding:18px"><h3>Master snapshot ready</h3>` +
    `<p>Save this JSON beside the repository so the exact Sheet master can be rebuilt later.</p>` +
    `<p><a download="${fileName}" href="data:application/json;base64,${encoded}" style="display:inline-block;padding:10px 14px;background:#17365D;color:white;text-decoration:none;border-radius:4px">Download ${fileName}</a></p></div>`,
  ).setWidth(520).setHeight(210);
  SpreadsheetApp.getUi().showModalDialog(html, "Download Site BOM master snapshot");
}

function validateSiteBomBeforeApproval() {
  const spreadsheet = SpreadsheetApp.getActive();
  syncSiteBomMasterData_(spreadsheet);
  validateImportedProjectInputs_(spreadsheet);
  validateProjectAdjustments_(spreadsheet);
  validateApprovalReadiness_(spreadsheet);
  SpreadsheetApp.getUi().alert("Site BOM approval validation passed. Imports, master data, calculations, and required project sign-offs are clean.");
}

function syncSiteBomMasterData_(spreadsheet) {
  const itemSheet = requiredSheet_(spreadsheet, "Items");
  const lineSheet = requiredSheet_(spreadsheet, "BOM Lines");
  const ruleSheet = requiredSheet_(spreadsheet, "Rules");
  prepareMasterTableRows_(itemSheet, lineSheet, ruleSheet);
  const items = masterRows_(itemSheet, 4, 14);
  const lines = masterRows_(lineSheet, 4, 12);
  const rules = masterRows_(ruleSheet, 4, 11);
  const errors = [];
  const itemIds = uniqueIds_(items, 0, "Item ID", errors);
  const lineIds = uniqueIds_(lines, 0, "Line ID", errors);
  const ruleIds = uniqueIds_(rules, 0, "Rule Line ID", errors);
  const linesByPhase = new Map(SITE_BOM_PHASE_SHEETS.map((name) => [name, []]));
  validateMasterTables_(spreadsheet, items, lines, rules, errors);

  for (const row of lines) {
    const lineId = text_(row[0]);
    const itemId = text_(row[1]);
    const phase = text_(row[2]);
    const scope = text_(row[6]).toUpperCase();
    if (!itemIds.has(itemId)) errors.push(`BOM Line ${lineId} references missing Item ID ${itemId || "<blank>"}.`);
    if (!ruleIds.has(lineId)) errors.push(`BOM Line ${lineId} has no matching Rules row.`);
    if (!linesByPhase.has(phase)) errors.push(`BOM Line ${lineId} uses invalid phase ${phase || "<blank>"}.`);
    else if (scope !== "FACTORY") linesByPhase.get(phase).push(lineId);
  }
  for (const ruleId of ruleIds) {
    if (!lineIds.has(ruleId)) errors.push(`Rules row ${ruleId} has no matching BOM Line.`);
  }
  if (items.length === 0) errors.push("Items must contain at least one data row.");
  if (items.length > SITE_BOM_MAX_MASTER_ROWS) errors.push(`Items exceeds the supported ${SITE_BOM_MAX_MASTER_ROWS} rows.`);
  for (const phase of SITE_BOM_PHASE_SHEETS) {
    if (linesByPhase.get(phase).length === 0) errors.push(`${phase} must contain at least one non-factory BOM Line.`);
    if (linesByPhase.get(phase).length > SITE_BOM_MAX_PHASE_ROWS) errors.push(`${phase} exceeds the supported ${SITE_BOM_MAX_PHASE_ROWS} rows.`);
  }
  if (errors.length) throw new Error(`Site BOM master tables are invalid:\n- ${errors.join("\n- ")}`);

  syncProcurementRows_(requiredSheet_(spreadsheet, "Procurement Summary"), [...itemIds]);
  for (const phase of SITE_BOM_PHASE_SHEETS) {
    syncPhaseRows_(requiredSheet_(spreadsheet, phase), linesByPhase.get(phase));
  }
}

function syncPhaseRows_(sheet, orderedLineIds) {
  const startRow = 8;
  const keyColumn = 4;
  const projectColumns = [16, 23, 37, 38, 39, 41]; // P, W, AK, AL, AM, AO
  const defaults = [0, 0, "", "Needs Review", false, ""];
  const saved = valuesByKey_(sheet, startRow, keyColumn, projectColumns);
  const oldLastRow = Math.max(startRow, lastDataRow_(sheet, keyColumn));
  const activeLastRow = startRow + orderedLineIds.length - 1;
  const capacityLastRow = Math.max(oldLastRow, activeLastRow);
  ensureRows_(sheet, capacityLastRow);
  copyTemplateRow_(sheet, startRow, capacityLastRow, 46);
  sheet.getRange(startRow, 1, capacityLastRow - startRow + 1, 46).clearContent();
  setColumn_(sheet, startRow, keyColumn, capacityLastRow, orderedLineIds.map((id) => id));
  restoreByKey_(sheet, startRow, projectColumns, capacityLastRow, orderedLineIds, saved, defaults);
  if (orderedLineIds.length) {
    const formulas = orderedLineIds.map((_, index) => phaseRowFormulas(startRow + index, 2, 1001, sheet.getName()));
    setFormulaColumns_(sheet, startRow, formulas, new Map([
      [1, "stage"], [2, "category"], [3, "kitId"], [5, "itemId"], [6, "scope"], [7, "item"], [8, "specification"],
      [9, "unit"], [10, "owner"], [11, "sourceMode"], [12, "inputKey"], [13, "sourceValue"], [14, "multiplier"],
      [15, "fixedQty"], [17, "calculation"], [18, "requiredQty"], [19, "sparePercent"], [20, "spareQty"],
      [21, "increment"], [22, "minimumKitQty"], [24, "kitDemand"], [25, "totalItemDemand"], [26, "onHand"],
      [27, "alreadyCommitted"], [28, "netNeed"], [29, "packSize"], [30, "minimumOrderQty"], [31, "orderQty"],
      [32, "procurementMethod"], [33, "vendor"], [34, "partNumber"], [35, "unitCost"], [36, "extendedCost"],
      [40, "templateNotes"], [42, "review"], [43, "system"], [44, "deliveryStage"],
      [45, "siteTeam"], [46, "teamScope"],
    ]));
  }
  if (orderedLineIds.length) ensureCheckboxesPreserveValues_(sheet.getRange(startRow, 39, orderedLineIds.length, 1));
  updatePhaseSummary_(sheet, Math.max(startRow, activeLastRow));
  replaceFilter_(sheet, 7, Math.max(startRow, activeLastRow), 46);
  refreshPhaseConditionalFormatting_(sheet, Math.max(startRow, activeLastRow));
}

function syncProcurementRows_(sheet, orderedItemIds) {
  const startRow = 4;
  const keyColumn = 1;
  const projectColumns = [15, 16, 20, 21, 22, 23]; // O, P, T, U, V, W
  const defaults = [0, 0, "", "Needs Review", false, ""];
  const saved = valuesByKey_(sheet, startRow, keyColumn, projectColumns);
  const oldLastRow = Math.max(startRow, lastDataRow_(sheet, keyColumn));
  const activeLastRow = startRow + orderedItemIds.length - 1;
  const capacityLastRow = Math.max(oldLastRow, activeLastRow);
  ensureRows_(sheet, capacityLastRow);
  copyTemplateRow_(sheet, startRow, capacityLastRow, 24);
  sheet.getRange(startRow, 1, capacityLastRow - startRow + 1, 24).clearContent();
  setColumn_(sheet, startRow, keyColumn, capacityLastRow, orderedItemIds.map((id) => id));
  restoreByKey_(sheet, startRow, projectColumns, capacityLastRow, orderedItemIds, saved, defaults);
  if (orderedItemIds.length) {
    const formulas = orderedItemIds.map((_, index) => procurementRowFormulas(startRow + index, SITE_BOM_PHASE_SHEETS));
    setFormulaColumns_(sheet, startRow, formulas, new Map([
      [2, "item"], [3, "specification"], [4, "specificationApproved"], [5, "unit"], [6, "owner"],
      [7, "procurementMethod"], [8, "vendor"], [9, "partNumber"], [10, "unitCost"], [11, "packSize"],
      [12, "minimumOrderQty"], [13, "targetStockQty"], [14, "totalKitDemand"], [17, "netNeed"],
      [18, "orderQty"], [19, "extendedCost"], [24, "review"],
    ]));
  }
  ensureCheckboxesPreserveValues_(sheet.getRange(startRow, 22, orderedItemIds.length, 1));
  sheet.getRange("B2").setFormula(`=SUM($S$4:$S$${activeLastRow})`);
  sheet.getRange("D2").setFormula(`=COUNTIF($X$4:$X$${activeLastRow},"<>")`);
  sheet.getRange("F2").setFormula(`=COUNTIF($R$4:$R$${activeLastRow},">0")`);
  replaceFilter_(sheet, 3, activeLastRow, 24);
  refreshProcurementConditionalFormatting_(sheet, activeLastRow);
}

function updatePhaseSummary_(sheet, lastRow) {
  const formulas = phaseSummaryFormulas(8, lastRow);
  sheet.getRange("A5").setFormula(formulas.totalLines);
  sheet.getRange("D5").setFormula(formulas.accountedFor);
  sheet.getRange("G5").setFormula(formulas.needsReview);
  sheet.getRange("J5").setFormula(formulas.kitDemand);
  sheet.getRange("M5").setFormula(formulas.importIssues);
  sheet.getRange("P5").setFormula(formulas.readyPercent);
}

function prepareMasterTableRows_(itemSheet, lineSheet, ruleSheet) {
  const itemLastRow = Math.max(4, itemSheet.getLastRow());
  const itemRowCount = itemLastRow - 3;
  const itemRange = itemSheet.getRange(4, 1, itemRowCount, ITEM_HEADERS.length);
  const itemValues = itemRange.getValues();
  itemRange.setBackground(SITE_BOM_COLORS.templateInput);
  itemSheet.getRange(4, 3, itemRowCount, 1).setWrap(true);
  itemSheet.getRange(4, 10, itemRowCount, 1).setNumberFormat('"$"#,##0.00').setDataValidation(nonNegativeNumberValidation_());
  itemSheet.getRange(4, 11, itemRowCount, 1).setNumberFormat("#,##0.##").setDataValidation(positiveNumberValidation_());
  itemSheet.getRange(4, 12, itemRowCount, 2).setNumberFormat("#,##0.##").setDataValidation(nonNegativeNumberValidation_());
  itemSheet.getRange(4, 5, itemRowCount, 1).setDataValidation(rangeValidation_("Template Settings", "G4:G100"));
  itemSheet.getRange(4, 6, itemRowCount, 1).setDataValidation(rangeValidation_("Template Settings", "F4:F100"));
  itemSheet.getRange(4, 7, itemRowCount, 1).setDataValidation(rangeValidation_("Template Settings", "H4:H100"));
  const approvals = itemValues.map((row) => [
    row.some((value, index) => index !== 3 && text_(value) !== "") ? row[3] === true : "",
  ]);
  const approvalRange = itemSheet.getRange(4, 4, itemRowCount, 1);
  approvalRange.insertCheckboxes();
  approvalRange.setValues(approvals);
  replaceFilter_(itemSheet, 3, itemLastRow, ITEM_HEADERS.length);

  const lineLastRow = Math.max(4, lineSheet.getLastRow());
  const lineRowCount = lineLastRow - 3;
  lineSheet.getRange(4, 1, lineRowCount, BOM_LINE_HEADERS.length).setBackground(SITE_BOM_COLORS.templateInput);
  lineSheet.getRange(4, 3, lineRowCount, 1).setDataValidation(listValidation_(SITE_BOM_PHASE_SHEETS));
  lineSheet.getRange(4, 5, lineRowCount, 1).setDataValidation(rangeValidation_("Template Settings", "K4:K100"));
  lineSheet.getRange(4, 7, lineRowCount, 1).setDataValidation(listValidation_(["SITE", "FACTORY", "BOTH"]));
  lineSheet.getRange(4, 10, lineRowCount, 1).setDataValidation(listValidation_(SITE_BOM_BUILD_DATA.settings.siteStages));
  replaceFilter_(lineSheet, 3, lineLastRow, BOM_LINE_HEADERS.length);

  const ruleLastRow = Math.max(4, ruleSheet.getLastRow());
  const ruleRowCount = ruleLastRow - 3;
  ruleSheet.getRange(4, 1, ruleRowCount, RULE_HEADERS.length).setBackground(SITE_BOM_COLORS.templateInput);
  ruleSheet.getRange(4, 2, ruleRowCount, 1).setDataValidation(listValidation_(["DIRECT", "CALCULATED", "FIXED", "MANUAL"]));
  ruleSheet.getRange(4, 4, ruleRowCount, 1).setDataValidation(rangeValidation_("Template Settings", "G4:G100"));
  ruleSheet.getRange(4, 5, ruleRowCount, 3).setNumberFormat("#,##0.##").setDataValidation(nonNegativeNumberValidation_());
  ruleSheet.getRange(4, 7, ruleRowCount, 1).setNumberFormat("0.0%");
  ruleSheet.getRange(4, 8, ruleRowCount, 1).setNumberFormat("#,##0.##").setDataValidation(positiveNumberValidation_());
  ruleSheet.getRange(4, 9, ruleRowCount, 1).setNumberFormat("#,##0.##").setDataValidation(nonNegativeNumberValidation_());
  ruleSheet.getRange(4, 10, ruleRowCount, 1).setDataValidation(rangeValidation_("Template Settings", "J4:J100"));
  replaceFilter_(ruleSheet, 3, ruleLastRow, RULE_HEADERS.length);
}

function masterRows_(sheet, startRow, columnCount) {
  const lastRow = sheet.getLastRow();
  if (lastRow < startRow) return [];
  return sheet.getRange(startRow, 1, lastRow - startRow + 1, columnCount)
    .getValues()
    .filter((row) => row.some((value) => text_(value) !== ""));
}

function validateMasterTables_(spreadsheet, items, lines, rules, errors) {
  const settings = requiredSheet_(spreadsheet, "Template Settings");
  validateSettingsList_(settings, 5, "Statuses", errors, { requiredValues: ["Needs Review"] });
  validateSettingsList_(settings, 6, "Owners", errors, { requiredValues: ["Unassigned"] });
  validateSettingsList_(settings, 7, "Units", errors, { requireUppercase: true, requiredValues: ["EA"] });
  validateSettingsList_(settings, 8, "Procurement Methods", errors, { requiredValues: ["TBD", "Order"] });
  validateSettingsList_(settings, 9, "Sources", errors, { requireUppercase: true, requiredValues: ["REVIT"] });
  validateSettingsList_(settings, 10, "Rule Statuses", errors, { requireUppercase: true, requiredValues: ["NEEDS_REVIEW", "APPROVED"] });
  validateSettingsList_(settings, 11, "Categories", errors);
  const owners = new Set(listValues_(settings, 6));
  const units = new Set(listValues_(settings, 7));
  const procurementMethods = new Set(listValues_(settings, 8));
  const ruleStatuses = new Set(listValues_(settings, 10));
  const categories = new Set(listValues_(settings, 11));
  const idPattern = /^[A-Za-z0-9][A-Za-z0-9_.:-]*$/;
  const inputKeyPattern = /^[a-z][a-z0-9_]*$/;
  const unitByKey = new Map();

  items.forEach((row, index) => {
    const label = `Items row ${index + 4}`;
    const id = text_(row[0]);
    if (!idPattern.test(id)) errors.push(`${label} has invalid Item ID ${id || "<blank>"}.`);
    if (!text_(row[1])) errors.push(`${label} is missing Item.`);
    if (!text_(row[2])) errors.push(`${label} is missing Specification.`);
    if (typeof row[3] !== "boolean") errors.push(`${label} Specification Approved must be a checkbox.`);
    if (!units.has(text_(row[4]))) errors.push(`${label} has invalid Unit ${text_(row[4]) || "<blank>"}.`);
    if (!owners.has(text_(row[5]))) errors.push(`${label} has invalid Owner ${text_(row[5]) || "<blank>"}.`);
    if (!procurementMethods.has(text_(row[6]))) errors.push(`${label} has invalid Procurement Method ${text_(row[6]) || "<blank>"}.`);
    validateNumber_(row[9], `${label} Unit Cost`, errors, { allowBlank: true, minimum: 0 });
    validateNumber_(row[10], `${label} Pack Size`, errors, { minimum: Number.MIN_VALUE });
    validateNumber_(row[11], `${label} Minimum Order Qty`, errors, { minimum: 0 });
    validateNumber_(row[12], `${label} Target Stock Qty`, errors, { minimum: 0 });
  });

  lines.forEach((row, index) => {
    const label = `BOM Lines row ${index + 4}`;
    if (!idPattern.test(text_(row[0]))) errors.push(`${label} has invalid Line ID ${text_(row[0]) || "<blank>"}.`);
    if (!idPattern.test(text_(row[1]))) errors.push(`${label} has invalid Item ID ${text_(row[1]) || "<blank>"}.`);
    if (!SITE_BOM_PHASE_SHEETS.includes(text_(row[2]))) errors.push(`${label} has invalid Phase ${text_(row[2]) || "<blank>"}.`);
    if (!categories.has(text_(row[4]))) errors.push(`${label} has invalid Category ${text_(row[4]) || "<blank>"}.`);
    for (const [column, name] of [[3, "Stage"], [4, "Category"], [5, "Kit ID"]]) {
      if (!text_(row[column])) errors.push(`${label} is missing ${name}.`);
    }
    if (!["SITE", "FACTORY", "BOTH"].includes(text_(row[6]).toUpperCase())) errors.push(`${label} has invalid Scope ${text_(row[6]) || "<blank>"}.`);
    if (!text_(row[8])) errors.push(`${label} is missing System.`);
    if (!SITE_BOM_BUILD_DATA.settings.siteStages.includes(text_(row[9]))) errors.push(`${label} has invalid Delivery Stage ${text_(row[9]) || "<blank>"}.`);
    if (text_(row[10]) !== SITE_BOM_BUILD_DATA.settings.categoryTeams[text_(row[4])]) errors.push(`${label} has an invalid Site Team.`);
    if (text_(row[11]) !== SITE_BOM_BUILD_DATA.settings.categoryTeamScopes[text_(row[4])]) errors.push(`${label} has an invalid Team Scope.`);
  });

  rules.forEach((row, index) => {
    const label = `Rules row ${index + 4}`;
    const lineId = text_(row[0]);
    const mode = text_(row[1]).toUpperCase();
    const key = text_(row[2]);
    const expectedUnit = text_(row[3]).toUpperCase();
    if (!idPattern.test(lineId)) errors.push(`${label} has invalid Line ID ${lineId || "<blank>"}.`);
    if (!["DIRECT", "CALCULATED", "FIXED", "MANUAL"].includes(mode)) errors.push(`${label} has invalid Source Mode ${mode || "<blank>"}.`);
    if (["DIRECT", "CALCULATED"].includes(mode)) {
      if (!inputKeyPattern.test(key)) errors.push(`${label} has invalid Input Key ${key || "<blank>"}.`);
      if (!units.has(expectedUnit)) errors.push(`${label} has invalid Expected Input Unit ${expectedUnit || "<blank>"}.`);
      const prior = unitByKey.get(key);
      if (prior && prior !== expectedUnit) errors.push(`${label} conflicts with expected unit ${prior} for ${key}.`);
      else if (key && expectedUnit) unitByKey.set(key, expectedUnit);
    } else if (key || expectedUnit) {
      errors.push(`${label} must leave Input Key and Expected Input Unit blank for ${mode}.`);
    }
    validateNumber_(row[4], `${label} Multiplier`, errors, { minimum: 0 });
    validateNumber_(row[5], `${label} Fixed Qty`, errors, { minimum: 0 });
    validateNumber_(row[6], `${label} Spare %`, errors, { minimum: 0 });
    validateNumber_(row[7], `${label} Qty Increment`, errors, { minimum: Number.MIN_VALUE });
    validateNumber_(row[8], `${label} Minimum Kit Qty`, errors, { minimum: 0 });
    if (!ruleStatuses.has(text_(row[9]))) errors.push(`${label} has invalid Rule Status ${text_(row[9]) || "<blank>"}.`);
  });
}

function validateImportedProjectInputs_(spreadsheet, options = {}) {
  const sheet = requiredSheet_(spreadsheet, "Project Inputs");
  const errors = [];
  const header = sheet.getRange(1, 1, 1, PROJECT_INPUT_HEADERS.length).getDisplayValues()[0];
  PROJECT_INPUT_HEADERS.forEach((name, index) => {
    if (text_(header[index]) !== name) errors.push(`Project Inputs column ${index + 1} must be ${name}.`);
  });
  const lastRow = sheet.getLastRow();
  const inputRange = lastRow < 2 ? null : sheet.getRange(2, 1, lastRow - 1, PROJECT_INPUT_HEADERS.length);
  const inputValues = inputRange ? inputRange.getValues() : [];
  const inputFormulas = inputRange ? inputRange.getFormulas() : [];
  inputFormulas.forEach((formulaRow, rowIndex) => {
    formulaRow.forEach((formula, columnIndex) => {
      if (formula) errors.push(`Project Inputs row ${rowIndex + 2} column ${columnIndex + 1} must not contain a formula.`);
    });
  });
  if (sheet.getLastColumn() > PROJECT_INPUT_HEADERS.length) {
    const extraColumnCount = sheet.getLastColumn() - PROJECT_INPUT_HEADERS.length;
    const extraRange = sheet.getRange(1, PROJECT_INPUT_HEADERS.length + 1, Math.max(1, lastRow), extraColumnCount);
    const hasUnexpectedData = extraRange.getDisplayValues().some((row) => row.some((value) => text_(value) !== ""))
      || extraRange.getFormulas().some((row) => row.some(Boolean));
    if (hasUnexpectedData) errors.push("Project Inputs contains unexpected data after column L.");
  }
  const rows = inputValues
    .map((row, index) => ({ row, rowNumber: index + 2 }))
    .filter(({ row }) => row.some((value) => text_(value) !== ""));
  if (rows.length === 0 && options.allowEmpty !== true) errors.push("Project Inputs must contain at least one imported data row.");
  if (rows.length > SITE_BOM_MAX_INPUT_ROWS) errors.push(`Project Inputs exceeds the supported ${SITE_BOM_MAX_INPUT_ROWS} rows.`);
  if (rows.length === 0) {
    if (errors.length) throw new Error(`Project Inputs are invalid:\n- ${[...new Set(errors)].join("\n- ")}`);
    return;
  }

  const settings = requiredSheet_(spreadsheet, "Template Settings");
  const expectedSchema = text_(settings.getRange("B5").getDisplayValue());
  const expectedSchemaId = text_(settings.getRange("B10").getDisplayValue());
  const activeProject = text_(settings.getRange("B6").getDisplayValue());
  const activeRevision = text_(settings.getRange("B7").getDisplayValue());
  const allowedUnits = new Set(listValues_(settings, 7));
  const allowedSources = new Set(listValues_(settings, 9));
  const rules = masterRows_(requiredSheet_(spreadsheet, "Rules"), 4, 11);
  const expectedUnits = new Map(rules
    .filter((row) => ["DIRECT", "CALCULATED"].includes(text_(row[1]).toUpperCase()))
    .map((row) => [text_(row[2]), text_(row[3]).toUpperCase()]));
  const seen = new Set();
  const unitsByKey = new Map();
  const inputKeyPattern = /^[a-z][a-z0-9_]*$/;

  for (const { row, rowNumber } of rows) {
    const label = `Project Inputs row ${rowNumber}`;
    const schema = text_(row[0]);
    const project = text_(row[1]);
    const revision = text_(row[2]);
    const recordType = text_(row[3]).toUpperCase();
    const key = text_(row[4]);
    const value = row[5];
    const unit = text_(row[6]).toUpperCase();
    const source = text_(row[7]).toUpperCase();
    const reference = text_(row[8]);
    const schemaId = text_(row[11]);
    if (schemaId !== expectedSchemaId) errors.push(`${label} schema ID ${schemaId || "<blank>"} does not match ${expectedSchemaId}.`);
    if (schema !== expectedSchema) errors.push(`${label} schema ${schema || "<blank>"} does not match ${expectedSchema}.`);
    if (project !== activeProject) errors.push(`${label} project ${project || "<blank>"} does not match ${activeProject}.`);
    if (revision !== activeRevision) errors.push(`${label} revision ${revision || "<blank>"} does not match ${activeRevision}.`);
    if (!["FACT", "DIRECT_ITEM"].includes(recordType)) errors.push(`${label} has invalid Record Type ${recordType || "<blank>"}.`);
    if (!inputKeyPattern.test(key)) errors.push(`${label} has invalid Input Key ${key || "<blank>"}.`);
    else if (!expectedUnits.has(key)) errors.push(`${label} uses unknown Input Key ${key}.`);
    if (typeof value !== "number" || !Number.isFinite(value) || value < 0) errors.push(`${label} Value must be a non-negative number.`);
    if (!allowedUnits.has(unit)) errors.push(`${label} has invalid Unit ${unit || "<blank>"}.`);
    if (expectedUnits.has(key) && unit !== expectedUnits.get(key)) errors.push(`${label} Unit ${unit || "<blank>"} does not match ${expectedUnits.get(key)} for ${key}.`);
    if (!allowedSources.has(source)) errors.push(`${label} has invalid Source ${source || "<blank>"}.`);
    if (!reference) errors.push(`${label} is missing Source Reference.`);
    const priorUnit = unitsByKey.get(key);
    if (priorUnit && priorUnit !== unit) errors.push(`Project Inputs uses mixed units for ${key}: ${priorUnit}, ${unit}.`);
    else if (key && unit) unitsByKey.set(key, unit);
    const identity = [key, source, reference].map((valuePart) => valuePart.toLowerCase()).join("\u0000");
    if (key && source && reference && seen.has(identity)) errors.push(`${label} duplicates source ${source}:${reference} for ${key}.`);
    seen.add(identity);
  }
  if (errors.length) throw new Error(`Project Inputs are invalid:\n- ${[...new Set(errors)].join("\n- ")}`);
}

function validateProjectAdjustments_(spreadsheet) {
  const errors = [];
  const statuses = new Set(listValues_(requiredSheet_(spreadsheet, "Template Settings"), 5));
  for (const phase of SITE_BOM_PHASE_SHEETS) {
    const sheet = requiredSheet_(spreadsheet, phase);
    const lastRow = Math.max(8, lastDataRow_(sheet, 4));
    const rows = sheet.getRange(8, 1, lastRow - 7, 42).getValues();
    rows.forEach((row, index) => {
      if (!text_(row[3])) return;
      const label = `${phase} row ${index + 8}`;
      validateNumber_(row[15], `${label} Manual Base Qty`, errors, { minimum: 0 });
      validateNumber_(row[22], `${label} Manual Extra`, errors, { minimum: 0 });
      if (text_(row[10]) === "MANUAL" && row[15] === 0 && text_(row[37]) !== "Not Required") {
        errors.push(`${label} requires a positive Manual Base Qty or Status Not Required.`);
      }
      if (typeof row[22] === "number" && row[22] > 0 && !text_(row[40])) {
        errors.push(`${label} Manual Extra requires an Adjustment Reason / Notes.`);
      }
      validateOptionalDate_(row[36], `${label} Needed By`, errors);
      if (!statuses.has(text_(row[37]))) errors.push(`${label} has invalid Status ${text_(row[37]) || "<blank>"}.`);
      if (typeof row[38] !== "boolean") errors.push(`${label} Accounted For must be a checkbox.`);
    });
  }

  const procurement = requiredSheet_(spreadsheet, "Procurement Summary");
  const lastRow = Math.max(4, lastDataRow_(procurement, 1));
  const rows = procurement.getRange(4, 1, lastRow - 3, 24).getValues();
  rows.forEach((row, index) => {
    if (!text_(row[0])) return;
    const label = `Procurement Summary row ${index + 4}`;
    validateNumber_(row[14], `${label} On Hand`, errors, { minimum: 0 });
    validateNumber_(row[15], `${label} Already Committed`, errors, { minimum: 0 });
    validateOptionalDate_(row[19], `${label} Needed By`, errors);
    if (!statuses.has(text_(row[20]))) errors.push(`${label} has invalid Status ${text_(row[20]) || "<blank>"}.`);
    if (typeof row[21] !== "boolean") errors.push(`${label} Accounted For must be a checkbox.`);
  });
  if (errors.length) throw new Error(`Project adjustment fields are invalid:\n- ${[...new Set(errors)].join("\n- ")}`);
}

function validateApprovalReadiness_(spreadsheet) {
  SpreadsheetApp.flush();
  const issues = [];
  const audit = requiredSheet_(spreadsheet, "Import Audit").getRange("A5:D1004").getDisplayValues();
  audit.forEach((row) => {
    if (text_(row[3])) issues.push(`Import row ${text_(row[0]) || "<unknown>"}: ${text_(row[3])}`);
  });

  for (const phase of SITE_BOM_PHASE_SHEETS) {
    const sheet = requiredSheet_(spreadsheet, phase);
    const lastRow = Math.max(8, lastDataRow_(sheet, 4));
    const rows = sheet.getRange(8, 1, lastRow - 7, 42).getValues();
    rows.forEach((row, index) => {
      const lineId = text_(row[3]);
      if (!lineId) return;
      const label = `${phase} ${lineId} (row ${index + 8})`;
      if (text_(row[41])) issues.push(`${label}: ${text_(row[41])}`);
      if (row[38] !== true) issues.push(`${label}: Accounted For is not checked.`);
      if (text_(row[37]) === "Needs Review") issues.push(`${label}: Status is still Needs Review.`);
    });
  }

  const procurement = requiredSheet_(spreadsheet, "Procurement Summary");
  const lastRow = Math.max(4, lastDataRow_(procurement, 1));
  const rows = procurement.getRange(4, 1, lastRow - 3, 24).getValues();
  rows.forEach((row, index) => {
    const itemId = text_(row[0]);
    if (!itemId) return;
    const label = `Procurement ${itemId} (row ${index + 4})`;
    if (text_(row[23])) issues.push(`${label}: ${text_(row[23])}`);
    if (typeof row[17] === "number" && row[17] > 0) {
      if (row[21] !== true) issues.push(`${label}: Accounted For is not checked.`);
      if (text_(row[20]) === "Needs Review") issues.push(`${label}: Status is still Needs Review.`);
    }
  });

  if (issues.length) {
    const preview = issues.slice(0, 25);
    if (issues.length > preview.length) preview.push(`...and ${issues.length - preview.length} more issue(s).`);
    throw new Error(`Site BOM is not ready for approval (${issues.length} issue(s)):\n- ${preview.join("\n- ")}`);
  }
}

function validateSettingsList_(sheet, column, label, errors, options = {}) {
  const values = listValues_(sheet, column);
  if (!values.length) {
    errors.push(`Template Settings ${label} list must contain at least one value.`);
    return;
  }
  const seen = new Set();
  for (const value of values) {
    const identity = value.toLowerCase();
    if (seen.has(identity)) errors.push(`Template Settings ${label} contains duplicate value ${value}.`);
    seen.add(identity);
    if (options.requireUppercase === true && value !== value.toUpperCase()) {
      errors.push(`Template Settings ${label} value ${value} must be uppercase.`);
    }
  }
  for (const requiredValue of options.requiredValues ?? []) {
    if (!values.includes(requiredValue)) errors.push(`Template Settings ${label} must include ${requiredValue}.`);
  }
}

function validateOptionalDate_(value, label, errors) {
  if (text_(value) === "") return;
  if (!(value instanceof Date) || !Number.isFinite(value.getTime())) errors.push(`${label} must be a valid date or blank.`);
}

function validateNumber_(value, label, errors, options) {
  const allowBlank = options.allowBlank === true;
  if (allowBlank && text_(value) === "") return;
  if (typeof value !== "number" || !Number.isFinite(value) || value < options.minimum) {
    const requirement = options.minimum > 0 ? "a positive number" : "a non-negative number";
    errors.push(`${label} must be ${requirement}.`);
  }
}

function listValues_(sheet, column) {
  const lastRow = Math.max(4, sheet.getLastRow());
  return sheet.getRange(4, column, lastRow - 3, 1).getDisplayValues().flat().map(text_).filter(Boolean);
}

function uniqueIds_(rows, columnIndex, label, errors) {
  const result = new Set();
  for (const row of rows) {
    const id = text_(row[columnIndex]);
    if (!id) errors.push(`${label} cannot be blank.`);
    else if ([...result].some((existing) => existing.toLowerCase() === id.toLowerCase())) errors.push(`Duplicate ${label}: ${id}.`);
    else result.add(id);
  }
  return result;
}

function valuesByKey_(sheet, startRow, keyColumn, valueColumns) {
  const lastRow = Math.max(startRow, lastDataRow_(sheet, keyColumn));
  const width = Math.max(keyColumn, ...valueColumns);
  const rows = sheet.getRange(startRow, 1, lastRow - startRow + 1, width).getValues();
  const result = new Map();
  for (const row of rows) {
    const key = text_(row[keyColumn - 1]);
    if (key) result.set(key, valueColumns.map((column) => row[column - 1]));
  }
  return result;
}

function restoreByKey_(sheet, startRow, columns, capacityLastRow, orderedIds, saved, defaults) {
  const rowCount = capacityLastRow - startRow + 1;
  for (let index = 0; index < columns.length; index += 1) {
    const values = [];
    for (let offset = 0; offset < rowCount; offset += 1) {
      const id = orderedIds[offset];
      values.push([id ? (saved.get(id)?.[index] ?? defaults[index]) : ""]);
    }
    sheet.getRange(startRow, columns[index], rowCount, 1).setValues(values);
  }
}

function setColumn_(sheet, startRow, column, capacityLastRow, activeValues) {
  const rowCount = capacityLastRow - startRow + 1;
  const values = Array.from({ length: rowCount }, (_, index) => [activeValues[index] ?? ""]);
  sheet.getRange(startRow, column, rowCount, 1).setValues(values);
}

function copyTemplateRow_(sheet, sourceRow, lastRow, columnCount) {
  const source = sheet.getRange(sourceRow, 1, 1, columnCount);
  const rowCount = lastRow - sourceRow + 1;
  const destination = sheet.getRange(sourceRow, 1, rowCount, columnCount);
  const validations = source.getDataValidations()[0];
  source.copyFormatToRange(sheet, 1, columnCount, sourceRow, lastRow);
  destination.setDataValidations(Array.from({ length: rowCount }, () => [...validations]));
}

function clearColumns_(sheet, startRow, lastRow, columns) {
  const rowCount = lastRow - startRow + 1;
  for (const column of columns) sheet.getRange(startRow, column, rowCount, 1).clearContent();
}

function ensureRows_(sheet, requiredLastRow) {
  if (sheet.getMaxRows() < requiredLastRow) {
    sheet.insertRowsAfter(sheet.getMaxRows(), requiredLastRow - sheet.getMaxRows());
  }
}

function text_(value) {
  return String(value == null ? "" : value).trim();
}

function ensureCheckboxesPreserveValues_(range) {
  const values = range.getValues().map((row) => [row[0] === true]);
  range.insertCheckboxes();
  range.setValues(values);
}

function replaceFilter_(sheet, headerRow, lastRow, columnCount) {
  if (sheet.getFilter()) sheet.getFilter().remove();
  sheet.getRange(headerRow, 1, lastRow - headerRow + 1, columnCount).createFilter();
}

function refreshPhaseConditionalFormatting_(sheet, lastRow) {
  sheet.setConditionalFormatRules([]);
  addNotBlankRule_(sheet, sheet.getRange(8, 42, lastRow - 7, 1), SITE_BOM_COLORS.warning, SITE_BOM_COLORS.warningText);
  addTextEqualRule_(sheet, sheet.getRange(8, 38, lastRow - 7, 1), "Ready", SITE_BOM_COLORS.success, SITE_BOM_COLORS.successText);
}

function refreshProcurementConditionalFormatting_(sheet, lastRow) {
  sheet.setConditionalFormatRules([]);
  addNotBlankRule_(sheet, sheet.getRange(4, 24, lastRow - 3, 1), SITE_BOM_COLORS.warning, SITE_BOM_COLORS.warningText);
}

function requiredSheet_(spreadsheet, name) {
  const sheet = spreadsheet.getSheetByName(name);
  if (!sheet) throw new Error(`Required Site BOM sheet is missing: ${name}`);
  return sheet;
}

function lastDataRow_(sheet, keyColumn) {
  const maxRow = sheet.getLastRow();
  if (maxRow < 1) return 1;
  const values = sheet.getRange(1, keyColumn, maxRow, 1).getDisplayValues();
  for (let index = values.length - 1; index >= 0; index -= 1) {
    if (values[index][0] !== "") return index + 1;
  }
  return 1;
}

function protectStrict_(range, description) {
  const protection = range.protect().setDescription(description).setWarningOnly(false);
  const currentUser = Session.getEffectiveUser();
  protection.addEditor(currentUser);
  const currentEmail = currentUser.getEmail();
  const otherEditors = protection.getEditors().filter((user) => user.getEmail() !== currentEmail);
  if (otherEditors.length) protection.removeEditors(otherEditors);
  if (protection.canDomainEdit()) protection.setDomainEdit(false);
}

function removeManagedProtections_(spreadsheet) {
  for (const type of [SpreadsheetApp.ProtectionType.RANGE, SpreadsheetApp.ProtectionType.SHEET]) {
    for (const protection of spreadsheet.getProtections(type)) {
      if (protection.canEdit() && String(protection.getDescription() || "").startsWith(SITE_BOM_PROTECTION_PREFIX)) {
        protection.remove();
      }
    }
  }
}
