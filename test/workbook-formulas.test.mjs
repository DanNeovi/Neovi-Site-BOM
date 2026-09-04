import test from "node:test";
import assert from "node:assert/strict";
import {
  PHASE_HEADERS,
  importAuditRowFormulas,
  phaseRowFormulas,
  phaseSummaryFormulas,
  procurementRowFormulas,
} from "../src/workbook-formulas.mjs";

test("phase formulas use bounded revision-safe Project Inputs ranges", () => {
  const formulas = phaseRowFormulas(8, 2, 1001, "Panels");
  for (const formula of Object.values(formulas)) {
    assert.ok(formula.startsWith("="));
    assert.ok(!formula.includes("$E:$E"));
    assert.ok(!formula.includes("$F:$F"));
  }
  assert.match(formulas.sourceValue, /SUMIFS/);
  assert.match(formulas.sourceValue, /'Project Inputs'!\$G\$2:\$G\$1001/);
  assert.match(formulas.sourceValue, /'Project Inputs'!\$A\$2:\$A\$1001/);
  assert.match(formulas.sourceValue, /'Project Inputs'!\$L\$2:\$L\$1001/);
  assert.match(formulas.sourceValue, /'Template Settings'!\$B\$5/);
  assert.match(formulas.sourceValue, /'Template Settings'!\$B\$6/);
  assert.match(formulas.sourceValue, /'Template Settings'!\$B\$7/);
  assert.match(formulas.sourceValue, /'Template Settings'!\$B\$10/);
});

test("phase identity, item data, rules, and purchasing use separate tables", () => {
  const formulas = phaseRowFormulas(8, 2, 1001, "Panels");
  assert.match(formulas.stage, /'BOM Lines'!/);
  assert.match(formulas.system, /'BOM Lines'!\$I\$4:\$I\$1000/);
  assert.match(formulas.deliveryStage, /'BOM Lines'!\$J\$4:\$J\$1000/);
  assert.match(formulas.siteTeam, /'BOM Lines'!\$K\$4:\$K\$1000/);
  assert.match(formulas.teamScope, /'BOM Lines'!\$L\$4:\$L\$1000/);
  assert.match(formulas.item, /'Items'!/);
  assert.match(formulas.sourceMode, /'Rules'!/);
  assert.match(formulas.orderQty, /'Procurement Summary'!/);
  assert.match(formulas.review, /Line belongs on different phase tab/);
  assert.match(formulas.review, /Calculation rule needs approval/);
  assert.match(formulas.review, /Manual quantities must be non-negative numbers/);
  assert.match(formulas.review, /Manual quantity required or mark Not Required/);
  assert.match(formulas.review, /Status required/);
  assert.match(formulas.review, /^=IF\(\$D8="","",/);
  assert.equal(PHASE_HEADERS.length, 46);
});

test("line formulas calculate kit demand without vendor pack rounding", () => {
  const formulas = phaseRowFormulas(8);
  assert.match(formulas.requiredQty, /\$M8\*\$N8/);
  assert.match(formulas.spareQty, /CEILING\(MAX\(0,\$R8\*\$S8\),\$U8\)/);
  assert.match(formulas.kitDemand, /MAX\(0,\$W8\)/);
  assert.match(formulas.kitDemand, /\$U8<=0/);
  assert.doesNotMatch(formulas.kitDemand, /\$AC8/);
});

test("procurement formulas aggregate phases then apply pack rounding", () => {
  const formulas = procurementRowFormulas(4, ["Foundation", "Panels", "Finishing"]);
  assert.match(formulas.totalKitDemand, /'Foundation'!\$X\$8:\$X\$1000/);
  assert.match(formulas.totalKitDemand, /'Panels'!\$X\$8:\$X\$1000/);
  assert.match(formulas.netNeed, /MAX\(0,\$N4\)\+MAX\(0,\$M4\)-MAX\(0,\$O4\)-MAX\(0,\$P4\)/);
  assert.match(formulas.orderQty, /\$K4<=0/);
  assert.match(formulas.review, /^=IF\(\$A4="","",/);
});

test("import audit detects revision mismatch and duplicate source rows", () => {
  const formulas = importAuditRowFormulas(5, 2);
  assert.match(formulas.issue, /Revision mismatch/);
  assert.match(formulas.issue, /Duplicate source row/);
  assert.match(formulas.issue, /Missing input key/);
  assert.match(formulas.issue, /Unknown input key/);
  assert.match(formulas.issue, /Unit does not match input key/);
  assert.match(formulas.issue, /Schema ID mismatch/);
  assert.match(formulas.issue, /COUNTA\('Project Inputs'!A2:L2\)>0/);
  assert.match(formulas.issue, /COUNTIFS/);
});

test("summary formulas target the requested phase row range", () => {
  const formulas = phaseSummaryFormulas(8, 31);
  assert.equal(formulas.totalLines, "=COUNTA($D$8:$D$31)");
  assert.equal(formulas.accountedFor, "=COUNTIF($AM$8:$AM$31,TRUE)");
  assert.equal(formulas.kitDemand, "=SUM($X$8:$X$31)");
  assert.match(formulas.needsReview, /\$AL\$8:\$AL\$31,"Needs Review"/);
  assert.match(formulas.readyPercent, /\$AL\$8:\$AL\$31,"<>Needs Review"/);
  assert.match(formulas.readyPercent, /\$AL\$8:\$AL\$31,"<>"/);
});
