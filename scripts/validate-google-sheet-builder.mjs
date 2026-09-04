import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { loadTemplateConfig } from "../src/template-model.mjs";

export async function validateGoogleSheetBuilder(builderFile) {
  if (!builderFile) {
    const { config } = await loadTemplateConfig();
    builderFile = `outputs/site-bom-v${config.settings.templateVersion}/Neovi-Site-BOM-Builder.gs`;
  }
  const builderPath = path.resolve(builderFile);
  const source = await fs.readFile(builderPath, "utf8");
  assert.match(source, /^\/\*\* @OnlyCurrentDoc \*\//);
  const load = new Function(`${source}\nreturn {
    data: SITE_BOM_BUILD_DATA,
    phaseNames: SITE_BOM_PHASE_SHEETS,
    phaseFormulas: phaseRowFormulas,
    procurementFormulas: procurementRowFormulas,
    auditFormulas: importAuditRowFormulas,
    preserveCheckboxes: ensureCheckboxesPreserveValues_,
    build: buildSiteBomTemplate,
  };`);
  const builder = load();

  assert.deepEqual(builder.phaseNames, ["Foundation", "Panels", "Finishing"]);
  assert.deepEqual(builder.data.settings.visiblePhases, builder.phaseNames);
  assert.equal(builder.data.settings.schemaId, "neovi.site-bom.project-inputs");
  assert.ok(builder.data.lines.every((line) => line.system
    && line.siteTeam
    && line.teamScope
    && builder.data.settings.siteStages.includes(line.deliveryStage)));
  assert.ok(builder.data.lines.length > 0);
  assert.ok(builder.data.items.length > 0);
  assert.ok(Array.isArray(builder.data.projectInputs));
  for (const phaseName of builder.phaseNames) {
    assert.ok(builder.data.lines.some((line) => line.phase === phaseName), `${phaseName} has no BOM lines.`);
  }

  const phase = builder.phaseFormulas(8, 2, 1001, "Panels");
  assert.match(phase.sourceValue, /SUMIFS/);
  assert.match(phase.sourceValue, /'Project Inputs'!\$G\$2:\$G\$1001/);
  assert.match(phase.sourceValue, /'Project Inputs'!\$L\$2:\$L\$1001/);
  assert.match(phase.sourceValue, /'Template Settings'!\$B\$7/);
  assert.match(phase.kitDemand, /MAX\(0,\$W8\)/);
  assert.match(phase.kitDemand, /\$U8<=0/);
  assert.doesNotMatch(phase.kitDemand, /\$AC8/);
  assert.match(phase.review, /^=IF\(\$D8="","",/);

  const procurement = builder.procurementFormulas(4, builder.phaseNames);
  assert.match(procurement.totalKitDemand, /'Foundation'!\$X\$8:\$X\$1000/);
  assert.match(procurement.totalKitDemand, /'Finishing'!\$X\$8:\$X\$1000/);
  assert.match(procurement.netNeed, /MAX\(0,\$N4\)\+MAX\(0,\$M4\)-MAX\(0,\$O4\)-MAX\(0,\$P4\)/);
  assert.match(procurement.orderQty, /\$K4<=0/);

  const audit = builder.auditFormulas(5, 2);
  assert.match(audit.issue, /Revision mismatch/);
  assert.match(audit.issue, /Schema ID mismatch/);
  assert.match(audit.issue, /Duplicate source row/);
  assert.match(audit.issue, /Missing input key/);
  assert.match(audit.issue, /Unknown input key/);
  assert.match(audit.issue, /Unit does not match input key/);
  assert.match(audit.issue, /COUNTA\('Project Inputs'!A2:L2\)>0/);
  assert.match(source, /function protectStrict_/);
  assert.match(source, /function downloadSiteBomMasterSnapshot/);
  assert.match(source, /function validateProjectAdjustments_/);
  assert.match(source, /function validateApprovalReadiness_/);
  assert.match(source, /function validateSettingsList_/);
  assert.match(source, /function prepareMasterTableRows_/);
  assert.match(source, /getFormulas\(\)/);
  assert.match(source, /\["Import Audit", "A1:D1004"\]/);
  assert.match(source, /"A1:AT7"/);
  assert.match(source, /"A1:X3"/);
  assert.match(source, /\["BOM Lines", "A1:L3"\]/);
  assert.match(source, /`Q8:AJ\$\{lastRow\}`/);
  assert.match(source, /fixed master/);
  assert.match(source, /Site BOM is not ready for approval/);
  assert.doesNotMatch(source, /setWarningOnly\(true\)/);
  assert.doesNotMatch(source, /function native(?:Phase|Procurement|Audit)Formulas_/);

  let insertedCheckboxes = false;
  let restoredCheckboxValues = null;
  builder.preserveCheckboxes({
    getValues: () => [[true], [false], [""]],
    insertCheckboxes() {
      insertedCheckboxes = true;
      return this;
    },
    setValues(values) {
      restoredCheckboxValues = values;
      return this;
    },
  });
  assert.equal(insertedCheckboxes, true);
  assert.deepEqual(restoredCheckboxValues, [[true], [false], [false]]);
  assert.equal(typeof builder.build, "function");

  console.log(`Valid native Google Sheets builder: ${builderPath}`);
  console.log(`Lines: ${builder.data.lines.length}; items: ${builder.data.items.length}; inputs: ${builder.data.projectInputs.length}`);
  return builder;
}

const invokedDirectly = process.argv[1]
  && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url;
if (invokedDirectly) await validateGoogleSheetBuilder(process.argv[2]);
