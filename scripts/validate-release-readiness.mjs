import { loadTemplateConfig } from "../src/template-model.mjs";

const { config, lines, items } = await loadTemplateConfig();
const issues = [];

for (const line of lines) {
  const label = `${line.lineId} ${line.description}`;
  if (/^Define\b/i.test(line.description)) issues.push(`${label}: replace the definition placeholder with exact purchasable items.`);
  if (!line.specificationApproved || /^TBD\b/i.test(line.specification)) issues.push(`${label}: specification is not approved.`);
  if (line.owner === "Unassigned") issues.push(`${label}: owner is unassigned.`);
  if (line.procurementMethod === "TBD") issues.push(`${label}: procurement method is TBD.`);
  if (line.ruleStatus !== "APPROVED") issues.push(`${label}: calculation rule is ${line.ruleStatus}.`);
}

const uniqueIssues = [...new Set(issues)];
console.log(`Site BOM ${config.settings.templateVersion} release-readiness review`);
console.log(`Lines: ${lines.length}; purchasable items: ${items.length}; blocking issues: ${uniqueIssues.length}`);
for (const issue of uniqueIssues.slice(0, 50)) console.log(`- ${issue}`);
if (uniqueIssues.length > 50) console.log(`- ...and ${uniqueIssues.length - 50} more issue(s).`);
if (uniqueIssues.length) {
  console.error("Catalog remains DRAFT and must not be approved for purchasing.");
  process.exitCode = 1;
}
